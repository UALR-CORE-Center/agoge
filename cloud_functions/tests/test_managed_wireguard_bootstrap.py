from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from cloud_fn_utilities.course_objects.compute.base_compute_manager import BaseComputeManager
from cloud_fn_utilities.course_objects.compute import base_compute_manager as base_module
from cloud_fn_utilities.course_objects.compute import lab_server_manager as module
from cloud_fn_utilities.server_specific.wireguard_gateway import (
    BOOT_METADATA_KEY, SECRET_METADATA_KEY, UBUNTU_IMAGE,
    WireGuardGatewayIdentity, managed_metadata,
)
from common.constants.states import ServerStates
from common.exceptions import BadRequest, NotFound


LabServerManager = module.LabServerManager
UNIT = 'abcdefghij'
SECRET = f'projects/tenant-project/secrets/agoge-wg-{UNIT}/versions/1'
NONCE = 'a' * 32
EMAIL = f'agoge-wg-{UNIT}@tenant-project.iam.gserviceaccount.com'


def manager():
    value = object.__new__(LabServerManager)
    value.parent_build_id = UNIT
    value.server_name = f'{UNIT}-wireguard'
    value.env = SimpleNamespace(project='tenant-project', zone='us-central1-a', region='us-central1')
    value.env_dict = {'project': 'tenant-project'}
    value.server_spec = SimpleNamespace(
        wireguard_managed=True, wireguard_endpoint_id='10000',
        name=value.server_name, build_type=None, add_disk=0,
        metadata=None, nics=[], disk_size=10,
    )
    value.s = ServerStates
    value.state_manager = MagicMock()
    value.compute_instance = MagicMock()
    value.wireguard_registry = MagicMock()
    value.logger = MagicMock()
    value.class_name = 'LabServerManager'
    value.primary_external_ip = None
    value._wireguard_provisioning = MagicMock()
    lease = SimpleNamespace(secret_version_name=SECRET, boot_id=NONCE, health_error=None,
                            status='reserved', expires=10_000_000_000)
    lease.is_ready = MagicMock(return_value=True)
    value._wireguard_provisioning.return_value.get_lease.return_value = lease
    value._wireguard_provisioning.return_value.prepare_boot.return_value = NONCE
    return value


def existing(status='TERMINATED', nonce=NONCE, secret=SECRET, email=EMAIL):
    return {
        'status': status,
        'service_accounts': [{'email': email}],
        'metadata': {'fingerprint': 'current-fingerprint', 'items': [
            {'key': BOOT_METADATA_KEY, 'value': nonce},
            {'key': SECRET_METADATA_KEY, 'value': secret},
            {'key': 'startup-script', 'value': 'old script'},
            {'key': 'unrelated-setting', 'value': 'preserved'},
        ]},
    }


def test_managed_gateway_uses_official_ubuntu_without_custom_image_lookup():
    value = manager()
    value._get_boot_disk = MagicMock(return_value='ubuntu-boot-disk')
    value._add_disks()
    value._get_boot_disk.assert_called_once_with(image_source=UBUNTU_IMAGE, disk_size_gb=10)
    assert value.server_spec.disks == ['ubuntu-boot-disk']


def test_metadata_contains_embedded_code_references_and_no_config_material():
    metadata = managed_metadata(SECRET, NONCE)
    fields = {item['key']: item['value'] for item in metadata['items']}
    assert fields[SECRET_METADATA_KEY] == SECRET
    assert fields[BOOT_METADATA_KEY] == NONCE
    assert fields['startup-script'].startswith('#!/bin/bash')
    assert 'startup-script-url' not in fields
    value = manager()
    value._managed_wireguard_metadata = metadata
    value.server_spec.startup_script = 'do not run catalog script'
    value.assessment = MagicMock()
    value._add_metadata()
    assert value.server_spec.metadata == metadata
    value.assessment.get_startup_scripts.assert_not_called()


