"""CtfSetup: create an event from a catalog template, manage the team roster in DRAFT, edit flags,
and build/start/stop every team's servers. Firestore is an in-memory fake; Pub/Sub is a mock."""
import copy
import json
import re
import time
from unittest.mock import MagicMock

import pytest

from common.constants.build_constants import BuildConstants
from common.constants.database import DbCollections, DbOperationTypes, DbOperators
from common.constants.pub_sub import PubSub
from common.constants.states import CtfStates, WorkoutStates
from common.exceptions.agoge import AgogeValidationError, BadRequest, Conflict, NotFound, ServiceUnavailable, Unauthorized
from common.models.agoge import (
    CtfActionRequest, CtfBoardModel, CtfCreateRequest, CtfEventModel, CtfSpecModel, CtfTeamMembersRequest,
    CtfTeamRequest, UnitModel,
)
from common.models.users import AgogeUser
from common.utilities.ctf_flags import derive_flag_value, flag_digest
from core.ctf.event import NOT_PROVISIONED_MESSAGE, CtfEvent
from core.ctf.setup import CtfSetup

SEED = "s" * 64
GM = "gm@example.edu"
SPEC_ID = "web-lab"
CTF_ID = "ctfaaaaaaa"


def merge(target, data):
    for key, value in data.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            merge(target[key], value)
        else:
            target[key] = copy.deepcopy(value)


class FakeSnapshot:
    def __init__(self, data):
        self.exists = data is not None
        self._data = data

    def to_dict(self):
        return copy.deepcopy(self._data)


class FakeRef:
    def __init__(self, store, doc_id):
        self.store, self.doc_id = store, doc_id

    def get(self, transaction=None):
        return FakeSnapshot(self.store.get(self.doc_id))


class FakeTransaction:
    def __init__(self):
        self.sets = []

    def update(self, ref, data):
        merge(ref.store[ref.doc_id], data)

    def set(self, ref, data):
        self.sets.append(ref.doc_id)
        ref.store[ref.doc_id] = json.loads(json.dumps(data))


class FakeFirestoreClient:
    def __init__(self, fake):
        self.fake = fake

    def collection(self, name):
        store = self.fake.collection(name)
        return MagicMock(document=lambda doc_id: FakeRef(store, doc_id))


class FakeDb:
    """In-memory Firestore stand-in recording every batch commit."""

    def __init__(self):
        self.docs = {}
        self.commits = []
        self.queries = []
        self.deleted = []
        self.db = FakeFirestoreClient(self)

    def collection(self, name):
        return self.docs.setdefault(getattr(name, "value", name), {})

    def get(self, collection_name, doc_id):
        return copy.deepcopy(self.collection(collection_name).get(doc_id))

    def update(self, collection_name, doc_id, data):
        merge(self.collection(collection_name).setdefault(doc_id, {}), json.loads(json.dumps(data, default=str)))

    def delete(self, collection_name, doc_id):
        self.deleted.append((getattr(collection_name, "value", collection_name), doc_id))
        self.collection(collection_name).pop(doc_id, None)

    def query(self, collection_name, filters=None):
        self.queries.append((collection_name, filters))
        out = []
        for doc in self.collection(collection_name).values():
            ok = True
            for field, op, value in filters or []:
                if op == DbOperators.EQUAL:
                    ok &= doc.get(field) == value
                elif op == DbOperators.IN:
                    assert len(value) <= 30
                    ok &= doc.get(field) in value
                elif op == DbOperators.ARRAY_CONTAINS_ANY:
                    assert len(value) <= 30
                    ok &= bool(set(doc.get(field) or []) & set(value))
                else:
                    raise AssertionError(f"unexpected operator {op}")
            if ok:
                out.append(copy.deepcopy(doc))
        return out

    def operation(self, collection_name, doc_id, operation_type, data=None):
        return (collection_name, doc_id, operation_type, data)

    def batch_write(self, operations):
        assert len(operations) <= 500
        self.commits.append(list(operations))
        for collection, doc_id, op_type, data in operations:
            if op_type == DbOperationTypes.SET:
                self.collection(collection)[doc_id] = json.loads(json.dumps(data))
            elif op_type == DbOperationTypes.DELETE:
                self.collection(collection).pop(doc_id, None)
            else:
                raise AssertionError(op_type)

    def transaction(self, operation_func, *args, **kwargs):
        return operation_func(FakeTransaction(), *args, **kwargs)


def flag(flag_id, slot=1, server="web", **kw):
    return {
        "id": flag_id, "server": server, "slot": slot, "location_type": "file",
        "path": f"/opt/{flag_id}.txt", "operating_system": "linux", "points": 100, **kw,
    }


def ctf_block(flags=None, name="Spring CTF"):
    return {"name": name, "flags": flags or [flag("user-flag", 1), flag("root-flag", 2)]}


def catalog_doc(spec_id=SPEC_ID, ctf="default", **kw):
    doc = {
        "id": spec_id, "build_type": "unit", "version": "1", "instructor_id": ["author@example.edu"],
        "unit_type": BuildConstants.UnitType.SOLO.value,
        "summary": {"name": "Web Lab", "description": "A web lab"},
        "servers": [{"name": "web", "image": "img", "machine_type": "e2-small", "details": {"os": "linux"}}],
        "creation_timestamp": 1,
        **kw,
    }
    if ctf == "default":
        doc["ctf"] = ctf_block()
    elif ctf is not None:
        doc["ctf"] = ctf
    return doc


def make_env(seed=SEED):
    env = MagicMock()
    env.ctf_flag_seed = seed
    return env


def user(email=GM, admin=False):
    return AgogeUser(uid="uid", email=email, permissions={"instructor": True, "admin": admin})


def future_ts():
    return time.time() + 3600


@pytest.fixture
def db():
    fake = FakeDb()
    fake.collection(DbCollections.CATALOG)[SPEC_ID] = catalog_doc()
    return fake


@pytest.fixture
def pubsub():
    return MagicMock()


def make_setup(db, pubsub=None, env_dict=None, seed=SEED):
    return CtfSetup(
        env_dict={} if env_dict is None else env_dict, db=db, pubsub=pubsub or MagicMock(), env=make_env(seed),
    )


def create_event(db, setup=None, **request_kw):
    setup = setup or make_setup(db)
    request = CtfCreateRequest(spec_id=SPEC_ID, expires=future_ts(), **request_kw)
    return setup.create(request, user(), ctf_id=CTF_ID)


def team(name="Red", members=("a@x.edu",)):
    return CtfTeamRequest(team_name=name, members=list(members))


# --- create ------------------------------------------------------------------------

