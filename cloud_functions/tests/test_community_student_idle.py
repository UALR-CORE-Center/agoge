"""Initial student claims finish idle, without stopping the Unit display proxy."""
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from cloud_fn_utilities.course_objects.compute.lab_server_manager import LabServerManager
from cloud_fn_utilities.course_objects.workout import community_workout as module
from cloud_fn_utilities.state_managers.workout_states import WorkoutStatesManager
from common.constants.database import DbCollections
from common.constants.states import ServerStates, WorkoutStates


class State:
    def __init__(self, record):
        self.record = record
        self.transitions = []

    def get_state(self):
        return self.record['state']

    def state_transition(self, state):
        self.record['state'] = state.value
        self.transitions.append(state)

    def are_server_builds_finished(self):
        return True


class Database:
    def __init__(self, records):
        self.records = records

    def get(self, collection_name, doc_id):
        return deepcopy(self.records.get(doc_id, {}))


class Compute:
    """Real LabServerManager stop path; fake only database and Compute SDK."""
    def __init__(self, records):
        self.records = records
        self.current = None
        self.stopped = []
        self.loads = []
        self.provider = {name: 'RUNNING' for name in records}
        self.fail_once = None

    def load(self, server_name, network_prefix):
        assert network_prefix == 'abcdefghij'
        self.loads.append(server_name)
        self.current = server_name

    def _get_instance_status(self):
        return self.provider[self.current]

    def stop(self):
        name = self.current
        if name == self.fail_once:
            self.fail_once = None
            raise ConnectionError('temporary stop failure')
        manager = object.__new__(LabServerManager)
        manager.server_name = name
        manager.s = ServerStates
        manager.server_spec = SimpleNamespace(wireguard_managed=False, wireguard_endpoint_id=None)
        manager.compute_instance = SimpleNamespace(stop=lambda **kwargs: self._stop_rpc(name, **kwargs))
        manager.state_manager = State(self.records[name])
        manager.logger = Mock()
        manager.class_name = 'LabServerManager'
        manager._dns_record = lambda: None
        manager.stop()

    def _stop_rpc(self, name, **kwargs):
        assert kwargs == {'resource_name': name, 'wait': True}
        self.stopped.append(name)
        self.provider[name] = 'TERMINATED'
        return True


@pytest.fixture
def initial():
    unit_id, workout_id = 'abcdefghij', 'klmnopqrst'
    record = {'state': WorkoutStates.COMPLETED_SERVERS.value}
    names = [f'{workout_id}-student']
    servers = {name: {'name': name.split('-', 1)[1], 'parent_id': workout_id,
                      'state': ServerStates.RUNNING.value} for name in names}
    servers[f'{unit_id}-wireguard'] = {'name': 'wireguard', 'parent_id': unit_id,
                                     'state': ServerStates.RUNNING.value}
    servers['other-student'] = {'name': 'student', 'parent_id': 'other', 'state': ServerStates.RUNNING.value}
    value = object.__new__(module.CommunityWorkout)
    value.workout_id, value.unit_id = workout_id, unit_id
    value.class_name, value.s = 'CommunityWorkout', WorkoutStates
    value.unit_model = SimpleNamespace(wireguard_lease={'kit_id': 'remote-lab'}, servers=[
        SimpleNamespace(name='wireguard', community_server=True),
        SimpleNamespace(name='display-guacamole-server', community_server=True, community_proxy=True),
        SimpleNamespace(name='student', community_server=False)])
    value.logger = Mock()
    value.state_manager = State(record)
    value.db = Database(servers)
    value.db_queries = SimpleNamespace(get_servers=lambda parent_id: [deepcopy(server)
        for server in servers.values() if server['parent_id'] == parent_id])
    value._prepare_community_connections = Mock()
    value._CommunityWorkout__send_server_build_msg = Mock()
    value.compute_manager = Compute(servers)
    value.pubsub_manager = Mock()
    value.debug = True
    return SimpleNamespace(value=value, record=record, servers=servers, names=names,
                           shared=f'{unit_id}-wireguard')