def test_new_vm_prepares_nonce_dedicated_identity_and_narrow_secret_access():
    value = manager()
    value.compute_instance.get.side_effect = NotFound('not created yet')
    with patch.object(module, 'WireGuardGatewayIdentity') as identity:
        identity.return_value.ensure.return_value = EMAIL
        value._prepare_wireguard_bootstrap()
    service = value._wireguard_provisioning.return_value
    service.grant_gateway_access.assert_called_once_with(UNIT, EMAIL)
    service.prepare_boot.assert_called_once_with(UNIT)
    assert value.server_spec.service_accounts == [
        {'email': EMAIL, 'scopes': ['https://www.googleapis.com/auth/cloud-platform']}
    ]
    assert value.server_spec.can_ip_forward is True
    value.compute_instance.replace_metadata.assert_not_called()


def test_start_replaces_nonce_before_start_and_preserves_metadata_fingerprint():
    value = manager()
    value.compute_instance.get.return_value = existing()
    value._wireguard_provisioning.return_value.prepare_boot.return_value = 'b' * 32
    with patch.object(module, 'WireGuardGatewayIdentity') as identity:
        identity.return_value.ensure.return_value = EMAIL
        value._prepare_wireguard_bootstrap(for_start=True)
    name, metadata = value.compute_instance.replace_metadata.call_args.args
    assert name == value.server_name
    assert metadata['fingerprint'] == 'current-fingerprint'
    fields = {item['key']: item['value'] for item in metadata['items']}
    assert fields[BOOT_METADATA_KEY] == 'b' * 32
    assert fields['unrelated-setting'] == 'preserved'
    assert fields['startup-script'].startswith('#!/bin/bash')


def test_duplicate_insert_reuses_running_boot_generation():
    value = manager()
    value.compute_instance.get.return_value = existing(status='RUNNING')
    with patch.object(module, 'WireGuardGatewayIdentity') as identity:
        identity.return_value.ensure.return_value = EMAIL
        value._prepare_wireguard_bootstrap()
    value._wireguard_provisioning.return_value.prepare_boot.assert_not_called()


@pytest.mark.parametrize('change', [
    {'secret': SECRET.replace('/1', '/2')}, {'email': 'another@example.test'},
    {'status': 'RUNNING', 'nonce': 'stale-boot'},
])
def test_existing_foreign_or_stale_vm_does_not_get_new_configuration(change):
    value = manager()
    value.compute_instance.get.return_value = existing(**change)
    with patch.object(module, 'WireGuardGatewayIdentity') as identity:
        identity.return_value.ensure.return_value = EMAIL
        with pytest.raises(BadRequest):
            value._prepare_wireguard_bootstrap()
    value.compute_instance.replace_metadata.assert_not_called()


def test_build_waits_for_guest_service_before_reporting_running():
    value = manager()
    events = []
    value.state_manager.get_state.return_value = ServerStates.READY.value
    value.state_manager.state_transition.side_effect = lambda state: events.append(state)
    for name in ['_require_wireguard_provisionable', '_prepare_wireguard_bootstrap',
                 '_refresh_wireguard_external_ip', '_stage_wireguard_endpoint',
                 '_ensure_dns_record', '_build_routes', '_wait_for_wireguard_service']:
        setattr(value, name, lambda name=name: events.append(name))
    value._build_server = lambda finalize_state: events.append('vm')
    value.build()
    assert events[-2:] == ['_wait_for_wireguard_service', ServerStates.RUNNING]
    assert events.index('_prepare_wireguard_bootstrap') < events.index('vm')
    assert events.index('vm') < events.index('_refresh_wireguard_external_ip')


def test_unhealthy_guest_never_reports_running_and_hides_endpoint():
    value = manager()
    value.state_manager.get_state.return_value = ServerStates.READY.value
    for name in ['_require_wireguard_provisionable', '_prepare_wireguard_bootstrap',
                 '_build_server', '_refresh_wireguard_external_ip', '_stage_wireguard_endpoint',
                 '_ensure_dns_record', '_build_routes']:
        setattr(value, name, MagicMock())
    value._wait_for_wireguard_service = MagicMock(side_effect=TimeoutError('bootstrap failed'))
    value._mark_wireguard_endpoint_error = MagicMock()
    with pytest.raises(TimeoutError):
        value.build()
    value.state_manager.state_transition.assert_called_once_with(ServerStates.BROKEN)
    value._mark_wireguard_endpoint_error.assert_called_once()


