"""Enroll existing Agoge display proxies in Secret Manager-backed TLS."""
import re
import subprocess
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from google.api_core.exceptions import PreconditionFailed
from google.cloud import compute_v1, firestore

from cloud_fn_utilities.gcp.dns_manager import DnsManager
from cloud_fn_utilities.server_specific.guacamole.community_proxy_bootstrap import (
    CommunityProxyIdentity, SECRET_METADATA_KEY,
)
from common.constants.database import ADMIN_INFO_DOCUMENT, DATABASE_NAME, DbCollections
from common.constants.states import ServerStates
from common.services.community_guacamole_startup import render_community_guacamole_startup
from common.services.community_proxy_spec import COMMUNITY_PROXY_NAME
from common.services.guacamole_tls_startup import (
    GUACAMOLE_TLS_READER_METADATA_KEY, GUACAMOLE_TLS_SCOPE, GUACAMOLE_TLS_SECRET_PATTERN,
    guacamole_tls_metadata, guacamole_tls_reader_email, install_guacamole_tls_in_startup,
    render_guacamole_tls_install,
)
from common.utilities.ctf_plant_contract import LINUX_LOADER, PLANT_METADATA_KEY


_PROXY_NAME = re.compile(rf'([a-z]{{10}})-{COMMUNITY_PROXY_NAME}')
_STARTUP = 'startup-script'
_UNSAFE_METADATA = {'startup-script-url', PLANT_METADATA_KEY}
_TRANSITIONING = {ServerStates.START.value, ServerStates.BUILDING.value, ServerStates.STARTING.value,
                  ServerStates.STOPPING.value, ServerStates.RESETTING.value, ServerStates.RELOADING.value,
                  ServerStates.DELETING.value, ServerStates.DELETED.value, ServerStates.EXPIRED.value}
_RPC_TIMEOUT = 30
_OPERATION_TIMEOUT = 180


@dataclass(frozen=True)
class _ProxyMigration:
    hostname: str
    email: str
    change_account: bool
    unit_id: str | None
    boot_updates: dict = field(repr=False)
    record_updates: dict = field(repr=False)
    guest_install: str = field(repr=False)


def _merged_items(existing: dict, updates: dict) -> dict:
    merged = existing | updates
    if GUACAMOLE_TLS_READER_METADATA_KEY not in updates:
        merged.pop(GUACAMOLE_TLS_READER_METADATA_KEY, None)
    return merged


def _existing_metadata(metadata) -> dict:
    return {item.key: item.value for item in metadata.items}


def _items(values: dict) -> list[dict]:
    return [{'key': key, 'value': value} for key, value in values.items()]


def _standard_scripts(live: str, recorded: str, secret: str, hostname: str, domain: str) -> tuple[str, str]:
    recorded_boot = install_guacamole_tls_in_startup(recorded, secret, hostname, domain)
    live_boot = install_guacamole_tls_in_startup(live, secret, hostname, domain)
    # The generic LabServer manager adds this repository-owned loader after
    # Guacamole's script. Refuse unknown script bodies before enabling cert access.
    if live_boot.rstrip() not in {recorded_boot.rstrip(), f'{recorded_boot.rstrip()}\n{LINUX_LOADER.lstrip()}'.rstrip()}:
        raise ValueError('the VM has a startup script outside its generated Guacamole configuration')
    return live_boot, recorded_boot


