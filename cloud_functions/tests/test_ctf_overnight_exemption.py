"""SC-20: the midnight stop leaves CTF boards running while their event is armed or in play."""
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from cloud_fn_utilities.course_objects.compute.project_server_manager import ProjectServerManager
from cloud_fn_utilities.periodic_maintenance import daily_maintenance as daily_maintenance_module
from cloud_fn_utilities.periodic_maintenance.daily_maintenance import DailyMaintenance
from common.constants.database import DbCollections, DbOperators
from common.constants.pub_sub import PubSub
from common.constants.states import CtfStates


class FakeDb:
    """Applies the == / in filters the exemption query uses to in-memory collections."""

    def __init__(self, collections: dict):
        self.collections = collections
        self.queries = []

    def query(self, collection_name, filters=None, limit=None):
        self.queries.append((collection_name, filters))
        docs = self.collections.get(collection_name, [])
        for field, op, value in filters or []:
            if op == DbOperators.EQUAL:
                docs = [d for d in docs if d.get(field) == value]
            elif op == DbOperators.IN:
                docs = [d for d in docs if d.get(field) in value]
            else:
                raise AssertionError(f"unexpected operator {op}")
        return docs


def _event(ctf_id, state):
    return {'id': ctf_id, 'state': state.value}


def _board(ctf_id, workout_id, active=True):
    return {'id': f"{ctf_id}-{workout_id}", 'ctf_id': ctf_id, 'workout_id': workout_id, 'active': active}


def _maintenance(events, boards, running_workout_ids, debug=False):
    maintenance = object.__new__(DailyMaintenance)
    maintenance.debug = debug
    maintenance.env_dict = {}
    maintenance.db = FakeDb({DbCollections.CTF: events, DbCollections.CTF_BOARD: boards})
    maintenance.db_query = Mock()
    maintenance.db_query.get_running.return_value = [{'id': w} for w in running_workout_ids]
    maintenance.pub_sub_mgr = Mock()
    maintenance.project_server_manager = Mock()
    return maintenance


def _stopped_workout_ids(maintenance):
    stopped = []
    for call in maintenance.pub_sub_mgr.msg.call_args_list:
        attrs = call.kwargs
        assert attrs[PubSub.EventAttributes.ACTION] == PubSub.Actions.STOP.value
        stopped.append(attrs[PubSub.EventAttributes.BUILD_ID])
    return stopped


@pytest.fixture(autouse=True)
def _no_template_servers():
    with patch.object(daily_maintenance_module, 'ComputeManagerFactory') as factory:
        yield factory


@pytest.mark.parametrize('state', [CtfStates.ARMING, CtfStates.ARMED, CtfStates.RUNNING, CtfStates.PAUSED])
def test_no_stop_for_active_board_in_live_event(state):
    maintenance = _maintenance(
        events=[_event('ctfeventaa', state)],
        boards=[_board('ctfeventaa', 'boardwkaaa'), _board('ctfeventaa', 'boardwkbbb')],
        running_workout_ids=['boardwkaaa', 'boardwkbbb', 'plainwkccc'],
    )

    maintenance._stop_all()

    # SC-20: 0 STOPs for the boards; the ordinary workout is still stopped
    assert _stopped_workout_ids(maintenance) == ['plainwkccc']
    maintenance.project_server_manager.stop_everything.assert_called_once_with(
        exempt_prefixes=['boardwkaaa-', 'boardwkbbb-']
    )


@pytest.mark.parametrize('state', [CtfStates.DRAFT, CtfStates.ENDED, CtfStates.ARCHIVED, CtfStates.BROKEN])
def test_boards_in_other_event_states_are_stopped(state):
    maintenance = _maintenance(
        events=[_event('ctfeventaa', state)],
        boards=[_board('ctfeventaa', 'boardwkaaa')],
        running_workout_ids=['boardwkaaa'],
    )

    maintenance._stop_all()

    assert _stopped_workout_ids(maintenance) == ['boardwkaaa']
    maintenance.project_server_manager.stop_everything.assert_called_once_with(exempt_prefixes=[])


