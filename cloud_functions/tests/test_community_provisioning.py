import copy
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Lock
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from common.constants.states import ServerStates, UnitStates, WorkoutStates
from common.constants.pub_sub import PubSub
from common.models.agoge import NicModel, RouteModel, ServerModel
from cloud_functions.cloud_fn_utilities.course_objects.unit.community_unit import CommunityUnit
from cloud_functions.cloud_fn_utilities.course_objects.unit.unit_dhcp_service import UnitDHCP
from cloud_functions.cloud_fn_utilities.course_objects.workout.community_workout import CommunityWorkout


class _AcceptValidator:
    def __init__(self, *args, **kwargs):
        pass

    def load(self, data, **kwargs):
        return data


class _RecordingDatabase:
    def __init__(self, error=None, records=None):
        self.error = error
        self.updates = []
        self.records = records or {}

    def get(self, collection_name, doc_id):
        return self.records.get(doc_id, {})

    def update(self, **kwargs):
        if self.error:
            raise self.error
        self.updates.append(kwargs)
        self.records.setdefault(kwargs['doc_id'], {}).update(kwargs['data'])


class _Snapshot:
    def __init__(self, data):
        self._data = copy.deepcopy(data)
        self.exists = bool(data)

    def to_dict(self):
        return copy.deepcopy(self._data)


class _DocumentReference:
    def __init__(self, database, doc_id):
        self.database = database
        self.id = doc_id

    def get(self, transaction=None):
        return _Snapshot(self.database.records.get(self.id, {}))


class _CollectionReference:
    def __init__(self, database):
        self.database = database

    def document(self, doc_id):
        return _DocumentReference(self.database, doc_id)

    def where(self, *, filter):
        return SimpleNamespace(get=lambda transaction=None: [
            _Snapshot(value) for value in self.database.records.values()
            if value.get(filter.field_path) == filter.value])


class _TransactionalDatabase(_RecordingDatabase):
    """Small serialized transaction fake for shared-start race tests."""

    def __init__(self, records=None, transaction_barrier=None):
        super().__init__(records=records)
        self.db = self
        self.transaction_barrier = transaction_barrier
        self._transaction_lock = Lock()

    def collection(self, collection_name):
        return _CollectionReference(self)

    def transaction(self, operation_func, **kwargs):
        if self.transaction_barrier:
            self.transaction_barrier.wait()
        with self._transaction_lock:
            return operation_func(self, **kwargs)

    def set(self, doc_ref, data, merge=False):
        if merge:
            self.records.setdefault(doc_ref.id, {}).update(copy.deepcopy(data))
        else:
            self.records[doc_ref.id] = copy.deepcopy(data)


class _RecordingPublisher:
    def __init__(self, error=None):
        self.error = error
        self.attempts = 0
        self.messages = []

    def msg(self, **kwargs):
        self.attempts += 1
        if self.error:
            error, self.error = self.error, None
            raise error
        self.messages.append(kwargs)


class _DHCP:
    def __init__(self, addresses, records=None, error=None):
        self.addresses = iter(addresses)
        self.records = records if records is not None else {}
        self.error = error
        self.requests = []
        self.released = []
        self.claims = []

    def get_network_address(self, network_name, subnet_name='default'):
        self.requests.append((network_name, subnet_name))
        return next(self.addresses)

    def release_network_address(self, network_name, address, subnet_name='default'):
        self.released.append((network_name, subnet_name, address))

    def claim_server_leases(self, server_name, server_data):
        self.claims.append(server_name)
        if self.error:
            raise self.error

        claimed = copy.deepcopy(server_data)
        existing_server = self.records.get(server_name, {})
        existing_nics = existing_server.get('nics') or []
        for index, nic in enumerate(claimed.get('nics') or []):
            subnet_name = nic.get('subnet_name') or 'default'
            existing_nic = existing_nics[index] if index < len(existing_nics) else {}
            if (
                existing_nic.get('network') == nic.get('network')
                and (existing_nic.get('subnet_name') or 'default') == subnet_name
                and existing_nic.get('internal_ip')
            ):
                nic['internal_ip'] = existing_nic['internal_ip']
            else:
                self.requests.append((nic['network'], subnet_name))
                nic['internal_ip'] = next(self.addresses)
        claimed[UnitDHCP.LEASE_CLAIM_FIELD] = existing_server.get(
            UnitDHCP.LEASE_CLAIM_FIELD,
            f'claim-{server_name}',
        )
        claimed[UnitDHCP.LEASE_RELEASED_FIELD] = False
        self.records.setdefault(server_name, {}).update(copy.deepcopy(claimed))
        return claimed

    def release_server_leases(self, server_name, claim_id=None):
        self.released.append((server_name, claim_id))
        server = self.records.get(server_name)
        if not server or server.get(UnitDHCP.LEASE_RELEASED_FIELD):
            return False
        if server.get(UnitDHCP.LEASE_CLAIM_FIELD) != claim_id:
            return False
        server[UnitDHCP.LEASE_RELEASED_FIELD] = True
        return True


class _StateManager:
    def __init__(self, state, builds_finished=True):
        self.state = state
        self.builds_finished = builds_finished
        self.transitions = []
        self.wait_calls = 0

    def get_state(self):
        return self.state

    def state_transition(self, new_state):
        self.state = new_state.value
        self.transitions.append(new_state)

    def are_server_builds_finished(self):
        self.wait_calls += 1
        return self.builds_finished


def _server(direct_connect=False, nic_count=1, subnet_names=None):
    subnet_names = subnet_names or ['default'] * nic_count
    return ServerModel(
        name='kali',
        image='image-kali',
        community_server=False,
        nics=[
            NicModel(
                network=f'external-{index}',
                subnet_name=subnet_names[index],
                direct_connect=direct_connect,
            )
            for index in range(nic_count)
        ],
    )