def _plan(instance, record: dict, settings: dict, project: str, secret: str) -> _ProxyMigration:
    parent_id = _PROXY_NAME.fullmatch(instance.name)[1]
    if record.get('name') != COMMUNITY_PROXY_NAME or record.get('parent_id') != parent_id:
        raise ValueError('no matching Agoge proxy record')
    if record.get('no_service_account') is True:
        raise ValueError('legacy community compatibility proxy has no guest service account')
    if instance.status not in {'RUNNING', 'TERMINATED'} or record.get('state') in _TRANSITIONING:
        raise ValueError('proxy is transitioning or outside normal VM lifecycle states')

    domain = (settings.get('parent_dns_suffix') or settings.get('dns_suffix') or '').strip('.').lower()
    hostname = (record.get('dns_hostname') or record.get('hostname') or '').rstrip('.').lower()
    if hostname != f'{parent_id}-display.{domain}':
        raise ValueError('the hostname differs from the generated Agoge display hostname')
    metadata = _existing_metadata(instance.metadata)
    startup = metadata.get(_STARTUP, '')
    if _UNSAFE_METADATA.intersection(metadata) or not startup.startswith('#!/bin/bash\n'):
        raise ValueError('proxy has a custom or missing startup configuration')

    accounts = [(account.email, set(account.scopes)) for account in instance.service_accounts]
    reader = guacamole_tls_reader_email(project)
    unit_id = None
    impersonate = None
    record_updates = {}
    if record.get('community_proxy') is True:
        unit_id = parent_id
        email = f'agoge-guac-{unit_id}@{project}.iam.gserviceaccount.com'
        if accounts != [(email, {GUACAMOLE_TLS_SCOPE})]:
            raise ValueError('the community proxy is missing its Unit-owned service account or cloud-platform scope')
        unit_secret = record.get('guacamole_secret_version_name')
        if metadata.get(SECRET_METADATA_KEY) != unit_secret or not unit_secret:
            raise ValueError('the community proxy does not match its Unit signing-secret reference')
        # The Unit generates this bootstrap and forbids other startup code. A
        # mismatch may be a custom/older guest and needs an explicit inspection.
        existing_boot = render_community_guacamole_startup(unit_secret, unit_id, domain)
        stored_boot = _record_metadata_values(record).get(_STARTUP)
        if not isinstance(stored_boot, str) or 'AGOGE_COMMUNITY_GUAC_PY' not in stored_boot:
            stored_boot = existing_boot
        impersonate = reader
        desired = render_community_guacamole_startup(
            unit_secret, unit_id, domain, tls_secret=secret, tls_reader=reader,
        )
        if startup not in {existing_boot, stored_boot, desired}:
            raise ValueError('the VM has a startup script outside its generated community configuration')
        record_updates = {'guacamole_startup_script': None}
    else:
        recorded = record.get('guacamole_startup_script')
        if not isinstance(recorded, str) or not recorded.startswith('#!/bin/bash\n'):
            raise ValueError('proxy is missing its generated Guacamole startup script')
        email = reader
        # Do not take a service account from a differently configured VM.
        default_email = f'{settings.get("project_number")}-compute@developer.gserviceaccount.com'
        if any(account not in {reader, default_email, 'default'} for account, _ in accounts):
            raise ValueError('proxy has a custom service account')
        desired, recorded_boot = _standard_scripts(startup, recorded, secret, hostname, domain)
        account_fields = [{'email': reader, 'scopes': [GUACAMOLE_TLS_SCOPE]}]
        record_updates = {'guacamole_startup_script': recorded_boot,
                          'service_accounts': account_fields, 'serviceAccounts': account_fields}

    boot_updates = guacamole_tls_metadata(secret, hostname, impersonate=impersonate)
    boot_updates[_STARTUP] = desired
    desired_metadata = _merged_items(metadata, boot_updates)
    sizes = [len(key.encode()) + len(value.encode()) for key, value in desired_metadata.items()]
    if len(desired.encode()) > 256 * 1024 or sum(sizes) > 512 * 1024:
        raise ValueError('the TLS installer would exceed the VM metadata size limit')
    stored_updates = boot_updates if unit_id else guacamole_tls_metadata(secret, hostname)
    stored_metadata = record.get('metadata') or {}
    stored_values = _merged_items(_record_metadata_values(record), stored_updates)
    record_updates['metadata'] = (
        stored_metadata | {'items': _items(stored_values)} if unit_id or 'items' in stored_metadata else stored_values
    )
    return _ProxyMigration(
        hostname, email, accounts != [(email, {GUACAMOLE_TLS_SCOPE})], unit_id,
        boot_updates, record_updates,
        render_guacamole_tls_install(secret, hostname, domain, impersonate=impersonate),
    )


def _record_metadata_values(record: dict) -> dict:
    metadata = record.get('metadata') or {}
    if not isinstance(metadata, dict):
        raise ValueError('proxy has an unsupported Firestore metadata format')
    return metadata if 'items' not in metadata else {item['key']: item['value'] for item in metadata['items']}


