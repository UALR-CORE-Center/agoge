import base64
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
import threading

import pytest
from pydantic import ValidationError

from common.exceptions import BadRequest, Conflict, NotReady, Unauthorized
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
        {'project': 'agoge-test', 'parent_dns_suffix': '.example.edu', 'project_path': 'ualr'},
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
    context.db.collections['unit'][target.id] = {'workspace_settings': {'expires': 2000}}
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
    assert config['service_ready'] and config['tunnel_ready']
    assert 'private_key' not in config and 'callback_token' not in config and 'token_digest' not in config


@pytest.mark.parametrize('mutation', ['stopped', 'stale', 'expired', 'disabled', 'released', 'missing-unit'])
def test_pi_rejects_stale_stopped_expired_or_disabled_leases(context, mutation):
    target, _, _ = ready(context)
    lease = context.db.collections['wireguard-lease'][target.id]
    if mutation == 'stopped':
        context.db.records[target.wireguard_endpoint.id]['status'] = 'reserved'
    elif mutation == 'stale':
        lease['health_timestamp'] = 800
    elif mutation == 'expired':
        lease['expires'] = 900
    elif mutation == 'disabled':
        context.db.collections['wireguard-kit']['kit-one']['enabled'] = False
    elif mutation == 'released':
        context.service.release(target.id)
    elif mutation == 'missing-unit':
        context.db.collections['unit'].pop(target.id)
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