def _wireguard_activation_unit(listener_port='udp/51820', endpoint_port=51820):
    return SimpleNamespace(
        wireguard_endpoint=SimpleNamespace(id='12345', port=endpoint_port),
        servers=[
            SimpleNamespace(
                wireguard_gateway=True,
                tags=['wireguard-gateway'],
                nics=[SimpleNamespace(network='external', external_nat=True)],
            )
        ],
        firewall_rules=[
            SimpleNamespace(
                network='external',
                action='allow',
                direction='INGRESS',
                priority=1000,
                target_tags=['wireguard-gateway'],
                ports=[listener_port],
                ip_ranges=['0.0.0.0/0'],
            )
        ],
    )


def test_community_unit_endpoint_activation_includes_the_owning_unit_id():
    community_unit = object.__new__(CommunityUnit)
    community_unit.unit_id = 'unit-12345'
    community_unit.unit_model = _wireguard_activation_unit()
    community_unit.env_dict = {'project': 'tenant-project'}
    community_unit.db = Mock()

    with patch(
        'cloud_functions.cloud_fn_utilities.course_objects.unit.community_unit.'
        'WireGuardEndpointRegistry'
    ) as registry_class:
        community_unit._activate_wireguard_endpoint()

    registry_class.assert_called_once_with(
        env_dict=community_unit.env_dict,
        db=community_unit.db,
    )
    registry_class.return_value.activate.assert_called_once_with(
        '12345',
        unit_id='unit-12345',
    )


def test_community_unit_refuses_to_publish_endpoint_for_wrong_listener_port():
    community_unit = object.__new__(CommunityUnit)
    community_unit.unit_id = 'unit-12345'
    community_unit.unit_model = _wireguard_activation_unit(
        listener_port='udp/51820',
        endpoint_port=41194,
    )
    community_unit.env_dict = {'project': 'tenant-project'}
    community_unit.db = Mock()

    with patch(
        'cloud_functions.cloud_fn_utilities.course_objects.unit.community_unit.'
        'WireGuardEndpointRegistry'
    ) as registry_class:
        with pytest.raises(ValueError, match='does not allow public UDP/41194'):
            community_unit._activate_wireguard_endpoint()

    registry_class.assert_not_called()


def test_community_unit_serializes_pydantic_server_without_mutating_template():
    community_unit = object.__new__(CommunityUnit)
    community_unit.unit_id = 'unit-12345'
    community_unit.unit_model = SimpleNamespace(build_type='unit')
    community_unit.env = SimpleNamespace(parent_dns_suffix='.labs.example.org')
    community_unit.validator = _AcceptValidator
    community_unit.log_name = 'test'
    community_unit.db = _RecordingDatabase()
    community_unit.debug = False
    community_unit.pubsub_manager = _RecordingPublisher()
    template = _server(direct_connect=True)

    community_unit._CommunityUnit__send_server_build_msg(template)

    assert template.parent_id is None
    assert template.hostname is None
    assert template.tags == []
    saved = community_unit.db.updates[0]['data']
    assert isinstance(saved, dict)
    assert saved['parent_id'] == 'unit-12345'
    assert saved['hostname'] == 'unit-12345-kali.labs.example.org'
    assert saved['tags'] == ['unit-12345-direct-connect']


def test_community_unit_attaches_matching_routes_to_any_shared_next_hop():
    matching_route = RouteModel(
        name='remote-network',
        network='external',
        dest_range='172.30.0.0/24',
        next_hop_instance='router',
    )
    unrelated_route = RouteModel(
        name='other-network',
        network='external',
        dest_range='172.31.0.0/24',
        next_hop_instance='other-router',
    )
    community_unit = object.__new__(CommunityUnit)
    community_unit.unit_id = 'unit-12345'
    community_unit.unit_model = SimpleNamespace(
        build_type='unit',
        routes=[matching_route, unrelated_route],
    )
    community_unit.env = SimpleNamespace(parent_dns_suffix='.labs.example.org')
    community_unit.validator = _AcceptValidator
    community_unit.log_name = 'test'
    community_unit.db = _RecordingDatabase()
    community_unit.debug = False
    community_unit.pubsub_manager = _RecordingPublisher()
    template = ServerModel(
        name='router',
        image='image-router',
        community_server=True,
        can_ip_forward=True,
        nics=[NicModel(network='external', internal_ip='10.20.0.3')],
    )

    community_unit._CommunityUnit__send_server_build_msg(template)

    assert template.routes is None
    saved = community_unit.db.updates[0]['data']
    assert [route['name'] for route in saved['routes']] == ['remote-network']


def test_community_workout_persists_allocated_address_without_mutating_template():
    workout = object.__new__(CommunityWorkout)
    workout.workout_id = 'workout-67890'
    workout.unit_id = 'unit-12345'
    workout.workout = SimpleNamespace(build_type='workout')
    workout.logger = Mock()
    workout.env = SimpleNamespace(parent_dns_suffix='.labs.example.org')
    workout.db = _RecordingDatabase()
    workout.unit_dhcp = _DHCP(['10.20.0.3'], records=workout.db.records)
    workout.debug = False
    workout.pubsub_manager = _RecordingPublisher()
    template = _server(direct_connect=True)

    workout._CommunityWorkout__send_server_build_msg(template)

    assert template.parent_id is None
    assert template.nics[0].internal_ip is None
    saved = workout.db.records['workout-67890-kali']
    assert isinstance(saved, dict)
    assert saved['parent_id'] == 'workout-67890'
    assert saved['nics'][0]['internal_ip'] == '10.20.0.3'
    assert workout.unit_dhcp.requests == [('external-0', 'default')]
    assert saved['tags'] == ['workout-67890-direct-connect']
    assert workout.pubsub_manager.messages[0]['network_prefix'] == 'unit-12345'