def test_create_writes_a_marked_unit_and_a_draft_event_without_boards(db):
    expires = future_ts()
    ctf_id = make_setup(db).create(CtfCreateRequest(spec_id=SPEC_ID, expires=expires), user(), ctf_id=CTF_ID)

    assert ctf_id == CTF_ID
    [unit_doc] = db.collection(DbCollections.UNIT).values()
    unit = UnitModel(**unit_doc)
    assert unit.ctf_event_id == CTF_ID
    assert unit.workspace_settings.registration_required is True
    assert unit.workspace_settings.count == 0
    assert unit.workspace_settings.expires == int(expires)
    assert unit.instructor_id == [GM]
    assert unit.ctf.name == "Spring CTF"

    event = CtfEventModel(**db.get(DbCollections.CTF, CTF_ID))
    assert event.state == CtfStates.DRAFT.value
    assert event.board_ids == []
    assert event.unit_id == unit.id
    assert event.instructor_id == [GM]
    assert event.join_code and event.join_code == unit.join_code
    assert db.collection(DbCollections.CTF_BOARD) == {}
    assert db.collection(DbCollections.WORKOUT) == {}


def test_create_publishes_nothing(db, pubsub):
    create_event(db, make_setup(db, pubsub))
    pubsub.msg.assert_not_called()


def test_create_does_not_modify_the_catalog_template(db):
    before = copy.deepcopy(db.collection(DbCollections.CATALOG)[SPEC_ID])
    create_event(db)
    assert db.collection(DbCollections.CATALOG)[SPEC_ID] == before


def test_create_name_override_renames_the_event_and_unit_spec(db):
    create_event(db, name="Fall Showdown")

    event = CtfEventModel(**db.get(DbCollections.CTF, CTF_ID))
    [unit_doc] = db.collection(DbCollections.UNIT).values()
    assert event.spec.name == "Fall Showdown"
    assert unit_doc["ctf"]["name"] == "Fall Showdown"


def test_create_keeps_the_spec_name_without_an_override(db):
    create_event(db)
    assert CtfEventModel(**db.get(DbCollections.CTF, CTF_ID)).spec.name == "Spring CTF"


def test_create_unknown_template_raises_not_found(db):
    with pytest.raises(NotFound):
        make_setup(db).create(CtfCreateRequest(spec_id="missing", expires=future_ts()), user(), ctf_id=CTF_ID)
    assert db.collection(DbCollections.UNIT) == {}


@pytest.mark.parametrize("ctf", [None, {}])
def test_create_template_without_ctf_block_is_bad_request(db, ctf):
    doc = catalog_doc(ctf=None)
    if ctf is not None:
        doc["ctf"] = ctf
    db.collection(DbCollections.CATALOG)[SPEC_ID] = doc
    with pytest.raises(BadRequest):
        create_event(db)
    assert db.collection(DbCollections.UNIT) == {}


def test_create_community_template_is_bad_request(db):
    db.collection(DbCollections.CATALOG)[SPEC_ID] = catalog_doc(unit_type=BuildConstants.UnitType.COMMUNITY.value)
    with pytest.raises(BadRequest, match="solo"):
        create_event(db)
    assert db.collection(DbCollections.UNIT) == {}


@pytest.mark.parametrize("delta", [-60, 0])
def test_create_expiry_not_in_the_future_is_bad_request(db, delta):
    with pytest.raises(BadRequest, match="future"):
        make_setup(db).create(CtfCreateRequest(spec_id=SPEC_ID, expires=time.time() + delta), user(), ctf_id=CTF_ID)
    assert db.collection(DbCollections.UNIT) == {}


@pytest.mark.parametrize("seed", [None, ""])
def test_create_without_a_flag_seed_is_service_unavailable(db, seed):
    with pytest.raises(ServiceUnavailable) as exc:
        create_event(db, make_setup(db, seed=seed))
    assert str(exc.value.message) == NOT_PROVISIONED_MESSAGE
    assert db.collection(DbCollections.UNIT) == {}
    assert db.collection(DbCollections.CTF) == {}


def test_create_deletes_the_unit_when_the_event_write_fails(db):
    real_update = db.update

    def update(collection_name, doc_id, data):
        if collection_name == DbCollections.CTF:
            raise RuntimeError("write failed")
        real_update(collection_name, doc_id, data)

    db.update = update
    with pytest.raises(RuntimeError, match="write failed"):
        create_event(db)

    assert db.collection(DbCollections.UNIT) == {}
    assert db.collection(DbCollections.CTF) == {}
    assert [c for c, _ in db.deleted] == [DbCollections.UNIT.value]


# --- templates ---------------------------------------------------------------------

def test_templates_lists_only_solo_labs_with_a_valid_ctf_block_sorted_by_name(db):
    catalog = db.collection(DbCollections.CATALOG)
    catalog.clear()
    catalog["zeta"] = catalog_doc("zeta", summary={"name": "zeta lab", "description": "d"})
    catalog["alpha"] = catalog_doc("alpha", summary={"name": "Alpha lab", "description": "d"})
    catalog["noctf"] = catalog_doc("noctf", ctf=None)
    catalog["comm"] = catalog_doc("comm", unit_type=BuildConstants.UnitType.COMMUNITY.value)
    catalog["bad"] = catalog_doc("bad", ctf={"name": "Broken", "flags": []})

    rows = make_setup(db).templates()

    assert [row.id for row in rows] == ["alpha", "zeta"]


def test_template_row_counts_non_decoy_flags_and_lists_servers(db):
    db.collection(DbCollections.CATALOG)[SPEC_ID] = catalog_doc(
        ctf=ctf_block([flag("real-one", 1), flag("real-two", 2), flag("decoy-x", 3, points=-5, decoy=True)])
    )

    [row] = make_setup(db).templates()

    assert row.flag_count == 2
    assert row.ctf_name == "Spring CTF"
    assert row.name == "Web Lab"
    assert row.description == "A web lab"
    assert [(s.name, s.os, s.machine_type) for s in row.servers] == [("web", "linux", "e2-small")]


def test_template_without_unit_type_is_treated_as_solo(db):
    doc = catalog_doc()
    del doc["unit_type"]
    db.collection(DbCollections.CATALOG)[SPEC_ID] = doc
    assert [row.id for row in make_setup(db).templates()] == [SPEC_ID]


def test_templates_with_an_empty_catalog_is_empty(db):
    db.collection(DbCollections.CATALOG).clear()
    assert make_setup(db).templates() == []


# --- add_team ----------------------------------------------------------------------

