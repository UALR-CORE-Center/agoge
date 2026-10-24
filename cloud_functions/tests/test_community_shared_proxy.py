"""Real community orchestration with two students and hermetic cloud boundaries."""
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from cloud_fn_utilities.course_objects.unit.community_unit import CommunityUnit
from cloud_fn_utilities.course_objects.workout.community_workout import CommunityWorkout
from cloud_fn_utilities.course_objects.compute.lab_server_manager import LabServerManager
from common.constants.database import DbCollections
from common.document_database import DocumentDatabaseFactory
from common.constants.states import ServerStates, UnitStates, WorkoutStates
from common.models.agoge import UnitModel, WorkoutModel
from common.models.wireguard import WireGuardEndpointModel
from common.services.community_proxy_spec import ensure_community_proxy
from common.services.wireguard_lab_spec import default_wireguard_spec, configure_kit_topology


class Database:
    def __init__(self):
        self.records = {collection.value: {} for collection in DbCollections}
        self.db = self

    def get(self, collection_name, doc_id):
        return deepcopy(self.records[collection_name.value].get(doc_id, {}))

    def update(self, collection_name, doc_id, data):
        self.records[collection_name.value].setdefault(doc_id, {}).update(deepcopy(data))

    def query(self, collection_name, filters=None):
        def matches(record):
            for field, operator, value in filters or []:
                actual = record.get(field)
                operation = operator.value if hasattr(operator, 'value') else operator
                if operation == '==' and actual != value:
                    return False
                if operation == '!=' and actual == value:
                    return False
                if operation == 'not-in' and actual in value:
                    return False
            return True
        return [deepcopy(record) for record in self.records[collection_name.value].values()
                if matches(record)]

    def collection(self, name):
        def snapshot(data):
            return SimpleNamespace(exists=data is not None, to_dict=lambda: deepcopy(data))
        def document(identifier):
            return SimpleNamespace(id=identifier, collection=name,
                get=lambda transaction=None: snapshot(self.records[name].get(identifier)))
        def where(*, filter):
            return SimpleNamespace(get=lambda transaction=None: [snapshot(record)
                for record in self.records[name].values() if record.get(filter.field_path) == filter.value])
        return SimpleNamespace(document=document, where=where)

    def transaction(self, operation_func, **kwargs):
        return operation_func(self, **kwargs)

    def set(self, reference, data, merge=False):
        assert merge
        self.update(DbCollections(reference.collection), reference.id, data)


class Compute:
    """Compute SDK boundary; all selection, claims and persistence stay real."""
    def __init__(self, db):
        self.db, self.current = db, None
        self.operations, self.provider = [], {}
        self.delete_error = None

    def load(self, server_name, network_prefix=None, server_spec=None):
        self.current = server_name
        if server_spec:
            self.db.update(DbCollections.SERVER, server_name, server_spec)
        if not self.db.get(DbCollections.SERVER, server_name):
            raise LookupError(server_name)

    def _action(self, action, state, **kwargs):
        if action == 'delete' and self.delete_error:
            raise self.delete_error
        self.operations.append((action, self.current))
        record = self.db.records[DbCollections.SERVER.value][self.current]
        record['state'] = state.value
        if action == 'stop' and kwargs.get('community_stop_claim'):
            record['community_stop_claim']['completed'] = True
        self.provider[self.current] = 'TERMINATED' if state == ServerStates.STOPPED else 'RUNNING'
        if action == 'delete':
            self.provider.pop(self.current, None)
        return True

    def build(self): return self._action('build', ServerStates.RUNNING)
    def start(self, **kwargs): return self._action('start', ServerStates.RUNNING, **kwargs)
    def stop(self, **kwargs): return self._action('stop', ServerStates.STOPPED, **kwargs)
    def delete(self): return self._action('delete', ServerStates.DELETED)
    def _get_instance_status(self): return self.provider.get(self.current)


