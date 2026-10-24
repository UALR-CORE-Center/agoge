import base64
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
import threading

import pytest
from pydantic import ValidationError

from common.exceptions import BadRequest, Conflict, NotReady, Unauthorized
from common.constants.states import UnitStates
from common.models.wireguard_provisioning import WireGuardKitCreate, WireGuardHealthReport
from common.services.wireguard_provisioning import WireGuardProvisioningService
from common.tests.test_wireguard_endpoint_registry import _FakeDatabase


class Database(_FakeDatabase):
    def __init__(self):
        super().__init__()
        self.lock = threading.Lock()
        for collection in ('wireguard-kit', 'wireguard-lease', 'unit'):
            self.collections[collection] = {}

    def transaction(self, callback, *args, **kwargs):
        with self.lock:
            return super().transaction(callback, *args, **kwargs)


class Secrets:
    def __init__(self):
        self.payloads = {}
        self.deleted = []
        self.grants = []

    def ensure(self, unit_id, payload):
        return self.payloads.setdefault(unit_id, payload)

    def access(self, version):
        return self.payloads[version.split('/secrets/agoge-wg-')[1].split('/')[0]]

    def delete(self, version):
        self.deleted.append(version)
        self.payloads.pop(version.split('/secrets/agoge-wg-')[1].split('/')[0], None)

    def grant(self, version, email):
        self.grants.append((version, email))


@pytest.fixture
def context():
    db, secret_store = Database(), Secrets()
    service = WireGuardProvisioningService(
        {'project': 'agoge-test', 'parent_dns_suffix': '.example.edu', 'project_path': 'ualr',
         'wireguard_health_reporting_enabled': True},
        db=db, secret_store=secret_store, clock=lambda: 1000)
    admin = SimpleNamespace(is_admin=True, email='admin@example.edu')
    instructor = SimpleNamespace(is_admin=False, email='teacher@example.edu')
    enrollment = service.enroll(kit_data(), admin)
    return SimpleNamespace(db=db, secrets=secret_store, service=service, admin=admin,
                           instructor=instructor, enrollment=enrollment)


def kit_data(identifier='kit-one', subnet='172.30.0.0/24', key_number=1):
    return {'id': identifier, 'device_id': identifier + '-pi', 'equipment_subnet': subnet,
            'peer_public_key': base64.b64encode(bytes([key_number]) * 32).decode(),
            'authorized_instructors': ['teacher@example.edu']}


def unit(context, identifier='abcdefghij', endpoint_id='10000', subnet='10.20.0.0/24'):
    context.db.records[endpoint_id] = {'id': endpoint_id, 'unit_id': identifier, 'status': 'reserved',
                                     'hostname': 'wg10000.example.edu.', 'port': 51820}
    return SimpleNamespace(id=identifier, networks=[SimpleNamespace(subnets=[SimpleNamespace(ip_subnet=subnet)])],
                           workspace_settings=SimpleNamespace(expires=2000),
                           wireguard_endpoint=SimpleNamespace(id=endpoint_id, port=51820),
                           servers=[SimpleNamespace(wireguard_gateway=True, wireguard_managed=False)],
                           wireguard_lease=None)


def ready(context, target=None):
    target = target or unit(context)
    service = context.service
    service.reserve(target, 'kit-one', context.instructor)
    boot = service.prepare_boot(target.id)
    token = context.secrets.payloads[target.id]['callback_token']
    service.report_health(target.id, token, {
        'boot_id': boot, 'service_ready': True, 'tunnel_ready': True, 'latest_handshake': 990})
    context.db.records[target.wireguard_endpoint.id]['status'] = 'active'
    context.db.collections['unit'][target.id] = {'state': UnitStates.READY.value,
                                               'workspace_settings': {'expires': 2000}}
    return target, boot, token


def test_enrollment_only_returns_token_once_and_lists_safe_records(context):
    assert context.enrollment['enrollment_token']
    records = context.service.list_kits(context.instructor)
    assert len(records) == 1
    assert 'token_digest' not in records[0].model_dump()
    assert 'enrollment_token' not in records[0].model_dump()
    stored = context.db.collections['wireguard-kit']['kit-one']
    assert stored['token_digest'] != context.enrollment['enrollment_token']
    outsider = SimpleNamespace(is_admin=False, email='outsider@example.edu')
    assert context.service.list_kits(outsider) == []
    with pytest.raises(Unauthorized):
        context.service.enroll(kit_data('second', key_number=2), outsider)