def test_community_workout_does_not_publish_when_atomic_lease_claim_fails():
    workout = object.__new__(CommunityWorkout)
    workout.workout_id = 'workout-67890'
    workout.unit_id = 'unit-12345'
    workout.workout = SimpleNamespace(build_type='workout')
    workout.logger = Mock()
    workout.env = SimpleNamespace(parent_dns_suffix='.labs.example.org')
    workout.db = _RecordingDatabase()
    workout.unit_dhcp = _DHCP(
        ['10.20.0.3', '10.21.0.3'],
        records=workout.db.records,
        error=RuntimeError('transaction failed'),
    )
    workout.debug = False
    workout.pubsub_manager = _RecordingPublisher()
    template = _server(nic_count=2, subnet_names=['student-a', 'student-b'])

    with pytest.raises(RuntimeError, match='transaction failed'):
        workout._CommunityWorkout__send_server_build_msg(template)

    assert workout.db.records == {}
    assert workout.pubsub_manager.attempts == 0


def test_community_unit_resumes_incomplete_phases_and_waits_for_servers():
    community_unit = object.__new__(CommunityUnit)
    community_unit.unit_id = 'unit-12345'
    community_unit.class_name = 'CommunityUnit'
    community_unit.logger = Mock()
    community_unit.s = UnitStates
    community_unit.state_manager = _StateManager(UnitStates.BUILDING_NETWORKS.value)
    community_unit.unit_model = SimpleNamespace(
        networks=[SimpleNamespace(name='inside')],
        servers=[SimpleNamespace(name='gateway', community_server=True)],
        firewall_rules=[SimpleNamespace(name='allow-wireguard')],
    )
    community_unit.promiscuous_mode = False
    community_unit.vpc_manager = SimpleNamespace(build=Mock())
    community_unit.firewall_manager = SimpleNamespace(build=Mock())
    community_unit.packet_mirroring = SimpleNamespace(create=Mock())
    community_unit._CommunityUnit__set_promiscuous_mode = Mock()
    community_unit._CommunityUnit__send_server_build_msg = Mock()
    community_unit._activate_wireguard_endpoint = Mock()

    community_unit._build_unit()

    community_unit.vpc_manager.build.assert_called_once()
    community_unit._CommunityUnit__send_server_build_msg.assert_called_once()
    community_unit._activate_wireguard_endpoint.assert_called_once_with()
    assert community_unit.state_manager.wait_calls == 1
    assert community_unit.state_manager.transitions == [
        UnitStates.COMPLETED_NETWORKS,
        UnitStates.BUILDING_SERVERS,
        UnitStates.COMPLETED_SERVERS,
        UnitStates.BUILDING_FIREWALL_RULES,
        UnitStates.COMPLETED_FIREWALL_RULES,
        UnitStates.READY,
    ]


def test_community_unit_timeout_keeps_retryable_building_server_state():
    community_unit = object.__new__(CommunityUnit)
    community_unit.unit_id = 'unit-12345'
    community_unit.class_name = 'CommunityUnit'
    community_unit.logger = Mock()
    community_unit.s = UnitStates
    community_unit.state_manager = _StateManager(
        UnitStates.BUILDING_SERVERS.value,
        builds_finished=False,
    )
    community_unit.unit_model = SimpleNamespace(
        networks=[],
        servers=[SimpleNamespace(name='gateway', community_server=True)],
        firewall_rules=[],
    )
    community_unit._CommunityUnit__send_server_build_msg = Mock()

    with pytest.raises(TimeoutError, match='community servers'):
        community_unit._build_unit()

    assert community_unit.state_manager.state == UnitStates.BUILDING_SERVERS.value
    assert UnitStates.READY not in community_unit.state_manager.transitions


def test_community_workout_resumes_building_servers_delivery():
    workout = object.__new__(CommunityWorkout)
    workout.workout_id = 'workout-67890'
    workout.class_name = 'CommunityWorkout'
    workout.logger = Mock()
    workout.s = WorkoutStates
    workout.state_manager = _StateManager(WorkoutStates.BUILDING_SERVERS.value)
    student_server = SimpleNamespace(name='kali', community_server=False)
    workout.unit_model = SimpleNamespace(servers=[student_server])
    workout._CommunityWorkout__send_server_build_msg = Mock()

    workout.build()

    workout._CommunityWorkout__send_server_build_msg.assert_called_once_with(student_server)
    assert workout.state_manager.transitions == [
        WorkoutStates.COMPLETED_SERVERS,
        WorkoutStates.READY,
    ]


def test_community_workout_reuses_persisted_lease_after_publish_failure():
    workout = object.__new__(CommunityWorkout)
    workout.workout_id = 'workout-67890'
    workout.unit_id = 'unit-12345'
    workout.workout = SimpleNamespace(build_type='workout')
    workout.logger = Mock()
    workout.env = SimpleNamespace(parent_dns_suffix='.labs.example.org')
    workout.db = _RecordingDatabase()
    workout.unit_dhcp = _DHCP(['10.20.0.3'], records=workout.db.records)
    workout.debug = False
    workout.pubsub_manager = _RecordingPublisher(error=RuntimeError('publish failed'))
    template = _server()

    with pytest.raises(RuntimeError, match='publish failed'):
        workout._CommunityWorkout__send_server_build_msg(template)

    assert workout.unit_dhcp.released == []
    assert workout.db.records['workout-67890-kali']['nics'][0]['internal_ip'] == '10.20.0.3'

    workout._CommunityWorkout__send_server_build_msg(template)

    assert workout.unit_dhcp.requests == [('external-0', 'default')]
    assert workout.pubsub_manager.attempts == 2
    assert len(workout.pubsub_manager.messages) == 1


