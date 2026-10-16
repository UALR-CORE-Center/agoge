"""Joining a CTF unit: the email resolves through the roster (CTF_BOARD members) to the team's
shared workout; anyone else is refused with NotOnRoster. Non-CTF units keep their old behavior."""
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from common.constants.database import DbCollections, DbOperators
from common.constants.pub_sub import PubSub
from common.constants.states import WorkoutStates
from common.exceptions import Forbidden, NotOnRoster
from core.workout import Workout
from routers import workout as workout_routes

CTF_ID = "ctfaaaaaaa"
UNIT_ID = "unitaaaaaa"
JOIN_CODE = "JOIN-CODE"
RED, BLUE = "wkredaaaaa", "wkblueaaaa"


class FakeDb:
    def __init__(self):
        self.docs = {c: {} for c in DbCollections}
        self.queries = []

    def query(self, collection_name, filters=None):
        self.queries.append((collection_name, filters))
        out = []
        for doc in self.docs[collection_name].values():
            ok = True
            for field, op, value in filters or []:
                if op == DbOperators.EQUAL:
                    ok &= doc.get(field) == value
                elif op == DbOperators.ARRAY_CONTAINS:
                    ok &= value in (doc.get(field) or [])
                else:
                    raise AssertionError(op)
            if ok:
                out.append(dict(doc))
        return out


def make_workout(db, debug=False):
    workout = object.__new__(Workout)
    workout.db = db
    workout.collection = DbCollections.WORKOUT
    workout.env = MagicMock(max_workspaces=100)
    workout.pubsub_manager = MagicMock()
    workout.pubsub_keys = PubSub.EventAttributes
    workout.handler = PubSub.Handlers
    workout.logger = MagicMock()
    return workout


def board(workout_id, members, ctf_id=CTF_ID, active=True):
    return {"id": f"{ctf_id}-{workout_id}", "workout_id": workout_id, "ctf_id": ctf_id, "active": active,
            "members": members}


@pytest.fixture
def db():
    fake = FakeDb()
    fake.docs[DbCollections.UNIT][UNIT_ID] = {
        "id": UNIT_ID, "join_code": JOIN_CODE, "ctf_event_id": CTF_ID,
        "workspace_settings": {"count": 2, "registration_required": True},
    }
    fake.docs[DbCollections.WORKOUT][RED] = {
        "id": RED, "parent_id": UNIT_ID, "state": WorkoutStates.NOT_BUILT.value, "student_email": "a@x.edu",
    }
    fake.docs[DbCollections.WORKOUT][BLUE] = {
        "id": BLUE, "parent_id": UNIT_ID, "state": WorkoutStates.RUNNING.value, "student_email": "c@x.edu",
    }
    fake.docs[DbCollections.CTF_BOARD]["red"] = board(RED, ["a@x.edu", "b@x.edu"])
    fake.docs[DbCollections.CTF_BOARD]["blue"] = board(BLUE, ["c@x.edu"])
    return fake


def join(workout, email):
    return workout.build({"input_email": email, "join_code": JOIN_CODE})


def test_rostered_email_resolves_to_its_team_workout_and_builds_it_when_not_built(db):
    workout = make_workout(db)

    assert join(workout, "a@x.edu") == (RED, True)

    attrs = PubSub.EventAttributes
    workout.pubsub_manager.msg.assert_called_once_with(**{
        attrs.HANDLER: str(PubSub.Handlers.BUILD.value),
        attrs.ACTION: str(PubSub.Actions.BUILD.value),
        attrs.COURSE_OBJECT: str(PubSub.CourseObjects.WORKOUT.value),
        attrs.KEY_TYPE: str(DbCollections.WORKOUT.value),
        attrs.BUILD_ID: RED,
    })


def test_teammate_with_a_different_email_gets_the_same_workout(db):
    # b@x.edu is not the workout's student_email; the roster is what maps it to the team.
    assert join(make_workout(db), "b@x.edu") == (RED, True)


def test_email_is_normalized_before_the_roster_lookup(db):
    assert join(make_workout(db), "  B@X.Edu ") == (RED, True)


def test_already_built_team_workout_is_returned_without_publishing(db):
    workout = make_workout(db)
    assert join(workout, "c@x.edu") == (BLUE, True)
    workout.pubsub_manager.msg.assert_not_called()


def test_unknown_email_raises_not_on_roster_and_publishes_nothing(db):
    workout = make_workout(db)
    with pytest.raises(NotOnRoster):
        join(workout, "stranger@x.edu")
    workout.pubsub_manager.msg.assert_not_called()


def test_not_on_roster_is_a_forbidden_so_older_callers_still_see_a_refusal():
    assert issubclass(NotOnRoster, Forbidden)


