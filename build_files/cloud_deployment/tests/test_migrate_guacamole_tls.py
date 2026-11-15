from unittest.mock import Mock

import pytest
from google.api_core.exceptions import PermissionDenied, PreconditionFailed
from google.cloud import compute_v1

from cloud_deployment.operations.project_maintenance import migrate_guacamole_tls as migration
from common.services.community_guacamole_startup import render_community_guacamole_startup
from common.services.guacamole_tls_startup import (
    GUACAMOLE_TLS_SCOPE, GUACAMOLE_TLS_SECRET_METADATA_KEY, guacamole_tls_reader_email,
)


PROJECT = 'tenant-project'
UNIT = 'abcdefghij'
ZONE = 'us-central1-a'
DOMAIN = 'example.org'
HOST = f'{UNIT}-display.{DOMAIN}'
NAME = f'{UNIT}-display-guacamole-server'
READER = guacamole_tls_reader_email(PROJECT)
UNIT_ACCOUNT = f'agoge-guac-{UNIT}@{PROJECT}.iam.gserviceaccount.com'
UNIT_SECRET = f'projects/{PROJECT}/secrets/agoge-guac-{UNIT}/versions/1'
TLS_SECRET = 'projects/shared-resources/secrets/guac-tls'
LEGACY = '#!/bin/bash\nif [ -f /etc/guac_init_done ]; then exit 0; fi\necho legacy\n'
SETTINGS = {'project': PROJECT, 'parent_dns_suffix': f'.{DOMAIN}', 'project_number': '12345',
            'guacamole_tls_secret': TLS_SECRET}


@pytest.fixture
def gcp(monkeypatch):
    client = Mock()
    database = Mock()
    ref = database.collection.return_value.document.return_value
    admin = Mock()
    admin.get.return_value.to_dict.return_value = SETTINGS
    database.collection.side_effect = lambda name: Mock(document=Mock(
        return_value=admin if name == 'admin-info' else ref,
    ))
    monkeypatch.setattr(migration.firestore, 'Client', Mock(return_value=database))
    monkeypatch.setattr(migration.compute_v1, 'InstancesClient', Mock(return_value=client))
    monkeypatch.setattr(migration, 'DnsManager', Mock())
    monkeypatch.setattr(migration, 'CommunityProxyIdentity', Mock())
    monkeypatch.setattr(migration, '_install_on_running_guest', Mock(return_value=False))
    return client, database, ref


def add_proxy(gcp, *, status='TERMINATED', community=False, account=None):
    client, _, ref = gcp
    record = {'name': 'display-guacamole-server', 'parent_id': UNIT, 'hostname': HOST, 'zone': ZONE,
              'guacamole_startup_script': LEGACY, 'metadata': {'items': [{'key': 'kept', 'value': 'record'}]}}
    metadata = {'kept': 'instance', 'startup-script': LEGACY.rstrip() + '\n' + migration.LINUX_LOADER.lstrip()}
    if community:
        account = UNIT_ACCOUNT
        record['community_proxy'] = True
        record['guacamole_secret_version_name'] = UNIT_SECRET
        metadata['startup-script'] = render_community_guacamole_startup(UNIT_SECRET, UNIT, DOMAIN)
        metadata[migration.SECRET_METADATA_KEY] = UNIT_SECRET
    vm = compute_v1.Instance(
        id=42, name=NAME, status=status, metadata={'fingerprint': 'version1', 'items': migration._items(metadata)},
        service_accounts=[{'email': account or '12345-compute@developer.gserviceaccount.com',
                           'scopes': [GUACAMOLE_TLS_SCOPE]}],
        network_interfaces=[{'access_configs': [{'nat_i_p': '192.0.2.10'}]}],
    )
    client.aggregated_list.return_value = [(f'zones/{ZONE}', compute_v1.InstancesScopedList(instances=[vm]))]
    client.get.return_value = vm
    ref.get.return_value.to_dict.return_value = record
    return vm, record


def test_dry_run_and_apply_without_restart_leave_running_legacy_vm_untouched(gcp, capsys):
    client, _, ref = gcp
    add_proxy(gcp, status='RUNNING')
    assert migration.migrate_guacamole_tls(PROJECT, instance_name=NAME)
    assert 'stop/start required' in capsys.readouterr().out
    assert not migration.migrate_guacamole_tls(PROJECT, apply=True)
    assert 'requires explicit stop/start' in capsys.readouterr().out
    for method in (client.stop, client.start, client.set_metadata, client.set_service_account, ref.update):
        method.assert_not_called()


def test_stopped_proxy_updates_existing_vm_and_saved_spec_without_starting(gcp):
    client, db, ref = gcp
    add_proxy(gcp)
    assert migration.migrate_guacamole_tls(PROJECT, apply=True)
    client.stop.assert_not_called()
    client.start.assert_not_called()
    request = client.set_service_account.call_args.kwargs['instances_set_service_account_request_resource']
    assert request.email == READER and list(request.scopes) == [GUACAMOLE_TLS_SCOPE]
    metadata = client.set_metadata.call_args.kwargs['metadata_resource']
    assert metadata.fingerprint == 'version1'
    items = migration._existing_metadata(metadata)
    assert items['kept'] == 'instance' and items[GUACAMOLE_TLS_SECRET_METADATA_KEY] == TLS_SECRET
    assert items['startup-script'].index('BEGIN AGOGE GUACAMOLE TLS') < items['startup-script'].index('guac_init_done')
    assert migration.LINUX_LOADER.lstrip() in items['startup-script']
    saved = ref.update.call_args.args[0]
    assert saved['service_accounts'][0]['email'] == READER
    assert {'key': 'kept', 'value': 'record'} in saved['metadata']['items']
    assert 'echo legacy' in saved['guacamole_startup_script']
    assert ref.update.call_args.kwargs['option'] == db.write_option.return_value


