from types import SimpleNamespace
from unittest.mock import MagicMock, call

import pytest
from google.api_core.exceptions import NotFound as GoogleNotFound

from cloud_fn_utilities.course_objects.compute.lab_server_manager import (
    LabServerManager,
)

from common.constants.states import ServerStates
from common.utilities.gcp.pubsub_manager import PubSubManager


def test_pubsub_msg_returns_the_publish_future():
    manager = object.__new__(PubSubManager)
    manager.topic_path = "projects/test/topics/agoge"
    manager.publisher = MagicMock()
    publish_future = MagicMock()
    manager.publisher.publish.return_value = publish_future

    result = manager.msg(action=8, build_id="workout-a", ignored=None)

    assert result is publish_future
    manager.publisher.publish.assert_called_once_with(
        manager.topic_path,
        data=b"Agoge PubSub Message",
        action="8",
        build_id="workout-a",
    )


def test_lab_server_nuke_does_not_build_after_a_failed_delete():
    manager = object.__new__(LabServerManager)
    manager.server_name = "workout-a-kali"
    manager.delete = MagicMock(return_value=False)
    manager.build = MagicMock()

    with pytest.raises(RuntimeError, match="server deletion failed"):
        manager.nuke()

    manager.build.assert_not_called()


def test_lab_server_nuke_builds_after_a_successful_delete():
    manager = object.__new__(LabServerManager)
    manager.server_name = "workout-a-kali"
    manager.delete = MagicMock(return_value=True)
    manager.build = MagicMock()

    manager.nuke()

    manager.build.assert_called_once_with()


def test_lab_server_nuke_does_not_build_when_compute_delete_times_out():
    manager = object.__new__(LabServerManager)
    manager.server_name = "workout-a-kali"
    manager.class_name = "LabServerManager"
    manager.s = ServerStates
    manager.state_manager = MagicMock()
    manager.logger = MagicMock()
    manager.compute_instance = MagicMock()
    manager.compute_instance.delete.return_value = False
    manager.build = MagicMock()

    with pytest.raises(RuntimeError, match="server deletion failed"):
        manager.nuke()

    assert manager.state_manager.state_transition.call_args_list == [
        call(ServerStates.DELETING),
        call(ServerStates.BROKEN),
    ]
    manager.build.assert_not_called()


def test_lab_server_nuke_builds_when_compute_instance_is_already_absent():
    manager = object.__new__(LabServerManager)
    manager.server_name = "workout-a-kali"
    manager.parent_build_id = "workout-a"
    manager.class_name = "LabServerManager"
    manager.s = ServerStates
    manager.state_manager = MagicMock()
    manager.logger = MagicMock()
    manager.compute_instance = MagicMock()
    manager.compute_instance.delete.side_effect = GoogleNotFound(
        "The instance was not found"
    )
    manager._dns_record = MagicMock(return_value=False)
    manager.build = MagicMock()

    manager.nuke()

    assert manager.state_manager.state_transition.call_args_list == [
        call(ServerStates.DELETING),
        call(ServerStates.DELETED),
    ]
    manager.logger.info.assert_any_call(
        "LabServerManager:workout-a-kali - Server is already absent; "
        "continuing with the rebuild."
    )
    manager.build.assert_called_once_with()


def test_start_waits_for_guacamole_when_server_has_its_startup_script():
    manager = object.__new__(LabServerManager)
    manager.server_name = "workout-a-display-guacamole-server"
    manager.parent_build_id = "workout-a"
    manager.class_name = "LabServerManager"
    manager.s = ServerStates
    manager.server_spec = SimpleNamespace(
        delayed_start=False,
        guacamole_startup_script="#!/bin/bash",
    )
    manager.state_manager = MagicMock()
    manager.logger = MagicMock()
    manager.compute_instance = MagicMock()
    manager.compute_instance.start.return_value = True
    manager.dns_manager = MagicMock()
    manager._dns_record = MagicMock(return_value="workout-a-display.example.")
    manager._wait_for_guacamole = MagicMock(return_value=True)

    manager._start_server()

    manager._wait_for_guacamole.assert_called_once_with(
        "workout-a-display.example"
    )
    assert manager.state_manager.state_transition.call_args_list == [
        call(ServerStates.STARTING),
        call(ServerStates.RUNNING),
    ]