def test_add_team_writes_a_not_built_workout_a_board_and_digests(db):
    setup = make_setup(db)
    create_event(db, setup)

    row = setup.add_team(CTF_ID, team("Red", ["A@x.edu", "b@x.edu"]), user())

    [workout_id] = db.get(DbCollections.CTF, CTF_ID)["board_ids"]
    assert row.workout_id == workout_id
    assert (row.team_name, row.members) == ("Red", ["a@x.edu", "b@x.edu"])
    assert row.workout_state == WorkoutStates.NOT_BUILT.value
    assert row.workout_state_name == WorkoutStates.NOT_BUILT.name

    workout = db.get(DbCollections.WORKOUT, workout_id)
    assert workout["state"] == WorkoutStates.NOT_BUILT.value
    assert workout["team_name"] == "Red"
    assert workout["student_email"] == "a@x.edu"
    [unit_id] = db.collection(DbCollections.UNIT)
    assert workout["parent_id"] == unit_id

    board = CtfBoardModel(**db.get(DbCollections.CTF_BOARD, f"{CTF_ID}-{workout_id}"))
    assert board.members == ["a@x.edu", "b@x.edu"]
    assert board.team_name == "Red"
    assert board.active is True
    assert [f.flag_id for f in board.flags] == ["user-flag", "root-flag"]
    for f in board.flags:
        assert f.digest == flag_digest(derive_flag_value(SEED, workout_id, f.flag_id, 1, "agoge"))
        assert db.get(DbCollections.CTF_DIGEST, f.digest)["workout_id"] == workout_id


def test_add_team_sets_the_unit_workout_count_to_the_team_count(db):
    setup = make_setup(db)
    create_event(db, setup)
    [unit_id] = db.collection(DbCollections.UNIT)

    setup.add_team(CTF_ID, team("Red", ["a@x.edu"]), user())
    assert db.get(DbCollections.UNIT, unit_id)["workspace_settings"]["count"] == 1
    setup.add_team(CTF_ID, team("Blue", ["b@x.edu"]), user())
    assert db.get(DbCollections.UNIT, unit_id)["workspace_settings"]["count"] == 2
    # The merge touched only the count.
    assert db.get(DbCollections.UNIT, unit_id)["workspace_settings"]["registration_required"] is True


def test_add_team_appends_board_ids_in_order(db):
    setup = make_setup(db)
    create_event(db, setup)
    first = setup.add_team(CTF_ID, team("Red", ["a@x.edu"]), user())
    second = setup.add_team(CTF_ID, team("Blue", ["b@x.edu"]), user())
    assert db.get(DbCollections.CTF, CTF_ID)["board_ids"] == [first.workout_id, second.workout_id]


def test_add_team_stores_no_flag_value(db):
    setup = make_setup(db)
    create_event(db, setup)
    row = setup.add_team(CTF_ID, team(), user())
    blob = json.dumps(db.docs)
    assert not re.search(r"agoge\{", blob, re.IGNORECASE)
    assert derive_flag_value(SEED, row.workout_id, "user-flag", 1, "agoge") not in blob
    assert SEED not in blob


@pytest.mark.parametrize("duplicate", ["Red", "RED", "red"])
def test_add_team_duplicate_name_is_a_conflict(db, duplicate):
    setup = make_setup(db)
    create_event(db, setup)
    setup.add_team(CTF_ID, team("Red", ["a@x.edu"]), user())
    with pytest.raises(Conflict, match="already exists"):
        setup.add_team(CTF_ID, team(duplicate, ["b@x.edu"]), user())
    assert len(db.get(DbCollections.CTF, CTF_ID)["board_ids"]) == 1


def test_add_team_email_on_another_active_board_is_a_conflict(db):
    setup = make_setup(db)
    create_event(db, setup)
    setup.add_team(CTF_ID, team("Red", ["a@x.edu"]), user())
    with pytest.raises(Conflict, match="a@x.edu"):
        setup.add_team(CTF_ID, team("Blue", ["c@x.edu", "a@x.edu"]), user())
    assert len(db.collection(DbCollections.WORKOUT)) == 1


def test_add_team_email_on_an_inactive_board_is_allowed(db):
    db.collection(DbCollections.CTF_BOARD)["old-wkoutzzzzz"] = {
        "id": "old-wkoutzzzzz", "ctf_id": "oldctfxxxx", "active": False, "team_name": "Old", "members": ["a@x.edu"],
    }
    setup = make_setup(db)
    create_event(db, setup)
    row = setup.add_team(CTF_ID, team("Red", ["a@x.edu"]), user())
    assert row.members == ["a@x.edu"]


def test_add_team_roster_check_chunks_emails_in_30s(db):
    setup = make_setup(db)
    create_event(db, setup)
    members = [f"m{i}@x.edu" for i in range(65)]
    # The request caps members at 50, so exercise the chunking through the helper directly.
    setup._require_free_members(members)
    board_queries = [f for c, f in db.queries if c == DbCollections.CTF_BOARD]
    assert [len(f[0][2]) for f in board_queries] == [30, 30, 5]
    assert all(f[0][1] == DbOperators.ARRAY_CONTAINS_ANY for f in board_queries)


def test_add_team_beyond_ctf_max_boards_is_bad_request(db):
    setup = make_setup(db, env_dict={"ctf_max_boards": 2})
    create_event(db, setup)
    setup.add_team(CTF_ID, team("Red", ["a@x.edu"]), user())
    setup.add_team(CTF_ID, team("Blue", ["b@x.edu"]), user())
    with pytest.raises(BadRequest, match="at most 2"):
        setup.add_team(CTF_ID, team("Green", ["c@x.edu"]), user())
    assert len(db.get(DbCollections.CTF, CTF_ID)["board_ids"]) == 2


@pytest.mark.parametrize("state", [s for s in CtfStates if s != CtfStates.DRAFT])
def test_add_team_outside_draft_is_a_conflict(db, state):
    setup = make_setup(db)
    create_event(db, setup)
    db.collection(DbCollections.CTF)[CTF_ID]["state"] = state.value
    with pytest.raises(Conflict, match=state.name):
        setup.add_team(CTF_ID, team(), user())
    assert db.collection(DbCollections.WORKOUT) == {}


def test_add_team_without_a_flag_seed_is_service_unavailable(db):
    create_event(db)
    with pytest.raises(ServiceUnavailable):
        make_setup(db, seed=None).add_team(CTF_ID, team(), user())
    assert db.collection(DbCollections.WORKOUT) == {}


def test_add_team_by_a_stranger_is_unauthorized(db):
    setup = make_setup(db)
    create_event(db, setup)
    with pytest.raises(Unauthorized):
        setup.add_team(CTF_ID, team(), user(email="other@example.edu"))


