from types import SimpleNamespace
from unittest.mock import ANY, MagicMock, call

from cloud_fn_utilities.course_objects.workout.solo_workout import SoloWorkout

from common.constants.database import DbCollections
from common.constants.states import ServerStates, UnitStates, WorkoutStates
from common.models.agoge import ServerModel


def _solo_workout(*, servers: list[ServerModel]) -> SoloWorkout:
    workout = object.__new__(SoloWorkout)
    workout.class_name = "SoloWorkout"
    workout.workout_id = "workout-a"
    workout.workout = SimpleNamespace(
        build_type="workout",
        firewall_rules=[],
        servers=servers,
    )
    workout.unit_model = SimpleNamespace(
        id="unit-a",
        state=UnitStates.START.value,
        unit_type="solo",
    )
    workout.env = SimpleNamespace(parent_dns_suffix=".labs.example")
    workout.s = WorkoutStates
    workout.duration_seconds = 7200
    workout.debug = True
    workout.db = MagicMock()
    workout.db.transaction.return_value = True
    workout.db_queries = MagicMock()
    workout.db_queries.get_servers.return_value = []
    workout.compute_manager = MagicMock()
    workout.state_manager = MagicMock()
    workout.state_manager.get_state.return_value = WorkoutStates.READY.value
    workout.state_manager.are_server_builds_finished.return_value = True
    workout.logger = MagicMock()
    return workout


def test_direct_nuke_recovers_a_missing_solo_server_record_from_the_workout():
    embedded_server = ServerModel(
        name="kali",
        image="image-kali",
        nics=[
            {
                "network": "external",
                "subnet_name": "default",
                "internal_ip": "10.1.1.30",
                "external_nat": True,
                "direct_connect": True,
            }
        ],
        tags=[],
    )
    workout = _solo_workout(servers=[embedded_server])

    rebuilt = workout.nuke()

    assert rebuilt is True
    recovery_write = workout.db.update.call_args_list[0]
    assert recovery_write.kwargs["collection_name"] == DbCollections.SERVER
    assert recovery_write.kwargs["doc_id"] == "workout-a-kali"
    recovered = recovery_write.kwargs["data"]
    assert recovered["name"] == "kali"
    assert recovered["parent_id"] == "workout-a"
    assert recovered["parent_build_type"] == "workout"
    assert recovered["hostname"] == "workout-a-kali.labs.example"
    assert recovered["tags"] == ["workout-a-direct-connect"]
    assert embedded_server.parent_id is None

    assert workout.db.update.call_args_list[1] == call(
        collection_name=DbCollections.SERVER,
        doc_id="workout-a-kali",
        data={
            "state": ServerStates.RESETTING.value,
            "state_timestamp": ANY,
        },
    )
    workout.compute_manager.load.assert_called_once_with(
        server_name="workout-a-kali",
        network_prefix=None,
    )
    workout.compute_manager.nuke.assert_called_once_with()
    assert workout.db.update.call_args_list[-1] == call(
        collection_name=DbCollections.WORKOUT,
        doc_id="workout-a",
        data={"active": True, "shutoff_timestamp": ANY},
    )
    workout.state_manager.state_transition.assert_called_once_with(
        WorkoutStates.RUNNING
    )
    workout.logger.warning.assert_called_once()


def test_direct_nuke_still_refuses_when_no_server_spec_can_be_recovered():
    workout = _solo_workout(servers=[])

    rebuilt = workout.nuke()

    assert rebuilt is False
    workout.db.transaction.assert_not_called()
    workout.db.update.assert_not_called()
    workout.compute_manager.load.assert_not_called()
    workout.logger.warning.assert_called_once()
