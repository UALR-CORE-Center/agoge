import logging
import asyncio
from typing import List, Tuple

from api.core.workout import Workout
from common.constants.states import WorkoutStates
from common.constants.database import DbCollections
from .wait_helpers import wait_for_state

logger = logging.getLogger(__name__)


async def build_workouts_helper(
    db,
    env_dict: dict,
    unit_id: str,
    num_workouts: int = 1,
    return_first: bool = False,
    debug: bool = False
) -> List[Tuple[str, dict]]:
    """
    Helper function to build multiple workouts and wait for their states.

    If return_first is True, returns the first workout that reaches RUNNING.
    Otherwise, waits for all workouts to finish and returns their IDs and state objects.

    Returns:
        List of tuples (workout_id, workout_object).
    """
    # Fetch Unit data
    unit_object = db.get(collection_name=DbCollections.UNIT, doc_id=unit_id)
    input_data = {
        "join_code": unit_object.get("join_code"),
        "accessibility_features": False,
    }

    # Initialize the Workout instance
    workout_instance = Workout(env_dict=env_dict)

    # Build workouts
    logger.info(f"Building {num_workouts} workouts...")
    workout_ids = await asyncio.gather(
        *[_build_workout(workout_instance, input_data, i, debug) for i in range(num_workouts)]
    )

    # Monitor workout states
    tasks = [asyncio.create_task(_monitor_workout_state(db, w_id)) for w_id in workout_ids]

    if return_first:
        # Wait for the first workout to reach RUNNING
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        completed_task = next(iter(done))
        return [completed_task.result()]
    else:
        # Wait for all workouts to reach RUNNING
        return await asyncio.gather(*tasks)


async def _build_workout(
    workout_instance, input_data: dict, index: int, debug: bool
) -> str:
    """
    Build a single workout and return its ID.
    """
    input_data["input_email"] = f"test_case{index + 1}@example.com"
    input_data["debug"] = debug
    workout_id, _ = workout_instance.build(data=input_data)
    logger.info(f"Workout {workout_id} initiated.")
    return workout_id


async def _monitor_workout_state(
    db, workout_id: str, timeout: int = 150
) -> Tuple[str, dict]:
    """
    Monitor a workout until it reaches the RUNNING state.
    Returns the workout ID and its state object.
    """
    logger.info(f"Waiting for Workout {workout_id} to reach RUNNING state...")
    workout_object = await wait_for_state(
        db=db,
        collection_name=DbCollections.WORKOUT,
        doc_id=workout_id,
        desired_state=WorkoutStates.RUNNING.value,
        logger=logger,
        timeout=timeout,
    )
    logger.info(f"Workout {workout_id} is RUNNING.")
    return workout_id, workout_object
