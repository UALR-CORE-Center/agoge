"""A Compute create that outlasts its wait keeps the build alive instead of stranding it.

The deployed function does not retry, so a timed-out server stays BUILDING and the build handler
republishes the parent, whose resent server build rejoins the operation recorded on the owner.
"""
from unittest.mock import MagicMock, Mock, call, patch

import pytest

from cloud_fn_utilities.build_execution import (
    MAX_BUILD_RESUMES, BuildExecution, BuildPending, build_execution, build_message_attempt,
    unfinished_build_error,
)
from cloud_fn_utilities.course_objects.compute import base_compute_manager as base_compute_module
from cloud_fn_utilities.course_objects.compute.lab_server_manager import LabServerManager
from cloud_fn_utilities.course_objects.workout.solo_workout import SoloWorkout
from cloud_fn_utilities.state_managers.base_state_manager import BaseStateManager
from common.constants.database import DbCollections
from common.constants.pub_sub import PubSub
from common.constants.states import ServerStates
from handlers import build_handler as handler_module

from tests.test_build_server_create_failure import _manager
from tests.test_lab_build_incident_workers import _build_events, _database, _handler


def _execution(resume, server_id=None):
    return BuildExecution(Mock(), DbCollections.WORKOUT, 'workout-a', 'unit-a', 'workout-attempt', server_id, resume)


def _timed_out_build(manager, resume):
    manager._on_instance_created = MagicMock()
    with patch.object(base_compute_module, 'InstanceResource', return_value=MagicMock()), \
            patch.object(base_compute_module, 'tracked_compute_create', return_value=False), \
            build_execution(_execution(resume, manager.server_name)):
        manager._build_server()


def test_a_create_still_in_flight_leaves_the_server_building_for_a_resume():
    manager = _manager()

    with pytest.raises(BuildPending):
        _timed_out_build(manager, resume=0)

    assert manager.state_manager.state_transition.call_args_list == [call('building')]
    manager._on_instance_created.assert_called_once()


@pytest.mark.parametrize('resume', [MAX_BUILD_RESUMES, None])
def test_a_create_timeout_with_no_resume_left_marks_the_server_broken(resume):
    manager = _manager()

    with pytest.raises(TimeoutError):
        _timed_out_build(manager, resume)

    assert manager.state_manager.state_transition.call_args_list == [call('building'), call('broken')]


def test_lab_server_build_does_not_break_a_server_awaiting_resume():
    server = object.__new__(LabServerManager)
    server.s = ServerStates
    server.state_manager = Mock()
    server.state_manager.get_state.return_value = ServerStates.START.value
    server._wireguard_action_is_blocked = Mock(return_value=False)
    server._require_wireguard_provisionable = Mock()
    server._managed_wireguard = Mock(return_value=False)
    server._mark_wireguard_endpoint_error = Mock()
    server._build_server = Mock(side_effect=BuildPending('still creating'))

    with pytest.raises(BuildPending):
        server.build()

    server.state_manager.state_transition.assert_not_called()
    server._mark_wireguard_endpoint_error.assert_not_called()


def _state_manager(*states):
    manager = object.__new__(BaseStateManager)
    manager.build_id = 'workout-a'
    manager.server_states = ServerStates
    manager.db_queries = Mock()
    manager.db_queries.get_servers.return_value = [{'state': state} for state in states]
    return manager


@pytest.mark.parametrize('states, pending', [
    ((ServerStates.BUILDING.value, ServerStates.RUNNING.value), True),
    ((), True),
    ((ServerStates.BUILDING.value, ServerStates.BROKEN.value), False),
    ((ServerStates.STOPPED.value,), False),
])
def test_server_builds_are_pending_only_while_no_child_has_left_the_build(states, pending):
    assert _state_manager(*states).are_server_builds_pending() is pending


@pytest.mark.parametrize('resume, states, error', [
    (0, (ServerStates.BUILDING.value,), BuildPending),
    (0, (ServerStates.BROKEN.value,), TimeoutError),
    (MAX_BUILD_RESUMES, (ServerStates.BUILDING.value,), TimeoutError),
    (None, (ServerStates.BUILDING.value,), TimeoutError),
])
def test_an_unfinished_server_wait_is_resumable_only_with_budget_and_live_children(resume, states, error):
    with build_execution(_execution(resume)):
        assert type(unfinished_build_error('waiting', _state_manager(*states))) is error


