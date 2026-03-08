import logging
import string

from api.core.unit import Unit
from common.constants.states import UnitStates
from common.constants.build_constants import BuildConstants
from common.constants.database import DbCollections
from .wait_helpers import wait_for_state, check_state
from ...core.users import Users

logger = logging.getLogger(__name__)


async def build_unit_helper(env_dict, db, user_email: str, build_data: dict) -> str:
    """
    Helper function to build a unit and wait for it to be in READY/START state.
    Returns the unit_id.
    """
    # Build the unit
    logger.info("Starting unit build process.")
    unit_instance = Unit(env_dict=env_dict)
    requester = Users().get_user(user_email=user_email)
    unit_id = unit_instance.build(requester=requester, data=build_data)
    logger.info(f"Unit built successfully with ID: {unit_id}")

    # Validate the unit ID
    assert len(unit_id) == 10, f"Expected unit_id length 10, got {len(unit_id)}"
    assert all(char in string.ascii_lowercase for char in unit_id), \
        f"Expected all lowercase letters in unit_id, got {unit_id}"

    # If it’s a COMMUNITY unit, wait for READY state
    unit_object = db.get(collection_name=DbCollections.UNIT, doc_id=unit_id)
    if unit_object.get('type') == BuildConstants.UnitType.COMMUNITY.value:
        logger.info(f"Waiting for Unit {unit_id} to reach READY state...")
        unit_object = await wait_for_state(
            db=db,
            collection_name=DbCollections.UNIT,
            doc_id=unit_id,
            desired_state=UnitStates.READY.value,
            logger=logger,
            timeout=60
        )

    # Final validation
    assert check_state(unit_object.get('state'), [UnitStates.READY, UnitStates.START], DbCollections.UNIT), (
        f"Unit {unit_id} is not in READY or START state."
    )
    logger.info(f"Unit {unit_id} is READY.")
    return unit_id