@pytest.mark.parametrize('change', [
    {'id': 'kit-one', 'device_id': 'other', 'peer_public_key': base64.b64encode(b'2' * 32).decode()},
    {'id': 'kit-two', 'device_id': 'kit-one-pi', 'peer_public_key': base64.b64encode(b'2' * 32).decode()},
    {'id': 'kit-two', 'device_id': 'other'},
])
def test_duplicate_kit_identity_and_peer_key_cannot_enroll_twice(context, change):
    duplicate = {**kit_data(), **change}
    with pytest.raises(Conflict):
        context.service.enroll(duplicate, context.admin)


@pytest.mark.parametrize('subnet', ['0.0.0.0/0', '8.8.8.0/24', '127.0.0.0/8', '169.254.1.0/24', '192.0.2.0/24', '100.64.0.0/10', 'fd00::/64'])
def test_equipment_subnet_is_private_ipv4(subnet):
    with pytest.raises(ValidationError):
        WireGuardKitCreate(**kit_data(subnet=subnet))


@pytest.mark.parametrize('key', ['', 'bad key', base64.b64encode(b'\0' * 32).decode()])
def test_invalid_peer_keys_are_rejected(key):
    with pytest.raises(ValidationError):
        WireGuardKitCreate(**{**kit_data(), 'peer_public_key': key})


def test_reserve_is_idempotent_and_keeps_private_keys_out_of_firestore(context):
    target = unit(context)
    first = context.service.reserve(target, 'kit-one', context.instructor)
    payload = dict(context.secrets.payloads[target.id])
    second = context.service.reserve(target, 'kit-one', context.instructor)
    assert first.gateway_public_key == second.gateway_public_key
    assert payload == context.secrets.payloads[target.id]
    assert target.servers[0].wireguard_managed
    assert 'private_key' not in str(context.db.collections)
    assert payload['private_key'] not in str(context.db.collections)
    assert payload['callback_token'] not in str(context.db.collections)
    assert 'callback_token_digest' not in str(target.wireguard_lease.model_dump())
    assert payload['health_url'] == 'https://api.example.edu/ualr/wireguard/gateways/abcdefghij/health/'


def test_default_reservation_needs_no_api_url_or_callback_credential(context):
    context.service.env_dict = {'project': 'agoge-test'}
    target = unit(context)
    context.service.reserve(target, 'kit-one', context.instructor)
    payload = context.secrets.payloads[target.id]
    assert payload['health_reporting_enabled'] is False
    assert 'health_url' not in payload and 'callback_token' not in payload
    assert 'callback_token_digest' not in context.db.collections['wireguard-lease'][target.id]
    with pytest.raises(Unauthorized):
        context.service.report_health(target.id, 'not-enabled', {
            'boot_id': 'boot-nonce-long-enough', 'service_ready': True})


def test_explicit_guest_telemetry_opt_in_has_private_callback_credential(context):
    target = unit(context)
    context.service.reserve(target, 'kit-one', context.instructor)
    payload = context.secrets.payloads[target.id]
    assert payload['health_reporting_enabled'] is True
    assert payload['callback_token']
    assert payload['health_url'].endswith('/wireguard/gateways/abcdefghij/health/')
    assert payload['callback_token'] not in str(context.db.collections)


@pytest.mark.parametrize('value', ['true', 1, None])
def test_guest_telemetry_opt_in_requires_a_boolean(context, value):
    context.service.env_dict['wireguard_health_reporting_enabled'] = value
    with pytest.raises(BadRequest, match='must be a boolean'):
        context.service.reserve(unit(context), 'kit-one', context.instructor)
    assert not context.secrets.payloads


def test_concurrent_units_cannot_claim_same_kit(context):
    one, two = unit(context), unit(context, 'klmnopqrst', '10001')
    def reserve(target):
        try:
            return context.service.reserve(target, 'kit-one', context.instructor).unit_id
        except Conflict:
            return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(reserve, [one, two]))
    assert len([result for result in results if result]) == 1
    assert len(context.db.collections['wireguard-lease']) == 1


