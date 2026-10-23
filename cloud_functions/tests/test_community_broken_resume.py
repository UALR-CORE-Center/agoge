"""A BROKEN local lab must re-enter provisioning instead of reporting a no-op."""
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock

from google.cloud.compute_v1 import AttachedDisk
import pytest

from cloud_fn_utilities.course_objects.compute import lab_server_manager as server_module
from cloud_fn_utilities.course_objects.unit import community_unit as module
from common.constants.database import DbCollections
from common.constants.states import ServerStates, UnitStates, WorkoutStates
from common.exceptions import BadRequest, NotFound
from common.models.agoge import UnitModel
from common.models.wireguard import WireGuardEndpointModel
from common.services.wireguard_lab_spec import configure_kit_topology, default_wireguard_spec


class Database:
    def __init__(self):
        self.records = {collection.value: {} for collection in DbCollections}
        self.db = self
        self.before_transaction = None
        self.writes = []

    def get(self, collection_name, doc_id):
        return deepcopy(self.records[collection_name.value].get(doc_id, {}))

    def update(self, collection_name, doc_id, data):
        self.records[collection_name.value].setdefault(doc_id, {}).update(deepcopy(data))
        self.writes.append((collection_name.value, doc_id, deepcopy(data)))

    def collection(self, name):
        def document(identifier):
            def get(transaction=None):
                record = self.records[name].get(identifier)
                return SimpleNamespace(exists=record is not None, to_dict=lambda: deepcopy(record))
            return SimpleNamespace(id=identifier, collection=name, get=get)
        return SimpleNamespace(document=document)

    def transaction(self, operation):
        if self.before_transaction:
            self.before_transaction()
        return operation(self)

    def set(self, reference, data, merge=False):
        assert merge
        self.update(DbCollections(reference.collection), reference.id, data)


class State:
    def __init__(self, db, collection, identifier):
        self.db, self.collection, self.identifier = db, collection, identifier
        self.transitions = []

    def get_state(self):
        return self.db.records[self.collection.value][self.identifier]['state']

    def state_transition(self, state):
        self.transitions.append(state)
        self.db.update(self.collection, self.identifier, {'state': state.value})

    def set_build_record(self, identifier):
        assert identifier == self.identifier


