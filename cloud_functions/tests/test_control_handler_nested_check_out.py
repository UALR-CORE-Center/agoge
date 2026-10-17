"""A nested create's CHECK_OUT carries product keys to ImageTemplateManager.check_out and never into logs (PRD V12)."""
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

import main as main_module
from cloud_functions.handlers import control_handler as control_handler_module
from cloud_functions.handlers.control_handler import ControlHandler
from common.constants.pub_sub import PubSub

PRODUCT_KEY = 'ABCDE-FGHIJ-KLMNO-PQRST-UVWXY'


def _attributes(**extra):
    return {
        PubSub.EventAttributes.HANDLER: str(PubSub.Handlers.CONTROL.value),
        PubSub.EventAttributes.ACTION: str(PubSub.Actions.CHECK_OUT.value),
        PubSub.EventAttributes.IMAGE_NAME: 'ad-lab',
        PubSub.EventAttributes.COURSE_OBJECT: str(PubSub.CourseObjects.TEMPLATE_SERVER.value),
        **extra,
    }


def _route(attributes):
    env = MagicMock()
    env.get_env.return_value = {'project': 'agoge-test-project'}
    manager = MagicMock()
    with (
        patch.object(control_handler_module, 'CloudEnv', return_value=env),
        patch.object(control_handler_module, 'Logger') as logger_cls,
        patch.object(control_handler_module, 'PubSubManager'),
        patch.object(control_handler_module.DocumentDatabaseFactory, 'create_db_object'),
        patch.object(control_handler_module.ComputeManagerFactory, 'create_manager_object', return_value=manager),
    ):
        ControlHandler(event_attributes=attributes, env_dict={'project': 'agoge-test-project'}).route()
    return manager, logger_cls.return_value


def test_product_keys_reach_check_out():
    keys = {'ws01': PRODUCT_KEY}

    manager, _ = _route(_attributes(**{PubSub.EventAttributes.PRODUCT_KEYS: json.dumps(keys)}))

    manager.load.assert_called_once_with(server_name='ad-lab')
    manager.check_out.assert_called_once_with(product_keys=keys)


def test_check_out_without_product_keys_passes_an_empty_dict():
    manager, _ = _route(_attributes())

    manager.check_out.assert_called_once_with(product_keys={})


@pytest.mark.parametrize('raw', ['not json', '["ws01"]', f'"{PRODUCT_KEY}"'])
def test_malformed_product_keys_are_dropped_without_logging_them(raw):
    manager, logger = _route(_attributes(**{PubSub.EventAttributes.PRODUCT_KEYS: raw}))

    manager.check_out.assert_called_once_with(product_keys={})
    logger.error.assert_called_once()
    assert PRODUCT_KEY not in str(logger.error.call_args)


def test_main_routes_the_keys_but_redacts_them_from_every_log():
    attributes = _attributes(**{PubSub.EventAttributes.PRODUCT_KEYS: json.dumps({'ws01': PRODUCT_KEY})})
    context = SimpleNamespace(event_id='evt-1', timestamp='2026-10-17T00:00:00Z')
    with (
        patch.object(main_module, 'BudgetManager') as budget,
        patch.object(main_module, 'ControlHandler') as control_cls,
        patch.object(main_module, 'logger') as logger,
    ):
        budget.return_value.check_budget.return_value = True
        main_module.agoge_cloud_function({'attributes': attributes}, context)

    # The handler still receives the real keys.
    control_cls.assert_called_once_with(attributes, debug=False)
    assert logger.info.call_count >= 2
    for call in logger.method_calls:
        assert PRODUCT_KEY not in str(call)


def test_main_redacts_the_keys_when_the_handler_fails():
    attributes = _attributes(**{PubSub.EventAttributes.PRODUCT_KEYS: json.dumps({'ws01': PRODUCT_KEY})})
    context = SimpleNamespace(event_id='evt-1', timestamp='2026-10-17T00:00:00Z')
    with (
        patch.object(main_module, 'BudgetManager') as budget,
        patch.object(main_module, 'ControlHandler') as control_cls,
        patch.object(main_module, 'logger') as logger,
    ):
        budget.return_value.check_budget.return_value = True
        control_cls.return_value.route.side_effect = RuntimeError('boom')
        with pytest.raises(RuntimeError):
            main_module.agoge_cloud_function({'attributes': attributes}, context)

    logger.error.assert_called_once()
    assert PRODUCT_KEY not in str(logger.method_calls)
