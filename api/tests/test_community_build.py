import pytest
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List

from .utilities.build_unit_helpers import build_unit_helper
from .utilities.build_workouts_helpers import build_workouts_helper
from .utilities.workout_helpers import student_connection_helper, stop_workout_helper, start_workout_helper
from .utilities.delete_unit_helpers import delete_unit_helper
from .utilities.wait_helpers import check_state
from common.constants.states import WorkoutStates, ServerStates
from common.constants.database import DbCollections

logger = logging.getLogger(__name__)

build_input = {
    'user_email': 'instructor@example.com',
    'input_data': {
        'registration_required': False,
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
async def built_workouts(db, env_dict, built_unit):
    """
    Build two workouts, and wait for RUNNING state. Then return the list of the two workout_ids.
    """
    workouts = await build_workouts_helper(db=db, env_dict=env_dict, unit_id=built_unit, num_workouts=2)
    for workout_id, workout_object in workouts:
        assert check_state(workout_object.get('state'), [WorkoutStates.RUNNING], DbCollections.WORKOUT), (
            f"Workout {workout_id} is not in RUNNING state."
        )
        logger.info(f"Workout {workout_id} is built and RUNNING.")
    return [workout_id for workout_id, _ in workouts]


@pytest.mark.dependency(depends=["test_build_unit"])
@pytest.mark.asyncio
async def test_build_workouts(built_workouts, built_unit):
    """
    Test that the workout was built successfully.
    """
    assert built_workouts is not None, "built_workout returned None"
    logger.info(f"Workouts {built_workouts} successfully built for unit {built_unit}")


@pytest.mark.dependency(depends=["test_build_workout"])
@pytest.mark.asyncio
async def test_student_connections(db, env_dict, built_workouts):
    """
    Test the connectivity for the new workout.
    """
    for workout_id in built_workouts:
        await student_connection_helper(db, env_dict, workout_id)


@pytest.mark.dependency(depends=["test_student_connection"])
def test_stop_first_workout(
    db,
    env_dict: Dict[str, Any],
    test_client: Any,
    built_workouts: List[Dict[str, Any]]
):
    """
    Test stopping the first workout and ensuring community servers remain active for the second workout.
    """
    # Stop the first workout
    stop_workout_id = built_workouts[0]
    stop_workout_helper(test_client, stop_workout_id)

    stopped_workout = db.get(collection_name=DbCollections.WORKOUT, doc_id=stop_workout_id)

    # Check the state of community servers in the stopped workout
    for server in stopped_workout.get("servers", []):
        is_community_server = server.get("community_server", False)
        if is_community_server:
            server_state = server.get("state")
            assert check_state(server_state, [ServerStates.RUNNING], DbCollections.SERVER), (
                f"Community server '{server.get('name')}' in workout '{stopped_workout.get('name', 'unknown')}' "
                f"should still be running, but it is in state '{server_state}'."
            )



@pytest.mark.dependency(depends=["test_stop_first_workout"])
def test_stop_second_workout(
    db,
    test_client,
    built_workouts: List[str]
):
    """
    Test stopping the last workout and ensuring all servers have stopped.
    """
    # Stop the 2nb workout
    stop_workout_id = built_workouts[1]
    stop_workout_helper(test_client, stop_workout_id)
    stopped_workout = db.get(collection_name=DbCollections.WORKOUT, doc_id=stop_workout_id)

    # Check the state of community servers in the stopped workout
    for server in stopped_workout.get("servers", []):
        is_community_server = server.get("community_server", False)
        if is_community_server:
            server_state = server.get("state")
            assert check_state(server_state, [ServerStates.STOPPED], DbCollections.SERVER), (
                f"Community server '{server.get('name')}' in workout '{stopped_workout.get('name', 'unknown')}' "
                f"should still be running, but it is in state '{server_state}'."
            )


@pytest.mark.dependency(depends=["test_stop_second_workout"])
def test_start_first_workout(db, test_client, built_workouts):
    """
    Now test starting the first workout again and determining whether the community servers started with the new workout.
    """
    # Stop the 2nb workout
    start_workout_id = built_workouts[0]
    start_workout_helper(test_client, start_workout_id)
    started_workout = db.get(collection_name=DbCollections.WORKOUT, doc_id=start_workout_id)

    # Check the state of community servers in the stopped workout
    for server in started_workout.get("servers", []):
        is_community_server = server.get("community_server", False)
        if is_community_server:
            server_state = server.get("state")
            assert check_state(server_state, [ServerStates.RUNNING], DbCollections.SERVER), (
                f"Community server '{server.get('name')}' in workout '{started_workout.get('name', 'unknown')}' "
                f"should still be running, but it is in state '{server_state}'."
            )


@pytest.mark.order("last")
def test_delete_unit(db, test_client, built_unit, fake_admin, env_dict):
    """
    Test deleting the unit (and clean up).
    """
    delete_unit_helper(
        db=db,
        built_unit=built_unit,
        env_dict=env_dict,
        fake_admin=fake_admin
    )