@pytest.fixture
def lab(monkeypatch):
    unit_id, server_name = 'abcdefghij', 'abcdefghij-wireguard'
    monkeypatch.setattr(module.time, 'time', lambda: 1000)
    db = Database()
    model = UnitModel(id=unit_id, instructor_id=['teacher@example.edu'],
                      workspace_settings={'count': 1, 'expires': 2000},
                      **default_wireguard_spec('projects/shared/global/images/student', []))
    configure_kit_topology(model, '192.168.50.0/24', 51820)
    model.servers[0].wireguard_managed = True
    model.wireguard_endpoint = WireGuardEndpointModel(
        id='10000', server_name=server_name, hostname='wg10000.example.edu', port=51820)
    db.records[DbCollections.UNIT.value][unit_id] = {**model.model_dump(), 'state': UnitStates.BROKEN.value}
    lease = {'unit_id': unit_id, 'status': 'reserved', 'endpoint_id': '10000', 'expires': 2000,
             'secret_version_name': f'projects/tenant-project/secrets/agoge-wg-{unit_id}/versions/latest',
             'boot_id': None, 'health_timestamp': 1000, 'service_ready': True, 'tunnel_ready': False}
    db.records[DbCollections.WIREGUARD_LEASE.value][unit_id] = lease
    db.records[DbCollections.WIREGUARD_ENDPOINT.value]['10000'] = {
        **model.wireguard_endpoint.model_dump(), 'unit_id': unit_id, 'status': 'error'}
    db.records[DbCollections.SERVER.value][server_name] = {
        'name': 'wireguard', 'parent_id': unit_id, 'state': ServerStates.BROKEN.value}
    events = []
    gateway = object.__new__(server_module.LabServerManager)
    gateway.logger, gateway.class_name = Mock(), 'LabServerManager'
    gateway.s, gateway.db = ServerStates, db
    gateway.server_spec = SimpleNamespace()
    gateway.server_name, gateway.parent_build_id = server_name, unit_id
    gateway.env = SimpleNamespace(project='tenant-project', region='us-central1', zone='us-central1-a')
    gateway.env_dict, gateway.ip_aliases = {'project': 'tenant-project'}, False
    gateway.primary_external_ip = None
    gateway.compute_instance = Mock()
    gateway.compute_instance.get.side_effect = NotFound('not created')

    def insert(**kwargs):
        events.append('compute.insert')
        return True
    gateway.compute_instance.create.side_effect = insert
    gateway.state_manager = State(db, DbCollections.SERVER, server_name)
    gateway._require_wireguard_provisionable = Mock()
    service = Mock()
    current_lease = SimpleNamespace(**lease)
    current_lease.is_ready = lambda timestamp: True
    service.get_lease.return_value = current_lease
    service.grant_gateway_access.side_effect = lambda *args: events.append('secret.grant')
    service.prepare_boot.return_value = 'a' * 32
    gateway._wireguard_provisioning = lambda: service
    identity = Mock()
    identity.return_value.ensure.return_value = f'agoge-wg-{unit_id}@tenant-project.iam.gserviceaccount.com'
    monkeypatch.setattr(server_module, 'WireGuardGatewayIdentity', identity)

    def load(*, server_name):
        gateway._load_lab_server(server_name, db.get(DbCollections.SERVER, server_name))
    gateway.load = Mock(side_effect=load)
    gateway._get_boot_disk = lambda **kwargs: AttachedDisk(
        boot=True, auto_delete=True, initialize_params={'source_image': kwargs['image_source'],
                                                       'disk_size_gb': kwargs['disk_size_gb']})
    gateway._lookup_machine_type = lambda machine_type: machine_type
    for method in ('_refresh_wireguard_external_ip', '_stage_wireguard_endpoint',
                   '_ensure_dns_record', '_build_routes', '_mark_wireguard_endpoint_error'):
        setattr(gateway, method, Mock())

    unit = object.__new__(module.CommunityUnit)
    unit.unit_id, unit.unit_model, unit.db = unit_id, model, db
    unit.env_dict, unit.env = gateway.env_dict, SimpleNamespace(parent_dns_suffix='.example.edu')
    unit.class_name, unit.logger, unit.s = 'CommunityUnit', Mock(), UnitStates
    unit.log_name = 'cloud_functions'
    unit.debug, unit.lms_integration, unit.workout_id = True, False, None
    unit.state_manager = State(db, DbCollections.UNIT, unit_id)
    unit.state_manager.are_server_builds_finished = lambda: gateway.state_manager.get_state() == ServerStates.RUNNING.value
    unit.db_queries = SimpleNamespace(
        get_children=lambda **kwargs: list(db.records[DbCollections.WORKOUT.value].values()),
        get_servers=lambda **kwargs: list(db.records[DbCollections.SERVER.value].values()))
    unit.vpc_manager = SimpleNamespace(
        _network_name=lambda parent, network: f'{parent}-{network.name}',
        _subnet_name=lambda name, subnet: f'{name}-{subnet.name}',
        networks_client=Mock(), subnetworks_client=Mock(), build=Mock())
    unit.compute_manager = gateway
    unit.validator = lambda model, **kwargs: SimpleNamespace(load=lambda data: model(**data))
    unit.firewall_manager, unit.packet_mirroring = Mock(), Mock()
    unit.promiscuous_mode = False
    unit._activate_wireguard_endpoint = Mock(side_effect=lambda: events.append('endpoint.activate'))
    return SimpleNamespace(unit=unit, gateway=gateway, service=service, db=db, events=events,
                           unit_id=unit_id, server_name=server_name, lease=lease)


def test_real_broken_unit_build_reaches_bootstrap_and_compute_insert_without_recreating_network(lab):
    lab.unit.build()

    assert lab.events == ['secret.grant', 'compute.insert', 'endpoint.activate']
    request = lab.gateway.compute_instance.create.call_args.kwargs
    assert request['resource_name'] == 'abcdefghij-wireguard' and request['wait'] is True
    instance = request['instance_resource']
    assert instance.name == 'abcdefghij-wireguard'
    assert instance.can_ip_forward
    assert instance.disks[0].initialize_params.source_image == server_module.UBUNTU_IMAGE
    assert instance.service_accounts[0].email == 'agoge-wg-abcdefghij@tenant-project.iam.gserviceaccount.com'
    assert 'startup-script' in {item.key for item in instance.metadata.items}
    lab.unit.vpc_manager.build.assert_not_called()
    lab.unit.vpc_manager.networks_client.get.assert_called_once_with(resource='abcdefghij-external')
    lab.unit.vpc_manager.subnetworks_client.get.assert_called_once_with(resource='abcdefghij-external-default')
    assert lab.unit.state_manager.get_state() == UnitStates.READY.value
    assert lab.gateway.state_manager.get_state() == ServerStates.RUNNING.value
    assert lab.lease['expires'] == 2000 and lab.lease['status'] == 'reserved'


