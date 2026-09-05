import time
from types import SimpleNamespace
from unittest.mock import ANY, MagicMock, call

import pytest
from cloud_fn_utilities.course_objects.workout.community_workout import (
    CommunityWorkout,
)

from common.constants.database import DbCollections
from common.constants.pub_sub import PubSub
from common.constants.states import ServerStates, UnitStates, WorkoutStates


def _community_workout(*, builds_finished: bool) -> CommunityWorkout:
    workout = object.__new__(CommunityWorkout)
    workout.class_name = "CommunityWorkout"
    workout.workout_id = "workout-a"
    workout.unit_id = "unit-1"
    workout.unit_model = SimpleNamespace(
        id="unit-1",
        state=UnitStates.READY.value,
        unit_type="community",
    )
    workout.s = WorkoutStates
    workout.duration_seconds = 7200
    workout.debug = False
    workout.db = MagicMock()
    workout.db.transaction.return_value = True
    workout.db_queries = MagicMock()
    workout.db_queries.get_servers.return_value = [
        {"parent_id": "workout-a", "name": "kali"},
        {"parent_id": "workout-a", "name": "router"},
    ]
    workout.pubsub_manager = MagicMock()
    workout.publish_future = MagicMock()
    workout.pubsub_manager.msg.return_value = workout.publish_future
    workout.state_manager = MagicMock()
    workout.state_manager.get_state.return_value = WorkoutStates.READY.value
    workout.state_manager.are_server_builds_finished.return_value = builds_finished
    workout.logger = MagicMock()
    return workout


def _server_rebuild_call(server_name: str):
    return call(
        handler=str(PubSub.Handlers.CONTROL.value),
        action=str(PubSub.Actions.NUKE.value),
        build_id=server_name,
        network_prefix="unit-1",
        course_object=str(PubSub.CourseObjects.LAB_SERVER.value),
    )


def test_nuke_rebuilds_only_servers_parented_to_the_community_workout():
    workout = _community_workout(builds_finished=True)

    rebuilt = workout.nuke()

    assert rebuilt is True
    workout.db_queries.get_servers.assert_called_once_with(parent_id="workout-a")
    assert workout.db.update.call_args_list == [
        call(
            collection_name=DbCollections.SERVER,
            doc_id="workout-a-kali",
            data={
                "state": ServerStates.RESETTING.value,
                "state_timestamp": ANY,
            },
        ),
        call(
            collection_name=DbCollections.SERVER,
            doc_id="workout-a-router",
            data={
                "state": ServerStates.RESETTING.value,
                "state_timestamp": ANY,
            },
        ),
        call(
            collection_name=DbCollections.WORKOUT,
            doc_id="workout-a",
            data={"shutoff_timestamp": ANY},
        ),
    ]
    assert workout.pubsub_manager.msg.call_args_list == [
        _server_rebuild_call("workout-a-kali"),
        _server_rebuild_call("workout-a-router"),
    ]
    workout.state_manager.state_transition.assert_called_once_with(
        WorkoutStates.RUNNING
    )
    shutoff_timestamp = workout.db.update.call_args_list[-1].kwargs["data"][
        "shutoff_timestamp"
    ]
    assert shutoff_timestamp > time.time()
    assert workout.publish_future.result.call_args_list == [
        call(timeout=workout.REBUILD_PUBLISH_TIMEOUT_SECONDS),
        call(timeout=workout.REBUILD_PUBLISH_TIMEOUT_SECONDS),
    ]


def test_nuke_marks_the_workout_broken_when_server_rebuilds_time_out():
    workout = _community_workout(builds_finished=False)

    with pytest.raises(TimeoutError, match="Timed out"):
        workout.nuke()

    workout.state_manager.state_transition.assert_called_once_with(WorkoutStates.BROKEN)
    workout.logger.error.assert_called_once()


def test_nuke_marks_the_workout_broken_when_finalization_fails():
    workout = _community_workout(builds_finished=True)
    workout.db.update.side_effect = [
        None,
        None,
        RuntimeError("timestamp write failed"),
    ]

    with pytest.raises(RuntimeError, match="timestamp write failed"):
        workout.nuke()

    workout.state_manager.state_transition.assert_called_once_with(WorkoutStates.BROKEN)
    workout.logger.error.assert_called_once()


def test_nuke_refuses_to_run_while_the_unit_is_being_deleted():
    workout = _community_workout(builds_finished=True)
    workout.unit_model.state = UnitStates.DELETING_SERVERS.value

    rebuilt = workout.nuke()

    assert rebuilt is False
    workout.db_queries.get_servers.assert_not_called()
    workout.pubsub_manager.msg.assert_not_called()
    workout.state_manager.state_transition.assert_not_called()
    workout.logger.warning.assert_called_once()