def test_add_team_unknown_event_is_not_found(db):
    with pytest.raises(NotFound):
        make_setup(db).add_team(CTF_ID, team(), user())


def test_add_team_rolls_back_its_documents_when_the_board_id_transaction_fails(db):
    setup = make_setup(db)
    create_event(db, setup)

    def fail(*_, **__):
        raise Conflict(message="event changed")

    db.transaction = fail
    with pytest.raises(Conflict, match="event changed"):
        setup.add_team(CTF_ID, team(), user())

    assert db.collection(DbCollections.WORKOUT) == {}
    assert db.collection(DbCollections.CTF_BOARD) == {}
    assert db.collection(DbCollections.CTF_DIGEST) == {}


def test_board_id_change_inside_the_transaction_refuses_a_non_draft_event(db):
    setup = make_setup(db)
    create_event(db, setup)
    db.collection(DbCollections.CTF)[CTF_ID]["state"] = CtfStates.ARMING.value
    with pytest.raises(Conflict, match="ARMING"):
        setup._change_board_ids(FakeTransaction(), CTF_ID, add="wkoutaaaaa")
    assert db.get(DbCollections.CTF, CTF_ID)["board_ids"] == []


# --- teams -------------------------------------------------------------------------

def test_teams_lists_boards_in_board_order_with_workout_state(db):
    setup = make_setup(db)
    create_event(db, setup)
    red = setup.add_team(CTF_ID, team("Red", ["a@x.edu"]), user())
    blue = setup.add_team(CTF_ID, team("Blue", ["b@x.edu"]), user())
    db.collection(DbCollections.WORKOUT)[blue.workout_id]["state"] = WorkoutStates.RUNNING.value

    rows = setup.teams(CTF_ID, user())

    assert [r.workout_id for r in rows] == [red.workout_id, blue.workout_id]
    assert [r.workout_state_name for r in rows] == ["NOT_BUILT", "RUNNING"]
    assert rows[0].members == ["a@x.edu"]


# --- remove_team -------------------------------------------------------------------

def test_remove_team_deletes_digests_board_and_workout_and_updates_the_event(db):
    setup = make_setup(db)
    create_event(db, setup)
    red = setup.add_team(CTF_ID, team("Red", ["a@x.edu"]), user())
    blue = setup.add_team(CTF_ID, team("Blue", ["b@x.edu"]), user())
    [unit_id] = db.collection(DbCollections.UNIT)

    setup.remove_team(CTF_ID, red.workout_id, user())

    assert db.get(DbCollections.CTF, CTF_ID)["board_ids"] == [blue.workout_id]
    assert db.get(DbCollections.WORKOUT, red.workout_id) is None
    assert db.get(DbCollections.CTF_BOARD, f"{CTF_ID}-{red.workout_id}") is None
    remaining = {d["workout_id"] for d in db.collection(DbCollections.CTF_DIGEST).values()}
    assert remaining == {blue.workout_id}
    assert db.get(DbCollections.WORKOUT, blue.workout_id) is not None
    assert db.get(DbCollections.UNIT, unit_id)["workspace_settings"]["count"] == 1


def test_remove_last_team_sets_the_count_to_zero(db):
    setup = make_setup(db)
    create_event(db, setup)
    only = setup.add_team(CTF_ID, team(), user())
    setup.remove_team(CTF_ID, only.workout_id, user())
    [unit_id] = db.collection(DbCollections.UNIT)
    assert db.get(DbCollections.UNIT, unit_id)["workspace_settings"]["count"] == 0


def test_remove_team_with_built_servers_is_a_conflict(db):
    setup = make_setup(db)
    create_event(db, setup)
    row = setup.add_team(CTF_ID, team(), user())
    db.collection(DbCollections.WORKOUT)[row.workout_id]["state"] = WorkoutStates.RUNNING.value

    with pytest.raises(Conflict, match="already built"):
        setup.remove_team(CTF_ID, row.workout_id, user())

    assert db.get(DbCollections.CTF, CTF_ID)["board_ids"] == [row.workout_id]
    assert db.get(DbCollections.CTF_BOARD, f"{CTF_ID}-{row.workout_id}") is not None


def test_remove_unknown_team_is_not_found(db):
    setup = make_setup(db)
    create_event(db, setup)
    with pytest.raises(NotFound):
        setup.remove_team(CTF_ID, "wkoutzzzzz", user())


def test_remove_team_outside_draft_is_a_conflict(db):
    setup = make_setup(db)
    create_event(db, setup)
    row = setup.add_team(CTF_ID, team(), user())
    db.collection(DbCollections.CTF)[CTF_ID]["state"] = CtfStates.ARMED.value
    with pytest.raises(Conflict):
        setup.remove_team(CTF_ID, row.workout_id, user())


# --- set_members -------------------------------------------------------------------

def members_request(*emails):
    return CtfTeamMembersRequest(members=list(emails))


def test_set_members_replaces_the_roster_and_the_workout_student_email(db):
    setup = make_setup(db)
    create_event(db, setup)
    row = setup.add_team(CTF_ID, team("Red", ["a@x.edu"]), user())

    updated = setup.set_members(CTF_ID, row.workout_id, members_request("c@x.edu", "d@x.edu"), user())

    assert updated.members == ["c@x.edu", "d@x.edu"]
    assert updated.team_name == "Red"
    assert db.get(DbCollections.CTF_BOARD, f"{CTF_ID}-{row.workout_id}")["members"] == ["c@x.edu", "d@x.edu"]
    assert db.get(DbCollections.WORKOUT, row.workout_id)["student_email"] == "c@x.edu"


@pytest.mark.parametrize("state", [CtfStates.RUNNING, CtfStates.PAUSED, CtfStates.ARMED])
def test_set_members_is_allowed_after_draft_while_the_event_is_live(db, state):
    setup = make_setup(db)
    create_event(db, setup)
    row = setup.add_team(CTF_ID, team("Red", ["a@x.edu"]), user())
    db.collection(DbCollections.CTF)[CTF_ID]["state"] = state.value

    updated = setup.set_members(CTF_ID, row.workout_id, members_request("a@x.edu", "late@x.edu"), user())

    assert updated.members == ["a@x.edu", "late@x.edu"]


@pytest.mark.parametrize("state", [CtfStates.ENDED, CtfStates.ARCHIVED])
def test_set_members_is_refused_once_the_event_is_over(db, state):
    setup = make_setup(db)
    create_event(db, setup)
    row = setup.add_team(CTF_ID, team("Red", ["a@x.edu"]), user())
    db.collection(DbCollections.CTF)[CTF_ID]["state"] = state.value

    with pytest.raises(Conflict, match=state.name):
        setup.set_members(CTF_ID, row.workout_id, members_request("z@x.edu"), user())

    assert db.get(DbCollections.CTF_BOARD, f"{CTF_ID}-{row.workout_id}")["members"] == ["a@x.edu"]