def _community_unit_for_network_delete(vpc_delete_result):
    community_unit = object.__new__(CommunityUnit)
    community_unit.unit_id = 'unit-12345'
    community_unit.class_name = 'CommunityUnit'
    community_unit.logger = Mock()
    community_unit.s = UnitStates
    community_unit.state_manager = SimpleNamespace(
        get_state=Mock(return_value=UnitStates.RUNNING.value),
        state_transition=Mock(),
        are_workouts_deleted=Mock(return_value=True),
    )
    community_unit.db_queries = SimpleNamespace(
        get_children=Mock(return_value=[]),
    )
    community_unit.unit_model = SimpleNamespace(
        networks=[SimpleNamespace(name='external')],
        firewalls=None,
    )
    community_unit.debug = False
    community_unit.promiscuous_mode = False
    community_unit.packet_mirroring = SimpleNamespace(delete=Mock())
    community_unit.firewall_manager = SimpleNamespace(
        delete=Mock(return_value=True),
    )
    community_unit.vpc_manager = SimpleNamespace(
        delete=Mock(return_value=vpc_delete_result),
    )
    community_unit._CommunityUnit__set_promiscuous_mode = Mock()
    community_unit._CommunityUnit__get_servers = Mock(return_value=[])
    community_unit._CommunityUnit__get_community_servers = Mock(return_value=[])
    community_unit._CommunityUnit__are_servers_deleted = Mock(return_value=True)
    return community_unit


def test_community_unit_does_not_reach_deleted_when_vpc_delete_is_unconfirmed():
    community_unit = _community_unit_for_network_delete(False)

    with pytest.raises(ConnectionError, match='VPC deletion'):
        community_unit.delete()

    assert community_unit.state_manager.state_transition.call_args_list == [
        ((UnitStates.DELETING_SERVERS,), {}),
        ((UnitStates.BROKEN,), {}),
    ]


def test_community_unit_marks_broken_when_vpc_delete_raises():
    community_unit = _community_unit_for_network_delete(True)
    community_unit.vpc_manager.delete.side_effect = ConnectionError('subnetwork delete failed')

    with pytest.raises(ConnectionError, match='subnetwork delete failed'):
        community_unit.delete()

    assert community_unit.state_manager.state_transition.call_args_list == [
        ((UnitStates.DELETING_SERVERS,), {}),
        ((UnitStates.BROKEN,), {}),
    ]


def test_community_unit_reaches_deleted_after_confirmed_vpc_delete():
    community_unit = _community_unit_for_network_delete(True)

    community_unit.delete()

    assert community_unit.state_manager.state_transition.call_args_list == [
        ((UnitStates.DELETING_SERVERS,), {}),
        ((UnitStates.DELETED,), {}),
    ]


def test_community_server_redelivery_does_not_overwrite_running_record():
    community_unit = object.__new__(CommunityUnit)
    community_unit.unit_id = 'unit-12345'
    community_unit.unit_model = SimpleNamespace(build_type='unit')
    community_unit.env = SimpleNamespace(parent_dns_suffix='.labs.example.org')
    community_unit.validator = _AcceptValidator
    community_unit.log_name = 'test'
    community_unit.db = _RecordingDatabase(records={
        'unit-12345-kali': {'state': ServerStates.RUNNING.value},
    })
    community_unit.debug = False
    community_unit.pubsub_manager = _RecordingPublisher()

    community_unit._CommunityUnit__send_server_build_msg(_server())

    assert community_unit.db.updates == []
    assert community_unit.pubsub_manager.messages == []


@pytest.mark.parametrize('action', [PubSub.Actions.START, PubSub.Actions.STOP])
def test_shared_gateway_only_follows_boundary_workout_using_persisted_state_values(action):
    workout = object.__new__(CommunityWorkout)
    workout.workout_id = 'workout-current'
    workout.unit_id = 'unit-12345'
    workout.workout = SimpleNamespace(parent_id='unit-12345')
    workout.unit_model = SimpleNamespace(servers=[
        SimpleNamespace(name='kali', community_server=False),
        SimpleNamespace(name='wireguard', community_server=True),
    ])
    workout.db_queries = SimpleNamespace(get_children=Mock(return_value=[]))

    # With no other running Workout this is either the first start or the last
    # stop, so the shared gateway follows the student server.
    servers, boundary_workout = workout._CommunityWorkout__get_servers_for_action(action)
    assert boundary_workout is True
    assert servers == ['workout-current-kali', 'unit-12345-wireguard']

    workout.db_queries.get_children.return_value = [{
        'id': 'workout-other',
        'state': WorkoutStates.RUNNING.value,
    }]
    servers, boundary_workout = workout._CommunityWorkout__get_servers_for_action(action)
    assert boundary_workout is False
    assert servers == ['workout-current-kali']


def test_last_stop_keeps_gateway_for_a_sibling_still_starting():
    workout = object.__new__(CommunityWorkout)
    workout.workout_id, workout.unit_id = 'workout-current', 'unit-12345'
    workout.workout = SimpleNamespace(parent_id=workout.unit_id)
    workout.unit_model = SimpleNamespace(servers=[
        SimpleNamespace(name='kali', community_server=False),
        SimpleNamespace(name='wireguard', community_server=True),
    ])
    workout.db_queries = SimpleNamespace(get_children=Mock(return_value=[
        {'id': 'workout-other', 'state': WorkoutStates.STARTING.value}]))

    servers, boundary = workout._CommunityWorkout__get_servers_for_action(PubSub.Actions.STOP)

    assert boundary is False
    assert servers == ['workout-current-kali']