def _set_boot_metadata(client, target: dict, instance, changes: dict) -> None:
    original = _existing_metadata(instance.metadata)
    for attempt in range(3):
        current = _same_instance(client, target, instance.id)
        existing = _existing_metadata(current.metadata)
        if (existing.get(_STARTUP) not in {original.get(_STARTUP), changes[_STARTUP]}
                or _UNSAFE_METADATA.intersection(existing)):
            raise ValueError('the proxy startup configuration changed during migration')
        desired = _merged_items(existing, changes)
        if desired == existing:
            return
        try:
            client.set_metadata(
                **target,
                metadata_resource=compute_v1.Metadata(fingerprint=current.metadata.fingerprint, items=_items(desired)),
                timeout=_RPC_TIMEOUT,
            ).result(timeout=_OPERATION_TIMEOUT)
            return
        except PreconditionFailed:
            if attempt == 2:
                raise


def _same_instance(client, target: dict, instance_id: int):
    instance = client.get(**target, timeout=_RPC_TIMEOUT)
    if instance.id != instance_id:
        raise ValueError('the original VM was replaced during migration')
    return instance


def _external_ip(instance) -> str | None:
    return next((access.nat_i_p for nic in instance.network_interfaces
                 for access in nic.access_configs if access.nat_i_p), None)


def _set_identity_and_metadata(client, target: dict, instance, plan: _ProxyMigration, settings: dict):
    current = _same_instance(client, target, instance.id)
    if current.status != instance.status or list(current.service_accounts) != list(instance.service_accounts):
        raise ValueError('the VM state or service account changed during migration')
    restart = current.status == 'RUNNING' and plan.change_account
    if restart:
        old_address = _external_ip(current)
        if not old_address or any(disk.type_ == 'SCRATCH' for disk in current.disks):
            raise ValueError('this running VM cannot be restarted safely by the migration')
        dns = DnsManager(env_dict=settings)
    try:
        if restart:
            client.stop(**target, timeout=_RPC_TIMEOUT).result(timeout=_OPERATION_TIMEOUT)
        if plan.change_account:
            current = _same_instance(client, target, instance.id)
            if current.status != 'TERMINATED' or list(current.service_accounts) != list(instance.service_accounts):
                raise ValueError('the VM must be stopped and retain its original identity during migration')
            client.set_service_account(
                **target,
                instances_set_service_account_request_resource=compute_v1.InstancesSetServiceAccountRequest(
                    email=plan.email, scopes=[GUACAMOLE_TLS_SCOPE],
                ),
                timeout=_RPC_TIMEOUT,
            ).result(timeout=_OPERATION_TIMEOUT)
        _set_boot_metadata(client, target, instance, plan.boot_updates)
    finally:
        if restart:
            current = _same_instance(client, target, instance.id)
            if current.status == 'TERMINATED':
                client.start(**target, timeout=_RPC_TIMEOUT).result(timeout=_OPERATION_TIMEOUT)
                current = _same_instance(client, target, instance.id)
            if current.status != 'RUNNING':
                raise ValueError(f'VM did not resume after migration (status {current.status})')
            address = _external_ip(current)
            if not address or (address != old_address and not dns.add_dns_record(
                    plan.hostname, instance.name, ip_address=address)):
                raise ValueError('VM resumed, but its public DNS record could not be refreshed')