def test_set_members_conflict_ignores_the_teams_own_board(db):
    setup = make_setup(db)
    create_event(db, setup)
    row = setup.add_team(CTF_ID, team("Red", ["a@x.edu"]), user())
    # Keeping a@x.edu while adding a new one must not collide with the team's own board.
    updated = setup.set_members(CTF_ID, row.workout_id, members_request("a@x.edu", "n@x.edu"), user())
    assert updated.members == ["a@x.edu", "n@x.edu"]


def test_set_members_email_on_another_active_board_is_a_conflict(db):
    setup = make_setup(db)
    create_event(db, setup)
    red = setup.add_team(CTF_ID, team("Red", ["a@x.edu"]), user())
    setup.add_team(CTF_ID, team("Blue", ["b@x.edu"]), user())
    with pytest.raises(Conflict, match="b@x.edu"):
        setup.set_members(CTF_ID, red.workout_id, members_request("a@x.edu", "b@x.edu"), user())
    assert db.get(DbCollections.CTF_BOARD, f"{CTF_ID}-{red.workout_id}")["members"] == ["a@x.edu"]


def test_set_members_unknown_team_is_not_found(db):
    setup = make_setup(db)
    create_event(db, setup)
    with pytest.raises(NotFound):
        setup.set_members(CTF_ID, "wkoutzzzzz", members_request("a@x.edu"), user())


# --- update_spec -------------------------------------------------------------------

def test_update_spec_recomputes_digests_deletes_stale_ones_and_keeps_members(db):
    setup = make_setup(db)
    create_event(db, setup)
    red = setup.add_team(CTF_ID, team("Red", ["a@x.edu", "b@x.edu"]), user())
    old_root = derive_flag_value(SEED, red.workout_id, "root-flag", 1, "agoge")
    old_root_digest = flag_digest(old_root)
    assert db.get(DbCollections.CTF_DIGEST, old_root_digest)

    new_spec = CtfSpecModel(**ctf_block([flag("user-flag", 1), flag("fresh-flag", 2)], name="Renamed"))
    updated = setup.update_spec(CTF_ID, new_spec, user())

    assert updated.spec.name == "Renamed"
    assert db.get(DbCollections.CTF_DIGEST, old_root_digest) is None
    new_digest = flag_digest(derive_flag_value(SEED, red.workout_id, "fresh-flag", 1, "agoge"))
    assert db.get(DbCollections.CTF_DIGEST, new_digest)["flag_id"] == "fresh-flag"
    board = CtfBoardModel(**db.get(DbCollections.CTF_BOARD, f"{CTF_ID}-{red.workout_id}"))
    assert [f.flag_id for f in board.flags] == ["user-flag", "fresh-flag"]
    assert board.members == ["a@x.edu", "b@x.edu"]
    assert board.team_name == "Red"
    assert {d["flag_id"] for d in db.collection(DbCollections.CTF_DIGEST).values()} == {"user-flag", "fresh-flag"}
    assert db.get(DbCollections.CTF, CTF_ID)["spec"]["name"] == "Renamed"
    [unit_id] = db.collection(DbCollections.UNIT)
    assert [f["id"] for f in db.get(DbCollections.UNIT, unit_id)["ctf"]["flags"]] == ["user-flag", "fresh-flag"]


def test_update_spec_with_the_flag_prefix_changed_rewrites_every_digest(db):
    setup = make_setup(db)
    create_event(db, setup)
    red = setup.add_team(CTF_ID, team(), user())
    block = ctf_block()
    block["scoring"] = {"flag_prefix": "acme"}

    setup.update_spec(CTF_ID, CtfSpecModel(**block), user())

    expected = flag_digest(derive_flag_value(SEED, red.workout_id, "user-flag", 1, "acme"))
    assert db.get(DbCollections.CTF_DIGEST, expected)
    assert len(db.collection(DbCollections.CTF_DIGEST)) == 2


def test_update_spec_with_no_teams_still_saves_the_spec(db):
    create_event(db)
    make_setup(db).update_spec(CTF_ID, CtfSpecModel(**ctf_block(name="Solo")), user())
    assert db.get(DbCollections.CTF, CTF_ID)["spec"]["name"] == "Solo"


def test_update_spec_rejects_a_flag_on_an_unknown_server_and_writes_nothing(db):
    setup = make_setup(db)
    create_event(db, setup)
    setup.add_team(CTF_ID, team(), user())
    before = copy.deepcopy(db.docs)

    with pytest.raises(AgogeValidationError, match="ghost"):
        setup.update_spec(CTF_ID, CtfSpecModel(**ctf_block([flag("user-flag", 1, server="ghost")])), user())

    assert db.docs == before


def test_update_spec_rejects_a_path_that_would_reach_a_script(db):
    setup = make_setup(db)
    create_event(db, setup)
    with pytest.raises(AgogeValidationError):
        setup.update_spec(CTF_ID, CtfSpecModel(**ctf_block([flag("user-flag", 1, path="/opt/x; rm -rf /")])), user())


@pytest.mark.parametrize("state", [s for s in CtfStates if s != CtfStates.DRAFT])
def test_update_spec_outside_draft_is_a_conflict(db, state):
    create_event(db)
    db.collection(DbCollections.CTF)[CTF_ID]["state"] = state.value
    with pytest.raises(Conflict, match=state.name):
        make_setup(db).update_spec(CTF_ID, CtfSpecModel(**ctf_block()), user())


def test_update_spec_without_a_flag_seed_is_service_unavailable(db):
    create_event(db)
    with pytest.raises(ServiceUnavailable):
        make_setup(db, seed=None).update_spec(CTF_ID, CtfSpecModel(**ctf_block()), user())


# --- servers -----------------------------------------------------------------------

def sent(pubsub):
    return [call.kwargs for call in pubsub.msg.call_args_list]


def set_states(db, state, *workout_ids):
    for workout_id in workout_ids:
        db.collection(DbCollections.WORKOUT)[workout_id]["state"] = state.value


def two_teams(db, pubsub):
    setup = make_setup(db, pubsub)
    create_event(db, setup)
    red = setup.add_team(CTF_ID, team("Red", ["a@x.edu"]), user())
    blue = setup.add_team(CTF_ID, team("Blue", ["b@x.edu"]), user())
    return setup, red.workout_id, blue.workout_id


