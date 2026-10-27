from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock, patch

from common.constants.database import DbCollections
from common.constants.build_constants import BuildConstants
from common.constants.pub_sub import PubSub
from common.constants.states import ServerStates, WorkoutStates
from common.models.agoge import ServerModel, WorkoutModel
from common.services.wireguard_lab_spec import configure_kit_topology, default_wireguard_spec
from common.models.agoge import UnitModel
from cloud_fn_utilities.course_objects.unit.unit_dhcp_service import UnitDHCP
from cloud_fn_utilities.course_objects.workout.community_workout import CommunityWorkout
from cloud_fn_utilities.server_specific.guacamole.display_proxy import DisplayProxy


class Database:
    def __init__(self, records):
        self.records = deepcopy(records)
        self.db = self
        self.writing = False

    def collection(self, name):
        return self

    def document(self, name):
        db = self

        class Document:
            id = name

            def get(self, transaction=None):
                assert not db.writing, 'Firestore read after write'
                value = deepcopy(db.records.get(name))
                return SimpleNamespace(exists=value is not None, to_dict=lambda: value)

        return Document()

    def get(self, collection_name, doc_id):
        return deepcopy(self.records.get(doc_id, {}))

    def update(self, collection_name, doc_id, data):
        self.records.setdefault(doc_id, {}).update(deepcopy(data))

    def set(self, document, data, merge=False):
        self.writing = True
        if not merge:
            self.records[document.id] = {}
        self.records.setdefault(document.id, {}).update(deepcopy(data))

    def transaction(self, operation):
        self.writing = False
        try:
            return operation(self)
        finally:
            self.writing = False


def unit_and_workout():
    unit = UnitModel(**default_wireguard_spec('image-kali', [
        {'display': True, 'protocol': 'rdp', 'username': 'kali', 'password': 'example'}]),
        id='abcdefghij', instructor_id=['teacher@example.edu'])
    configure_kit_topology(unit, '172.30.0.0/24', 51820)
    student = unit.servers[1].model_copy(deep=True)
    student.nics[0].internal_ip = '10.20.0.2'
    student.parent_id = 'klmnopqrst'
    student.parent_build_type = 'workout'
    student.state = ServerStates.RUNNING.value
    workout = WorkoutModel(id='klmnopqrst', parent_id=unit.id, parent_build_type='unit',
        build_type='workout', servers=[student], networks=unit.networks)
    return unit, workout


def proxy_for(db, unit, workout):
    proxy = object.__new__(DisplayProxy)
    proxy.db = db
    proxy.build_id = workout.id
    proxy.server_id = f'{workout.id}-display-guacamole-server'
    proxy.managed_community_unit = unit.id
    proxy.unit_dhcp = object.__new__(UnitDHCP)
    proxy.unit_dhcp.unit_id = unit.id
    proxy.unit_dhcp.db = db
    proxy.unit_dhcp._validate_unit = lambda value: UnitModel(**value)
    return proxy


def test_managed_proxy_claims_actual_unit_subnet_and_reuses_credentials_on_retry():
    unit, workout = unit_and_workout()
    db = Database({unit.id: unit.model_dump(), workout.id: workout.model_dump()})
    # The student address is already reserved by the student-server transaction.
    db.records[unit.id]['networks'][0]['reservations'].append('10.20.0.2')
    proxy = proxy_for(db, unit, workout)
    record = ServerModel(name='display-guacamole-server', image='image-guac', parent_id=workout.id,
        parent_build_type='workout', no_service_account=True,
        nics=[{'network': 'external', 'external_nat': True}],
        guacamole_startup_script='first-bootstrap').model_dump()
    connections = [SimpleNamespace(model_dump=lambda: {'server': 'kali', 'password': 'first-password'})]

    first = proxy._claim_managed_proxy(record, connections)
    second = proxy._claim_managed_proxy(
        {**record, 'guacamole_startup_script': 'changed-bootstrap'},
        [SimpleNamespace(model_dump=lambda: {'server': 'kali', 'password': 'changed-password'})],
    )

    assert first['nics'][0]['internal_ip'] == '10.20.0.3'
    assert second['nics'] == first['nics']
    assert second['guacamole_startup_script'] == 'first-bootstrap'
    assert db.records[workout.id]['proxy_connections'][0]['password'] == 'first-password'
    assert db.records[unit.id]['networks'][0]['reservations'].count('10.20.0.3') == 1
    assert second['no_service_account'] is True


