from types import SimpleNamespace
from unittest.mock import MagicMock, call

import pytest
from cloud_deployment import setup_manager as setup_manager_module
from cloud_deployment.operations.project_maintenance.rebuild_workouts import (
    RebuildWorkouts,
)
from cloud_deployment.setup_manager import SetupManager
from cloud_deployment.utilities.menu_options import (
    PROJECT_MAINTENANCE_REGISTRY,
    ProjectMaintenanceOptions,
)

from common.constants.database import DbCollections
from common.constants.pub_sub import PubSub
from common.constants.states import UnitStates, WorkoutStates

PROJECT = "agoge-test-project"
UNIT = {
    "id": "unit-1",
    "state": UnitStates.READY.value,
    "unit_type": "community",
    "summary": {"name": "Routing Lab"},
}


def _workout(workout_id: str, state: int, **values) -> dict:
    return {
        "id": workout_id,
        "parent_id": UNIT["id"],
        "state": state,
        **values,
    }


def _operation(answers: list[str], workouts: list[dict]):
    db = MagicMock()
    current_workouts = {workout["id"]: workout for workout in workouts}

    def get_document(collection_name, doc_id):
        if collection_name == DbCollections.UNIT:
            return UNIT
        return current_workouts.get(doc_id, {})

    db.get.side_effect = get_document

    db_queries = MagicMock()
    db_queries.get_active.return_value = [UNIT]
    db_queries.get_children.return_value = workouts

    pubsub_manager = MagicMock()
    answer_iter = iter(answers)
    operation = RebuildWorkouts(
        project=PROJECT,
        db=db,
        db_queries=db_queries,
        pubsub_manager=pubsub_manager,
        input_func=lambda _: next(answer_iter),
    )
    return operation, db, db_queries, pubsub_manager


def _rebuild_call(workout_id: str):
    return call(
        handler=str(PubSub.Handlers.CONTROL.value),
        action=str(PubSub.Actions.NUKE.value),
        course_object=str(PubSub.CourseObjects.WORKOUT.value),
        build_id=workout_id,
    )


def test_full_unit_queues_each_rebuildable_workout_and_skips_unsafe_states(
    capsys,
):
    workouts = [
        _workout("workout-running", WorkoutStates.RUNNING.value),
        _workout("workout-building", WorkoutStates.BUILDING_SERVERS.value),
        _workout("workout-ready", WorkoutStates.READY.value),
        _workout("workout-broken", WorkoutStates.BROKEN.value),
    ]
    operation, _, db_queries, pubsub_manager = _operation(
        answers=["1", "1", "REBUILD"],
        workouts=workouts,
    )

    operation.run()

    db_queries.get_active.assert_called_once_with(collection_name=DbCollections.UNIT)
    db_queries.get_children.assert_called_once_with(
        parent_id=UNIT["id"],
        child_collection=DbCollections.WORKOUT,
    )
    assert pubsub_manager.msg.call_args_list == [
        _rebuild_call("workout-broken"),
        _rebuild_call("workout-ready"),
        _rebuild_call("workout-running"),
    ]
    assert pubsub_manager.msg.call_count == 3
    assert pubsub_manager.msg.return_value.result.call_count == 3

    output = capsys.readouterr().out
    assert "shared Community infrastructure is preserved" in output
    assert "workout-building" in output
    assert "Rebuild requests queued: 3" in output
    assert "Workouts skipped: 1" in output


def test_individual_selection_accepts_ids_and_numbers_and_deduplicates(capsys):
    workouts = [
        _workout("workout-a", WorkoutStates.READY.value),
        _workout("workout-b", WorkoutStates.DELETED.value),
        _workout("workout-c", WorkoutStates.BROKEN.value),
    ]
    operation, _, _, pubsub_manager = _operation(
        answers=["unit-1", "2", "1, workout-c 1 2", "REBUILD"],
        workouts=workouts,
    )

    operation.run()

    assert pubsub_manager.msg.call_args_list == [
        _rebuild_call("workout-a"),
        _rebuild_call("workout-c"),
    ]
    output = capsys.readouterr().out
    assert "workout-b" in output
    assert "Workouts skipped: 1" in output


