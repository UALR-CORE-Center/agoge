"""Delete partial debug labs through the normal resource lifecycle, without GCP."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from cloud_fn_utilities.course_objects.compute import lab_server_manager as server_module
from cloud_fn_utilities.course_objects.unit.community_unit import CommunityUnit
from common.constants.database import DbCollections
from common.constants.pub_sub import PubSub
from common.constants.states import ServerStates, UnitStates
from common.exceptions import NotFound
from common.models.agoge import UnitModel
from common.models.wireguard import WireGuardEndpointModel
from common.services.wireguard_endpoint import WireGuardEndpointRegistry
from common.services.wireguard_lab_spec import configure_kit_topology, default_wireguard_spec
from common.services.wireguard_provisioning import WireGuardProvisioningService
from common.tests.test_wireguard_endpoint_registry import _FakeDatabase


@pytest.mark.parametrize('debug_mode', [False, True])
def test_delete_is_routed_even_when_budget_would_block_new_work(monkeypatch, debug_mode):
    from cloud_functions import main as module

    budget, control = Mock(), Mock()
    budget.return_value.check_budget.return_value = False
    monkeypatch.setattr(module, 'BudgetManager', budget)
    monkeypatch.setattr(module, 'ControlHandler', control)
    env = {'project': 'test-dev-787001'}
    attributes = {'handler': 'CONTROL', 'action': str(PubSub.Actions.DELETE.value),
                  'course_object': str(PubSub.CourseObjects.UNIT.value), 'build_id': 'abcdefghij'}

    module.agoge_cloud_function({'attributes': attributes},
                               SimpleNamespace(event_id='cleanup', timestamp='now'),
                               debug_mode=debug_mode, env_dict=env)

    budget.assert_not_called()
    control.assert_called_once_with(attributes, debug=debug_mode, env_dict=env)
    control.return_value.route.assert_called_once()


@pytest.mark.parametrize('debug_mode', [False, True])
@pytest.mark.parametrize('handler,action', [
    ('CONTROL', str(PubSub.Actions.START.value)),
    ('CONTROL', str(PubSub.Actions.STOP.value)),
    ('CONTROL', '03'), ('CONTROL', PubSub.Actions.DELETE.value),
    ('BUILD', str(PubSub.Actions.DELETE.value)),
    ('MAINTENANCE', str(PubSub.Actions.DELETE.value)),
])
def test_budget_exception_does_not_extend_to_other_actions_or_malformed_deletes(
        monkeypatch, debug_mode, handler, action):
    from cloud_functions import main as module

    budget, control = Mock(), Mock()
    budget.return_value.check_budget.return_value = False
    monkeypatch.setattr(module, 'BudgetManager', budget)
    monkeypatch.setattr(module, 'ControlHandler', control)
    event = {'attributes': {'handler': handler, 'action': action, 'build_id': 'abcdefghij'}}
    context = SimpleNamespace(event_id='blocked', timestamp='now')
    if debug_mode:
        with pytest.raises(RuntimeError, match='Budget exceeded'):
            module.agoge_cloud_function(event, context, debug_mode=True)
    else:
        module.agoge_cloud_function(event, context)
    budget.return_value.check_budget.assert_called_once()
    control.assert_not_called()


class CleanupDatabase(_FakeDatabase):
    def update(self, collection_name, doc_id, data):
        self.collections.setdefault(collection_name.value, {}).setdefault(doc_id, {}).update(data)


@pytest.fixture
def cleanup(monkeypatch):
    unit_id = 'abcdefghij'
    env = {'project': 'test-dev-787001', 'region': 'us-central1', 'zone': 'us-central1-a',
           'parent_dns_suffix': '.example.edu'}
    db = CleanupDatabase()
    unit = UnitModel(id=unit_id, instructor_id=['teacher@example.edu'],
                     **default_wireguard_spec('projects/shared/global/images/student', []))
    configure_kit_topology(unit, '192.168.50.0/24', 51820)
    unit.servers[0].wireguard_managed = True
    unit.wireguard_endpoint = WireGuardEndpointModel(
        id='10000', server_name=f'{unit_id}-wireguard',
        hostname='wg10000.example.edu', external_ip_name='legacy-address')
    db.collections[DbCollections.SERVER.value] = {}
    db.collections[DbCollections.WIREGUARD_KIT.value] = {
        'remote-lab-01': {'assigned_unit_id': unit_id}}
    db.collections[DbCollections.WIREGUARD_LEASE.value] = {unit_id: {
        'kit_id': 'remote-lab-01', 'status': 'reserved',
        'secret_version_name': f'projects/test-dev-787001/secrets/agoge-wg-{unit_id}/versions/latest'}}
    db.records['10000'] = {**unit.wireguard_endpoint.model_dump(), 'unit_id': unit_id,
                           'created_timestamp': 1, 'updated_timestamp': 1, 'public_ip': '203.0.113.10'}
    secrets = Mock()
    provisioning = WireGuardProvisioningService(env, db=db, secret_store=secrets)
    registry = WireGuardEndpointRegistry(env, db=db, timestamp_factory=lambda: 100)

    server = object.__new__(server_module.LabServerManager)
    server.class_name, server.logger = 'LabServerManager', Mock()
    server.env = SimpleNamespace(**env)
    server.env_dict, server.db, server.s = env, db, ServerStates
    server.primary_external_ip = None
    server.wireguard_registry = registry
    server._wireguard_provisioning = Mock(return_value=provisioning)
    server._delete_routes = Mock()
    server._dns_record = Mock(return_value=unit.wireguard_endpoint.hostname)
    server.dns_manager = SimpleNamespace(delete_dns=Mock(return_value=True))
    server.compute_instance = SimpleNamespace(delete=Mock(return_value=True))
    server._release_reserved_external_addresses = Mock()
    server.build = Mock(side_effect=AssertionError('cleanup must not build a VM'))
    server.state_manager = SimpleNamespace(
        get_state=lambda: db.collections[DbCollections.SERVER.value][server.server_name]['state'],
        state_transition=lambda state: db.update(DbCollections.SERVER, server.server_name, {'state': state.value}),
    )

    def load(*, server_name, server_spec=None):
        server.server_name = server_name
        record = server_spec or db.get(DbCollections.SERVER, server_name)
        if not record:
            raise LookupError('missing server metadata')
        server.server_spec = SimpleNamespace(**record)
        server.parent_build_id = record['parent_id']

    server.load = Mock(side_effect=load)
    identity = Mock()
    monkeypatch.setattr(server_module, 'WireGuardGatewayIdentity', identity)

    community = object.__new__(CommunityUnit)
    community.unit_id, community.unit_model = unit_id, unit
    community.env_dict, community.db = env, db
    community.class_name, community.logger, community.s = 'CommunityUnit', Mock(), UnitStates
    state = SimpleNamespace(value=UnitStates.START.value)
    community.state_manager = SimpleNamespace(
        get_state=lambda: state.value,
        state_transition=lambda value: setattr(state, 'value', value.value),
        are_workouts_deleted=lambda: True, server_states=ServerStates,
        MAX_WAIT_TIME=1, SLEEP_TIME=0.01,
    )
    community.db_queries = SimpleNamespace(get_children=Mock(return_value=[]))
    community.debug, community.promiscuous_mode = True, False
    community.packet_mirroring = SimpleNamespace(delete=Mock())
    community.firewall_manager = SimpleNamespace(delete=Mock(return_value=True))
    community.vpc_manager = SimpleNamespace(delete=Mock(return_value=True))
    community.compute_manager, community.pubsub_manager = server, Mock()
    return SimpleNamespace(unit=community, model=unit, state=state, db=db,
                           server=server, secrets=secrets, identity=identity,
                           lease=db.collections[DbCollections.WIREGUARD_LEASE.value][unit_id],
                           peer=db.collections[DbCollections.WIREGUARD_KIT.value]['remote-lab-01'])


@pytest.mark.parametrize('unit_state,server_state', [
    (UnitStates.START, None), (UnitStates.BROKEN, None),
    (UnitStates.DELETED, None), (UnitStates.DELETED, ServerStates.DELETED),
])
def test_partial_gateway_cleanup_uses_normal_delete_before_releasing_peer(cleanup, unit_state, server_state):
    cleanup.state.value = unit_state.value
    if server_state:
        cleanup.db.collections[DbCollections.SERVER.value]['abcdefghij-wireguard'] = {'state': server_state.value}

    cleanup.unit.delete()

    cleanup.server.compute_instance.delete.assert_called_once_with(resource_name='abcdefghij-wireguard', wait=True)
    cleanup.server.build.assert_not_called()
    assert cleanup.lease['status'] == 'released' and cleanup.peer['assigned_unit_id'] is None
    cleanup.secrets.delete.assert_called_once_with(cleanup.lease['secret_version_name'])
    cleanup.identity.return_value.delete.assert_called_once_with('abcdefghij')
    assert cleanup.db.records['10000']['status'] == 'released'
    assert cleanup.state.value == UnitStates.DELETED.value
    record = cleanup.server.load.call_args.kwargs['server_spec']
    assert record['parent_id'] == 'abcdefghij' and record['parent_build_type'] == 'unit'
    assert record['wireguard_managed'] and record['wireguard_endpoint_id'] == '10000'
    assert record['hostname'] == 'wg10000.example.edu.'
    assert record['nics'][0]['external_ip_name'] == 'legacy-address'
    assert record['routes'][0]['dest_range'] == '192.168.50.0/24'
    # Recovery does not mutate the saved template into runtime server metadata.
    assert cleanup.model.servers[0].parent_id is None


def test_never_created_vm_still_releases_its_prebuild_reservation(cleanup):
    cleanup.server.compute_instance.delete.side_effect = NotFound('VM was never created')
    cleanup.unit.delete()
    assert cleanup.lease['status'] == 'released' and cleanup.peer['assigned_unit_id'] is None
    assert cleanup.state.value == UnitStates.DELETED.value


def test_failed_resource_delete_preserves_lease_and_prevents_network_teardown(cleanup):
    cleanup.server.compute_instance.delete.return_value = False
    with pytest.raises(ConnectionError, match='Server deletion was not confirmed'):
        cleanup.unit.delete()
    assert cleanup.lease['status'] == 'reserved' and cleanup.peer['assigned_unit_id'] == 'abcdefghij'
    cleanup.secrets.delete.assert_not_called()
    cleanup.identity.return_value.delete.assert_not_called()
    cleanup.unit.vpc_manager.delete.assert_not_called()
    assert cleanup.state.value == UnitStates.BROKEN.value


def test_completed_delete_stays_idempotent(cleanup):
    cleanup.state.value = UnitStates.DELETED.value
    cleanup.lease['status'] = 'released'
    cleanup.peer['assigned_unit_id'] = None
    cleanup.unit.delete()
    cleanup.server.load.assert_not_called()
    cleanup.server.compute_instance.delete.assert_not_called()


@pytest.mark.parametrize('missing', ['endpoint', 'interface'])
def test_recovery_refuses_incomplete_authoritative_gateway_spec(cleanup, missing):
    if missing == 'endpoint':
        cleanup.model.wireguard_endpoint = None
    else:
        cleanup.model.servers[0].nics = []
    with pytest.raises(ValueError, match='Cannot recover gateway cleanup'):
        cleanup.unit.delete()
    cleanup.server.compute_instance.delete.assert_not_called()
    cleanup.secrets.delete.assert_not_called()
    assert cleanup.lease['status'] == 'reserved'
