"""H-3/H-4: an instructor role is not enough to act on a Unit. Unit, rubric, snapshot and
teacher-doc operations require the requester to be one of the Unit's instructors (or an admin)."""
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from common.constants.database import DbCollections
from common.constants.pub_sub import PubSub
from common.constants.states import WorkoutStates
from common.exceptions import BadRequest, NotFound, Unauthorized
from common.models.agoge import RubricModel
from common.models.model_validators.model_validator import ModelValidator
from common.models.users import AgogeUser
from core.compute.snapshot import ComputeSnapshot
from core.docs import Docs
from core.rubric import Rubric
from core.unit import Unit
from core.unit_access import UnitAccess
from routers import unit as unit_routes

UNIT_ID = "klmnopqrst"
WORKOUT_ID = "abcdefghij"
OWNER = "owner@example.edu"
OTHER = "other@example.edu"
LAB_SERVER = f"{WORKOUT_ID}-kali"
TEMPLATE_SERVER = "template-kali"

RUBRIC = {
    "build_id": UNIT_ID,
    "headers": ["Excellent", "Poor"],
    "categories": ["Configuration"],
    "criteria": [],
}


def _docs():
    return {
        (DbCollections.UNIT, UNIT_ID): {
            "id": UNIT_ID, "instructor_id": [OWNER],
            "workspace_settings": {"expires": 1000},
            "summary": {"teacher_instructions_id": "teacher-doc"},
        },
        (DbCollections.WORKOUT, WORKOUT_ID): {
            "id": WORKOUT_ID, "parent_id": UNIT_ID, "expires": 1000,
            "state": WorkoutStates.RUNNING.value,
        },
        (DbCollections.SERVER, LAB_SERVER): {"name": "kali", "parent_id": WORKOUT_ID},
        (DbCollections.IMAGE, TEMPLATE_SERVER): {"name": TEMPLATE_SERVER},
        (DbCollections.RUBRIC, UNIT_ID): dict(RUBRIC),
        (DbCollections.INSTRUCTIONS, "teacher-doc"): {"uid": "teacher-doc", "content": "answers"},
    }


def _db(docs=None):
    docs = _docs() if docs is None else docs
    db = MagicMock()
    db.get.side_effect = lambda collection_name, doc_id: docs.get((collection_name, doc_id))
    db.query.return_value = [doc for (collection, _), doc in docs.items() if collection == DbCollections.WORKOUT]
    return db


def _user(email, admin=False):
    return MagicMock(spec=AgogeUser, uid=email, email=email, is_admin=admin, is_authorized=True)


def _request(body):
    request = MagicMock()
    request.json = AsyncMock(return_value=body)
    request.client.host = "203.0.113.1"
    return request


def _unit(db=None):
    unit = object.__new__(Unit)
    unit.collection = DbCollections.UNIT
    unit.db = db or _db()
    unit.logger = MagicMock()
    unit.pubsub_mgr = MagicMock()
    unit.handler = PubSub.Handlers
    unit.pubsub_actions = PubSub.Actions
    unit.workout_model_validator = MagicMock()
    unit.workout_model_validator.load.side_effect = lambda workouts: [
        MagicMock(id=w["id"], state=WorkoutStates.NOT_BUILT.value, student_email="s@example.edu")
        for w in workouts
    ]
    unit._reset_expiration = MagicMock()
    return unit


# --- UnitAccess -----------------------------------------------------------------------------

@pytest.mark.parametrize("requester", [_user(OWNER), _user(OTHER, admin=True)])
def test_owner_and_admin_resolve_every_build_object(requester):
    access = UnitAccess(_db())
    assert access.unit(UNIT_ID, requester)["id"] == UNIT_ID
    assert access.workout(WORKOUT_ID, requester)["id"] == WORKOUT_ID
    access.build(WORKOUT_ID, requester)
    access.build(UNIT_ID, requester)
    access.server(LAB_SERVER, requester)