@pytest.fixture
def community_scenario(monkeypatch):
    unit_id = 'abcdefghij'
    db = Database()
    model = UnitModel(id=unit_id, instructor_id=['teacher@example.edu'],
        **default_wireguard_spec('projects/shared/global/images/student', [
            {'display': True, 'protocol': 'rdp', 'username': 'student', 'password': 'test-only'}]))
    configure_kit_topology(model, '192.168.50.0/24', 51820)
    model.servers[0].wireguard_managed = True
    model.wireguard_endpoint = WireGuardEndpointModel(id='10000', server_name=f'{unit_id}-wireguard',
        hostname='wg10000.example.edu', port=51820)
    db.update(DbCollections.UNIT, unit_id, {**model.model_dump(), 'state': UnitStates.BUILDING_NETWORKS.value})
    compute = Compute(db)
    import cloud_fn_utilities.course_objects.unit.base_unit as base_unit_module
    import cloud_fn_utilities.course_objects.unit.community_unit as unit_module
    import cloud_fn_utilities.course_objects.workout.base_workout as base_workout_module
    import cloud_fn_utilities.state_managers.base_state_manager as state_module
    env_dict = {'project': 'test'}
    env = SimpleNamespace(parent_dns_suffix='.example.edu', main_app_url='https://example.edu',
                          get_env=lambda: env_dict)
    monkeypatch.setattr(DocumentDatabaseFactory, 'create_db_object', lambda **_: db)
    for module in (base_unit_module, base_workout_module):
        monkeypatch.setattr(module, 'CloudEnv', lambda **_: env)
        monkeypatch.setattr(module, 'PubSubManager', lambda *_, **__: Mock())
    for module in (unit_module, base_workout_module):
        monkeypatch.setattr(module, 'VpcManager', lambda **_: Mock())
        monkeypatch.setattr(module, 'FirewallManager', lambda **_: Mock())
    monkeypatch.setattr(unit_module.ComputeManagerFactory, 'create_manager_object', lambda **_: compute)
    monkeypatch.setattr(unit_module.PacketMirrorFactory, 'create_packet_mirror_object', lambda **_: Mock())

    def unexpected_wait(_):
        raise AssertionError('Fake cloud operations complete immediately; lifecycle unexpectedly waited')
    monkeypatch.setattr(state_module.time, 'sleep', unexpected_wait)
    cleanup = Mock(side_effect=lambda *args, **kwargs: (
        None if f'{unit_id}-display-guacamole-server' not in compute.provider
        else pytest.fail('Signing material removed while shared proxy still exists')))
    bootstrap = Mock(return_value={'guacamole_secret_version_name': 'projects/test/secrets/proxy/versions/1',
        'metadata': {'items': [{'key': 'startup-script', 'value': 'repository bootstrap'}]},
        'service_accounts': [{'email': 'proxy@test.iam.gserviceaccount.com', 'scopes': ['https://www.googleapis.com/auth/cloud-platform']}]})
    import cloud_fn_utilities.server_specific.guacamole.community_proxy_bootstrap as bootstrap_module
    monkeypatch.setattr(bootstrap_module, 'prepare_community_proxy', bootstrap)
    monkeypatch.setattr(bootstrap_module, 'delete_community_proxy', cleanup)
    unit = CommunityUnit(unit_model=model, debug=True, env_dict=env_dict)
    unit._activate_wireguard_endpoint = Mock()
    workouts = {}
    def student(identifier):
        record = WorkoutModel(id=identifier, parent_id=unit_id, build_type='workout', parent_build_type='unit',
            state=WorkoutStates.BUILDING_SERVERS.value)
        db.update(DbCollections.WORKOUT, identifier, record.model_dump())
        workout = CommunityWorkout(workout_id=identifier, workout_model=record,
            unit_model=model, debug=True, env_dict=env_dict)
        workouts[identifier] = workout
        return workout
    monkeypatch.setattr(unit_module.WorkoutFactory, 'create_workout_object',
                        lambda workout_id, **kwargs: workouts[workout_id])
    return SimpleNamespace(unit=unit, student=student, db=db, compute=compute, bootstrap=bootstrap,
                           cleanup=cleanup, proxy=f'{unit_id}-display-guacamole-server', gateway=f'{unit_id}-wireguard')