def test_unauthorized_instructor_cannot_reserve_kit(context):
    with pytest.raises(Unauthorized):
        context.service.reserve(unit(context), 'kit-one', SimpleNamespace(is_admin=False, email='other@example.edu'))
    assert not context.secrets.payloads


@pytest.mark.parametrize('network', ['172.30.0.0/24', '10.254.254.0/30', '::/64', '192.0.2.0/24'])
def test_student_equipment_and_tunnel_overlap_is_rejected(context, network):
    with pytest.raises(BadRequest):
        context.service.reserve(unit(context, subnet=network), 'kit-one', context.instructor)


def test_equipment_tunnel_overlap_is_rejected(context):
    context.db.collections['wireguard-kit']['kit-one']['equipment_subnet'] = '10.254.254.0/30'
    with pytest.raises(BadRequest):
        context.service.reserve(unit(context), 'kit-one', context.instructor)


def test_enrollment_token_only_authenticates_its_kit(context):
    ready(context)
    other = context.service.enroll(kit_data('kit-two', key_number=2), context.admin)
    with pytest.raises(Unauthorized):
        context.service.pi_configuration('kit-one', other['enrollment_token'])
    with pytest.raises(Unauthorized):
        context.service.pi_configuration('missing', context.enrollment['enrollment_token'])


def test_pi_configuration_contains_only_its_public_config(context):
    target, _, _ = ready(context)
    config = context.service.pi_configuration('kit-one', context.enrollment['enrollment_token'])
    assert config['unit_id'] == target.id
    assert config['allowed_ips'] == ['10.20.0.0/24', '10.254.254.1/32']
    assert config['equipment_subnet'] == '172.30.0.0/24'
    assert config['gateway_ready'] is True
    assert config['service_ready'] and config['tunnel_ready']
    assert 'private_key' not in config and 'callback_token' not in config and 'token_digest' not in config


@pytest.mark.parametrize('changes', [
    {'service_ready': False, 'tunnel_ready': False, 'health_timestamp': None},
    {'service_ready': True, 'tunnel_ready': True, 'health_timestamp': 800},
])
def test_pi_gets_gcp_ready_configuration_without_fresh_guest_telemetry(context, changes):
    target, _, _ = ready(context)
    context.db.collections['wireguard-lease'][target.id].update(changes)
    config = context.service.pi_configuration('kit-one', context.enrollment['enrollment_token'])
    assert config['gateway_ready'] is True
    assert config['service_ready'] is False and config['tunnel_ready'] is False


@pytest.mark.parametrize('mutation', [
    'stopped', 'expired', 'disabled', 'released', 'missing-unit', 'unit-starting',
    'unit-stopping', 'unit-expired', 'unit-broken', 'unit-deleted', 'unit-expiration',
    'missing-endpoint', 'foreign-endpoint', 'stale-assignment', 'changed-device', 'changed-key',
])
def test_pi_rejects_inactive_expired_or_stale_assignments(context, mutation):
    target, _, _ = ready(context)
    lease = context.db.collections['wireguard-lease'][target.id]
    if mutation == 'stopped':
        context.db.records[target.wireguard_endpoint.id]['status'] = 'reserved'
    elif mutation == 'expired':
        lease['expires'] = 900
    elif mutation == 'disabled':
        context.db.collections['wireguard-kit']['kit-one']['enabled'] = False
    elif mutation == 'released':
        context.service.release(target.id)
    elif mutation == 'missing-unit':
        context.db.collections['unit'].pop(target.id)
    elif mutation.startswith('unit-') and mutation != 'unit-expiration':
        context.db.collections['unit'][target.id]['state'] = {
            'unit-starting': UnitStates.STARTING.value, 'unit-stopping': UnitStates.STOPPING.value,
            'unit-expired': UnitStates.EXPIRED.value, 'unit-broken': UnitStates.BROKEN.value,
            'unit-deleted': UnitStates.DELETED.value,
        }[mutation]
    elif mutation == 'unit-expiration':
        context.db.collections['unit'][target.id]['workspace_settings']['expires'] = 900
    elif mutation == 'missing-endpoint':
        context.db.records.pop(target.wireguard_endpoint.id)
    elif mutation == 'foreign-endpoint':
        context.db.records[target.wireguard_endpoint.id]['unit_id'] = 'otherunitx'
    elif mutation == 'stale-assignment':
        context.db.collections['wireguard-lease']['klmnopqrst'] = dict(lease)
        context.db.collections['wireguard-kit']['kit-one']['assigned_unit_id'] = 'klmnopqrst'
    elif mutation == 'changed-device':
        context.db.collections['wireguard-kit']['kit-one']['device_id'] = 'replaced-device'
    elif mutation == 'changed-key':
        context.db.collections['wireguard-kit']['kit-one']['peer_public_key'] = 'replaced-key'
    with pytest.raises(NotReady):
        context.service.pi_configuration('kit-one', context.enrollment['enrollment_token'])