def test_two_students_automatically_start_and_stop_only_the_shared_gateway_boundaries():
    unit_id, gateway_name = 'unit-12345', 'unit-12345-wireguard'
    records = {
        gateway_name: {'state': ServerStates.STOPPED.value},
        'student-a-kali': {'state': ServerStates.RUNNING.value},
        'student-b-kali': {'state': ServerStates.RUNNING.value},
        'student-a': {'id': 'student-a', 'parent_id': unit_id, 'state': WorkoutStates.READY.value},
        'student-b': {'id': 'student-b', 'parent_id': unit_id, 'state': WorkoutStates.READY.value},
    }
    database = _TransactionalDatabase(records=records)
    cloud_actions = []

    class State(_StateManager):
        def __init__(self, identifier):
            super().__init__(WorkoutStates.READY.value)
            self.identifier = identifier

        def state_transition(self, new_state):
            super().state_transition(new_state)
            database.records[self.identifier]['state'] = new_state.value

        def are_servers_started(self):
            return database.records[f'{self.identifier}-kali']['state'] == ServerStates.RUNNING.value

        def are_servers_stopped(self):
            return database.records[f'{self.identifier}-kali']['state'] == ServerStates.STOPPED.value

    class Compute:
        def load(self, server_name):
            self.name = server_name

        def start(self, **kwargs):
            cloud_actions.append(('start', self.name))
            database.records[self.name]['state'] = ServerStates.RUNNING.value

        def stop(self, **kwargs):
            cloud_actions.append(('stop', self.name))
            database.records[self.name]['state'] = ServerStates.STOPPED.value
            if kwargs.get('community_stop_claim'):
                database.records[self.name]['community_stop_claim']['completed'] = True

    def make(identifier):
        workout = object.__new__(CommunityWorkout)
        workout.workout_id, workout.unit_id = identifier, unit_id
        workout.workout = SimpleNamespace(parent_id=unit_id, shutoff_timestamp=None)
        workout.unit_model = SimpleNamespace(servers=[
            SimpleNamespace(name='kali', community_server=False),
            SimpleNamespace(name='wireguard', community_server=True, wireguard_gateway=True,
                            wireguard_managed=True),
        ])
        workout.db = database
        workout.db_queries = SimpleNamespace(get_children=lambda **kwargs: [
            database.records['student-a'], database.records['student-b']])
        workout.s, workout.state_manager = WorkoutStates, State(identifier)
        workout._add_build_action = Mock()
        workout.packet_mirroring = SimpleNamespace(start=Mock(), stop=Mock())
        workout.compute_manager, workout.debug, workout.logger = Compute(), True, Mock()
        workout.duration_seconds = 3600
        workout.get_record = lambda: SimpleNamespace(parent_id=unit_id, shutoff_timestamp=None)
        workout.update_record = Mock()
        return workout

    first, second = make('student-a'), make('student-b')
    first.start()
    assert records[gateway_name]['state'] == ServerStates.RUNNING.value
    assert first.state_manager.get_state() == WorkoutStates.RUNNING.value
    second.start()
    assert records[gateway_name]['state'] == ServerStates.RUNNING.value
    first.stop()
    assert records[gateway_name]['state'] == ServerStates.RUNNING.value
    second.stop()
    assert records[gateway_name]['state'] == ServerStates.STOPPED.value
    assert second.state_manager.get_state() == WorkoutStates.READY.value
    assert [action for action in cloud_actions if action[1] == gateway_name] == [
        ('start', gateway_name), ('stop', gateway_name)]


@pytest.mark.parametrize('workout_state', [WorkoutStates.RUNNING, WorkoutStates.STARTING])
def test_idle_gateway_parking_never_stops_a_gateway_with_active_students(workout_state):
    unit = object.__new__(CommunityUnit)
    unit.unit_id = 'unit-12345'
    unit.unit_model = SimpleNamespace(servers=[SimpleNamespace(
        name='wireguard', community_server=True, wireguard_gateway=True, wireguard_managed=True)])
    unit.db_queries = SimpleNamespace(get_children=Mock(return_value=[{'state': workout_state.value}]))
    unit.compute_manager = Mock()

    assert unit._stop_idle_managed_wireguard() is False

    unit.compute_manager.load.assert_not_called()


def test_managed_idle_gateway_stop_failure_is_not_a_successful_build():
    unit = object.__new__(CommunityUnit)
    unit.unit_id = 'unit-12345'
    unit.unit_model = SimpleNamespace(servers=[SimpleNamespace(
        name='wireguard', community_server=True, wireguard_gateway=True, wireguard_managed=True)])
    unit.db_queries = SimpleNamespace(get_children=Mock(return_value=[]))
    unit.db = _RecordingDatabase(records={'unit-12345-wireguard': {'state': ServerStates.BROKEN.value}})
    unit.compute_manager, unit.debug = Mock(), True

    with pytest.raises(TimeoutError, match='Could not confirm idle WireGuard gateway stopped'):
        unit._stop_idle_managed_wireguard()


