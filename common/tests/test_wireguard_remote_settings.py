"""Durable stopped-lab edits without exposing or prematurely selecting secrets."""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from common.constants.database import DbCollections
from common.constants.states import ServerStates, UnitStates, WorkoutStates
from common.exceptions import BadRequest, Conflict, Unauthorized
from common.tests.test_wireguard_provisioning import context, kit_data, unit, Secrets


class ConfigurationSecrets(Secrets):
    def __init__(self):
        super().__init__()
        self.versions = {}

    def stage_configuration(self, unit_id, revision, payload):
        version = f'projects/agoge-test/secrets/agoge-wg-{unit_id}-cfg-{revision}/versions/1'
        self.versions[version] = deepcopy(payload)
        return version

    def access(self, version):
        return deepcopy(self.versions[version] if version in self.versions else super().access(version))

    def delete(self, version):
        if version in self.versions:
            self.deleted.append(version)
            del self.versions[version]
        else:
            super().delete(version)


@pytest.fixture
def stopped(context):
    context.secrets = ConfigurationSecrets()
    context.service._secret_store = context.secrets
    target = unit(context)
    context.service.reserve(target, 'kit-one', context.instructor)
    context.db.collections[DbCollections.SERVER.value] = {
        f'{target.id}-wireguard': {'name': 'wireguard', 'state': ServerStates.STOPPED.value}}
    context.db.collections[DbCollections.WORKOUT.value] = {
        'klmnopqrst': {'id': 'klmnopqrst', 'parent_id': target.id, 'state': WorkoutStates.READY.value}}
    context.db.collections['unit'][target.id] = {
        'id': target.id, 'state': UnitStates.READY.value, 'instructor_id': ['teacher@example.edu'],
        'workspace_settings': {'expires': 2000},
        'servers': [{'name': 'wireguard', 'wireguard_gateway': True, 'wireguard_managed': True}],
        'wireguard_lease': target.wireguard_lease.model_dump(),
        'routes': [{'name': 'wireguard-equipment', 'dest_range': '172.30.0.0/24', 'network': 'external',
                    'next_hop_instance': 'wireguard', 'tags': ['wireguard-client']}],
        'firewall_rules': [{'name': 'allow-kit-to-students', 'ip_ranges': ['172.30.0.0/24']}],
    }
    context.target = target
    return context


def edit(data=None):
    return {'remote_peer_id': 'kit-one', 'remote_network_cidr': '192.168.50.0/24', **(data or {})}


def test_admin_edits_friendly_registration_without_returning_credentials(stopped):
    peer = stopped.service.update_remote_peer('kit-one', {'name': 'Remote pump station', 'description': 'Plant LAN'}, stopped.admin)
    assert peer.name == 'Remote pump station'
    assert peer.description == 'Plant LAN'
    assert 'token_digest' not in peer.model_dump()
    assert stopped.db.collections['wireguard-kit']['kit-one']['token_digest']
    with pytest.raises(Conflict, match='assigned'):
        stopped.service.update_remote_peer('kit-one', {'remote_network_cidr': '192.168.60.0/24'}, stopped.admin)
    unchanged = stopped.service.update_remote_peer('kit-one', {'remote_network_cidr': '172.30.0.0/24'}, stopped.admin)
    assert unchanged.assigned_unit_id == stopped.target.id


def test_admin_key_update_enforces_unique_peer_identity(context):
    context.service.enroll(kit_data('kit-two', key_number=2), context.admin)
    with pytest.raises(Conflict, match='public key'):
        context.service.update_remote_peer('kit-two', {'peer_public_key': kit_data()['peer_public_key']}, context.admin)
    with pytest.raises(Unauthorized):
        context.service.update_remote_peer('kit-one', {'name': 'No'}, context.instructor)


def test_stopped_instructor_lab_saves_private_lan_and_immutable_secret_for_next_start(stopped):
    old_payload = deepcopy(stopped.secrets.payloads[stopped.target.id])

    result = stopped.service.update_lab_settings(stopped.target.id, edit(), stopped.instructor)

    lease = stopped.service.get_lease(stopped.target.id)
    assert result['configuration_status'] == 'saved' and result['can_edit']
    assert lease.configuration_pending and lease.configuration_revision
    assert lease.secret_version_name.endswith('/versions/1')
    assert lease.previous_secret_version_name.endswith('/versions/latest')
    assert stopped.secrets.payloads[stopped.target.id] == old_payload
    assert stopped.secrets.versions[lease.secret_version_name]['equipment_subnet'] == '192.168.50.0/24'
    assert stopped.db.collections['wireguard-kit']['kit-one']['equipment_subnet'] == '172.30.0.0/24'
    saved = stopped.db.collections['unit'][stopped.target.id]
    assert saved['routes'][0]['dest_range'] == '192.168.50.0/24'
    assert saved['firewall_rules'][0]['ip_ranges'] == ['192.168.50.0/24']
    assert 'private_key' not in str(stopped.db.collections)
    assert old_payload['private_key'] not in str(stopped.db.collections)
    stopped.service.configuration_applied(stopped.target.id, lease.configuration_revision)
    assert stopped.service.lab_settings(stopped.target.id, stopped.instructor)['configuration_status'] == 'current'


