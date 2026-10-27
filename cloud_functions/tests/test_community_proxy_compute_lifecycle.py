"""Shared proxy cloud completion and delayed event handling, without guest gates."""
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from cloud_fn_utilities.course_objects.compute.lab_server_manager import LabServerManager
from common.constants.states import ServerStates
from common.exceptions import BaseAgogeException


def proxy_manager(state):
    value = object.__new__(LabServerManager)
    value.s = ServerStates
    value.server_spec = SimpleNamespace(community_proxy=True, wireguard_endpoint_id=None,
        wireguard_managed=False, guacamole_startup_script=None, delayed_start=False)
    value.state_manager = MagicMock()
    value.state_manager.get_state.return_value = state.value
    value.compute_instance = MagicMock()
    value.logger = MagicMock()
    value.class_name = 'LabServerManager'
    value.server_name = 'abcdefghij-display-guacamole-server'
    value.parent_build_id = 'abcdefghij'
    value.dns_manager = MagicMock()
    value.primary_external_ip = None
    value._dns_record = MagicMock(return_value='abcdefghij-display.example.test.')
    value._require_wireguard_provisionable = MagicMock()
    value._build_server = MagicMock()
    value._stage_wireguard_endpoint = MagicMock()
    value._mark_wireguard_endpoint_error = MagicMock()
    value._build_routes = MagicMock()
    value._wait_for_guacamole = MagicMock(side_effect=AssertionError('Guest health must not gate cloud completion'))
    return value


@pytest.mark.parametrize('state', [ServerStates.STARTING, ServerStates.STOPPING, ServerStates.STOPPED,
                                  ServerStates.EXPIRED, ServerStates.MISFIT, ServerStates.DELETING,
                                  ServerStates.DELETED])
def test_delayed_shared_proxy_build_cannot_resurrect_parked_or_retired_server(state):
    value = proxy_manager(state)
    value.build()
    value._build_server.assert_not_called()
    value.compute_instance.create.assert_not_called()
    value._require_wireguard_provisionable.assert_not_called()
    value.state_manager.state_transition.assert_not_called()


@pytest.mark.parametrize('state', [ServerStates.STOPPING, ServerStates.EXPIRED, ServerStates.MISFIT,
                                  ServerStates.DELETING, ServerStates.DELETED])
def test_stale_shared_proxy_start_is_ignored_during_teardown(state):
    value = proxy_manager(state)
    value.start()
    value.compute_instance.start.assert_not_called()
    value.state_manager.state_transition.assert_not_called()


def test_manual_start_from_stopped_is_valid_and_does_not_wait_for_guest_service():
    value = proxy_manager(ServerStates.STOPPED)
    value.compute_instance.start.return_value = True
    value.dns_manager.add_dns_record.return_value = True
    value.start()
    value.compute_instance.start.assert_called_once_with(resource_name=value.server_name, wait=True)
    value.dns_manager.add_dns_record.assert_called_once_with('abcdefghij-display.example.test.', value.server_name)
    assert value.state_manager.state_transition.call_args_list[-1].args == (ServerStates.RUNNING,)
    value._wait_for_guacamole.assert_not_called()


def test_build_dns_failure_never_reports_proxy_running():
    value = proxy_manager(ServerStates.READY)
    value.dns_manager.add_dns_record.return_value = False
    with pytest.raises(BaseAgogeException, match='Unable to publish DNS'):
        value.build()
    value._build_server.assert_called_once_with(finalize_state=False)
    value.state_manager.state_transition.assert_called_once_with(ServerStates.BROKEN)
    value._wait_for_guacamole.assert_not_called()


def test_start_dns_failure_can_retry_already_running_vm_without_another_start_rpc():
    value = proxy_manager(ServerStates.STOPPED)
    value.compute_instance.start.return_value = True
    value.dns_manager.add_dns_record.return_value = False
    with pytest.raises(BaseAgogeException, match='community display DNS'):
        value.start()
    assert value.state_manager.state_transition.call_args_list[-1].args == (ServerStates.STARTING,)
    value.state_manager.get_state.return_value = ServerStates.STARTING.value
    value.compute_instance.get.return_value = {'status': 'RUNNING'}
    value.dns_manager.add_dns_record.return_value = True
    value.start()
    value.compute_instance.start.assert_called_once()
    assert value.dns_manager.add_dns_record.call_count == 2
    assert value.state_manager.state_transition.call_args_list[-1].args == (ServerStates.RUNNING,)
    value._wait_for_guacamole.assert_not_called()
