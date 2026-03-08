import asyncio
import logging
import time

from common.constants.database import DbCollections, DbOperators
from common.constants.states import ServerStates
from core.compute.image import ComputeImage
from common.models.users import SafeAgogeUser
from tests.utilities.wait_helpers import wait_for_state

logger = logging.getLogger(__name__)

def get_server_list_from_db(env_dict):
    """
    Helper to retrieve the list of server images using the ComputeImage service.
    """
    logger.info("Retrieving server images via ComputeImage service...")
    image_docs = ComputeImage(env_dict).list_images()
    logger.info("Retrieved %d images from ComputeImage.", len(image_docs))
    return image_docs

def create_server_helper(env_dict, db, image_family, payload, fake_admin: SafeAgogeUser):
    """
    Creates a new server using the provided payload and waits for it to reach the RUNNING state.

    Args:
        env_dict (dict): Environment configuration dictionary including project and zone settings.
        db (DocumentDatabase): Database instance used to retrieve and update server data.
        image_family (str): The base image family to filter for when selecting an image template.
        payload (dict): Server creation parameters including name, image template, and configuration.
        fake_admin (SafeAgogeUser): A mock or test user object with admin permissions.

    Returns:
        dict: The server document from the database once it reaches the RUNNING state.

    Raises:
        AssertionError: If the image template is not found or the server fails to reach RUNNING state.
    """
    server_id = payload["server_name"]
    logger.info(f"Creating server '{server_id}' with payload: {payload}")

    logger.info(f"Fetching a valid {image_family} image UUID")
    images = db.query(
        collection_name=DbCollections.GOOGLE_IMAGES,
        filters=[
            ("is_enabled", DbOperators.EQUAL, True),
            ("family", DbOperators.EQUAL, image_family),
        ]
    )
    assert images, f"No valid {image_family} image found in the database."
    payload["image_template"] = images[0]["uuid"]

    ComputeImage(env_dict).create_image_server(fake_admin, payload)

    logger.info(f"Waiting for server '{server_id}' to reach RUNNING state.")
    created_server = asyncio.run(
        wait_for_state(
            db=db,
            collection_name=DbCollections.IMAGE,
            doc_id=server_id,
            desired_state=ServerStates.RUNNING.value,
            logger=logger,
            timeout=120,
        )
    )

    assert created_server, f"Failed to reach RUNNING state for {server_id}."
    logger.info(f"Server '{server_id}' reached RUNNING state.")

    created_server_data = db.get(
        collection_name=DbCollections.IMAGE,
        doc_id=server_id,
    )
    assert created_server_data, f"Failed to retrieve server data for {server_id}."
    logger.info(f"Server '{server_id}' successfully created and data confirmed.")

def process_server_action_helper(env_dict, db, action, server_id: str, fake_admin: SafeAgogeUser):
    image_data = db.get(collection_name=DbCollections.IMAGE, doc_id=server_id)
    if not image_data:
        raise ValueError(f"No server data found for {server_id}")
    payload = {
        "images": [image_data],
        "action": action,
    }

    ComputeImage(env_dict).process_action_on_list(user=fake_admin.email, data=payload)
    logger.info(f"Processing action '{action}' on server '{server_id}'.")

def update_server_helper(env_dict, db, server_id: str, updated_data, fake_admin: SafeAgogeUser):
    image_service = ComputeImage(env_dict)
    image_service.update_image(server_id, updated_data)

    updated_doc = db.get(collection_name=DbCollections.IMAGE, doc_id=server_id)
    assert updated_doc, f"Failed to retrieve image data for {server_id}."
    for key, value in updated_data.items():
        if isinstance(value, list):
            if key == "human_interaction":
                continue
            assert updated_doc.get(key) == value, f"Failed to update {key} on server '{server_id}'."
        elif isinstance(value, dict):
            for subkey, subval in value.items():
                assert updated_doc.get(key, {}).get(subkey) == subval, f"Failed to update {key} on server '{server_id}'."
        else:
            if key == "disk_size":
                assert str(updated_doc.get("add_disk")) == str(
                    value), f"Failed to update {key} (as add_disk) on server '{server_id}'."
            else:
                assert str(updated_doc.get(key)) == str(value), f"Failed to update {key} on server '{server_id}'."

    logger.info(f"Updated {updated_data} on server '{server_id}'.")

def delete_server_helper(env_dict, db, server_id: str, fake_admin: SafeAgogeUser):
    image_service = ComputeImage(env_dict)
    image_service.delete(server_id)
    logger.info("Triggered deletion for server %s", server_id)

    timeout = 60
    interval = 5
    elapsed = 0
    while elapsed < timeout:
        deleted_server = db.get(collection_name=DbCollections.IMAGE, doc_id=server_id)
        if deleted_server is None:
            break
        time.sleep(interval)
        elapsed += interval

    final_check = db.get(collection_name=DbCollections.IMAGE, doc_id=server_id)
    if final_check is None or final_check == {}:
        logger.info(f"Server '{server_id}' has been successfully deleted.")
    else:
        raise AssertionError(f"Server '{server_id}' was not fully deleted after {timeout} seconds.")
    logger.info(f"Server '{server_id}' has been successfully deleted.")