def test_health_wait_tolerates_initial_configuration_and_requires_current_ready():
    value = manager()
    value._WIREGUARD_READY_ATTEMPTS = 2
    stale = SimpleNamespace(is_ready=lambda now: False, health_error='wireguard_service_unready')
    ready = SimpleNamespace(is_ready=lambda now: True, health_error=None)
    value._wireguard_provisioning.return_value.get_lease.side_effect = [stale, ready]
    with patch.object(module.time, 'sleep') as sleep:
        value._wait_for_wireguard_service()
    sleep.assert_called_once_with(5)


def test_ephemeral_address_is_read_from_current_instance():
    value = manager()
    value.compute_instance.get.return_value = {'network_interfaces': [
        {'access_configs': [{'nat_i_p': '203.0.113.17'}]},
    ]}
    value._refresh_wireguard_external_ip()
    assert value.primary_external_ip == '203.0.113.17'


def test_managed_nic_never_reserves_or_releases_a_static_address():
    value = manager()
    value.server_spec.network_prefix = UNIT
    value.server_spec.parent_id = UNIT
    value.server_spec.nics = [{
        'network': 'external', 'subnet_name': 'default', 'external_nat': True,
        'external_ip_name': 'legacy-static-address',
    }]
    value.address_manager = MagicMock()
    with patch.object(module, 'NetworkInterfaceResource') as interfaces:
        value._add_nics()
    value.address_manager.reserve.assert_not_called()
    interfaces.return_value.access_config.assert_called_once_with(
        type_='ONE_TO_ONE_NAT', name='External NAT', nat_ip=None,
    )
    assert value._reserved_external_address_names() == []


def test_stop_invalidates_health_and_removes_owned_ephemeral_dns():
    value = manager()
    value._require_wireguard_provisionable = MagicMock()
    endpoint = SimpleNamespace(id='10000', hostname='wg10000.test.example.', public_ip='203.0.113.17')
    value.wireguard_registry.get.return_value = endpoint
    value._stop_server = MagicMock()
    value.state_manager.get_state.return_value = ServerStates.STOPPED.value
    value.dns_manager = MagicMock()
    value.stop()
    value._wireguard_provisioning.return_value.prepare_boot.assert_called_once_with(UNIT, force=True)
    value.dns_manager.delete_dns.assert_called_once_with(
        record_name=endpoint.hostname, ip_address=endpoint.public_ip,
    )
    value.wireguard_registry.release.assert_not_called()


def test_identity_grants_act_as_only_on_the_new_gateway_account():
    iam = MagicMock()
    accounts = iam.projects.return_value.serviceAccounts.return_value
    accounts.get.return_value.execute.return_value = {'email': EMAIL}
    accounts.getIamPolicy.return_value.execute.return_value = {
        'etag': 'retain-me', 'bindings': [{'role': 'roles/viewer', 'members': ['user:keep@example.test']}],
    }
    assert WireGuardGatewayIdentity('tenant-project', iam=iam).ensure(UNIT) == EMAIL
    request = accounts.setIamPolicy.call_args.kwargs
    assert request['resource'] == f'projects/tenant-project/serviceAccounts/{EMAIL}'
    policy = request['body']['policy']
    assert policy['etag'] == 'retain-me'
    assert policy['bindings'][0]['members'] == ['user:keep@example.test']
    assert policy['bindings'][1] == {
        'role': 'roles/iam.serviceAccountUser',
        'members': ['serviceAccount:agoge-service@tenant-project.iam.gserviceaccount.com'],
    }


def test_disabled_gateway_identity_is_rejected():
    iam = MagicMock()
    iam.projects.return_value.serviceAccounts.return_value.get.return_value.execute.return_value = {'disabled': True}
    with pytest.raises(BadRequest, match='disabled'):
        WireGuardGatewayIdentity('tenant-project', iam=iam).ensure(UNIT)