def test_managed_build_stops_real_student_and_proxy_before_ready_without_shared_servers(initial):
    value = initial.value

    value.build()

    assert value.state_manager.transitions == [WorkoutStates.COMPLETED_STUDENT_ENTRY, WorkoutStates.READY]
    value._prepare_community_connections.assert_called_once()
    assert set(value.compute_manager.stopped) == set(initial.names)
    assert all(initial.servers[name]['state'] == ServerStates.STOPPED.value for name in initial.names)
    assert all(value.compute_manager.provider[name] == 'TERMINATED' for name in initial.names)
    assert initial.servers[initial.shared]['state'] == ServerStates.RUNNING.value
    assert initial.servers['other-student']['state'] == ServerStates.RUNNING.value
    value.pubsub_manager.msg.assert_not_called()


def test_partial_stop_retry_uses_checkpoint_without_rebuilding_stopped_proxy(initial):
    value = initial.value
    value.compute_manager.fail_once = initial.names[0]
    with pytest.raises(ConnectionError):
        value.build()
    assert value.state_manager.get_state() == WorkoutStates.COMPLETED_STUDENT_ENTRY.value

    value.build()

    value._prepare_community_connections.assert_called_once()
    assert value.state_manager.get_state() == WorkoutStates.READY.value
    assert set(value.compute_manager.stopped) == set(initial.names)
    assert len(value.compute_manager.stopped) == 1


def test_provider_must_confirm_stopped_even_if_record_says_stopped(initial):
    value = initial.value
    initial.record['state'] = WorkoutStates.COMPLETED_STUDENT_ENTRY.value
    for name in initial.names:
        initial.servers[name]['state'] = ServerStates.STOPPED.value

    with pytest.raises(TimeoutError, match='GCP has not confirmed student server'):
        value.build()

    assert value.state_manager.get_state() == WorkoutStates.COMPLETED_STUDENT_ENTRY.value
    assert WorkoutStates.READY not in value.state_manager.transitions
    value._prepare_community_connections.assert_not_called()


def test_async_build_publishes_only_owned_stops_and_waits_for_gcp_completion(initial):
    value = initial.value
    value.debug = False
    def publish(**attributes):
        name = attributes['build_id']
        assert name in initial.names
        initial.servers[name]['state'] = ServerStates.STOPPED.value
        value.compute_manager.provider[name] = 'TERMINATED'
    value.pubsub_manager.msg.side_effect = publish

    value.build()

    assert value.pubsub_manager.msg.call_count == 1
    assert value.compute_manager.stopped == []
    assert value.state_manager.get_state() == WorkoutStates.READY.value


def test_missing_or_foreign_student_record_never_stops_an_unowned_vm(initial):
    initial.servers[initial.names[0]]['parent_id'] = 'another-workout'

    with pytest.raises(LookupError, match='ownership is missing'):
        initial.value.build()

    assert initial.value.compute_manager.stopped == []
    assert initial.record['state'] == WorkoutStates.COMPLETED_STUDENT_ENTRY.value


@pytest.mark.parametrize('state', [WorkoutStates.READY, WorkoutStates.RUNNING, WorkoutStates.STARTING,
                                  WorkoutStates.STOPPING, WorkoutStates.EXPIRED,
                                  WorkoutStates.BROKEN, WorkoutStates.DELETING_SERVERS, WorkoutStates.DELETED])
def test_stale_build_delivery_never_stops_an_existing_runtime_or_terminal_workout(initial, state):
    initial.record['state'] = state.value

    initial.value.build()

    assert initial.value.compute_manager.stopped == []
    assert initial.record['state'] == state.value
    initial.value._prepare_community_connections.assert_not_called()


def test_initial_entry_checkpoint_has_a_valid_ready_transition():
    manager = object.__new__(WorkoutStatesManager)
    manager.s = WorkoutStates
    manager.logger = Mock()

    assert manager._is_valid_transition(WorkoutStates.COMPLETED_STUDENT_ENTRY.value, WorkoutStates.READY.value)


def test_non_managed_community_build_retains_existing_behavior(initial):
    value = initial.value
    value.unit_model.wireguard_lease = None
    value.unit_model.servers = [server for server in value.unit_model.servers
                                if not getattr(server, 'community_proxy', False)]

    value.build()

    assert value.state_manager.transitions == [WorkoutStates.READY]
    assert value.compute_manager.stopped == []
