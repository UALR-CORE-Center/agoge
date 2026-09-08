from unittest.mock import MagicMock, patch

from cloud_functions.handlers import control_handler as control_handler_module
from cloud_functions.handlers.control_handler import ControlHandler
from common.constants.pub_sub import PubSub


def test_lab_server_nuke_loads_the_unit_network_prefix():
    handler = object.__new__(ControlHandler)
    handler.course_object = str(PubSub.CourseObjects.LAB_SERVER.value)
    handler.build_id = "workout-a-kali"
    handler.network_prefix = "unit-1"
    handler.env_dict = {"project": "agoge-test-project"}

    compute_manager = MagicMock()
    with patch.object(
        control_handler_module.ComputeManagerFactory,
        "create_manager_object",
        return_value=compute_manager,
    ):
        handler._nuke()

    compute_manager.load.assert_called_once_with(
        server_name="workout-a-kali",
        network_prefix="unit-1",
    )
    compute_manager.nuke.assert_called_once_with()


def test_handler_reads_network_prefix_from_event_attributes():
    event_attributes = {
        PubSub.EventAttributes.ACTION: str(PubSub.Actions.NUKE.value),
        PubSub.EventAttributes.BUILD_ID: "workout-a-kali",
        PubSub.EventAttributes.COURSE_OBJECT: str(
            PubSub.CourseObjects.LAB_SERVER.value
        ),
        PubSub.EventAttributes.NETWORK_PREFIX: "unit-1",
    }
    env = MagicMock()
    env.get_env.return_value = {"project": "agoge-test-project"}

    with (
        patch.object(control_handler_module, "CloudEnv", return_value=env),
        patch.object(control_handler_module, "Logger"),
        patch.object(control_handler_module, "PubSubManager"),
        patch.object(
            control_handler_module.DocumentDatabaseFactory,
            "create_db_object",
        ),
    ):
        handler = ControlHandler(
            event_attributes=event_attributes,
            env_dict={"project": "agoge-test-project"},
        )

    assert handler.network_prefix == "unit-1"