def test_rechecks_workout_state_immediately_before_queueing(capsys):
    workouts = [_workout("workout-a", WorkoutStates.READY.value)]
    operation, db, _, pubsub_manager = _operation(
        answers=["1", "1", "REBUILD"],
        workouts=workouts,
    )

    def get_document(collection_name, doc_id):
        if collection_name == DbCollections.UNIT:
            return UNIT
        return _workout("workout-a", WorkoutStates.STARTING.value)

    db.get.side_effect = get_document

    operation.run()

    pubsub_manager.msg.assert_not_called()
    output = capsys.readouterr().out
    assert "no longer eligible" in output
    assert "Rebuild requests queued: 0" in output
    assert "Workouts skipped: 1" in output


def test_confirmation_must_match_exactly(capsys):
    workouts = [_workout("workout-a", WorkoutStates.READY.value)]
    operation, _, _, pubsub_manager = _operation(
        answers=["1", "1", "rebuild"],
        workouts=workouts,
    )

    operation.run()

    pubsub_manager.msg.assert_not_called()
    assert "Confirmation did not match" in capsys.readouterr().out


def test_no_units_returns_without_prompting_or_publishing(capsys):
    input_func = MagicMock()
    db_queries = MagicMock()
    db_queries.get_active.return_value = []
    pubsub_manager = MagicMock()
    operation = RebuildWorkouts(
        project=PROJECT,
        db=MagicMock(),
        db_queries=db_queries,
        pubsub_manager=pubsub_manager,
        input_func=input_func,
    )

    operation.run()

    input_func.assert_not_called()
    pubsub_manager.msg.assert_not_called()
    assert "No rebuildable Units" in capsys.readouterr().out


def test_units_in_transitional_or_teardown_states_are_not_offered(capsys):
    input_func = MagicMock()
    db_queries = MagicMock()
    db_queries.get_active.return_value = [
        {**UNIT, "state": UnitStates.START.value},
        {**UNIT, "state": UnitStates.BUILDING_SERVERS.value},
        {**UNIT, "id": "unit-expired", "state": UnitStates.EXPIRED.value},
        {**UNIT, "id": "unit-deleting", "state": UnitStates.DELETING_SERVERS.value},
    ]
    pubsub_manager = MagicMock()
    operation = RebuildWorkouts(
        project=PROJECT,
        db=MagicMock(),
        db_queries=db_queries,
        pubsub_manager=pubsub_manager,
        input_func=input_func,
    )

    operation.run()

    input_func.assert_not_called()
    pubsub_manager.msg.assert_not_called()
    assert "No rebuildable Units" in capsys.readouterr().out


def test_solo_unit_in_start_state_is_offered(capsys):
    solo_unit = {
        **UNIT,
        "unit_type": "solo",
        "state": UnitStates.START.value,
    }
    db_queries = MagicMock()
    db_queries.get_active.return_value = [solo_unit]
    db_queries.get_children.return_value = []
    operation = RebuildWorkouts(
        project=PROJECT,
        db=MagicMock(),
        db_queries=db_queries,
        pubsub_manager=MagicMock(),
        input_func=lambda _: "1",
    )

    operation.run()

    assert "has no Workouts" in capsys.readouterr().out


def test_unit_state_is_rechecked_before_each_publish(capsys):
    workouts = [
        _workout("workout-a", WorkoutStates.READY.value),
        _workout("workout-b", WorkoutStates.READY.value),
    ]
    operation, db, _, pubsub_manager = _operation(
        answers=["1", "1", "REBUILD"],
        workouts=workouts,
    )
    unit_reads = iter(
        [
            UNIT,
            {**UNIT, "state": UnitStates.DELETING_SERVERS.value},
        ]
    )

    def get_document(collection_name, doc_id):
        if collection_name == DbCollections.UNIT:
            return next(unit_reads)
        return next(workout for workout in workouts if workout["id"] == doc_id)

    db.get.side_effect = get_document

    operation.run()

    assert pubsub_manager.msg.call_args_list == [_rebuild_call("workout-a")]
    output = capsys.readouterr().out
    assert "Unit unit-1 is no longer eligible" in output
    assert "Workouts skipped: 1" in output


