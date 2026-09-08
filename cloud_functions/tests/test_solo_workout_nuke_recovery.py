from types import SimpleNamespace
from unittest.mock import ANY, MagicMock, call, patch

from cloud_fn_utilities.course_objects.workout.solo_workout import SoloWorkout
from cloud_fn_utilities.server_specific.guacamole.display_proxy import DisplayProxy

from common.constants.database import DbCollections
from common.constants.states import ServerStates, UnitStates, WorkoutStates
from common.models.agoge import ServerModel


def _solo_workout(*, servers: list[ServerModel], networks: list = None) -> SoloWorkout:
    workout = object.__new__(SoloWorkout)
    workout.class_name = "SoloWorkout"
    workout.workout_id = "workout-a"
    workout.workout = SimpleNamespace(
        build_type="workout",
        firewall_rules=[],
        networks=networks or [],
        servers=servers,
    )
    workout.unit_model = SimpleNamespace(
        id="unit-a",
        state=UnitStates.START.value,
        unit_type="solo",
    )
    workout.env = SimpleNamespace(parent_dns_suffix=".labs.example")
    workout.env_dict = {"project": "test-project"}
    workout.s = WorkoutStates
    workout.duration_seconds = 7200
    workout.debug = True
    workout.db = MagicMock()
    workout.db.transaction.return_value = True
    workout.db_queries = MagicMock()
    workout.db_queries.get_servers.return_value = []
    workout.compute_manager = MagicMock()
    workout.vpc_manager = MagicMock()
    workout.firewall_manager = MagicMock()
    workout.update_record = MagicMock(return_value=workout.workout)
    workout._recover_auxiliary_server_records = MagicMock(
        side_effect=lambda records: records
    )
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


def test_direct_nuke_repairs_solo_network_before_rebuilding_server():
    embedded_server = ServerModel(
        name="kali",
        image="image-kali",
        nics=[{"network": "external", "subnet_name": "default"}],
    )
    network = SimpleNamespace(name="external")
    workout = _solo_workout(servers=[embedded_server], networks=[network])
    operation_order = []
    workout.vpc_manager.build.side_effect = lambda **_: operation_order.append(
        "network"
    )
    workout.compute_manager.nuke.side_effect = lambda: operation_order.append(
        "server"
    )

    rebuilt = workout.nuke()

    assert rebuilt is True
    workout.vpc_manager.build.assert_called_once_with(network=network)
    assert operation_order == ["network", "server"]


def test_direct_nuke_recovers_and_rebuilds_a_missing_guacamole_server():
    embedded_server = ServerModel(
        name="kali",
        image="image-kali",
        nics=[{"network": "external", "subnet_name": "default"}],
    )
    main_server_record = {
        "parent_id": "workout-a",
        "name": "kali",
    }
    display_server_record = {
        "parent_id": "workout-a",
        "name": "display-guacamole-server",
    }
    workout = _solo_workout(
        servers=[embedded_server],
        networks=[SimpleNamespace(name="external")],
    )
    workout.db_queries.get_servers.return_value = [main_server_record]
    del workout._recover_auxiliary_server_records

    with patch(
        "cloud_fn_utilities.course_objects.workout.solo_workout.DisplayProxy"
    ) as display_proxy_cls:
        display_proxy = display_proxy_cls.return_value
        display_proxy.prepare_server_record.return_value = display_server_record

        rebuilt = workout.nuke()

    assert rebuilt is True
    display_proxy_cls.assert_called_once_with(
        build_id="workout-a",
        build_spec=workout.workout,
        collection=DbCollections.WORKOUT,
        env_dict={"project": "test-project"},
    )
    display_proxy.prepare_server_record.assert_called_once_with()
    assert workout.compute_manager.load.call_args_list == [
        call(server_name="workout-a-kali", network_prefix=None),
        call(
            server_name="workout-a-display-guacamole-server",
            network_prefix=None,
        ),
    ]
    assert workout.compute_manager.nuke.call_count == 2