def test_servers_build_publishes_one_build_per_not_built_workout(db, pubsub):
    setup, red, blue = two_teams(db, pubsub)

    assert setup.servers(CTF_ID, "build", user()) == 2

    attrs = PubSub.EventAttributes
    assert sent(pubsub) == [{
        attrs.HANDLER: str(PubSub.Handlers.BUILD.value), attrs.ACTION: str(PubSub.Actions.BUILD.value),
        attrs.COURSE_OBJECT: str(PubSub.CourseObjects.WORKOUT.value), attrs.BUILD_ID: workout_id,
    } for workout_id in (red, blue)]


def test_servers_build_skips_workouts_that_are_already_built(db, pubsub):
    setup, red, blue = two_teams(db, pubsub)
    db.collection(DbCollections.WORKOUT)[red]["state"] = WorkoutStates.RUNNING.value

    assert setup.servers(CTF_ID, "build", user()) == 1
    assert [m[PubSub.EventAttributes.BUILD_ID] for m in sent(pubsub)] == [blue]


def test_servers_build_with_everything_built_publishes_nothing(db, pubsub):
    setup, red, blue = two_teams(db, pubsub)
    for workout_id in (red, blue):
        db.collection(DbCollections.WORKOUT)[workout_id]["state"] = WorkoutStates.READY.value
    assert setup.servers(CTF_ID, "build", user()) == 0
    pubsub.msg.assert_not_called()


@pytest.mark.parametrize("action, pubsub_action", [("start", PubSub.Actions.START), ("stop", PubSub.Actions.STOP)])
def test_servers_start_and_stop_publish_a_control_message_for_every_team(db, pubsub, action, pubsub_action):
    setup, red, blue = two_teams(db, pubsub)
    db.collection(DbCollections.WORKOUT)[red]["state"] = WorkoutStates.RUNNING.value
    db.collection(DbCollections.WORKOUT)[blue]["state"] = WorkoutStates.READY.value

    assert setup.servers(CTF_ID, action, user()) == 2

    attrs = PubSub.EventAttributes
    messages = sent(pubsub)
    assert {m[attrs.BUILD_ID] for m in messages} == {red, blue}
    assert all(m[attrs.HANDLER] == str(PubSub.Handlers.CONTROL.value) for m in messages)
    assert all(m[attrs.ACTION] == str(pubsub_action.value) for m in messages)
    assert all(m[attrs.COURSE_OBJECT] == str(PubSub.CourseObjects.WORKOUT.value) for m in messages)


@pytest.mark.parametrize("action", ["start", "stop"])
def test_servers_start_and_stop_skip_unbuilt_workouts(db, pubsub, action):
    setup, red, blue = two_teams(db, pubsub)
    set_states(db, WorkoutStates.READY, blue)

    assert setup.servers(CTF_ID, action, user()) == 1
    assert [m[PubSub.EventAttributes.BUILD_ID] for m in sent(pubsub)] == [blue]


@pytest.mark.parametrize("gone", [
    WorkoutStates.DELETING_SERVERS, WorkoutStates.COMPLETED_DELETING_SERVERS, WorkoutStates.DELETED,
])
@pytest.mark.parametrize("action", ["start", "stop"])
def test_servers_start_and_stop_skip_workouts_being_deleted(db, pubsub, action, gone):
    setup, red, blue = two_teams(db, pubsub)
    set_states(db, WorkoutStates.READY, red)
    set_states(db, gone, blue)

    assert setup.servers(CTF_ID, action, user()) == 1
    assert [m[PubSub.EventAttributes.BUILD_ID] for m in sent(pubsub)] == [red]


@pytest.mark.parametrize("action", ["start", "stop"])
def test_servers_start_and_stop_with_nothing_built_publish_nothing(db, pubsub, action):
    setup, *_ = two_teams(db, pubsub)
    assert setup.servers(CTF_ID, action, user()) == 0
    pubsub.msg.assert_not_called()


def test_servers_build_skips_workouts_being_deleted(db, pubsub):
    setup, red, blue = two_teams(db, pubsub)
    set_states(db, WorkoutStates.DELETED, red)
    assert setup.servers(CTF_ID, "build", user()) == 1


def test_servers_stop_is_refused_while_the_event_is_running(db, pubsub):
    setup, *_ = two_teams(db, pubsub)
    db.collection(DbCollections.CTF)[CTF_ID]["state"] = CtfStates.RUNNING.value
    with pytest.raises(Conflict, match="RUNNING"):
        setup.servers(CTF_ID, "stop", user())
    pubsub.msg.assert_not_called()


@pytest.mark.parametrize("state", [CtfStates.ENDED, CtfStates.ARCHIVED])
def test_servers_stop_is_allowed_after_the_event_ends(db, pubsub, state):
    setup, red, blue = two_teams(db, pubsub)
    set_states(db, WorkoutStates.RUNNING, red, blue)
    db.collection(DbCollections.CTF)[CTF_ID]["state"] = state.value
    assert setup.servers(CTF_ID, "stop", user()) == 2


@pytest.mark.parametrize("action", ["build", "start"])
def test_servers_build_and_start_are_refused_once_archived(db, pubsub, action):
    setup, *_ = two_teams(db, pubsub)
    db.collection(DbCollections.CTF)[CTF_ID]["state"] = CtfStates.ARCHIVED.value
    with pytest.raises(Conflict, match="ARCHIVED"):
        setup.servers(CTF_ID, action, user())
    pubsub.msg.assert_not_called()


def test_servers_start_is_allowed_while_the_event_is_running(db, pubsub):
    setup, red, blue = two_teams(db, pubsub)
    set_states(db, WorkoutStates.READY, red, blue)
    db.collection(DbCollections.CTF)[CTF_ID]["state"] = CtfStates.RUNNING.value
    assert setup.servers(CTF_ID, "start", user()) == 2


@pytest.mark.parametrize("action", ["build", "start", "stop"])
def test_servers_without_teams_is_bad_request(db, pubsub, action):
    setup = make_setup(db, pubsub)
    create_event(db, setup)
    with pytest.raises(BadRequest, match="at least one team"):
        setup.servers(CTF_ID, action, user())
    pubsub.msg.assert_not_called()


def test_servers_build_is_refused_while_arming(db, pubsub):
    setup, *_ = two_teams(db, pubsub)
    db.collection(DbCollections.CTF)[CTF_ID]["state"] = CtfStates.ARMING.value
    with pytest.raises(Conflict, match="ARMING"):
        setup.servers(CTF_ID, "build", user())


def test_servers_publish_failure_is_raised(db, pubsub):
    setup, *_ = two_teams(db, pubsub)
    pubsub.msg.return_value.result.side_effect = RuntimeError("topic missing")
    with pytest.raises(RuntimeError, match="topic missing"):
        setup.servers(CTF_ID, "build", user())