@pytest.mark.parametrize('expected,pending', [
    (ServerStates.RUNNING, ServerStates.STARTING),
    (ServerStates.STOPPED, ServerStates.STOPPING),
])
def test_student_lifecycle_waits_for_shared_gateway_cloud_completion(expected, pending):
    workout = object.__new__(CommunityWorkout)
    workout.unit_id = 'unit-12345'
    workout.unit_model = SimpleNamespace(servers=[SimpleNamespace(
        name='wireguard', community_server=True, wireguard_gateway=True, wireguard_managed=True)])
    workout.db = Mock()
    workout.db.get.side_effect = [{'state': pending.value}, {'state': expected.value}]
    workout.workout_id = 'student-current'
    workout.db_queries = SimpleNamespace(get_children=Mock(return_value=[]))

    with patch('cloud_functions.cloud_fn_utilities.course_objects.workout.community_workout.time.sleep') as sleep:
        assert workout._managed_gateways_reached(expected) is True

    sleep.assert_called_once_with(workout.MANAGED_GATEWAY_POLL_SECONDS)
    assert workout.db.get.call_count == 2


def test_failed_shared_gateway_cannot_complete_a_student_start():
    workout = object.__new__(CommunityWorkout)
    workout.unit_id = 'unit-12345'
    workout.unit_model = SimpleNamespace(servers=[SimpleNamespace(
        name='wireguard', community_server=True, wireguard_gateway=True, wireguard_managed=True)])
    workout.db = Mock()
    workout.db.get.return_value = {'state': ServerStates.BROKEN.value}

    assert workout._managed_gateways_reached(ServerStates.RUNNING) is False


def test_community_workout_duplicate_delete_is_noop_after_deleted():
    workout = object.__new__(CommunityWorkout)
    workout.s = WorkoutStates
    workout.state_manager = _StateManager(WorkoutStates.DELETED.value)
    workout._add_build_action = Mock()
    workout.db_queries = SimpleNamespace(get_servers=Mock())

    workout.delete()

    workout._add_build_action.assert_not_called()
    workout.db_queries.get_servers.assert_not_called()
    assert workout.state_manager.transitions == []


def test_community_workout_releases_the_captured_server_lease_claim():
    server_name = 'workout-current-kali'
    server = {
        'name': 'kali',
        'parent_id': 'workout-current',
        'nics': [{
            'network': 'external',
            'subnet_name': 'default',
            'internal_ip': '10.20.0.3',
        }],
        UnitDHCP.LEASE_CLAIM_FIELD: 'claim-current',
        UnitDHCP.LEASE_RELEASED_FIELD: False,
    }
    workout = object.__new__(CommunityWorkout)
    workout.workout_id = 'workout-current'
    workout.class_name = 'CommunityWorkout'
    workout.s = WorkoutStates
    workout.state_manager = _StateManager(WorkoutStates.READY.value)
    workout._add_build_action = Mock()
    workout.db_queries = SimpleNamespace(get_servers=Mock(return_value=[server]))
    workout.debug = False
    workout.pubsub_manager = _RecordingPublisher()
    workout.logger = Mock()
    workout.unit_dhcp = _DHCP([], records={server_name: copy.deepcopy(server)})
    workout._CommunityWorkout__are_servers_deleted = Mock(return_value=True)

    workout.delete()

    assert workout.unit_dhcp.released == [(server_name, 'claim-current')]
    assert workout.state_manager.state == WorkoutStates.DELETED.value


def test_simultaneous_first_workout_starts_publish_one_shared_server_action():
    server_name = 'unit-12345-wireguard'
    database = _TransactionalDatabase(
        records={server_name: {'state': ServerStates.STOPPED.value}},
        transaction_barrier=Barrier(2),
    )
    publisher = _RecordingPublisher()
    gateway = SimpleNamespace(name='wireguard', community_server=True)

    def make_workout(workout_id):
        workout = object.__new__(CommunityWorkout)
        workout.workout_id = workout_id
        workout.unit_id = 'unit-12345'
        workout.workout = SimpleNamespace(
            parent_id='unit-12345',
            shutoff_timestamp=None,
        )
        workout.unit_model = SimpleNamespace(servers=[gateway])
        workout.db = database
        workout.db_queries = SimpleNamespace(get_children=Mock(return_value=[]))
        workout.s = WorkoutStates
        workout.state_manager = _StateManager(WorkoutStates.READY.value)
        workout.state_manager.are_servers_started = Mock(return_value=True)
        workout._add_build_action = Mock()
        workout.packet_mirroring = SimpleNamespace(start=Mock())
        workout.pubsub_manager = publisher
        workout.debug = False
        workout.logger = Mock()
        workout.duration_seconds = 3600
        workout.get_record = Mock(
            return_value=SimpleNamespace(shutoff_timestamp=None)
        )
        workout.update_record = Mock()
        return workout

    workouts = [make_workout('workout-a'), make_workout('workout-b')]

    with ThreadPoolExecutor(max_workers=2) as executor:
        list(executor.map(lambda workout: workout.start(), workouts))

    shared_messages = [
        message
        for message in publisher.messages
        if message['build_id'] == server_name
    ]
    assert len(shared_messages) == 1
    assert database.records[server_name]['state'] == ServerStates.STARTING.value
    assert database.records[server_name]['community_start_claim']['owner'] in {
        'workout-a',
        'workout-b',
    }


def test_shared_server_start_claim_is_idempotent_for_owning_workout_retry():
    server_name = 'unit-12345-wireguard'
    database = _TransactionalDatabase(
        records={server_name: {'state': ServerStates.STOPPED.value}},
    )
    workout = object.__new__(CommunityWorkout)
    workout.workout_id = 'workout-a'
    workout.db = database

    assert workout._CommunityWorkout__claim_shared_server_start(server_name)
    assert workout._CommunityWorkout__claim_shared_server_start(server_name)
    assert database.records[server_name]['community_start_claim']['owner'] == 'workout-a'


