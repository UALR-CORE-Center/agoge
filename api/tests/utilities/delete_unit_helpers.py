import logging
import asyncio

from common.constants.database import DbCollections, DbOperators
from common.constants.states import UnitStates
from ...core.unit import Unit
from .wait_helpers import wait_for_state, check_state

logger = logging.getLogger(__name__)


def delete_unit_helper(db, built_unit: str, env_dict, fake_admin):
    """
    Helper that deletes a unit, waits for it to be DELETED,
    and cleans up the database entries.
    """
    logger.info(f"Starting deletion process for Unit {built_unit}...")
    unit_obj = Unit(env_dict=env_dict)
    unit_obj.delete(requester=fake_admin, build_id=built_unit)

    # Wait for DELETED state
    logger.info(f"Waiting for Unit {built_unit} to reach DELETED state...")
    unit_object = asyncio.run(
        wait_for_state(
            db=db,
            collection_name=DbCollections.UNIT,
            doc_id=built_unit,
            desired_state=UnitStates.DELETED.value,
            logger=logger,
            timeout=200
        )
    )
    assert unit_object, f"Unit {built_unit} did not reach the DELETED state within the timeout period."

    assert check_state(unit_object.get('state'), [UnitStates.DELETED], DbCollections.UNIT), (
        f"Unit {built_unit} is not in {UnitStates.DELETED.value} state."
    )
    logger.info(f"Unit {built_unit} successfully transitioned to DELETED state.")

    # Cleanup leftover DB entries
    logger.info(f"Cleaning up database entries for Unit {built_unit}")

    filters = [('parent_id', DbOperators.EQUAL, built_unit)]
    servers = db.query(collection_name=DbCollections.SERVER, filters=filters)
    for server in servers:
        db.delete(collection_name=DbCollections.SERVER, doc_id=server.get('id'))

    workouts = db.query(collection_name=DbCollections.WORKOUT, filters=filters)
    for workout in workouts:
        db.delete(collection_name=DbCollections.WORKOUT, doc_id=workout.get('id'))
        filters = [('parent_id', DbOperators.EQUAL, workout.get('id'))]
        servers = db.query(collection_name=DbCollections.SERVER, filters=filters)
        for server in servers:
            db.delete(collection_name=DbCollections.SERVER, doc_id=server.get('id'))
    db.delete(collection_name=DbCollections.UNIT, doc_id=built_unit)
    logger.info(f"Cleanup complete. Unit {built_unit} removed from the database.")
