from unittest.mock import MagicMock

import pytest

from cloud_fn_utilities.state_managers.workout_states import WorkoutStatesManager
from common.constants.database import DbCollections
from common.constants.states import WorkoutStates


def _manager(existing_state: WorkoutStates, active: bool) -> WorkoutStatesManager:
    manager = object.__new__(WorkoutStatesManager)
    manager.s = WorkoutStates
    manager.class_name = "WorkoutStatesManager"
    manager.build_id = "abcdefghij"
    manager.collection = DbCollections.WORKOUT
    manager.model = MagicMock()
    manager.logger = MagicMock()
    manager.update_masks = ["state", "state_timestamp", "active"]
    manager.db = MagicMock()
    manager.db.get.return_value = {"id": "abcdefghij", "state": existing_state.value, "active": active}
    manager.update_record = MagicMock()
    return manager


def _written(manager: WorkoutStatesManager) -> dict:
    manager.update_record.assert_called_once()
    return manager.update_record.call_args.kwargs["data"]


@pytest.mark.parametrize("existing", [WorkoutStates.DELETING_SERVERS, WorkoutStates.COMPLETED_DELETING_SERVERS])
def test_deleted_workout_is_marked_inactive(existing):
    manager = _manager(existing, active=True)

    manager.state_transition(WorkoutStates.DELETED)

    written = _written(manager)
    assert written["state"] == WorkoutStates.DELETED.value
    assert written["active"] is False


def test_ready_workout_is_marked_active_even_off_the_allow_list():
    manager = _manager(WorkoutStates.RUNNING, active=False)

    assert manager.state_transition(WorkoutStates.READY) is False

    written = _written(manager)
    assert written["state"] == WorkoutStates.READY.value
    assert written["active"] is True


def test_invalid_transition_still_writes_state_and_returns_false():
    manager = _manager(WorkoutStates.RUNNING, active=True)

    assert manager.state_transition(WorkoutStates.BROKEN) is False

    written = _written(manager)
    assert written["state"] == WorkoutStates.BROKEN.value
    assert written["active"] is True
    assert written["prev_state"] == WorkoutStates.RUNNING.value


def test_not_built_workout_may_start_building_networks():
    manager = _manager(WorkoutStates.NOT_BUILT, active=False)

    assert manager.state_transition(WorkoutStates.BUILDING_NETWORKS) is True