def test_other_instructor_is_denied_every_build_object():
    access = UnitAccess(_db())
    for check, target in [(access.unit, UNIT_ID), (access.workout, WORKOUT_ID),
                          (access.build, WORKOUT_ID), (access.server, LAB_SERVER)]:
        with pytest.raises(Unauthorized):
            check(target, _user(OTHER))


def test_missing_unit_or_workout_is_not_found():
    access = UnitAccess(_db({}))
    with pytest.raises(NotFound):
        access.unit(UNIT_ID, _user(OWNER))
    with pytest.raises(NotFound):
        access.workout(WORKOUT_ID, _user(OWNER))


def test_template_servers_are_shared_by_all_instructors():
    UnitAccess(_db()).server(TEMPLATE_SERVER, _user(OTHER))


def test_deleted_lab_server_resolves_its_unit_through_its_snapshots():
    docs = _docs()
    del docs[(DbCollections.SERVER, LAB_SERVER)]
    docs[(DbCollections.SNAPSHOTS, LAB_SERVER)] = {"server_id": LAB_SERVER, "parent_build_id": WORKOUT_ID}
    access = UnitAccess(_db(docs))
    access.server(LAB_SERVER, _user(OWNER))
    with pytest.raises(Unauthorized):
        access.server(LAB_SERVER, _user(OTHER))


def test_image_named_like_a_lab_server_does_not_bypass_ownership():
    docs = _docs()
    del docs[(DbCollections.SERVER, LAB_SERVER)]
    docs[(DbCollections.IMAGE, LAB_SERVER)] = {"name": LAB_SERVER}
    with pytest.raises(Unauthorized):
        UnitAccess(_db(docs)).server(LAB_SERVER, _user(OTHER))


def test_server_with_no_known_owner_is_denied():
    with pytest.raises(Unauthorized):
        UnitAccess(_db()).server("zzzzzzzzzz-ghost", _user(OWNER))


# --- H-3: Unit routes -----------------------------------------------------------------------

def test_other_instructor_cannot_list_unit_workouts():
    unit = _unit()
    with pytest.raises(Unauthorized):
        unit.list_workouts(UNIT_ID, requester=_user(OTHER))
    assert [w.id for w in unit.list_workouts(UNIT_ID, requester=_user(OWNER))] == [WORKOUT_ID]


def test_other_instructor_cannot_build_all_workouts():
    unit = _unit()
    with pytest.raises(Unauthorized):
        unit.build_all(UNIT_ID, requester=_user(OTHER))
    unit.pubsub_mgr.msg.assert_not_called()

    unit.build_all(UNIT_ID, requester=_user(OWNER))
    unit.pubsub_mgr.msg.assert_called_once()


@pytest.mark.parametrize("body", [
    {"action": PubSub.Actions.START.value, "workout_ids": [WORKOUT_ID]},
    {"action": PubSub.Actions.STOP.value},
    {"action": PubSub.Actions.BUILD.value, "workout_ids": [WORKOUT_ID]},
    {"action": PubSub.Actions.RESET_EXPIRATION.value, "days": 2},
])
async def test_other_instructor_cannot_act_on_unit(body):
    unit = _unit()
    with pytest.raises(Unauthorized):
        await unit.process_action(UNIT_ID, _request(body), requester=_user(OTHER))
    unit.pubsub_mgr.msg.assert_not_called()
    unit._reset_expiration.assert_not_called()


async def test_owner_can_act_on_unit():
    unit = _unit()
    await unit.process_action(
        UNIT_ID, _request({"action": PubSub.Actions.START.value, "workout_ids": [WORKOUT_ID]}),
        requester=_user(OWNER),
    )
    unit.pubsub_mgr.msg.assert_called_once()


@pytest.mark.parametrize("days", [0, -3, 61, 2.5, "3", True, None])
async def test_reset_expiration_rejects_days_outside_one_to_sixty(days):
    unit = _unit()
    body = {"action": PubSub.Actions.RESET_EXPIRATION.value, "days": days}
    with pytest.raises(BadRequest):
        await unit.process_action(UNIT_ID, _request(body), requester=_user(OWNER))
    unit._reset_expiration.assert_not_called()