def _gateway_claim_workout(database, identifier):
    workout = object.__new__(CommunityWorkout)
    workout.workout_id, workout.unit_id = identifier, 'unit-12345'
    workout.workout = SimpleNamespace(parent_id=workout.unit_id)
    workout.unit_model = SimpleNamespace(servers=[SimpleNamespace(
        name='wireguard', community_server=True, wireguard_gateway=True, wireguard_managed=True)])
    workout.db = database
    workout.db_queries = SimpleNamespace(get_children=lambda **kwargs: [
        value for value in database.records.values() if value.get('parent_id') == workout.unit_id])
    return workout


def test_stop_transaction_rechecks_a_new_start_after_last_student_selection():
    name = 'unit-12345-wireguard'
    database = _TransactionalDatabase(records={
        name: {'state': ServerStates.RUNNING.value},
        'student-a': {'id': 'student-a', 'parent_id': 'unit-12345', 'state': WorkoutStates.STOPPING.value},
        'student-b': {'id': 'student-b', 'parent_id': 'unit-12345', 'state': WorkoutStates.READY.value},
    })
    departing = _gateway_claim_workout(database, 'student-a')
    selected, last = departing._CommunityWorkout__get_servers_for_action(PubSub.Actions.STOP)
    assert selected == [name] and last
    database.records['student-b']['state'] = WorkoutStates.STARTING.value

    assert departing._CommunityWorkout__claim_shared_server_stop(name) is None

    assert database.records[name]['state'] == ServerStates.RUNNING.value
    assert 'community_stop_claim' not in database.records[name]


@pytest.mark.parametrize('pending', [ServerStates.STOPPING, ServerStates.STOPPED])
def test_new_first_student_waits_for_claimed_stop_then_obsoletes_queued_stop(pending):
    from cloud_functions.cloud_fn_utilities.course_objects.compute.lab_server_manager import LabServerManager

    name = 'unit-12345-wireguard'
    database = _TransactionalDatabase(records={
        name: {'state': ServerStates.RUNNING.value},
        'student-a': {'id': 'student-a', 'parent_id': 'unit-12345', 'state': WorkoutStates.STOPPING.value},
        'student-b': {'id': 'student-b', 'parent_id': 'unit-12345', 'state': WorkoutStates.READY.value},
    })
    departing = _gateway_claim_workout(database, 'student-a')
    arriving = _gateway_claim_workout(database, 'student-b')
    stop_token = departing._CommunityWorkout__claim_shared_server_stop(name)
    assert stop_token and database.records[name]['state'] == ServerStates.STOPPING.value
    database.records[name]['state'] = pending.value
    database.records['student-b']['state'] = WorkoutStates.STARTING.value

    def finish_stop(_):
        database.records[name]['state'] = ServerStates.STOPPED.value
        database.records[name]['community_stop_claim']['completed'] = True

    with patch('cloud_functions.cloud_fn_utilities.course_objects.workout.community_workout.time.sleep',
               side_effect=finish_stop) as sleep:
        start_token = arriving._CommunityWorkout__claim_shared_server_start(name)

    sleep.assert_called_once_with(arriving.MANAGED_GATEWAY_POLL_SECONDS)
    assert start_token and start_token != stop_token
    assert database.records[name]['state'] == ServerStates.STARTING.value
    gateway = object.__new__(LabServerManager)
    gateway.db, gateway.server_name, gateway.logger = database, name, Mock()
    gateway._stop_server = Mock()
    gateway.stop(community_stop_claim=stop_token)
    gateway._stop_server.assert_not_called()
    assert gateway._community_claim_is_current('start', start_token)
    # The departing student's completion must not wait for the gateway to
    # become idle again now that another student legitimately needs it.
    assert departing._managed_gateways_reached(ServerStates.STOPPED)


def test_queued_start_is_ignored_after_an_idle_stop_claim_replaces_it():
    from cloud_functions.cloud_fn_utilities.course_objects.compute.lab_server_manager import LabServerManager

    name = 'unit-12345-wireguard'
    database = _TransactionalDatabase(records={name: {'state': ServerStates.STOPPED.value}})
    workout = _gateway_claim_workout(database, 'student-a')
    start_token = workout._CommunityWorkout__claim_shared_server_start(name)
    def finish_start(_):
        database.records[name]['state'] = ServerStates.RUNNING.value
    with patch('cloud_functions.cloud_fn_utilities.course_objects.workout.community_workout.time.sleep',
               side_effect=finish_start) as sleep:
        stop_token = workout._CommunityWorkout__claim_shared_server_stop(name)
    sleep.assert_called_once_with(workout.MANAGED_GATEWAY_POLL_SECONDS)
    assert stop_token and database.records[name]['state'] == ServerStates.STOPPING.value
    gateway = object.__new__(LabServerManager)
    gateway.db, gateway.server_name, gateway.logger = database, name, Mock()
    gateway._start_server = Mock()

    gateway.start(community_start_claim=start_token)

    gateway._start_server.assert_not_called()


def test_instructor_stop_remains_unconditional_without_an_automatic_claim():
    from cloud_functions.cloud_fn_utilities.course_objects.compute.lab_server_manager import LabServerManager

    gateway = object.__new__(LabServerManager)
    gateway._managed_wireguard = Mock(return_value=False)
    gateway._wireguard_endpoint_id = Mock(return_value=None)
    gateway._stop_server = Mock()

    gateway.stop()

    gateway._stop_server.assert_called_once_with()