def test_resumed_bootstrap_failure_propagates_instead_of_reporting_success(lab):
    lab.service.grant_gateway_access.side_effect = RuntimeError('bootstrap did not complete')
    with pytest.raises(RuntimeError, match='bootstrap did not complete'):
        lab.unit.build()
    lab.gateway.compute_instance.create.assert_not_called()
    lab.unit._activate_wireguard_endpoint.assert_not_called()
    assert lab.unit.state_manager.get_state() == UnitStates.BUILDING_SERVERS.value


def test_deployed_broken_build_is_not_resurrected_by_a_stale_delivery(lab):
    lab.unit.debug = False
    with pytest.raises(BadRequest, match='explicit local debug'):
        lab.unit.build()
    lab.gateway.compute_instance.create.assert_not_called()
    assert lab.unit.state_manager.get_state() == UnitStates.BROKEN.value


@pytest.mark.parametrize('state', [UnitStates.RUNNING, UnitStates.READY, UnitStates.STOPPING,
                                  UnitStates.STARTING, UnitStates.EXPIRED, UnitStates.MISFIT,
                                  UnitStates.DELETING_SERVERS, UnitStates.DELETED])
def test_runtime_or_retired_unit_is_not_rebuilt(lab, state):
    lab.db.records[DbCollections.UNIT.value][lab.unit_id]['state'] = state.value
    lab.unit.build()
    lab.gateway.compute_instance.create.assert_not_called()
    lab.unit.vpc_manager.build.assert_not_called()
    assert lab.unit.state_manager.get_state() == state.value


@pytest.mark.parametrize('state', [ServerStates.STOPPING, ServerStates.STOPPED, ServerStates.EXPIRED,
                                  ServerStates.MISFIT, ServerStates.DELETING, ServerStates.DELETED])
def test_stopped_or_retired_gateway_is_not_resurrected(lab, state):
    lab.db.records[DbCollections.SERVER.value][lab.server_name]['state'] = state.value
    with pytest.raises(BadRequest, match='stopped or retired'):
        lab.unit.build()
    lab.gateway.compute_instance.create.assert_not_called()
    assert lab.unit.state_manager.get_state() == UnitStates.BROKEN.value


@pytest.mark.parametrize('collection', [DbCollections.UNIT, DbCollections.WIREGUARD_LEASE])
@pytest.mark.parametrize('expires', [None, 0, 999, 1000, True, float('nan'), float('inf')])
def test_expired_or_invalid_expiration_is_never_extended(lab, collection, expires):
    record = lab.db.records[collection.value][lab.unit_id]
    target = record['workspace_settings'] if collection == DbCollections.UNIT else record
    target['expires'] = expires
    with pytest.raises(BadRequest, match='expired'):
        lab.unit.build()
    lab.gateway.compute_instance.create.assert_not_called()
    assert target['expires'] is expires


@pytest.mark.parametrize('state', [UnitStates.DELETING_SERVERS, UnitStates.DELETED])
def test_concurrent_teardown_cannot_be_overwritten_by_recovery(lab, state):
    lab.db.before_transaction = lambda: lab.db.records[DbCollections.UNIT.value][lab.unit_id].update(state=state.value)
    with pytest.raises(BadRequest, match='state changed'):
        lab.unit.build()
    assert lab.unit.state_manager.get_state() == state.value
    lab.gateway.compute_instance.create.assert_not_called()


@pytest.mark.parametrize('field,value', [('status', 'released'), ('expires', 999), ('endpoint_id', '10001')])
def test_concurrent_reservation_change_blocks_recovery(lab, field, value):
    lab.db.before_transaction = lambda: lab.lease.update({field: value})
    with pytest.raises(BadRequest):
        lab.unit.build()
    lab.gateway.compute_instance.create.assert_not_called()
    assert lab.unit.state_manager.get_state() == UnitStates.BROKEN.value


def test_missing_network_blocks_ambiguous_legacy_recovery_without_inserting(lab):
    lab.unit.vpc_manager.networks_client.get.side_effect = NotFound('absent')
    with pytest.raises(BadRequest, match='network is missing'):
        lab.unit.build()
    lab.unit.vpc_manager.build.assert_not_called()
    lab.gateway.compute_instance.create.assert_not_called()


@pytest.mark.parametrize('state', [WorkoutStates.RUNNING, WorkoutStates.READY, WorkoutStates.BROKEN, WorkoutStates.DELETED])
def test_existing_workout_lifecycle_blocks_initial_build_recovery(lab, state):
    lab.db.records[DbCollections.WORKOUT.value]['klmnopqrst'] = {'id': 'klmnopqrst', 'state': state.value}
    with pytest.raises(BadRequest, match='student workout lifecycle'):
        lab.unit.build()
    lab.gateway.compute_instance.create.assert_not_called()