@pytest.mark.parametrize("days", [1, 60])
async def test_reset_expiration_accepts_days_within_cap(days):
    unit = _unit()
    body = {"action": PubSub.Actions.RESET_EXPIRATION.value, "days": days}
    await unit.process_action(UNIT_ID, _request(body), requester=_user(OWNER))
    unit._reset_expiration.assert_called_once_with(build_id=UNIT_ID, days=days)


async def test_non_numeric_action_is_bad_request():
    with pytest.raises(BadRequest):
        await _unit().process_action(UNIT_ID, _request({"action": "start"}), requester=_user(OWNER))


@pytest.mark.parametrize("method,path,body", [
    ("get", f"/units/{UNIT_ID}/workouts/", None),
    ("post", f"/units/{UNIT_ID}/", None),
    ("put", f"/units/{UNIT_ID}/", {"action": PubSub.Actions.STOP.value}),
])
def test_unit_routes_return_403_for_other_instructor(monkeypatch, method, path, body):
    unit = _unit()
    monkeypatch.setattr(unit_routes, "Unit", MagicMock(return_value=unit))
    app = FastAPI()
    app.include_router(unit_routes.unit_router)
    app.dependency_overrides[unit_routes.get_cloud_env] = lambda: {}
    app.dependency_overrides[unit_routes.teacher_required] = lambda: _user(OTHER)

    with TestClient(app) as client:
        response = client.request(method, path, json=body)

    assert response.status_code == 403
    unit.pubsub_mgr.msg.assert_not_called()


# --- H-4: rubrics ---------------------------------------------------------------------------

def _rubric(db=None):
    rubric = object.__new__(Rubric)
    rubric.collection = DbCollections.RUBRIC
    rubric.db = db or _db()
    rubric.logger = MagicMock()
    rubric.model_validator = ModelValidator(model=RubricModel)
    return rubric


def test_other_instructor_cannot_read_or_update_rubric():
    rubric = _rubric()
    with pytest.raises(Unauthorized):
        rubric.get(UNIT_ID, requester=_user(OTHER))
    assert rubric.get(UNIT_ID, requester=_user(OWNER)).build_id == UNIT_ID


async def test_other_instructor_cannot_update_rubric():
    rubric = _rubric()
    with pytest.raises(Unauthorized):
        await rubric.update(UNIT_ID, _request({"headers": ["A"]}), requester=_user(OTHER))
    rubric.db.update.assert_not_called()


async def test_rubric_update_is_validated_and_keeps_its_unit_id():
    rubric = _rubric()
    await rubric.update(UNIT_ID, _request({"headers": ["A", "B"], "build_id": "zzzzzzzzzz"}),
                        requester=_user(OWNER))
    saved = rubric.db.update.call_args.kwargs["data"]
    assert saved["build_id"] == UNIT_ID
    assert saved["headers"] == ["A", "B"]


async def test_invalid_rubric_update_is_not_written():
    rubric = _rubric()
    with pytest.raises(BadRequest):
        await rubric.update(UNIT_ID, _request({"headers": "not-a-list"}), requester=_user(OWNER))
    rubric.db.update.assert_not_called()


# --- H-4: snapshots -------------------------------------------------------------------------

def _snapshot(db=None):
    snapshot = object.__new__(ComputeSnapshot)
    snapshot.collection = DbCollections.SNAPSHOTS
    snapshot.db = db or _db()
    snapshot.access = UnitAccess(snapshot.db)
    snapshot.pubsub_manager = MagicMock()
    snapshot.pubsub_keys = PubSub.EventAttributes
    snapshot.logger = MagicMock()
    snapshot.env = MagicMock(project="agoge-test")
    return snapshot