def test_swap_claims_are_exclusive_and_remote_defaults_are_unchanged(stopped):
    stopped.service.enroll(kit_data('kit-two', subnet='192.168.10.0/24', key_number=2), stopped.admin)
    result = stopped.service.update_lab_settings(stopped.target.id, edit({'remote_peer_id': 'kit-two'}), stopped.instructor)
    assert result['remote_peer_id'] == 'kit-two'
    assert stopped.db.collections['wireguard-kit']['kit-one']['assigned_unit_id'] is None
    assert stopped.db.collections['wireguard-kit']['kit-two']['assigned_unit_id'] == stopped.target.id
    assert stopped.db.collections['wireguard-kit']['kit-two']['equipment_subnet'] == '192.168.10.0/24'
    assert stopped.service.get_lease(stopped.target.id).endpoint_id == '10000'


@pytest.mark.parametrize('bad_lan', ['10.20.0.0/24', '10.254.254.0/30'])
def test_existing_student_or_tunnel_overlap_is_rejected_before_secret_staging(stopped, bad_lan):
    with pytest.raises(BadRequest, match='overlaps'):
        stopped.service.update_lab_settings(stopped.target.id, edit({'remote_network_cidr': bad_lan}), stopped.instructor)
    assert stopped.secrets.versions == {}


@pytest.mark.parametrize('change', ['gateway', 'student', 'expiry'])
def test_lifecycle_in_use_blocks_edits_without_staging_secrets(stopped, change):
    if change == 'gateway':
        stopped.db.collections[DbCollections.SERVER.value][f'{stopped.target.id}-wireguard']['state'] = ServerStates.RUNNING.value
    elif change == 'student':
        stopped.db.collections[DbCollections.WORKOUT.value]['klmnopqrst']['state'] = WorkoutStates.STARTING.value
    else:
        stopped.db.collections['unit'][stopped.target.id]['workspace_settings']['expires'] = 999
    assert not stopped.service.lab_settings(stopped.target.id, stopped.instructor)['can_edit']
    with pytest.raises(Conflict):
        stopped.service.update_lab_settings(stopped.target.id, edit(), stopped.instructor)
    assert stopped.secrets.versions == {}


def test_ownership_and_selected_peer_authorization_are_checked(stopped):
    outsider = SimpleNamespace(is_admin=False, email='outsider@example.edu')
    with pytest.raises(Unauthorized):
        stopped.service.lab_settings(stopped.target.id, outsider)
    with pytest.raises(Unauthorized):
        stopped.service.update_lab_settings(stopped.target.id, edit(), outsider)
    stopped.service.enroll({**kit_data('kit-two', key_number=2), 'authorized_instructors': ['other@example.edu']}, stopped.admin)
    with pytest.raises(Unauthorized):
        stopped.service.update_lab_settings(stopped.target.id, edit({'remote_peer_id': 'kit-two'}), stopped.instructor)
    assert not stopped.secrets.versions


def test_student_start_between_preflight_and_commit_preserves_old_configuration(stopped):
    original = stopped.db.transaction
    old_lease = stopped.service.get_lease(stopped.target.id)
    def raced(callback):
        stopped.db.collections[DbCollections.WORKOUT.value]['klmnopqrst']['state'] = WorkoutStates.STARTING.value
        return original(callback)
    stopped.db.transaction = raced
    with pytest.raises(Conflict, match='Stop every student'):
        stopped.service.update_lab_settings(stopped.target.id, edit(), stopped.instructor)
    assert stopped.service.get_lease(stopped.target.id).secret_version_name == old_lease.secret_version_name
    assert stopped.secrets.payloads[stopped.target.id]['equipment_subnet'] == '172.30.0.0/24'
    assert stopped.db.collections['unit'][stopped.target.id]['routes'][0]['dest_range'] == '172.30.0.0/24'
    assert stopped.secrets.versions == {}


def test_initial_build_accepts_validated_per_lab_lan_without_changing_registration(context):
    target = unit(context)
    lease = context.service.reserve(target, 'kit-one', context.instructor, remote_network_cidr='192.168.50.0/24')
    assert lease.equipment_subnet == '192.168.50.0/24'
    assert context.secrets.payloads[target.id]['equipment_subnet'] == '192.168.50.0/24'
    assert context.db.collections['wireguard-kit']['kit-one']['equipment_subnet'] == '172.30.0.0/24'


def test_ambiguous_failure_after_commit_never_deletes_selected_configuration(stopped):
    original = stopped.db.transaction
    def committed_then_transport_failed(callback):
        original(callback)
        raise TimeoutError('database response was lost')
    stopped.db.transaction = committed_then_transport_failed
    with pytest.raises(TimeoutError):
        stopped.service.update_lab_settings(stopped.target.id, edit(), stopped.instructor)
    selected = stopped.service.get_lease(stopped.target.id).secret_version_name
    assert selected in stopped.secrets.versions
    assert stopped.secrets.deleted == []


def test_repeated_pending_edits_keep_original_vm_reference_and_cleanup_all_committed_secrets(stopped):
    stopped.service.update_lab_settings(stopped.target.id, edit(), stopped.instructor)
    first = stopped.service.get_lease(stopped.target.id)
    stopped.service.update_lab_settings(stopped.target.id, edit({'remote_network_cidr': '192.168.60.0/24'}), stopped.instructor)
    final = stopped.service.get_lease(stopped.target.id)
    assert final.previous_secret_version_name == first.previous_secret_version_name
    assert first.secret_version_name in final.secret_history
    stopped.service.release(stopped.target.id)
    assert set(stopped.secrets.deleted) == {final.secret_version_name, *final.secret_history}
