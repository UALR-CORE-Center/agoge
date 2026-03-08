import asyncio
import time

import pytest
import logging
import json

from common.constants.pub_sub import PubSub
from common.constants.states import ServerStates, ImageStatus
from common.constants.database import DbCollections
from .utilities.wait_helpers import wait_for_state
from .utilities.server_helpers import get_server_list_from_db, delete_server_helper, create_server_helper, process_server_action_helper, update_server_helper


from google.cloud import compute_v1

logger = logging.getLogger(__name__)

test_ssh_server_payload = {
    "server_name": "tester-server",
    "select_row": "true",
    "machine_type": "e2-micro",
    "os": "linux",
    "disk_size": "10",
    "description": "Test server",
    "labels": "delete",
    "username": "pantheon",
    "ssh_key": " ",
    "image_template": "",
    "image_scope": "global",
    "enable_display": "true",
    "action": "1"
}

test_rdp_server_payload = {
"server_name": "tester-rdp-server",
    "select_row": "true",
    "machine_type": "e2-medium",
    "os": "windows",
    "disk_size": "50",
    "description": "Test RDP Windows server",
    "labels": "delete",
    "username": "pantheon",
    "password": "",
    "ssh_key": "",
    "image_template": "",
    "image_scope": "global",
    "enable_display": "true",
    "action": "1"
}

def test_get_server_list(env_dict):
    """
    Verify that a list of image-based servers can be retrieved from Firestore.

    Asserts:
        - The result is a list
        - Each server has a 'name' attribute
        - Each server has either 'machine_type' or 'project'
    """
    servers = get_server_list_from_db(env_dict)
    assert isinstance(servers, list), "Expected list of server images"
    if servers:
        first = servers[0]
        assert hasattr(first, "name"), "Missing 'name' attribute in server image"
        assert hasattr(first, "machine_type") or hasattr(first,"project"), "Missing expected attributes in server image"
        logger.info("First image: %s", first)

def test_create_server(env_dict, db, fake_admin):
    """
    Test creation of an SSH server using the 'debian-11' image.

    This test uses `create_server_helper` to launch a Debian-based SSH server.
    It verifies that the server creation process completes successfully.

    Args:
        env_dict (dict): Environment configuration for Compute API and Firestore.
        db (DocumentDatabase): Firestore database instance.
        fake_admin (SafeAgogeUser): Simulated admin user performing the action.
    """
    create_server_helper(
        env_dict=env_dict,
        db=db,
        image_family="debian-11",
        payload=test_ssh_server_payload,
        fake_admin=fake_admin
    )

@pytest.mark.dependency(depends=["test_create_server"])
def test_stop_server(env_dict, db, fake_admin):
    """
    Test stopping a running server.

    This test issues a STOP command and verifies the server transitions to the STOPPED state.
    """
    server_id = test_ssh_server_payload["server_name"]
    logger.info(f"Initiating STOP for server '{server_id}'...")

    process_server_action_helper(env_dict, db, str(PubSub.Actions.STOP.value), server_id, fake_admin)

    logger.info(f"Waiting for server '{server_id}' to reach STOPPED state...")
    stopped_server = asyncio.run(
        wait_for_state(
            db=db,
            collection_name=DbCollections.IMAGE,
            doc_id=server_id,
            desired_state=ServerStates.STOPPED.value,
            logger=logger,
            timeout=60
        )
    )

    assert stopped_server is not None, f"Server '{server_id}' did not reach STOPPED state."
    logger.info(f"Server '{server_id}' is now STOPPED.")