@pytest.mark.parametrize("course_object", [
    PubSub.CourseObjects.LAB_SERVER.value,
    # The stored server record decides ownership, not the course object the caller sends
    PubSub.CourseObjects.TEMPLATE_SERVER.value,
])
def test_other_instructor_cannot_restore_snapshot_over_lab_server(course_object):
    snapshot = _snapshot()
    data = {"action": PubSub.Actions.RESTORE.value, "course_object": course_object,
            "snapshot_name": "snap-1"}
    with pytest.raises(Unauthorized):
        snapshot.process_server_action(LAB_SERVER, data, requester=_user(OTHER))
    snapshot.pubsub_manager.msg.assert_not_called()


def test_owner_can_restore_snapshot_over_lab_server():
    snapshot = _snapshot()
    data = {"action": PubSub.Actions.RESTORE.value,
            "course_object": PubSub.CourseObjects.LAB_SERVER.value, "snapshot_name": "snap-1"}
    snapshot.process_server_action(LAB_SERVER, data, requester=_user(OWNER))
    snapshot.pubsub_manager.msg.assert_called_once()


def test_lab_snapshot_parent_must_belong_to_requester():
    docs = _docs()
    docs[(DbCollections.UNIT, "uvwxyzabcd")] = {"id": "uvwxyzabcd", "instructor_id": [OTHER]}
    docs[(DbCollections.WORKOUT, "zyxwvutsrq")] = {"id": "zyxwvutsrq", "parent_id": "uvwxyzabcd"}
    snapshot = _snapshot(_db(docs))
    data = {"action": PubSub.Actions.SNAPSHOT.value,
            "course_object": PubSub.CourseObjects.LAB_SERVER.value, "build_id": "zyxwvutsrq"}
    with pytest.raises(Unauthorized):
        snapshot.process_server_action(LAB_SERVER, data, requester=_user(OWNER))
    snapshot.pubsub_manager.msg.assert_not_called()


def test_snapshot_list_action_publishes_nothing_if_any_workout_is_denied():
    docs = _docs()
    docs[(DbCollections.UNIT, "uvwxyzabcd")] = {"id": "uvwxyzabcd", "instructor_id": [OTHER]}
    docs[(DbCollections.WORKOUT, "zyxwvutsrq")] = {"id": "zyxwvutsrq", "parent_id": "uvwxyzabcd"}
    snapshot = _snapshot(_db(docs))
    data = {"items": [WORKOUT_ID, "zyxwvutsrq"], "action": PubSub.Actions.SNAPSHOT.value,
            "course_object": PubSub.CourseObjects.WORKOUT.value}
    with pytest.raises(Unauthorized):
        snapshot.process_action_on_list(data, requester=_user(OWNER))
    snapshot.pubsub_manager.msg.assert_not_called()


@pytest.mark.parametrize("build_id,course_object", [
    (WORKOUT_ID, PubSub.CourseObjects.WORKOUT.value),
    (UNIT_ID, PubSub.CourseObjects.UNIT.value),
    (LAB_SERVER, PubSub.CourseObjects.TEMPLATE_SERVER.value),
])
async def test_other_instructor_cannot_list_snapshots(build_id, course_object):
    with pytest.raises(Unauthorized):
        await _snapshot().list(build_id, course_object, requester=_user(OTHER))


async def test_other_instructor_cannot_read_server_snapshots():
    with pytest.raises(Unauthorized):
        await _snapshot().get(LAB_SERVER, requester=_user(OTHER))


# --- H-4: teacher instructions --------------------------------------------------------------

def _docs_handler():
    docs = object.__new__(Docs)
    docs.collection = DbCollections.INSTRUCTIONS
    docs.db = _db()
    return docs


async def test_teacher_instructions_require_unit_instructor():
    docs = _docs_handler()
    with pytest.raises(Unauthorized):
        await docs.get_instructions(UNIT_ID, DbCollections.UNIT, requester=_user(OTHER))
    with pytest.raises(Unauthorized):
        await docs.get_instructions(UNIT_ID, DbCollections.UNIT)
    result = await docs.get_instructions(UNIT_ID, DbCollections.UNIT, requester=_user(OWNER))
    assert result["content"] == "answers"