def test_unit_without_workouts_returns_without_publishing(capsys):
    operation, _, db_queries, pubsub_manager = _operation(
        answers=["1"],
        workouts=[],
    )

    operation.run()

    db_queries.get_children.assert_called_once_with(
        parent_id=UNIT["id"],
        child_collection=DbCollections.WORKOUT,
    )
    pubsub_manager.msg.assert_not_called()
    assert "has no Workouts" in capsys.readouterr().out


def test_invalid_unit_selection_retries_and_scope_can_cancel(capsys):
    workouts = [_workout("workout-a", WorkoutStates.READY.value)]
    operation, _, _, pubsub_manager = _operation(
        answers=["not-a-unit", "1", "0"],
        workouts=workouts,
    )

    operation.run()

    pubsub_manager.msg.assert_not_called()
    output = capsys.readouterr().out
    assert "Select a listed Unit number" in output
    assert "Workout rebuild cancelled" in output


def test_queue_failure_does_not_prevent_later_requests(capsys):
    workouts = [
        _workout("workout-a", WorkoutStates.READY.value),
        _workout("workout-b", WorkoutStates.BROKEN.value),
    ]
    operation, _, _, pubsub_manager = _operation(
        answers=["1", "1", "REBUILD"],
        workouts=workouts,
    )
    pubsub_manager.msg.side_effect = [RuntimeError("publisher unavailable"), None]

    operation.run()

    assert pubsub_manager.msg.call_args_list == [
        _rebuild_call("workout-a"),
        _rebuild_call("workout-b"),
    ]
    output = capsys.readouterr().out
    assert "Rebuild requests queued: 1" in output
    assert "Queue failures: 1" in output
    assert "Failed Workout IDs: workout-a" in output


def test_publish_acknowledgement_failure_is_reported_as_a_queue_failure(capsys):
    workouts = [_workout("workout-a", WorkoutStates.READY.value)]
    operation, _, _, pubsub_manager = _operation(
        answers=["1", "1", "REBUILD"],
        workouts=workouts,
    )
    pubsub_manager.msg.return_value.result.side_effect = TimeoutError(
        "publish acknowledgement timed out"
    )

    operation.run()

    output = capsys.readouterr().out
    assert "Rebuild requests queued: 0" in output
    assert "Queue failures: 1" in output
    assert "No rebuild requests were queued" in output


def test_constructor_rejects_an_environment_for_a_different_project():
    cloud_env = SimpleNamespace(
        project="some-other-project",
        get_env=lambda: {"project": "some-other-project"},
    )

    with pytest.raises(ValueError, match="does not match"):
        RebuildWorkouts(
            project=PROJECT,
            db=MagicMock(),
            db_queries=MagicMock(),
            cloud_env=cloud_env,
        )


def test_project_maintenance_menu_registers_rebuild_before_back():
    rebuild_items = [
        item
        for item in PROJECT_MAINTENANCE_REGISTRY
        if item["option"] == ProjectMaintenanceOptions.REBUILD_WORKOUTS
    ]

    assert len(rebuild_items) == 1
    assert rebuild_items[0]["operation_class"] is RebuildWorkouts
    assert PROJECT_MAINTENANCE_REGISTRY[-1]["option"] == ProjectMaintenanceOptions.BACK


def test_setup_manager_passes_the_selected_project_to_project_aware_operations(
    monkeypatch,
):
    received_projects = []

    class ProjectAwareOperation:
        REQUIRES_PROJECT = True

        def __init__(self, project):
            received_projects.append(project)

        def run(self):
            return None

    selections = iter(
        [
            ProjectMaintenanceOptions.REBUILD_WORKOUTS,
            ProjectMaintenanceOptions.BACK,
        ]
    )
    monkeypatch.setattr(
        setup_manager_module,
        "display_project_maintenance_menu",
        lambda: None,
    )
    monkeypatch.setattr(
        setup_manager_module,
        "get_user_selection",
        lambda _: 1,
    )
    monkeypatch.setattr(
        setup_manager_module,
        "get_project_maintenance_selection",
        lambda _: next(selections),
    )
    monkeypatch.setattr(
        setup_manager_module,
        "get_project_maintenance_operation",
        lambda _: ProjectAwareOperation,
    )

    manager = SetupManager(
        selection=None,
        project=PROJECT,
    )
    manager._run_project_maintenance_menu()

    assert received_projects == [PROJECT]