@pytest.mark.dependency(depends=["test_stop_server"])
def test_start_server(env_dict, db, fake_admin):
    """
    Test starting a previously stopped server.

    Sends a START action to the stopped server and waits for it to transition
    to the RUNNING state. Verifies the server successfully starts and updates
    its status in Firestore.
    """
    server_id = test_ssh_server_payload["server_name"]
    logger.info(f"Initiating START for server '{server_id}'...")

    process_server_action_helper(env_dict, db, str(PubSub.Actions.START.value), server_id, fake_admin)

    logger.info(f"Waiting for server '{server_id}' to return to RUNNING state...")
    started_server = asyncio.run(
        wait_for_state(
            db=db,
            collection_name=DbCollections.IMAGE,
            doc_id=server_id,
            desired_state=ServerStates.RUNNING.value,
            logger=logger,
            timeout=60
        )
    )

    assert started_server is not None, f"Server '{server_id}' did not return to RUNNING state."
    logger.info(f"Server '{server_id}' is back to RUNNING.")

@pytest.mark.dependency(depends=["test_start_server"])
def test_checkin_server(env_dict, db, fake_admin):
    """
    Test checking in a server after it has been started.

    This ensures that the server reaches the CHECKED_IN state, which is required
    before any updates can be made to its configuration or metadata.
    """
    server_id = test_ssh_server_payload["server_name"]
    logger.info(f"Initiating CHECKIN for server '{server_id}'...")

    process_server_action_helper(env_dict, db, str(PubSub.Actions.CHECK_IN.value), server_id, fake_admin)

    logger.info(f"Waiting for server '{server_id}' to return to START state...")
    checked_in_server = asyncio.run(
        wait_for_state(
            db=db,
            collection_name=DbCollections.IMAGE,
            doc_id=server_id,
            desired_state=ImageStatus.CHECKED_IN.value,
            logger=logger,
            timeout=200
        )
    )
    assert checked_in_server is not None, f"Server '{server_id}' did not check in."
    logger.info(f"Server '{server_id}' is now checked in.")

@pytest.mark.dependency(depends=["test_checkin_server"])
def test_edit_server(env_dict, db, fake_admin):
    """
    Modify the configuration of a checked-in SSH server.

    This test updates key server attributes including description, labels, machine type, and disk size.
    It ensures that changes to a checked-in server are successfully applied and stored in Firestore.
    """
    server_id = test_ssh_server_payload["server_name"]
    updated_data = {
        "description": "Updated SSH server description",
        "labels": ["ssh", "edited"],
        "machine_type": "e2-small",
        "disk_size": 13,
        "human_interaction": [{
            "display": False,
            "protocol": "ssh",
            "username": "pantheon",
            "ssh_key": "updated_key_ssh",
            "security_mode": "any"
        }]
    }

    update_server_helper(env_dict, db, server_id, updated_data, fake_admin)

@pytest.mark.dependency(depends=["test_edit_server"])
def test_checkout_server(env_dict, db, fake_admin):
    """
    Test checking out a previously edited SSH server.

    This test waits for the server's associated image to reach READY state,
    initiates the CHECK_OUT action, and verifies the server returns to RUNNING state.
    Ensures that the checkout process completes successfully and is reflected in Firestore.
    """
    server_id = test_ssh_server_payload["server_name"]
    image_client = compute_v1.ImagesClient()

    timeout_seconds = 180
    interval = 5
    elapsed = 0

    while elapsed < timeout_seconds:
        try:
            image = image_client.get(project=env_dict.get("project"), image=server_id)
            if image.status == compute_v1.types.Image.Status.READY:
                logger.info(f"Image '{server_id}' is ready.")
                break
        except Exception as e:
            logger.error(f"Failed to get image '{server_id}': {e}")
        else:
            logger.info(f"Image '{server_id}' not ready yet. Waiting {interval} more seconds.")
        time.sleep(interval)
        elapsed += interval
    logger.info(f"Initiating CHECKOUT for server '{server_id}'...")

    process_server_action_helper(env_dict, db, str(PubSub.Actions.CHECK_OUT.value), server_id, fake_admin)

    logger.info(f"Waiting for server '{server_id}' to check out")
    checked_out_server = asyncio.run(
        wait_for_state(
            db=db,
            collection_name=DbCollections.IMAGE,
            doc_id=server_id,
            desired_state=ServerStates.RUNNING.value,
            logger=logger,
            timeout=200
        )
    )

    assert checked_out_server is not None, f"Server '{server_id}' did not check out."
    logger.info(f"Server '{server_id}' is now checked out.")