def test_inactive_board_is_stopped_even_in_running_event():
    maintenance = _maintenance(
        events=[_event('ctfeventaa', CtfStates.RUNNING)],
        boards=[_board('ctfeventaa', 'boardwkaaa', active=False), _board('ctfeventaa', 'boardwkbbb')],
        running_workout_ids=['boardwkaaa', 'boardwkbbb'],
    )

    maintenance._stop_all()

    assert _stopped_workout_ids(maintenance) == ['boardwkaaa']
    maintenance.project_server_manager.stop_everything.assert_called_once_with(exempt_prefixes=['boardwkbbb-'])


def test_board_of_ended_event_is_stopped_while_other_event_runs():
    maintenance = _maintenance(
        events=[_event('ctfeventaa', CtfStates.RUNNING), _event('ctfeventbb', CtfStates.ENDED)],
        boards=[_board('ctfeventaa', 'boardwkaaa'), _board('ctfeventbb', 'boardwkbbb')],
        running_workout_ids=['boardwkaaa', 'boardwkbbb'],
    )

    maintenance._stop_all()

    assert _stopped_workout_ids(maintenance) == ['boardwkbbb']


def test_no_ctf_events_stops_every_running_workout():
    maintenance = _maintenance(events=[], boards=[], running_workout_ids=['plainwkaaa', 'plainwkbbb'])

    maintenance._stop_all()

    assert _stopped_workout_ids(maintenance) == ['plainwkaaa', 'plainwkbbb']
    maintenance.project_server_manager.stop_everything.assert_called_once_with(exempt_prefixes=[])


def test_event_query_asks_only_for_live_states():
    maintenance = _maintenance(events=[], boards=[], running_workout_ids=[])

    maintenance._stop_all()

    collection, filters = maintenance.db.queries[0]
    assert collection == DbCollections.CTF
    assert filters == [(
        'state', DbOperators.IN,
        [CtfStates.ARMING.value, CtfStates.ARMED.value, CtfStates.RUNNING.value, CtfStates.PAUSED.value]
    )]


def test_debug_path_skips_ctf_board_too():
    maintenance = _maintenance(
        events=[_event('ctfeventaa', CtfStates.RUNNING)],
        boards=[_board('ctfeventaa', 'boardwkaaa')],
        running_workout_ids=['boardwkaaa', 'plainwkccc'],
        debug=True,
    )

    with patch.object(daily_maintenance_module, 'WorkoutFactory') as factory:
        maintenance._stop_all()

    stopped = [call.kwargs['workout_id'] for call in factory.create_workout_object.call_args_list]
    assert stopped == ['plainwkccc']
    maintenance.pub_sub_mgr.msg.assert_not_called()


def _project_server_manager(instance_names):
    manager = object.__new__(ProjectServerManager)
    manager.class_name = 'ProjectServerManager'
    manager.logger = Mock()
    manager.env = SimpleNamespace(project='proj', zone='zone')
    manager.compute_instance = Mock()
    manager.compute_instance.list.return_value = [SimpleNamespace(name=n) for n in instance_names]
    manager.db = Mock()
    manager.db.query.return_value = []
    manager.collection = DbCollections
    return manager


def test_stop_everything_skips_exempt_instances():
    manager = _project_server_manager([
        'boardwkaaa-web', 'boardwkaaa-display-guacamole-server', 'plainwkccc-web', 'boardwkaaaz-web',
    ])

    manager.stop_everything(exempt_prefixes=['boardwkaaa-'])

    stopped = [call.kwargs['resource_name'] for call in manager.compute_instance.stop.call_args_list]
    # The trailing dash keeps a different id sharing the same letters from being exempted
    assert stopped == ['plainwkccc-web', 'boardwkaaaz-web']


def test_stop_everything_without_exemptions_stops_all():
    manager = _project_server_manager(['boardwkaaa-web', 'plainwkccc-web'])

    manager.stop_everything()

    stopped = [call.kwargs['resource_name'] for call in manager.compute_instance.stop.call_args_list]
    assert stopped == ['boardwkaaa-web', 'plainwkccc-web']