def test_an_unfinished_server_wait_outside_a_tracked_build_times_out():
    assert type(unfinished_build_error('waiting', Mock())) is TimeoutError


def test_child_messages_carry_the_parent_resume_count():
    with build_execution(_execution(0)):
        assert build_message_attempt() == {PubSub.EventAttributes.BUILD_ATTEMPT_ID: 'workout-attempt'}
    with build_execution(_execution(2)):
        assert build_message_attempt() == {
            PubSub.EventAttributes.BUILD_ATTEMPT_ID: 'workout-attempt',
            PubSub.EventAttributes.BUILD_RESUME: '2',
        }


def _pending_handler(monkeypatch, course_object, **attributes):
    db = _database()
    handler = _handler(db, course_object, target='workout-a', attempt='workout-attempt')
    handler.env_dict = {}
    handler.event_attributes.update(attributes)
    handler._dispatch = Mock(side_effect=BuildPending('Timed out waiting for servers'))
    publisher = Mock()
    monkeypatch.setattr(handler_module, 'PubSubManager', Mock(return_value=publisher))
    return db, handler, publisher


def test_handler_republishes_a_pending_parent_build_with_the_next_resume_count(monkeypatch):
    db, handler, publisher = _pending_handler(monkeypatch, PubSub.CourseObjects.WORKOUT, build_resume='1')

    handler.route()

    publisher.msg.assert_called_once_with(**{**handler.event_attributes, 'build_resume': 2})
    publisher.msg.return_value.result.assert_called_once()
    # A resumed delivery is the same build: no second start and no error.
    assert _build_events(db) == []


def test_handler_leaves_a_pending_server_to_its_parent(monkeypatch):
    db, handler, publisher = _pending_handler(
        monkeypatch, PubSub.CourseObjects.LAB_SERVER, server_name='workout-a-server',
    )

    handler.route()

    publisher.msg.assert_not_called()
    assert _build_events(db) == []
    assert db.get(DbCollections.SERVER, 'workout-a-server')['state'] == ServerStates.BUILDING.value


@pytest.mark.parametrize('attribute, debug, resume', [
    (None, False, 0), ('2', False, 2), ('not-a-number', False, 0), ('-4', False, 0), ('2', True, None),
])
def test_handler_reads_the_resume_count_and_never_resumes_a_debug_run(attribute, debug, resume):
    handler = _handler(_database(), PubSub.CourseObjects.WORKOUT, target='workout-a', attempt='workout-attempt')
    handler.debug_mode = debug
    if attribute is not None:
        handler.event_attributes['build_resume'] = attribute

    execution, _ = handler._execution()

    assert execution.resume == resume
    assert execution.resumable is (resume is not None and resume < MAX_BUILD_RESUMES)


def test_a_resumed_solo_workout_resends_only_the_servers_still_building():
    workout = object.__new__(SoloWorkout)
    workout.workout_id = 'workout-a'
    workout.pubsub_manager = Mock()
    workout.db_queries = Mock()
    workout.db_queries.get_servers.return_value = [
        {'name': 'kali', 'state': ServerStates.BUILDING.value},
        {'name': 'workout-a-display-guacamole-server', 'state': ServerStates.BUILDING.value},
        {'name': 'web', 'state': ServerStates.RUNNING.value},
        {'name': 'db', 'state': ServerStates.BROKEN.value},
    ]
    execution = _execution(1)
    execution.db.get.return_value = {'build_attempt_id': 'workout-attempt', 'state': 4}

    with build_execution(execution):
        workout._resume_server_builds()

    assert [sent.kwargs for sent in workout.pubsub_manager.msg.call_args_list] == [
        {'handler': 'BUILD', 'action': str(PubSub.Actions.BUILD.value), 'server_name': name,
         'course_object': str(PubSub.CourseObjects.LAB_SERVER.value),
         'build_attempt_id': 'workout-attempt', 'build_resume': '1'}
        for name in ('workout-a-kali', 'workout-a-display-guacamole-server')
    ]