@pytest.mark.parametrize('permission_failure', [False, True])
def test_opted_in_restart_restores_guest_and_dns_even_if_metadata_fails(gcp, permission_failure):
    client, _, ref = gcp
    initial, _ = add_proxy(gcp, status='RUNNING')
    stopped = compute_v1.Instance(initial)
    stopped.status = 'TERMINATED'
    started = compute_v1.Instance(initial)
    started.network_interfaces[0].access_configs[0].nat_i_p = '192.0.2.20'
    client.get.side_effect = [initial, initial, stopped, stopped, stopped, started]
    if permission_failure:
        client.set_metadata.side_effect = PermissionDenied('restricted details')
    assert migration.migrate_guacamole_tls(PROJECT, apply=True, restart_running=True) is not permission_failure
    client.stop.assert_called_once()
    client.start.assert_called_once()
    migration.DnsManager.return_value.add_dns_record.assert_called_once_with(HOST, NAME, ip_address='192.0.2.20')
    assert ref.update.called is not permission_failure


def test_unit_owned_running_proxy_keeps_identity_and_installs_only_tls_in_guest(gcp, capsys):
    client, _, ref = gcp
    add_proxy(gcp, status='RUNNING', community=True)
    migration._install_on_running_guest.return_value = True
    assert migration.migrate_guacamole_tls(PROJECT, apply=True)
    migration.CommunityProxyIdentity.return_value.grant_tls_reader_impersonation.assert_called_once_with(UNIT)
    for method in (client.stop, client.start, client.set_service_account):
        method.assert_not_called()
    config = migration._existing_metadata(client.set_metadata.call_args.kwargs['metadata_resource'])
    assert config[migration.SECRET_METADATA_KEY] == UNIT_SECRET
    assert config[migration.GUACAMOLE_TLS_READER_METADATA_KEY] == READER
    live_installer = migration._install_on_running_guest.call_args.args[1]
    assert READER in live_installer and UNIT_SECRET not in live_installer
    assert 'guacamole_startup_script' in ref.update.call_args.args[0]
    assert 'installer ran on the existing VM' in capsys.readouterr().out


def test_proxy_with_non_repository_startup_is_skipped(gcp, capsys):
    client, _, ref = gcp
    existing, _ = add_proxy(gcp)
    for item in existing.metadata.items:
        if item.key == 'startup-script':
            item.value += '\ncustom-command\n'
    migration.migrate_guacamole_tls(PROJECT, apply=True)
    client.set_service_account.assert_not_called()
    ref.update.assert_not_called()
    assert 'outside its generated Guacamole configuration' in capsys.readouterr().out


def test_matching_running_identity_with_flat_metadata_stages_if_guest_is_unreachable(gcp, capsys):
    client, _, ref = gcp
    _, record = add_proxy(gcp, status='RUNNING', account=READER)
    record['metadata'] = {GUACAMOLE_TLS_SECRET_METADATA_KEY: TLS_SECRET, 'kept': 'record'}
    assert migration.migrate_guacamole_tls(PROJECT, apply=True)
    client.stop.assert_not_called()
    client.set_service_account.assert_not_called()
    assert ref.update.call_args.args[0]['metadata']['kept'] == 'record'
    assert 'staged for the next boot' in capsys.readouterr().out


def test_no_service_account_compatibility_proxy_cannot_be_enabled(gcp, capsys):
    client, _, ref = gcp
    vm, record = add_proxy(gcp)
    record['no_service_account'] = True
    vm.service_accounts = []
    assert not migration.migrate_guacamole_tls(PROJECT, apply=True, instance_name=NAME)
    client.set_service_account.assert_not_called()
    ref.update.assert_not_called()
    assert 'legacy community compatibility proxy' in capsys.readouterr().out


def test_metadata_retry_preserves_new_unrelated_key(gcp):
    client, _, _ = gcp
    initial, _ = add_proxy(gcp)
    concurrent = compute_v1.Instance(initial)
    concurrent.metadata.fingerprint = 'version2'
    concurrent.metadata.items.append(compute_v1.Items(key='concurrent', value='added'))
    client.get.side_effect = [initial, concurrent]
    client.set_metadata.side_effect = [PreconditionFailed('stale fingerprint'), Mock()]
    migration._set_boot_metadata(client, {'instance': NAME, 'project': PROJECT, 'zone': ZONE},
                                 initial, {'startup-script': 'new script'})
    updated = client.set_metadata.call_args.kwargs['metadata_resource']
    assert updated.fingerprint == 'version2'
    assert migration._existing_metadata(updated)['concurrent'] == 'added'
