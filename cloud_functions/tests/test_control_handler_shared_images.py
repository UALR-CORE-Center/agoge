"""Shared image authorization must survive control routing and queued cleanup."""

from unittest.mock import MagicMock, patch

import pytest

from cloud_functions.handlers import control_handler as control_handler_module
from cloud_functions.handlers.control_handler import ControlHandler
from common.constants.pub_sub import PubSub


@pytest.mark.parametrize('action,method,field', [
    (PubSub.Actions.START, '_start', 'community_start_claim'),
    (PubSub.Actions.STOP, '_stop', 'community_stop_claim'),
])
def test_automatic_community_claim_survives_queued_control_dispatch(action, method, field):
    handler = object.__new__(ControlHandler)
    handler.course_object = str(PubSub.CourseObjects.LAB_SERVER.value)
    handler.build_id = 'abcdefghij-wireguard'
    handler.env_dict = {'project': 'agoge-test-project'}
    handler.event_attributes = {field: 'current-claim-token'}
    compute = MagicMock()
    with patch.object(control_handler_module.ComputeManagerFactory, 'create_manager_object', return_value=compute):
        getattr(handler, method)()

    getattr(compute, action.name.lower()).assert_called_once_with(**{field: 'current-claim-token'})


@pytest.mark.parametrize('authorization,expected', [
    (None, False), ('false', False), ('true', True), ('1', False), (True, False),
])
@pytest.mark.parametrize('action,method', [
    (PubSub.Actions.CHECK_OUT, 'check_out'),
    (PubSub.Actions.CHECK_IN, 'check_in'),
    (PubSub.Actions.DELETE, 'delete_server'),
    (PubSub.Actions.CANCEL, 'cancel'),
])
def test_template_control_uses_only_explicit_api_authorization(authorization, expected, action, method):
    event_attributes = {
        PubSub.EventAttributes.ACTION: str(action.value),
        PubSub.EventAttributes.IMAGE_NAME: 'image-shared-server',
        PubSub.EventAttributes.COURSE_OBJECT: str(PubSub.CourseObjects.TEMPLATE_SERVER.value),
    }
    if authorization is not None:
        event_attributes['shared_edit_authorized'] = authorization
    env = MagicMock()
    env.get_env.return_value = {'project': 'agoge-test-project'}
    compute_manager = MagicMock()

    with (
        patch.object(control_handler_module, 'CloudEnv', return_value=env),
        patch.object(control_handler_module, 'Logger'),
        patch.object(control_handler_module, 'PubSubManager'),
        patch.object(control_handler_module.DocumentDatabaseFactory, 'create_db_object'),
        patch.object(
            control_handler_module.ComputeManagerFactory, 'create_manager_object', return_value=compute_manager,
        ) as factory,
    ):
        handler = ControlHandler(event_attributes=event_attributes, env_dict={'project': 'agoge-test-project'})
        handler.route()

    assert factory.call_args.kwargs['shared_edit_authorized'] is expected
    compute_manager.load.assert_called_once_with(server_name='image-shared-server')
    getattr(compute_manager, method).assert_called_once()