def test_two_students_share_one_proxy_through_complete_community_lifecycle(community_scenario):
    scene = community_scenario
    scene.unit.build()
    shared = {scene.proxy, scene.gateway}
    assert all(scene.compute.provider[name] == 'TERMINATED' for name in shared)
    students = [scene.student(identifier) for identifier in ('klmnopqrst', 'uvwxyzabcd')]
    for workout in students:
        workout.build()
        assert workout.state_manager.get_state() == WorkoutStates.READY.value
        assert scene.compute.provider[f'{workout.workout_id}-kali'] == 'TERMINATED'
        assert workout.workout.proxy_connections[0].auth_type == 'json'
        assert workout.workout.proxy_connections[0].password is None
    assert [name for action, name in scene.compute.operations if action == 'build' and 'guacamole' in name] == [scene.proxy]
    assert len({workout.workout.proxy_connections[0].username for workout in students}) == 2
    addresses = {workout.workout.servers[0].nics[0].internal_ip for workout in students}
    assert len(addresses) == 2
    assert all(address.startswith('10.20.0.') for address in addresses)
    assert not addresses.intersection({'10.20.0.10', '10.20.0.11'})
    for workout in students:
        workout.start()
        assert workout.state_manager.get_state() == WorkoutStates.RUNNING.value
        assert all(scene.compute.provider[name] == 'RUNNING' for name in shared)
    assert all(scene.compute.operations.count(('start', name)) == 1 for name in shared)
    students[0].stop()
    assert all(scene.compute.provider[name] == 'RUNNING' for name in shared)
    students[1].stop()
    assert all(scene.compute.provider[name] == 'TERMINATED' for name in shared)
    students[0].delete()
    assert all(name in scene.compute.provider for name in shared)
    scene.unit.start()
    assert all(scene.compute.provider[name] == 'RUNNING' for name in shared)
    scene.unit.stop()
    assert all(scene.compute.provider[name] == 'TERMINATED' for name in shared)
    scene.unit.delete()
    assert scene.unit.state_manager.get_state() == UnitStates.DELETED.value
    assert scene.compute.provider == {}
    scene.cleanup.assert_called_once()


@pytest.mark.parametrize('remove_record', [False, True])
def test_shared_proxy_deletion_recovers_missing_record_before_secret_cleanup(community_scenario, remove_record):
    scene = community_scenario
    scene.unit._build_unit()
    if remove_record:
        del scene.db.records[DbCollections.SERVER.value][scene.proxy]
    scene.compute.delete_error = ConnectionError('provider delete unavailable')
    with pytest.raises(ConnectionError):
        scene.unit.delete()
    scene.cleanup.assert_not_called()
    assert scene.proxy in scene.compute.provider
    scene.compute.delete_error = None
    scene.unit.delete()
    scene.cleanup.assert_called_once()


def test_shared_proxy_metadata_and_scoped_identity_survive_real_compute_loader(community_scenario):
    scene = community_scenario
    scene.unit._build_unit()
    manager = object.__new__(LabServerManager)
    manager.server_spec = SimpleNamespace()
    manager._load_lab_server(scene.proxy, scene.db.get(DbCollections.SERVER, scene.proxy))
    manager.assessment = Mock()
    original = deepcopy(manager.server_spec.metadata)
    manager._add_metadata()
    assert manager.server_spec.community_proxy is True
    assert manager.server_spec.metadata == original
    assert manager.server_spec.service_accounts[0]['email'] == 'proxy@test.iam.gserviceaccount.com'
    manager.assessment.get_startup_scripts.assert_not_called()
    manager.env = SimpleNamespace(zone='us-central1-a')
    manager.state_manager, manager.compute_instance, manager.logger = Mock(), Mock(), Mock()
    manager.s, manager.class_name, manager.ip_aliases = ServerStates, 'LabServerManager', False
    manager._add_disks = lambda: setattr(manager.server_spec, 'disks', [])
    manager._add_nics = lambda: setattr(manager.server_spec, 'network_interfaces', [])
    manager._lookup_machine_type = lambda value: value
    manager._dns_record = lambda: None
    manager._build_server()
    instance = manager.compute_instance.create.call_args.kwargs['instance_resource']
    assert instance.service_accounts[0].email == 'proxy@test.iam.gserviceaccount.com'
    assert list(instance.service_accounts[0].scopes) == ['https://www.googleapis.com/auth/cloud-platform']
    manager.assessment.get_startup_scripts.assert_not_called()


def test_ordinary_community_uses_shared_proxy_and_same_vpc_subnets_need_one_nic(community_scenario):
    model = community_scenario.unit.unit_model
    model.servers = [server for server in model.servers if not server.community_server]
    model.networks[0].subnets.append(type(model.networks[0].subnets[0])(name='second', ip_subnet='10.20.1.0/24'))
    second = model.servers[0].model_copy(deep=True)
    second.name = 'second'
    second.nics[0].subnet_name = 'second'
    model.servers.append(second)
    proxy = ensure_community_proxy(model, '.example.edu', 'test')
    assert len(proxy.nics) == 1
    assert proxy.community_server and proxy.community_proxy
    model.unit_type = 'solo'
    assert ensure_community_proxy(model, '.example.edu', 'test') is None