def test_isolated_student_insert_has_no_default_service_account_or_oauth_scope():
    value = manager()
    value.server_spec = SimpleNamespace()
    value._load_lab_server('student-server', {
        'parent_id': 'workout-id', 'image': 'image-kali', 'no_service_account': True,
        # Even an old privileged value is discarded when isolation is required.
        'serviceAccounts': [{'email': 'default', 'scopes': ['cloud-platform']}],
    })
    value.server_spec.disks = []
    value.server_spec.metadata = {'items': []}
    value.server_spec.network_interfaces = []
    value._add_disks = MagicMock()
    value._add_metadata = MagicMock()
    value._add_nics = MagicMock()
    value._lookup_machine_type = MagicMock(return_value='e2-medium')
    value._dns_record = MagicMock(return_value=False)
    value.compute_instance.create.return_value = True
    value.ip_aliases = False
    BaseComputeManager._build_server(value, finalize_state=False)
    request = value.compute_instance.create.call_args.kwargs['instance_resource']
    assert list(request.service_accounts) == []


def test_managed_start_finishes_guest_dependencies_before_running_state():
    value = manager()
    events = []
    value.state_manager.get_state.return_value = ServerStates.STOPPED.value
    value._require_wireguard_provisionable = MagicMock()
    value._prepare_wireguard_bootstrap = lambda for_start: events.append('metadata')
    value._start_server = lambda finalize_state: events.append(('start', finalize_state)) or True
    for name in ['_refresh_wireguard_external_ip', '_stage_wireguard_endpoint',
                 '_ensure_dns_record', '_wait_for_wireguard_service', '_activate_wireguard_endpoint']:
        setattr(value, name, lambda name=name: events.append(name))
    value.state_manager.state_transition.side_effect = lambda state: events.append(state)
    value.start()
    assert events == ['metadata', ('start', False), '_refresh_wireguard_external_ip',
                      '_stage_wireguard_endpoint', '_ensure_dns_record',
                      '_wait_for_wireguard_service', '_activate_wireguard_endpoint', ServerStates.RUNNING]


def test_warm_process_managers_do_not_share_gateway_identity_or_metadata():
    env = SimpleNamespace(project='tenant-project', get_env=lambda: {})
    with patch.object(base_module, 'CloudEnv', return_value=env), \
            patch.object(base_module, 'DnsManager'), \
            patch.object(base_module, 'PubSubManager'), \
            patch.object(base_module, 'DocumentDatabaseFactory'), \
            patch.object(base_module, 'Logger'), \
            patch.object(BaseComputeManager, '_enable_compute_api'):
        first = BaseComputeManager(env_dict={'project': 'tenant-project'})
        second = BaseComputeManager(env_dict={'project': 'tenant-project'})
    first.server_spec.service_accounts = [{'email': EMAIL}]
    first.server_spec.metadata.append({'key': 'startup-script', 'value': 'gateway'})
    first.server_spec.wireguard_managed = True
    assert first.server_spec is not second.server_spec
    assert second.server_spec.service_accounts is None
    assert second.server_spec.metadata == []
    assert second.server_spec.wireguard_managed is False


@pytest.mark.parametrize('reference', [
    'projects/shared-project/global/images/kali-ready',
    'https://www.googleapis.com/compute/v1/projects/shared-project/global/images/kali-ready',
])
def test_registered_student_image_is_used_as_a_pinned_boot_source(reference):
    value = manager()
    value.server_spec.image = reference
    value.compute_image = MagicMock()
    disk = value._get_boot_disk()
    assert disk.initialize_params.source_image == 'projects/shared-project/global/images/kali-ready'
    value.compute_image.get.assert_not_called()


@pytest.mark.parametrize('reference', [
    'https://evil.example/projects/shared-project/global/images/kali-ready',
    'projects/shared-project/global/images/family/ubuntu-2404-lts-amd64',
    'https://www.googleapis.com/compute/v1/projects/shared-project/global/images/kali-ready?key=x',
    'https://www.googleapis.com/compute/v1/projects/shared-project/global/images/kali-ready#fragment',
    'projects/shared-project/global/images/../../other',
])
def test_untrusted_or_unpinned_boot_image_reference_is_rejected(reference):
    value = manager()
    value.server_spec.image = reference
    value.compute_image = MagicMock()
    with pytest.raises(BadRequest):
        value._get_boot_disk()
    value.compute_image.get.assert_not_called()