def test_direct_nuke_does_not_recreate_an_existing_guacamole_record():
    embedded_server = ServerModel(
        name="kali",
        image="image-kali",
        nics=[{"network": "external", "subnet_name": "default"}],
    )
    workout = _solo_workout(
        servers=[embedded_server],
        networks=[SimpleNamespace(name="external")],
    )
    workout.db_queries.get_servers.return_value = [
        {"parent_id": "workout-a", "name": "kali"},
        {
            "parent_id": "workout-a",
            "name": "display-guacamole-server",
        },
    ]
    del workout._recover_auxiliary_server_records

    with patch(
        "cloud_fn_utilities.course_objects.workout.solo_workout.DisplayProxy"
    ) as display_proxy_cls:
        rebuilt = workout.nuke()

    assert rebuilt is True
    display_proxy_cls.assert_not_called()
    assert workout.compute_manager.nuke.call_count == 2


def test_direct_nuke_synchronizes_hostname_into_the_embedded_workout_server():
    embedded_server = ServerModel(
        name="kali",
        image="image-kali",
        nics=[
            {
                "network": "external",
                "subnet_name": "default",
                "direct_connect": True,
                "external_nat": True,
            }
        ],
        tags=[],
    )
    expected_hostname = "workout-a-kali.labs.example"
    workout = _solo_workout(
        servers=[embedded_server],
        networks=[SimpleNamespace(name="external")],
    )
    workout.db_queries.get_servers.return_value = [
        {
            "parent_id": "workout-a",
            "name": "kali",
            "hostname": expected_hostname,
            "tags": ["workout-a-direct-connect"],
        },
        {
            "parent_id": "workout-a",
            "name": "display-guacamole-server",
        },
    ]
    del workout._recover_auxiliary_server_records

    rebuilt = workout.nuke()

    assert rebuilt is True
    assert embedded_server.hostname == expected_hostname
    assert embedded_server.tags == ["workout-a-direct-connect"]
    assert embedded_server.parent_id == "workout-a"
    assert embedded_server.parent_build_type == "workout"
    workout.update_record.assert_called_once_with(
        doc_id="workout-a",
        data=workout.workout,
        update_keys=["servers"],
    )


def test_direct_nuke_repairs_a_missing_hostname_in_the_child_server_record():
    expected_hostname = "workout-a-kali.labs.example"
    embedded_server = ServerModel(
        name="kali",
        image="image-kali",
        nics=[
            {
                "network": "external",
                "subnet_name": "default",
                "direct_connect": True,
                "external_nat": True,
            }
        ],
        hostname=expected_hostname,
        tags=["workout-a-direct-connect"],
        parent_id="workout-a",
        parent_build_type="workout",
    )
    main_server_record = {
        "parent_id": "workout-a",
        "name": "kali",
        "hostname": None,
        "tags": [],
    }
    workout = _solo_workout(
        servers=[embedded_server],
        networks=[SimpleNamespace(name="external")],
    )
    workout.db_queries.get_servers.return_value = [
        main_server_record,
        {
            "parent_id": "workout-a",
            "name": "display-guacamole-server",
        },
    ]
    del workout._recover_auxiliary_server_records

    rebuilt = workout.nuke()

    assert rebuilt is True
    assert main_server_record["hostname"] == expected_hostname
    assert main_server_record["tags"] == ["workout-a-direct-connect"]
    workout.update_record.assert_not_called()
    workout.db.update.assert_any_call(
        collection_name=DbCollections.SERVER,
        doc_id="workout-a-kali",
        data={
            "hostname": expected_hostname,
            "tags": ["workout-a-direct-connect"],
        },
    )


def test_display_proxy_build_prepares_its_record_before_compute_creation():
    display_proxy = object.__new__(DisplayProxy)
    lifecycle = MagicMock()
    display_proxy.server_id = "workout-a-display-guacamole-server"
    display_proxy.prepare_server_record = lifecycle.prepare_server_record
    display_proxy.compute_manager = lifecycle.compute_manager

    display_proxy.build()

    assert lifecycle.mock_calls == [
        call.prepare_server_record(),
        call.compute_manager.load("workout-a-display-guacamole-server"),
        call.compute_manager.build(),
    ]