def test_nuke_refuses_to_run_while_a_community_unit_is_starting():
    workout = _community_workout(builds_finished=True)
    workout.unit_model.state = UnitStates.START.value
    workout.unit_model.unit_type = "community"

    rebuilt = workout.nuke()

    assert rebuilt is False
    workout.db_queries.get_servers.assert_not_called()
    workout.pubsub_manager.msg.assert_not_called()
    workout.state_manager.state_transition.assert_not_called()
    workout.logger.warning.assert_called_once()


def test_nuke_does_not_overlap_an_already_claimed_workout():
    workout = _community_workout(builds_finished=True)
    workout.db.transaction.return_value = False

    rebuilt = workout.nuke()

    assert rebuilt is False
    workout.db.update.assert_not_called()
    workout.pubsub_manager.msg.assert_not_called()
    workout.state_manager.are_server_builds_finished.assert_not_called()
    workout.logger.warning.assert_called_once()


def test_debug_nuke_rebuilds_servers_directly_without_pubsub():
    workout = _community_workout(builds_finished=True)
    workout.debug = True
    workout.compute_manager = MagicMock()

    rebuilt = workout.nuke()

    assert rebuilt is True
    assert workout.compute_manager.load.call_args_list == [
        call(server_name="workout-a-kali", network_prefix="unit-1"),
        call(server_name="workout-a-router", network_prefix="unit-1"),
    ]
    assert workout.compute_manager.nuke.call_count == 2
    workout.pubsub_manager.msg.assert_not_called()


def test_rebuild_claim_atomically_moves_the_workout_into_a_building_state():
    workout = _community_workout(builds_finished=True)
    transaction = MagicMock()
    unit_ref = MagicMock()
    unit_snapshot = MagicMock()
    unit_snapshot.exists = True
    unit_snapshot.to_dict.return_value = {
        "state": UnitStates.READY.value,
        "unit_type": "community",
    }
    unit_ref.get.return_value = unit_snapshot
    workout_ref = MagicMock()
    workout_snapshot = MagicMock()
    workout_snapshot.exists = True
    workout_snapshot.to_dict.return_value = {
        "parent_id": "unit-1",
        "state": WorkoutStates.RUNNING.value,
    }
    workout_ref.get.return_value = workout_snapshot

    def document_reference(collection_name):
        if collection_name == DbCollections.UNIT.value:
            return MagicMock(document=MagicMock(return_value=unit_ref))
        return MagicMock(document=MagicMock(return_value=workout_ref))

    workout.db.db.collection.side_effect = document_reference

    claimed = workout._claim_workout_rebuild_transaction(transaction)

    assert claimed is True
    transaction.set.assert_called_once_with(
        workout_ref,
        {
            "action": PubSub.Actions.NUKE.value,
            "prev_state": WorkoutStates.RUNNING.value,
            "state": WorkoutStates.BUILDING_SERVERS.value,
            "state_timestamp": ANY,
        },
        merge=True,
    )


@pytest.mark.parametrize(
    "unit_state",
    [UnitStates.START.value, UnitStates.DELETING_SERVERS.value],
)
def test_rebuild_claim_rechecks_community_unit_state_in_the_transaction(unit_state):
    workout = _community_workout(builds_finished=True)
    transaction = MagicMock()
    unit_ref = MagicMock()
    unit_snapshot = MagicMock()
    unit_snapshot.exists = True
    unit_snapshot.to_dict.return_value = {
        "state": unit_state,
        "unit_type": "community",
    }
    unit_ref.get.return_value = unit_snapshot
    workout.db.db.collection.return_value.document.return_value = unit_ref

    claimed = workout._claim_workout_rebuild_transaction(transaction)

    assert claimed is False
    workout.db.db.collection.assert_called_once_with(DbCollections.UNIT.value)
    transaction.set.assert_not_called()


@pytest.mark.parametrize(
    "workout_document",
    [None, {"parent_id": "unit-1", "state": WorkoutStates.STARTING.value}],
)
def test_rebuild_claim_rejects_missing_or_ineligible_workout(workout_document):
    workout = _community_workout(builds_finished=True)
    transaction = MagicMock()
    unit_ref = MagicMock()
    unit_snapshot = MagicMock()
    unit_snapshot.exists = True
    unit_snapshot.to_dict.return_value = {
        "state": UnitStates.READY.value,
        "unit_type": "community",
    }
    unit_ref.get.return_value = unit_snapshot
    workout_ref = MagicMock()
    workout_snapshot = MagicMock()
    workout_snapshot.exists = workout_document is not None
    workout_snapshot.to_dict.return_value = workout_document
    workout_ref.get.return_value = workout_snapshot
    unit_collection = MagicMock()
    unit_collection.document.return_value = unit_ref
    workout_collection = MagicMock()
    workout_collection.document.return_value = workout_ref
    workout.db.db.collection.side_effect = [unit_collection, workout_collection]

    claimed = workout._claim_workout_rebuild_transaction(transaction)

    assert claimed is False
    transaction.set.assert_not_called()