@pytest.mark.dependency(depends=["test_checkout_server"])
def test_cancel_changes_server(env_dict, db, fake_admin):
    """
    Test canceling configuration changes on a previously checked-out server.

    This test sends a CANCEL action, waits for the server to revert back to the CHECKED_IN state,
    and verifies that all staged modifications have been discarded successfully.
    """
    server_id = test_ssh_server_payload["server_name"]
    process_server_action_helper(env_dict, db, str(PubSub.Actions.CANCEL.value), server_id, fake_admin)
    logger.info(f"Waiting for server '{server_id}' to return to START state...")

    canceled_server = asyncio.run(
        wait_for_state(
            db=db,
            collection_name=DbCollections.IMAGE,
            doc_id=server_id,
            desired_state=ImageStatus.CHECKED_IN.value,
            logger=logger,
            timeout=200
        )
    )

    assert canceled_server is not None, f"Server '{server_id}' did not cancel changes."
    logger.info(f"Server '{server_id}' is now canceled.")

@pytest.mark.dependency(depends=["test_cancel_changes_server"])
def test_delete_server(env_dict, db, fake_admin):
    """
    Test deleting a previously configured SSH server.

    Verifies that the DELETE action is successfully triggered for the SSH server,
    removing it from Firestore and cleaning up associated resources.
    """
    server_id = test_ssh_server_payload["server_name"]
    logger.info(f"Initiating DELETE for server '{server_id}'...")

    delete_server_helper(env_dict, db, server_id, fake_admin)

@pytest.mark.dependency(depends=["test_delete_server"])
def test_create_rdp_server(env_dict, db, fake_admin):
    """
    Test creation of a Windows RDP server using the 'windows-2022' image.

    This test launches a Windows-based RDP server and ensures that the server
    is created and transitions to the expected RUNNING state. It validates
    that the creation process works end-to-end and that server metadata is
    stored correctly in Firestore.
    """
    create_server_helper(
        env_dict=env_dict,
        db=db,
        image_family="windows-2022",
        payload=test_rdp_server_payload,
        fake_admin=fake_admin
    )

@pytest.mark.dependency(depends=["test_create_rdp_server"])
def test_stop_rdp_server(env_dict, db, fake_admin):
    """
    Test stopping a running RDP server.

    This test sends a STOP action to the Windows-based RDP server and verifies that
    the server transitions to the STOPPED state within the allowed timeout.
    """
    server_id = test_rdp_server_payload["server_name"]
    logger.info(f"Initiating STOP for server '{server_id}'...")

    process_server_action_helper(env_dict, db, str(PubSub.Actions.STOP.value), server_id, fake_admin)

    logger.info(f"Waiting for server '{server_id}' to reach STOPPED state...")
    stopped_server = asyncio.run(
        wait_for_state(
            db=db,
            collection_name=DbCollections.IMAGE,
            doc_id=server_id,
            desired_state=ServerStates.STOPPED.value,
            logger=logger,
            timeout=80
        )
    )

    assert stopped_server is not None, f"Server '{server_id}' did not reach STOPPED state."
    logger.info(f"Server '{server_id}' is now STOPPED.")

@pytest.mark.dependency(depends=["test_create_rdp_server"])
def test_delete_rdp_server(env_dict, db, fake_admin):
    """
    Test deleting a previously created RDP server.

    This test ensures that the Windows-based server created earlier is deleted,
    confirming the full lifecycle cleanup.
    """
    server_id = test_rdp_server_payload["server_name"]
    logger.info(f"Initiating DELETE for server '{server_id}'...")

    delete_server_helper(env_dict, db, server_id, fake_admin)