# --- arm with zero boards ----------------------------------------------------------

def test_arm_with_no_teams_is_refused_with_a_clear_message(db):
    setup = make_setup(db)
    create_event(db, setup)
    event = CtfEvent(env_dict={}, db=db, env=make_env())

    # The state manager is not reached: the empty board list is refused first.
    with pytest.raises(BadRequest, match="Add at least one team before arming"):
        event.process_action(CTF_ID, CtfActionRequest(action="arm"), user())


# --- update_spec ordering and atomicity ---------------------------------------------

def one_team_with_new_spec(db):
    setup = make_setup(db)
    create_event(db, setup)
    red = setup.add_team(CTF_ID, team("Red", ["a@x.edu"]), user())
    new_spec = CtfSpecModel(**ctf_block([flag("user-flag", 1), flag("fresh-flag", 2)]))
    return setup, red.workout_id, new_spec


def test_update_spec_keeps_digests_shared_with_the_old_spec_and_adds_only_new_ones(db):
    setup, workout_id, new_spec = one_team_with_new_spec(db)
    kept = flag_digest(derive_flag_value(SEED, workout_id, "user-flag", 1, "agoge"))
    db.commits.clear()

    setup.update_spec(CTF_ID, new_spec, user())

    first_commit = db.commits[0]
    added = [op[1] for op in first_commit if op[2] == DbOperationTypes.SET]
    assert kept not in added
    assert added == [flag_digest(derive_flag_value(SEED, workout_id, "fresh-flag", 1, "agoge"))]
    assert db.get(DbCollections.CTF_DIGEST, kept)


def test_update_spec_refuses_when_the_event_leaves_draft_inside_the_transaction(db):
    setup, workout_id, new_spec = one_team_with_new_spec(db)
    old_digests = set(db.collection(DbCollections.CTF_DIGEST))
    old_board = db.get(DbCollections.CTF_BOARD, f"{CTF_ID}-{workout_id}")
    real_transaction = db.transaction

    def arm_then_run(func, *a, **kw):
        db.collection(DbCollections.CTF)[CTF_ID]["state"] = CtfStates.ARMING.value
        return real_transaction(func, *a, **kw)

    db.transaction = arm_then_run
    with pytest.raises(Conflict, match="ARMING"):
        setup.update_spec(CTF_ID, new_spec, user())

    # Added digests rolled back, stale ones never deleted, board and spec untouched.
    assert set(db.collection(DbCollections.CTF_DIGEST)) == old_digests
    assert db.get(DbCollections.CTF_BOARD, f"{CTF_ID}-{workout_id}") == old_board
    assert db.get(DbCollections.CTF, CTF_ID)["spec"]["name"] == "Spring CTF"
    assert [f["id"] for f in db.collection(DbCollections.CTF)[CTF_ID]["spec"]["flags"]] == ["user-flag", "root-flag"]
    [unit_id] = db.collection(DbCollections.UNIT)
    assert [f["id"] for f in db.get(DbCollections.UNIT, unit_id)["ctf"]["flags"]] == ["user-flag", "root-flag"]


def test_update_spec_transaction_failure_leaves_old_boards_and_deletes_nothing(db):
    setup, workout_id, new_spec = one_team_with_new_spec(db)
    before = copy.deepcopy(db.docs)

    def fail(*_, **__):
        raise RuntimeError("transaction aborted")

    db.transaction = fail
    with pytest.raises(RuntimeError, match="transaction aborted"):
        setup.update_spec(CTF_ID, new_spec, user())

    assert db.docs == before


def test_update_spec_added_digest_commit_failure_changes_nothing(db):
    setup, workout_id, new_spec = one_team_with_new_spec(db)
    before = copy.deepcopy(db.docs)
    real = db.batch_write

    def fail_first(operations):
        db.batch_write = real
        raise RuntimeError("commit failed")

    db.batch_write = fail_first
    with pytest.raises(RuntimeError, match="commit failed"):
        setup.update_spec(CTF_ID, new_spec, user())
    assert db.docs == before


def test_update_spec_writes_stale_deletes_only_after_the_transaction(db):
    setup, workout_id, new_spec = one_team_with_new_spec(db)
    order = []
    real_transaction, real_batch = db.transaction, db.batch_write
    db.transaction = lambda *a, **kw: (order.append("transaction"), real_transaction(*a, **kw))[1]
    db.batch_write = lambda ops: (order.append(tuple(sorted({op[2] for op in ops}, key=str))), real_batch(ops))[1]

    setup.update_spec(CTF_ID, new_spec, user())

    assert order.index("transaction") < max(i for i, o in enumerate(order) if o == (DbOperationTypes.DELETE,))


# --- remove_team ordering and races -------------------------------------------------

def test_remove_team_race_reactivates_the_board_and_deletes_nothing(db):
    setup = make_setup(db)
    create_event(db, setup)
    row = setup.add_team(CTF_ID, team("Red", ["a@x.edu"]), user())
    board_id = f"{CTF_ID}-{row.workout_id}"
    real_update = db.update

    def update(collection_name, doc_id, data):
        real_update(collection_name, doc_id, data)
        if collection_name == DbCollections.CTF_BOARD and data == {"active": False}:
            # A member joins between the first check and the deactivation.
            db.collection(DbCollections.WORKOUT)[row.workout_id]["state"] = WorkoutStates.BUILDING_SERVERS.value

    db.update = update
    with pytest.raises(Conflict, match="no longer be removed"):
        setup.remove_team(CTF_ID, row.workout_id, user())

    assert db.get(DbCollections.CTF_BOARD, board_id)["active"] is True
    assert db.get(DbCollections.WORKOUT, row.workout_id) is not None
    assert db.get(DbCollections.CTF, CTF_ID)["board_ids"] == [row.workout_id]
    assert len(db.collection(DbCollections.CTF_DIGEST)) == 2
    assert not [c for c in db.deleted if c[0] == DbCollections.WORKOUT.value]


def test_remove_team_deactivates_the_board_before_deleting_anything(db):
    setup = make_setup(db)
    create_event(db, setup)
    row = setup.add_team(CTF_ID, team("Red", ["a@x.edu"]), user())
    events = []
    real_update, real_batch = db.update, db.batch_write
    db.update = lambda collection_name, doc_id, data: (
        events.append(("update", collection_name, data)), real_update(collection_name, doc_id, data))[1]
    db.batch_write = lambda ops: (events.append(("batch", [op[2] for op in ops])), real_batch(ops))[1]

    setup.remove_team(CTF_ID, row.workout_id, user())

    deactivate = events.index(("update", DbCollections.CTF_BOARD, {"active": False}))
    first_delete = next(i for i, e in enumerate(events) if e[0] == "batch")
    assert deactivate < first_delete