def _install_on_running_guest(instance, installer: str) -> bool:
    address = _external_ip(instance)
    if not address:
        return False
    # Use only existing SSH authorization and a previously trusted key for this
    # VM ID. `gcloud compute ssh` can add authorized keys to project metadata.
    command = [
        'ssh', '-T', '-oBatchMode=yes', '-oConnectTimeout=8', '-oStrictHostKeyChecking=yes',
        f'-oHostKeyAlias=compute.{instance.id}',
        '-oUserKnownHostsFile=~/.ssh/google_compute_known_hosts ~/.ssh/known_hosts',
    ]
    gcloud_key = Path('~/.ssh/google_compute_engine').expanduser()
    if gcloud_key.is_file():
        command.extend(['-i', str(gcloud_key)])
    try:
        result = subprocess.run(
            [*command, address, 'sudo -n /bin/bash -s'], input=installer, text=True,
            capture_output=True, timeout=_OPERATION_TIMEOUT + 30, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def migrate_guacamole_tls(project: str, *, apply: bool = False, restart_running: bool = False,
                          instance_name: str | None = None) -> bool:
    """Inventory or update existing proxies, leaving parked VMs stopped."""
    db = firestore.Client(project=project, database=DATABASE_NAME)
    ref = db.collection(DbCollections.ADMIN_INFO.value).document(ADMIN_INFO_DOCUMENT)
    settings = ref.get(timeout=_RPC_TIMEOUT).to_dict() or {}
    secret = settings.get('guacamole_tls_secret')
    if settings.get('project') != project or not re.fullmatch(GUACAMOLE_TLS_SECRET_PATTERN, str(secret)):
        print(f'{project}: configure a Guacamole TLS secret for this project before migration.')
        return False
    if instance_name and not _PROXY_NAME.fullmatch(instance_name):
        print('Use the full Agoge proxy VM name, such as abcdefghij-display-guacamole-server.')
        return False

    client = compute_v1.InstancesClient()
    query = compute_v1.AggregatedListInstancesRequest(project=project)
    if instance_name:
        query.filter = f'name = "{instance_name}"'
    else:
        query.filter = f'name eq "[a-z]{{10}}-{COMMUNITY_PROXY_NAME}"'
    servers = db.collection(DbCollections.SERVER.value)
    inventory = [
        (location.rsplit('/', 1)[-1], instance)
        for location, listing in client.aggregated_list(request=query, timeout=_RPC_TIMEOUT)
        for instance in listing.instances
        if _PROXY_NAME.fullmatch(instance.name) and (not instance_name or instance.name == instance_name)
    ]
    if not inventory:
        print(f'{project}: no matching Guacamole proxy VMs.')
        return instance_name is None
    name_counts = Counter(instance.name for _, instance in inventory)
    completed = True
    for zone, listed in inventory:
        target = {'project': project, 'zone': zone, 'instance': listed.name}
        label = f'{listed.name} ({zone})'
        try:
            instance = _same_instance(client, target, listed.id)
            record_ref = servers.document(instance.name)
            snapshot = record_ref.get(timeout=_RPC_TIMEOUT)
            record = snapshot.to_dict() or {}
            if record.get('zone') and record['zone'].rsplit('/', 1)[-1] != zone:
                raise ValueError('the Firestore server belongs to a different zone')
            if not record.get('zone') and name_counts[instance.name] > 1:
                raise ValueError('multiple VMs have this name and the Firestore server has no assigned zone')
            plan = _plan(instance, record, settings, project, secret)
        except ValueError as error:
            print(f'  {label}: skipped ({error})')
            if apply and instance_name:
                completed = False
            continue
        except Exception as error:
            print(f'  {label}: could not inspect proxy ({type(error).__name__})')
            completed = False
            continue

        running = instance.status == 'RUNNING'
        restart = running and plan.change_account
        if not apply:
            identity = 'change service account or scope' if plan.change_account else 'keep service account'
            action = 'stop/start required' if restart else 'install in guest' if running else 'stage for next boot'
            print(f'  {label}: {instance.status}; {identity}; {action}.')
            continue
        if restart and not restart_running:
            print(f'  {label}: skipped; changing a running VM requires explicit stop/start authorization.')
            completed = False
            continue
        try:
            if plan.unit_id:
                CommunityProxyIdentity(project).grant_tls_reader_impersonation(plan.unit_id)
            _set_identity_and_metadata(client, target, instance, plan, settings)
            record_ref.update(plan.record_updates, option=db.write_option(last_update_time=snapshot.update_time),
                              timeout=_RPC_TIMEOUT)
            if restart:
                print(f'  {label}: restarted with TLS installer staged for this boot.')
            elif running:
                if _install_on_running_guest(instance, plan.guest_install):
                    print(f'  {label}: TLS installer ran on the existing VM.')
                else:
                    print(f'  {label}: live TLS install unavailable; installer staged for the next boot.')
            else:
                print(f'  {label}: TLS installer staged for the next boot.')
        except ValueError as error:
            print(f'  {label}: migration incomplete ({error}). Check VM status and retry.')
            completed = False
        except Exception as error:
            print(f'  {label}: migration incomplete ({type(error).__name__}). Check VM status and retry.')
            completed = False
    return completed