def test_proxy_ownership_is_persisted_before_cloud_bootstrap_and_failed_save_is_recoverable(community_scenario):
    scene = community_scenario
    original_update = scene.db.update
    prepared = []
    def prepare(*args, **kwargs):
        persisted = scene.db.get(DbCollections.UNIT, scene.unit.unit_id)
        assert persisted['community_proxy_cleanup_pending'] is True
        assert any(server.get('community_proxy') for server in persisted['servers'])
        prepared.append(True)
        return scene.bootstrap.return_value
    scene.bootstrap.side_effect = prepare
    def update(collection_name, doc_id, data):
        if prepared and collection_name == DbCollections.UNIT and 'servers' in data:
            raise ConnectionError('post-bootstrap database write failed')
        original_update(collection_name, doc_id, data)
    scene.db.update = update
    with pytest.raises(ConnectionError, match='post-bootstrap'):
        scene.unit._build_unit()
    persisted = scene.db.get(DbCollections.UNIT, scene.unit.unit_id)
    assert persisted['community_proxy_cleanup_pending']
    scene.db.update = original_update
    scene.unit.delete()
    scene.cleanup.assert_called_once()
    assert not scene.db.get(DbCollections.UNIT, scene.unit.unit_id)['community_proxy_cleanup_pending']


def test_failed_proxy_ownership_write_creates_no_secret_or_identity(community_scenario):
    scene = community_scenario
    scene.db.update = Mock(side_effect=ConnectionError('ownership write failed'))
    with pytest.raises(ConnectionError, match='ownership write'):
        scene.unit._prepare_shared_display_proxy()
    scene.bootstrap.assert_not_called()


def test_proxy_key_cleanup_failure_keeps_pending_marker_for_retry(community_scenario):
    scene = community_scenario
    scene.unit._build_unit()
    scene.cleanup.side_effect = ConnectionError('secret cleanup failed')
    with pytest.raises(ConnectionError, match='secret cleanup'):
        scene.unit.delete()
    assert scene.db.get(DbCollections.UNIT, scene.unit.unit_id)['community_proxy_cleanup_pending']
    assert scene.unit.state_manager.get_state() != UnitStates.DELETED.value
    scene.cleanup.side_effect = None
    scene.unit.delete()
    assert scene.unit.state_manager.get_state() == UnitStates.DELETED.value
    assert not scene.db.get(DbCollections.UNIT, scene.unit.unit_id)['community_proxy_cleanup_pending']


def test_proxy_uses_current_project_tls_image_and_drops_untrusted_catalog_bootstrap(community_scenario):
    scene = community_scenario
    model = scene.unit.unit_model
    proxy = ensure_community_proxy(model, '.example.edu', 'tenant-project')
    proxy.guacamole_secret_version_name = 'projects/test/secrets/proxy/versions/1'
    proxy.image = 'projects/untrusted/global/images/malicious'
    proxy.startup_script = 'read signing key'
    proxy.metadata = {'items': [{'key': 'startup-script', 'value': 'read signing key'}]}
    proxy.service_accounts = [{'email': 'untrusted@example.test'}]
    first_address = proxy.nics[0].internal_ip
    proxy = ensure_community_proxy(model, '.example.edu', 'tenant-project')
    assert proxy.image == 'projects/tenant-project/global/images/image-guac-tenant-project'
    assert proxy.startup_script is None and proxy.metadata is None and proxy.service_accounts is None
    assert proxy.nics[0].internal_ip == first_address
    assert model.networks[0].reservations.count(first_address) == 1


def test_generated_proxy_rejects_more_vpcs_than_its_machine_supports(community_scenario):
    model = community_scenario.unit.unit_model
    for index in (2, 3):
        network = model.networks[0].model_copy(deep=True)
        network.name = f'external{index}'
        network.subnets[0].ip_subnet = f'10.{20 + index}.0.0/24'
        model.networks.append(network)
        server = model.servers[1].model_copy(deep=True)
        server.name = f'workstation{index}'
        server.nics[0].network = network.name
        model.servers.append(server)
    with pytest.raises(Exception, match='at most two VPC'):
        ensure_community_proxy(model, '.example.edu', 'tenant-project')
