import time
from unittest.mock import MagicMock

from common.constants.states import UnitStates
from core.unit import Unit


def _handler(records):
    handler = Unit.__new__(Unit)
    handler.class_name = 'Unit'
    handler.collection = 'unit'
    handler.logger = MagicMock()
    handler.db = MagicMock()
    handler.db.query.return_value = records
    handler.unit_model_validator = MagicMock()
    handler.unit_model_validator.load.side_effect = lambda units: units
    return handler


def test_active_admin_list_excludes_deleted_units_that_have_not_expired():
    future = int(time.time()) + 3600
    running = {'id': 'runningaaa', 'state': UnitStates.RUNNING.value, 'workspace_settings': {'expires': future}}
    deleted = {'id': 'deletedaaa', 'state': UnitStates.DELETED.value, 'workspace_settings': {'expires': future}}
    expired = {'id': 'expiredaaa', 'state': UnitStates.RUNNING.value, 'workspace_settings': {'expires': 1000}}
    handler = _handler([running, deleted, expired])

    units = handler.list(MagicMock(is_admin=True), active=True, expired=False, days=0, instructor=False)

    assert [unit['id'] for unit in units] == ['runningaaa']


def test_instructor_list_moves_deleted_units_to_expired():
    future = int(time.time()) + 3600
    running = {'id': 'runningaaa', 'state': UnitStates.RUNNING.value, 'workspace_settings': {'expires': future}}
    deleted = {'id': 'deletedaaa', 'state': UnitStates.DELETED.value, 'workspace_settings': {'expires': future}}
    expired = {'id': 'expiredaaa', 'state': UnitStates.RUNNING.value, 'workspace_settings': {'expires': 1000}}
    handler = _handler([running, deleted, expired])

    units = handler._get_instructor_units('teacher@example.edu')

    assert [unit['id'] for unit in units['active']] == ['runningaaa']
    assert [unit['id'] for unit in units['expired']] == ['deletedaaa', 'expiredaaa']