def test_stale_boot_callback_cannot_resurrect_gateway(context):
    target, old_boot, token = ready(context)
    new_boot = context.service.prepare_boot(target.id, force=True)
    assert new_boot != old_boot
    assert context.service.prepare_boot(target.id) == new_boot
    with pytest.raises(NotReady):
        context.service.report_health(target.id, token, {'boot_id': old_boot, 'service_ready': True})
    assert not context.service.get_lease(target.id).service_ready
    with pytest.raises(Unauthorized):
        context.service.report_health(target.id, 'wrong', {'boot_id': new_boot, 'service_ready': True})


def test_handshake_is_only_ready_when_recent_and_service_ready(context):
    target, boot, token = ready(context)
    context.service.report_health(target.id, token, {'boot_id': boot, 'service_ready': True,
                                                    'tunnel_ready': True, 'latest_handshake': 1})
    assert not context.service.get_lease(target.id).tunnel_ready
    with pytest.raises(BadRequest):
        context.service.report_health(target.id, token, {'boot_id': boot, 'service_ready': True,
                                                       'latest_handshake': 2000})


def test_release_frees_kit_only_for_its_own_lease_and_deletes_secret(context):
    target, boot, token = ready(context)
    context.db.collections['wireguard-kit']['kit-one']['assigned_unit_id'] = 'newunitxxx'
    context.service.release(target.id)
    assert context.db.collections['wireguard-kit']['kit-one']['assigned_unit_id'] == 'newunitxxx'
    assert context.service.get_lease(target.id).status == 'released'
    assert target.id not in context.secrets.payloads
    context.service.release(target.id)
    with pytest.raises(NotReady):
        context.service.report_health(target.id, token, {'boot_id': boot, 'service_ready': True})


def test_failed_precommit_reservation_removes_secret_and_claim(context):
    target = unit(context)
    context.service.reserve(target, 'kit-one', context.instructor)
    context.service.cancel_if_uncommitted(target)
    assert context.db.collections['wireguard-kit']['kit-one']['assigned_unit_id'] is None
    assert not context.secrets.payloads


def test_failed_claim_still_removes_orphan_secret(context):
    context.db.collections['wireguard-kit']['kit-one']['assigned_unit_id'] = 'otherunitx'
    target = unit(context)
    with pytest.raises(Conflict):
        context.service.reserve(target, 'kit-one', context.instructor)
    assert target.id in context.secrets.payloads
    context.service.cancel_if_uncommitted(target)
    assert not context.secrets.payloads
    assert context.db.collections['wireguard-kit']['kit-one']['assigned_unit_id'] == 'otherunitx'


def test_committed_unit_keeps_claim_and_keys_on_failed_publish(context):
    target, _, _ = ready(context)
    context.service.cancel_if_uncommitted(target)
    assert target.id in context.secrets.payloads
    assert context.db.collections['wireguard-kit']['kit-one']['assigned_unit_id'] == target.id


def test_secret_accessor_is_scoped_to_dedicated_gateway_identity(context):
    target = unit(context)
    context.service.reserve(target, 'kit-one', context.instructor)
    with pytest.raises(BadRequest):
        context.service.grant_gateway_access(target.id, 'default@agoge-test.iam.gserviceaccount.com')
    context.service.grant_gateway_access(target.id, 'agoge-wg-abcdefghij@agoge-test.iam.gserviceaccount.com')
    assert len(context.secrets.grants) == 1


def test_health_rejects_freeform_error_payloads():
    with pytest.raises(ValidationError):
        WireGuardHealthReport(boot_id='a' * 20, service_ready=False, error='private/key=value')


