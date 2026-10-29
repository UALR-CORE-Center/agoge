"""C-1 follow-up: a workout ID alone may start/stop/extend a lab, but destroying or
rebuilding it needs the unit's instructor."""
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from common.constants.pub_sub import PubSub
from common.constants.states import WorkoutStates
from common.exceptions import Unauthorized
from common.models.users import AgogeUser, AnonymousAppUser
from common.utilities.id_generator import IdGenerator
from core.workout import Workout
from dependencies import get_optional_user
from routers.unit import unit_router

UNIT_ID = "klmnopqrst"
WORKOUT_ID = "abcdefghij"
INSTRUCTOR = "owner@example.edu"


def _workout(state=WorkoutStates.RUNNING.value):
    docs = {
        WORKOUT_ID: {"id": WORKOUT_ID, "parent_id": UNIT_ID, "state": state},
        UNIT_ID: {"id": UNIT_ID, "instructor_id": [INSTRUCTOR]},
    }
    workout = object.__new__(Workout)
    workout.class_name = "Workout"
    workout.collection = "workout"
    workout.db = MagicMock()
    workout.db.get.side_effect = lambda collection_name, doc_id: docs.get(doc_id)
    workout.pubsub_keys = PubSub.EventAttributes
    workout.logger = MagicMock()
    workout._send_or_debug = MagicMock()
    return workout


def _request(action):
    request = MagicMock()
    request.json = AsyncMock(return_value={"action": str(action)})
    request.client.host = "203.0.113.1"
    return request


def _user(email, admin=False):
    return MagicMock(spec=AgogeUser, email=email, is_admin=admin, is_authorized=True)


@pytest.mark.parametrize("action", [PubSub.Actions.START.value, PubSub.Actions.STOP.value,
                                    PubSub.Actions.EXTEND_RUNTIME.value])
async def test_anonymous_student_can_still_control_runtime(action):
    state = WorkoutStates.READY.value if action == PubSub.Actions.START.value else WorkoutStates.RUNNING.value
    workout = _workout(state)

    await workout.process_action(WORKOUT_ID, _request(action), requester=AnonymousAppUser())

    workout._send_or_debug.assert_called_once()


@pytest.mark.parametrize("action", Workout.INSTRUCTOR_ACTIONS)
async def test_anonymous_caller_cannot_destroy_or_rebuild(action):
    workout = _workout()

    with pytest.raises(Unauthorized):
        await workout.process_action(WORKOUT_ID, _request(action), requester=AnonymousAppUser())

    workout._send_or_debug.assert_not_called()


async def test_instructor_of_another_unit_cannot_nuke():
    workout = _workout()

    with pytest.raises(Unauthorized):
        await workout.process_action(
            WORKOUT_ID, _request(PubSub.Actions.NUKE.value), requester=_user("other@example.edu")
        )

    workout._send_or_debug.assert_not_called()


@pytest.mark.parametrize("requester", [_user(INSTRUCTOR), _user("admin@example.edu", admin=True)])
async def test_unit_instructor_or_admin_can_nuke(requester):
    workout = _workout()

    await workout.process_action(WORKOUT_ID, _request(PubSub.Actions.NUKE.value), requester=requester)

    workout._send_or_debug.assert_called_once()


def test_optional_user_is_anonymous_without_a_header():
    app = FastAPI()

    @app.get("/me")
    def me(user: AgogeUser = Depends(get_optional_user)):
        return {"anonymous": isinstance(user, AnonymousAppUser)}

    response = TestClient(app).get("/me")

    assert response.status_code == 200
    assert response.json() == {"anonymous": True}


@pytest.mark.parametrize("path", [f"/units/{UNIT_ID}/state/", f"/units/{UNIT_ID}/roster/"])
def test_unauthenticated_unit_listing_routes_are_gone(path):
    app = FastAPI()
    app.include_router(unit_router)

    assert TestClient(app).get(path).status_code == 404


def test_ids_keep_their_format():
    assert all(len(i) == 10 and i.isalpha() and i.islower() for i in (IdGenerator.build_id() for _ in range(50)))
    assert all(len(c) == 6 and c.isdigit() for c in (IdGenerator.join_code() for _ in range(50)))