def test_automatic_stop_waits_for_gcp_before_completing_its_claim():
    from cloud_functions.cloud_fn_utilities.course_objects.compute.lab_server_manager import LabServerManager

    name, token = 'unit-12345-wireguard', 'current-stop'
    database = _TransactionalDatabase(records={name: {
        'state': ServerStates.STOPPING.value,
        'community_stop_claim': {'token': token, 'owner': 'student-a', 'completed': False},
    }})
    gateway = object.__new__(LabServerManager)
    gateway.db, gateway.server_name, gateway.logger = database, name, Mock()
    gateway._managed_wireguard = Mock(return_value=False)
    gateway._wireguard_endpoint_id = Mock(return_value=None)
    gateway._stop_server = Mock(side_effect=lambda: database.records[name].update(
        state=ServerStates.STOPPED.value))
    gateway._get_instance_status = Mock(side_effect=['STOPPING', 'TERMINATED'])

    with patch('cloud_functions.cloud_fn_utilities.course_objects.compute.lab_server_manager.time.sleep') as sleep:
        gateway.stop(community_stop_claim=token)

    sleep.assert_called_once_with(5)
    assert database.records[name]['community_stop_claim']['completed'] is True


def test_automatic_stop_retries_dns_cleanup_after_gcp_already_stopped():
    from cloud_functions.cloud_fn_utilities.course_objects.compute.lab_server_manager import LabServerManager
    from common.exceptions import BaseAgogeException

    name, token = 'unit-12345-wireguard', 'unfinished-stop'
    database = _TransactionalDatabase(records={name: {
        'state': ServerStates.STOPPING.value,
        'community_stop_claim': {'token': token, 'owner': 'student-a', 'completed': False},
    }})
    gateway = object.__new__(LabServerManager)
    gateway.db, gateway.server_name, gateway.parent_build_id = database, name, 'unit-12345'
    gateway.logger, gateway.s = Mock(), ServerStates
    gateway.state_manager = SimpleNamespace(get_state=lambda: database.records[name]['state'])
    gateway._managed_wireguard = Mock(return_value=True)
    gateway._wireguard_endpoint_id = Mock(return_value='10000')
    gateway._require_wireguard_provisionable = Mock()
    gateway.wireguard_registry = Mock()
    gateway.wireguard_registry.get.return_value = SimpleNamespace(
        id='10000', hostname='wg10000.example.edu', public_ip='203.0.113.10')
    gateway._wireguard_provisioning = Mock()
    gateway.dns_manager = SimpleNamespace(delete_dns=Mock(side_effect=[False, True]))
    rpc_stop = Mock()

    def stop_server():
        if database.records[name]['state'] != ServerStates.STOPPED.value:
            rpc_stop()
            database.records[name]['state'] = ServerStates.STOPPED.value

    gateway._stop_server = stop_server
    gateway._get_instance_status = Mock(return_value='TERMINATED')
    with pytest.raises(BaseAgogeException, match='DNS removal failed'):
        gateway.stop(community_stop_claim=token)
    assert database.records[name]['state'] == ServerStates.STOPPED.value
    assert database.records[name]['community_stop_claim']['completed'] is False

    gateway.stop(community_stop_claim=token)

    rpc_stop.assert_called_once_with()
    assert gateway.dns_manager.delete_dns.call_count == 2
    assert database.records[name]['community_stop_claim']['completed'] is True
    # A later duplicate of the completed claim must not restart cleanup.
    gateway.stop(community_stop_claim=token)
    assert gateway.dns_manager.delete_dns.call_count == 2


@pytest.mark.parametrize('action,state,claim', [
    ('start', ServerStates.STOPPING, {'community_stop_claim': {'token': 'pending-stop', 'completed': False}}),
    ('stop', ServerStates.STARTING, {'community_start_claim': {'token': 'pending-start'}}),
])
def test_opposite_automatic_operation_wait_is_bounded_without_overwriting_it(action, state, claim):
    name = 'unit-12345-wireguard'
    original = {'state': state.value, **claim}
    database = _TransactionalDatabase(records={name: copy.deepcopy(original)})
    workout = _gateway_claim_workout(database, 'student-a')

    with patch('cloud_functions.cloud_fn_utilities.course_objects.workout.community_workout.time.monotonic',
               side_effect=[0, 1000]), pytest.raises(TimeoutError):
        getattr(workout, f'_CommunityWorkout__claim_shared_server_{action}')(name)

    assert database.records[name] == original


@pytest.mark.parametrize(
    'blocked_state',
    [
        ServerStates.STOPPING,
        ServerStates.EXPIRED,
        ServerStates.MISFIT,
        ServerStates.DELETING,
        ServerStates.DELETED,
    ],
)
def test_shared_server_start_does_not_overwrite_blocked_lifecycle_state(blocked_state):
    server_name = 'unit-12345-wireguard'
    original_server = {
        'state': blocked_state.value,
        'state_timestamp': '2026-09-04T00:00:00+00:00',
    }
    database = _TransactionalDatabase(
        records={server_name: copy.deepcopy(original_server)},
    )
    publisher = _RecordingPublisher()
    workout = object.__new__(CommunityWorkout)
    workout.workout_id = 'workout-a'
    workout.unit_id = 'unit-12345'
    workout.workout = SimpleNamespace(parent_id='unit-12345')
    workout.unit_model = SimpleNamespace(servers=[
        SimpleNamespace(name='wireguard', community_server=True),
    ])
    workout.db = database
    workout.db_queries = SimpleNamespace(get_children=Mock(return_value=[]))
    workout.s = WorkoutStates
    workout.state_manager = _StateManager(WorkoutStates.READY.value)
    workout._add_build_action = Mock()
    workout.packet_mirroring = SimpleNamespace(start=Mock())
    workout.pubsub_manager = publisher
    workout.debug = False
    workout.logger = Mock()

    with pytest.raises(RuntimeError, match=blocked_state.name):
        workout.start()

    assert database.records[server_name] == original_server
    assert publisher.messages == []
    workout.packet_mirroring.start.assert_not_called()