@pytest.mark.parametrize('kit_id', ['../kit-one', 'kit-one/child', '', 'INVALID', None])
def test_direct_unit_call_cannot_inject_kit_document_paths(context, kit_id):
    with pytest.raises(BadRequest):
        context.service.get_authorized_kit(kit_id, context.instructor)
    assert not context.secrets.payloads


def test_remote_peer_enrollment_uses_private_lan_alias_without_migrating_storage(context):
    from common.models.wireguard_provisioning import WireGuardRemotePeerCreate
    body = kit_data('remote-lab-two', key_number=2)
    body['remote_network_cidr'] = body.pop('equipment_subnet')
    result = context.service.enroll_remote_peer(WireGuardRemotePeerCreate(**body), context.admin)
    public = result['remote_peer'].model_dump(by_alias=True)
    assert public['remote_network_cidr'] == '172.30.0.0/24'
    assert 'equipment_subnet' not in public and 'token_digest' not in public
    stored = context.db.collections['wireguard-kit']['remote-lab-two']
    assert stored['equipment_subnet'] == '172.30.0.0/24'
    assert 'remote_network_cidr' not in stored
    peers = context.service.list_remote_peers(context.instructor)
    assert {peer.id for peer in peers} == {'kit-one', 'remote-lab-two'}
    assert context.service.get_authorized_remote_peer('remote-lab-two', context.instructor).remote_network_cidr == '172.30.0.0/24'


@pytest.mark.parametrize('canonical', [False, True])
def test_remote_peer_model_accepts_legacy_network_field(context, canonical):
    from common.models.wireguard_provisioning import WireGuardRemotePeerCreate
    data = kit_data()
    if canonical:
        data['remote_network_cidr'] = data['equipment_subnet']
    peer = WireGuardRemotePeerCreate(**data)
    assert peer.remote_network_cidr == '172.30.0.0/24'


def test_remote_peer_model_rejects_conflicting_network_aliases():
    from common.models.wireguard_provisioning import WireGuardRemotePeerCreate
    with pytest.raises(ValidationError, match='conflicts'):
        WireGuardRemotePeerCreate(**kit_data(), remote_network_cidr='192.168.1.0/24')


@pytest.mark.parametrize('network', ['192.0.2.0/24', '0.0.0.0/0', 'fd00::/64'])
def test_remote_peer_model_requires_private_lan(network):
    from common.models.wireguard_provisioning import WireGuardRemotePeerCreate
    body = kit_data()
    body['remote_network_cidr'] = network
    body.pop('equipment_subnet')
    with pytest.raises(ValidationError):
        WireGuardRemotePeerCreate(**body)


@pytest.mark.parametrize('data', [
    {'remote_peer_id': 'remote-one'}, {'kit_id': 'remote-one'},
    {'remote_peer_id': 'remote-one', 'kit_id': 'remote-one'},
])
def test_build_remote_peer_selection_accepts_canonical_and_equal_legacy(data):
    from common.services.wireguard_provisioning import resolve_remote_peer_id
    assert resolve_remote_peer_id(data) == 'remote-one'


@pytest.mark.parametrize('data', [
    {'remote_peer_id': 'remote-one', 'kit_id': 'remote-two'},
    {'remote_peer_id': 'remote-one', 'kit_id': ''}, {'remote_peer_id': ''},
    {'remote_peer_id': '../other'}, {'remote_peer_id': 12}, {},
])
def test_build_remote_peer_selection_rejects_conflicts_and_invalid_identifiers(data):
    from common.services.wireguard_provisioning import resolve_remote_peer_id
    with pytest.raises(BadRequest):
        resolve_remote_peer_id(data)


def test_legacy_lease_serializes_additive_remote_peer_aliases(context):
    target = unit(context)
    lease = context.service.reserve(target, 'kit-one', context.instructor)
    public = lease.model_dump()
    assert public['remote_peer_id'] == public['kit_id'] == 'kit-one'
    assert public['remote_network_cidr'] == public['equipment_subnet'] == '172.30.0.0/24'
    # Old stored documents deserialize without backfilling or rewriting identifiers.
    public.pop('remote_peer_id')
    public.pop('remote_network_cidr')
    from common.models.wireguard_provisioning import WireGuardLeaseModel
    assert WireGuardLeaseModel(**public).remote_peer_id == 'kit-one'