def test_the_workouts_own_student_email_is_not_enough_without_a_board_entry(db):
    db.docs[DbCollections.CTF_BOARD]["red"]["members"] = ["b@x.edu"]
    with pytest.raises(NotOnRoster):
        join(make_workout(db), "a@x.edu")


def test_member_of_an_inactive_board_is_refused(db):
    db.docs[DbCollections.CTF_BOARD]["red"]["active"] = False
    with pytest.raises(NotOnRoster):
        join(make_workout(db), "a@x.edu")


def test_member_of_another_events_board_is_refused(db):
    db.docs[DbCollections.CTF_BOARD]["red"]["ctf_id"] = "otherctfxx"
    with pytest.raises(NotOnRoster):
        join(make_workout(db), "a@x.edu")


def test_inactive_and_foreign_boards_do_not_hide_the_active_one(db):
    boards = db.docs[DbCollections.CTF_BOARD]
    boards["old1"] = board(BLUE, ["a@x.edu"], active=False)
    boards["old2"] = board(BLUE, ["a@x.edu"], ctf_id="otherctfxx")
    assert join(make_workout(db), "a@x.edu") == (RED, True)


def test_roster_workout_missing_from_the_unit_is_refused(db):
    db.docs[DbCollections.WORKOUT].pop(RED)
    with pytest.raises(NotOnRoster):
        join(make_workout(db), "a@x.edu")


def test_roster_lookup_uses_one_array_filter_only(db):
    join(make_workout(db), "a@x.edu")
    [(_, filters)] = [q for q in db.queries if q[0] == DbCollections.CTF_BOARD]
    assert filters == [("members", DbOperators.ARRAY_CONTAINS, "a@x.edu")]


def test_a_ctf_unit_never_creates_a_new_workout_on_join(db):
    workout = make_workout(db)
    with pytest.raises(NotOnRoster):
        join(workout, "stranger@x.edu")
    # Unlike a plain unit there is no spare capacity: no unit BUILD with CHILD_ID is sent.
    workout.pubsub_manager.msg.assert_not_called()


# --- non-CTF units are unchanged -------------------------------------------------------

@pytest.fixture
def plain_db(db):
    db.docs[DbCollections.UNIT][UNIT_ID].pop("ctf_event_id")
    db.docs[DbCollections.CTF_BOARD].clear()
    return db


def test_plain_unit_matches_on_the_workouts_student_email(plain_db):
    workout = make_workout(plain_db)
    assert join(workout, "c@x.edu") == (BLUE, True)
    assert not [q for q in plain_db.queries if q[0] == DbCollections.CTF_BOARD]


def test_plain_unit_builds_a_not_built_workout_for_its_student(plain_db):
    workout = make_workout(plain_db)
    assert join(workout, "A@x.edu") == (RED, True)
    assert workout.pubsub_manager.msg.call_args.kwargs[PubSub.EventAttributes.BUILD_ID] == RED


def test_plain_unit_with_capacity_requests_a_new_workout_for_an_unknown_email(plain_db):
    plain_db.docs[DbCollections.UNIT][UNIT_ID]["workspace_settings"]["count"] = 3
    workout = make_workout(plain_db)

    workout_id, exists = join(workout, "new@x.edu")

    assert exists is False
    kwargs = workout.pubsub_manager.msg.call_args.kwargs
    assert kwargs[PubSub.EventAttributes.CHILD_ID] == workout_id
    assert kwargs[PubSub.EventAttributes.COURSE_OBJECT] == str(PubSub.CourseObjects.UNIT.value)


def test_plain_unit_at_capacity_raises_forbidden_not_not_on_roster(plain_db):
    with pytest.raises(Forbidden) as exc:
        join(make_workout(plain_db), "new@x.edu")
    assert not isinstance(exc.value, NotOnRoster)


# --- router mapping ----------------------------------------------------------------------

def post_join(monkeypatch, error):
    core = MagicMock()
    core.build.side_effect = error
    monkeypatch.setattr(workout_routes, "Workout", MagicMock(return_value=core))
    app = FastAPI()
    app.include_router(workout_routes.workout_router)
    app.dependency_overrides[workout_routes.get_cloud_env] = lambda: {}
    return TestClient(app, raise_server_exceptions=False).post(
        "/workouts/", json={"input_email": "x@x.edu", "join_code": JOIN_CODE})


def test_router_maps_not_on_roster_to_403_with_the_roster_message(monkeypatch):
    response = post_join(monkeypatch, NotOnRoster(message="x@x.edu is not on the roster"))

    assert response.status_code == 403
    assert "not on the roster" in response.json()["detail"]
    assert "Maximum allowed workout builds" not in response.json()["detail"]


def test_router_still_maps_plain_forbidden_to_the_capacity_message(monkeypatch):
    response = post_join(monkeypatch, Forbidden(message="max"))

    assert response.status_code == 403
    assert "Maximum allowed workout builds" in response.json()["detail"]