def test_remove_team_removes_the_board_id_after_deleting_the_documents(db):
    setup = make_setup(db)
    create_event(db, setup)
    row = setup.add_team(CTF_ID, team("Red", ["a@x.edu"]), user())
    seen = {}
    real_transaction = db.transaction

    def transaction(func, *a, **kw):
        seen["workout_gone"] = db.get(DbCollections.WORKOUT, row.workout_id) is None
        seen["board_gone"] = db.get(DbCollections.CTF_BOARD, f"{CTF_ID}-{row.workout_id}") is None
        return real_transaction(func, *a, **kw)

    db.transaction = transaction
    setup.remove_team(CTF_ID, row.workout_id, user())
    assert seen == {"workout_gone": True, "board_gone": True}


def test_unit_count_comes_from_the_length_the_transaction_returns(db):
    setup = make_setup(db)
    create_event(db, setup)
    [unit_id] = db.collection(DbCollections.UNIT)
    red = setup.add_team(CTF_ID, team("Red", ["a@x.edu"]), user())
    # A team added concurrently (not through this call) is counted: the stored list is authoritative.
    db.collection(DbCollections.CTF)[CTF_ID]["board_ids"].append("wkoutother1")

    setup.remove_team(CTF_ID, red.workout_id, user())
    assert db.get(DbCollections.UNIT, unit_id)["workspace_settings"]["count"] == 1

    setup.add_team(CTF_ID, team("Blue", ["b@x.edu"]), user())
    assert db.get(DbCollections.UNIT, unit_id)["workspace_settings"]["count"] == 2


def test_change_board_ids_returns_the_new_length(db):
    setup = make_setup(db)
    create_event(db, setup)
    assert setup._change_board_ids(FakeTransaction(), CTF_ID, add="wkoutaaaaa") == 1
    assert setup._change_board_ids(FakeTransaction(), CTF_ID, add="wkoutbbbbb") == 2
    assert setup._change_board_ids(FakeTransaction(), CTF_ID, remove="wkoutaaaaa") == 1


# --- create: template validation ---------------------------------------------------

def test_create_template_with_a_flag_on_an_unknown_server_is_a_validation_error(db):
    db.collection(DbCollections.CATALOG)[SPEC_ID] = catalog_doc(ctf=ctf_block([flag("user-flag", 1, server="ghost")]))
    with pytest.raises(AgogeValidationError, match="ghost"):
        create_event(db)
    assert db.collection(DbCollections.UNIT) == {}


def test_create_template_with_an_unsafe_flag_path_is_a_validation_error(db):
    db.collection(DbCollections.CATALOG)[SPEC_ID] = catalog_doc(ctf=ctf_block([flag("user-flag", 1, path="/opt/a;b")]))
    with pytest.raises(AgogeValidationError):
        create_event(db)
    assert db.collection(DbCollections.UNIT) == {}


def test_create_template_with_an_invalid_ctf_block_is_bad_request(db):
    db.collection(DbCollections.CATALOG)[SPEC_ID] = catalog_doc(ctf={"name": "Broken", "flags": [{"id": "x"}]})
    with pytest.raises(BadRequest, match="invalid"):
        create_event(db)
    assert db.collection(DbCollections.UNIT) == {}


def test_create_template_that_is_not_a_valid_lab_is_bad_request(db):
    doc = catalog_doc()
    del doc["summary"]
    db.collection(DbCollections.CATALOG)[SPEC_ID] = doc
    with pytest.raises(BadRequest, match="not a valid lab"):
        create_event(db)
    assert db.collection(DbCollections.UNIT) == {}
    assert db.collection(DbCollections.CTF) == {}


# --- event delete publishes the owned lab's deletion --------------------------------

ADMIN = user(email="root@example.edu", admin=True)


def delete_setup(db, monkeypatch, pubsub):
    monkeypatch.setattr(CtfEvent, "_rate_limit_ids", lambda self, ctf_id: [])
    setup = make_setup(db, pubsub)
    create_event(db, setup)
    return setup


def test_delete_publishes_a_unit_delete_for_the_lab_the_event_created(db, monkeypatch, pubsub):
    setup = delete_setup(db, monkeypatch, pubsub)
    [unit_id] = db.collection(DbCollections.UNIT)

    setup.events.delete(CTF_ID, ADMIN)

    attrs = PubSub.EventAttributes
    pubsub.msg.assert_called_once_with(**{
        attrs.HANDLER: str(PubSub.Handlers.CONTROL.value),
        attrs.ACTION: str(PubSub.Actions.DELETE.value),
        attrs.COURSE_OBJECT: str(PubSub.CourseObjects.UNIT.value),
        attrs.BUILD_ID: unit_id,
    })
    pubsub.msg.return_value.result.assert_called_once()
    assert db.get(DbCollections.CTF, CTF_ID) is None


def test_delete_does_not_touch_a_unit_the_event_did_not_create(db, monkeypatch, pubsub):
    setup = delete_setup(db, monkeypatch, pubsub)
    [unit_id] = db.collection(DbCollections.UNIT)
    db.collection(DbCollections.UNIT)[unit_id]["ctf_event_id"] = "otherctfxx"

    setup.events.delete(CTF_ID, ADMIN)

    pubsub.msg.assert_not_called()
    assert db.get(DbCollections.CTF, CTF_ID) is None


def test_delete_does_not_touch_a_plain_unit_without_ctf_event_id(db, monkeypatch, pubsub):
    setup = delete_setup(db, monkeypatch, pubsub)
    [unit_id] = db.collection(DbCollections.UNIT)
    del db.collection(DbCollections.UNIT)[unit_id]["ctf_event_id"]

    setup.events.delete(CTF_ID, ADMIN)

    pubsub.msg.assert_not_called()


def test_delete_with_a_missing_unit_publishes_nothing(db, monkeypatch, pubsub):
    setup = delete_setup(db, monkeypatch, pubsub)
    db.collection(DbCollections.UNIT).clear()

    setup.events.delete(CTF_ID, ADMIN)

    pubsub.msg.assert_not_called()
    assert db.get(DbCollections.CTF, CTF_ID) is None


def test_delete_propagates_a_failed_lab_delete_publish_after_the_documents_are_gone(db, monkeypatch, pubsub):
    setup = delete_setup(db, monkeypatch, pubsub)
    pubsub.msg.return_value.result.side_effect = RuntimeError("topic missing")

    with pytest.raises(RuntimeError, match="topic missing"):
        setup.events.delete(CTF_ID, ADMIN)