def test_managed_proxy_uses_shared_unit_network_prefix_for_compute():
    unit, workout = unit_and_workout()
    proxy = proxy_for(Database({}), unit, workout)
    proxy.compute_manager = Mock()
    proxy.prepare_server_record = Mock()
    proxy.build()
    proxy.compute_manager.load.assert_called_once_with(proxy.server_id, network_prefix=unit.id)


def test_managed_proxy_record_and_browser_connections_use_provisioned_addresses():
    unit, workout = unit_and_workout()
    db = Database({unit.id: unit.model_dump(), workout.id: workout.model_dump()})
    db.records[unit.id]['networks'][0]['reservations'].append('10.20.0.2')
    proxy = proxy_for(db, unit, workout)
    proxy.collection = DbCollections.WORKOUT
    proxy.model = WorkoutModel
    proxy.server_specs = workout.servers
    proxy.server_name = 'display-guacamole-server'
    proxy.build_type = BuildConstants.BuildType.WORKOUT
    proxy.env = SimpleNamespace(main_app_url='https://app.example.edu', parent_dns_suffix='.example.edu')
    proxy.db_mask = Mock()
    proxy.guac = Mock()
    proxy.guac.prepare_guac_connection.return_value = {
        'ip': '10.20.0.2', 'workspace_username': 'agoge1', 'workspace_password': 'browser-password'}
    proxy.guac.get_guac_startup_script.return_value = 'bundled-guacamole-script'
    proxy._create_network_settings()

    record = proxy.prepare_server_record()

    assert record['nics'][0]['internal_ip'] == '10.20.0.3'
    assert record['tags'] == ['student-entry', f'{unit.id}-student-entry']
    assert record['no_service_account'] is True
    assert db.records[workout.id]['proxy_connections'][0]['internal_ip_address'] == '10.20.0.2'
    assert db.records[workout.id]['proxy_connections'][0]['url'].endswith('/guacamole/0')
    assert proxy.guac.prepare_guac_connection.call_args.kwargs['server_ip'] == '10.20.0.2'


def test_managed_workout_persists_actual_student_addresses_before_building_proxy():
    unit, workout = unit_and_workout()
    manager = object.__new__(CommunityWorkout)
    manager.unit_model = unit
    manager.unit_id = unit.id
    manager.workout_id = workout.id
    manager.workout = workout
    manager.env_dict = {'project': 'example-project'}
    manager.db = Database({f'{workout.id}-kali': workout.servers[0].model_dump()})
    manager.update_record = Mock()
    with patch('cloud_fn_utilities.course_objects.workout.community_workout.DisplayProxy') as constructor:
        manager._build_managed_display_proxy()
    assert manager.workout.servers[0].nics[0].internal_ip == '10.20.0.2'
    assert len(manager.workout.servers) == 1
    manager.update_record.assert_called_once_with(doc_id=workout.id, data=workout, update_keys=['servers'])
    assert constructor.call_args.kwargs['collection'] == DbCollections.WORKOUT
    constructor.return_value.build.assert_called_once()


def test_managed_workout_starts_and_stops_its_own_proxy_with_student_machines():
    unit, workout = unit_and_workout()
    manager = object.__new__(CommunityWorkout)
    # Only presence is used here; avoid coupling this lifecycle test to the
    # enrollment model's required fields.
    manager.unit_model = SimpleNamespace(servers=unit.servers, wireguard_lease={'kit_id': 'factory-a'})
    manager.unit_id = unit.id
    manager.workout_id = workout.id
    manager.workout = workout
    manager.db_queries = Mock()
    manager.db_queries.get_children.return_value = [
        {'id': 'anotherxxx', 'state': WorkoutStates.RUNNING.value}]
    for action in (PubSub.Actions.START, PubSub.Actions.STOP):
        servers, boundary = manager._CommunityWorkout__get_servers_for_action(action)
        assert boundary is False
        assert servers == [f'{workout.id}-kali', f'{workout.id}-display-guacamole-server']
