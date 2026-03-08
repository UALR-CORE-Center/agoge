import pytest
import logging
from datetime import datetime, timedelta

from .utilities.build_unit_helpers import build_unit_helper
from .utilities.build_workouts_helpers import build_workouts_helper
from .utilities.workout_helpers import student_connection_helper, stop_workout_helper
from .utilities.delete_unit_helpers import delete_unit_helper
from .utilities.wait_helpers import check_state
from common.constants.states import WorkoutStates
from common.constants.database import DbCollections

logger = logging.getLogger(__name__)

build_input = {
    'user_email': 'philip@bastazo.com',
    'input_data': {
        'registration_required': True,
        'build_file': 'certbot#5205',
        'build_count': 2,
        'lms_integration': False,
        'test': True
    }
}


@pytest.fixture(scope='module')
@pytest.mark.asyncio
async def built_unit(env_dict, db) -> str:
    """
    Fixture to build a unit and return the unit_id.
    """
    user_email = build_input.get("user_email", "default@example.com")
    input_data = build_input.get("input_data", {})
    input_data['expires'] = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%dT%H:%M:%S')

    # Call utility function
    return await build_unit_helper(env_dict, db, user_email, input_data)


@pytest.mark.dependency()
@pytest.mark.asyncio
async def test_build_unit(built_unit):
    """
    Test building a unit.
    """
    assert built_unit is not None, "built_unit returned None"
    logger.info(f"Unit built successfully with ID: {built_unit}")


@pytest.fixture(scope='module')
@pytest.mark.asyncio
async def built_workout(db, env_dict, built_unit, debug):
    """
    Fixture to build a workout, wait for RUNNING, and return the workout_id.
    """
    workouts = await build_workouts_helper(db=db, env_dict=env_dict, unit_id=built_unit, num_workouts=1, debug=debug)
    workout_id, workout_object = workouts[0]
    assert check_state(workout_object.get('state'), [WorkoutStates.RUNNING], DbCollections.WORKOUT), (
        f"Workout {workout_id} is not in RUNNING state."
    )
    logger.info(f"Workout {workout_id} is RUNNING.")
    return workout_id


@pytest.mark.dependency(depends=["test_build_unit"])
@pytest.mark.asyncio
async def test_build_workout(built_workout):
    """
    Test that the workout was built successfully.
    """
    assert built_workout is not None, "built_workout returned None"
    logger.info(f"Workout built successfully with ID: {built_workout}")


@pytest.mark.dependency(depends=["test_build_workout"])
@pytest.mark.asyncio
async def test_student_connection(db, env_dict, built_workout):
    """
    Test the connectivity for the new workout.
    """
    await student_connection_helper(db, env_dict, built_workout)


@pytest.mark.dependency(depends=["test_student_connection"])
def test_stop_workout(env_dict, test_client, built_workout):
    """
    Test stopping the workout.
    """
    stop_workout_helper(test_client, built_workout)


@pytest.mark.dependency(depends=["test_stop_workout"])
def test_delete_unit(db, test_client, built_unit, built_workout, fake_admin, env_dict):
    """
    Test deleting the unit (and clean up).
    """
    delete_unit_helper(
        db=db,
        built_unit=built_unit,
        env_dict=env_dict,
        fake_admin=fake_admin
    )
