import json
import re
from unittest.mock import MagicMock

import pytest

from common.constants.database import DbCollections, DbOperationTypes, DbOperators
from common.constants.states import CtfStates, WorkoutStates
from common.exceptions.agoge import BadRequest, Conflict, NotFound, ServiceUnavailable, Unauthorized
from common.models.agoge import CtfBoardModel, CtfDigestModel, CtfEventModel
from common.models.users import AgogeUser
from common.utilities.ctf_flags import derive_flag_value, flag_digest
from core.ctf.event import NOT_PROVISIONED_MESSAGE, CtfEvent

SEED = "s" * 64
UNIT_ID = "unitabcdef"
GM = "gm@example.edu"
FLAG_PATTERN = re.compile(r"agoge\{", re.IGNORECASE)


class FakeDb:
    """In-memory Firestore stand-in: `operation` builds a deferred write, `batch_write`
    applies one commit. Records every commit so tests can check sizes and contents."""

    def __init__(self, fail_on_commit=None):
        self.docs = {}
        self.commits = []
        self.queries = []
        self.fail_on_commit = fail_on_commit

    def collection(self, name):
        return self.docs.setdefault(getattr(name, "value", name), {})

    def get(self, collection_name, doc_id):
        return self.collection(collection_name).get(doc_id)

    def query(self, collection_name, filters=None):
        self.queries.append((collection_name, filters))
        out = []
        for doc in self.collection(collection_name).values():
            ok = True
            for field, op, value in filters or []:
                if op == DbOperators.EQUAL:
                    ok &= doc.get(field) == value
                elif op == DbOperators.IN:
                    assert len(value) <= 30, "Firestore rejects an `in` filter over 30 values"
                    ok &= doc.get(field) in value
                else:
                    raise AssertionError(f"unexpected operator {op}")
            if ok:
                out.append(dict(doc))
        return out

    def operation(self, collection_name, doc_id, operation_type, data=None):
        assert isinstance(collection_name, str)
        return (collection_name, doc_id, operation_type, data)

    def batch_write(self, operations):
        assert len(operations) <= 500, "a single Firestore commit is limited to 500 writes"
        if self.fail_on_commit is not None and len(self.commits) == self.fail_on_commit:
            self.fail_on_commit = None
            raise RuntimeError("commit failed")
        self.commits.append(list(operations))
        for collection, doc_id, op_type, data in operations:
            if op_type == DbOperationTypes.SET:
                self.collection(collection)[doc_id] = json.loads(json.dumps(data))
            elif op_type == DbOperationTypes.DELETE:
                self.collection(collection).pop(doc_id, None)
            else:
                raise AssertionError(f"unexpected operation {op_type}")

    def written(self):
        return [op for commit in self.commits for op in commit if op[2] == DbOperationTypes.SET]


def flag(flag_id, server="web", **kw):
    return {
        "id": flag_id, "server": server, "slot": 1, "location_type": "file",
        "path": f"/opt/{flag_id}.txt", "operating_system": "linux", "points": 100, **kw,
    }


def make_unit(flags=None, instructor_id=(GM,), ctf=True, **kw):
    unit = {"id": UNIT_ID, "instructor_id": list(instructor_id), **kw}
    if ctf:
        unit["ctf"] = {"name": "Spring CTF", "flags": flags or [flag("user-flag"), flag("root-flag")]}
    return unit


def seed_db(db, unit, workouts):
    db.collection(DbCollections.UNIT)[unit["id"]] = unit
    for workout in workouts:
        db.collection(DbCollections.WORKOUT)[workout["id"]] = {"parent_id": unit["id"], **workout}


def workout_ids(n):
    # Ten lowercase letters, distinct per index.
    return ["w" + "".join(chr(97 + (i // 26 ** k) % 26) for k in range(9)) for i in range(n)]


def make_env(seed=SEED):
    env = MagicMock()
    env.ctf_flag_seed = seed
    return env


def user(email=GM, admin=False):
    return AgogeUser(uid="uid", email=email, permissions={"instructor": True, "admin": admin})


@pytest.fixture
def db():
    return FakeDb()


def make_event(db, env_dict=None, seed=SEED):
    return CtfEvent(env_dict=env_dict if env_dict is not None else {}, db=db, env=make_env(seed))


# --- SC-1: a valid create ---------------------------------------------------------

def test_create_writes_event_boards_and_digests(db):
    workouts = [
        {"id": "wkoutaaaaa", "team_name": "Red Team", "student_email": "r@x.edu"},
        {"id": "wkoutbbbbb", "student_email": "b@x.edu"},
        {"id": "wkoutccccc"},
    ]
    seed_db(db, make_unit(), workouts)

    ctf_id = make_event(db).create(UNIT_ID, user())

    assert re.fullmatch(r"[a-z]{10}", ctf_id)
    event = CtfEventModel(**db.get(DbCollections.CTF, ctf_id))
    assert event.unit_id == UNIT_ID
    assert event.instructor_id == [GM]
    assert event.state == CtfStates.DRAFT.value
    assert event.seed_version == 1
    assert event.board_ids == ["wkoutaaaaa", "wkoutbbbbb", "wkoutccccc"]
    assert event.spec.name == "Spring CTF"
    assert event.boards_pending == 0

    boards = {b["workout_id"]: CtfBoardModel(**b) for b in db.collection(DbCollections.CTF_BOARD).values()}
    assert set(boards) == set(event.board_ids)
    assert boards["wkoutaaaaa"].team_name == "Red Team"
    assert boards["wkoutbbbbb"].team_name == "b@x.edu"
    assert boards["wkoutccccc"].team_name == "wkoutccccc"
    for workout_id, board in boards.items():
        assert board.id == f"{ctf_id}-{workout_id}"
        assert board.ctf_id == ctf_id
        assert board.active is True
        assert board.arm_status == "pending"
        assert [f.flag_id for f in board.flags] == ["user-flag", "root-flag"]
        for f in board.flags:
            assert f.plant_status == "pending"
            assert f.digest == flag_digest(derive_flag_value(SEED, workout_id, f.flag_id, 1, "agoge"))

    digests = db.collection(DbCollections.CTF_DIGEST)
    assert len(digests) == 3 * 2
    for doc_id, doc in digests.items():
        digest = CtfDigestModel(**doc)
        assert doc_id == digest.digest
        assert digest.ctf_id == ctf_id
        board = boards[digest.workout_id]
        assert {f.flag_id: f.digest for f in board.flags}[digest.flag_id] == digest.digest


def test_digests_use_the_spec_flag_prefix(db):
    unit = make_unit()
    unit["ctf"]["scoring"] = {"flag_prefix": "acme"}
    seed_db(db, unit, [{"id": "wkoutaaaaa"}])

    make_event(db).create(UNIT_ID, user())

    [board] = db.collection(DbCollections.CTF_BOARD).values()
    expected = flag_digest(derive_flag_value(SEED, "wkoutaaaaa", "user-flag", 1, "acme"))
    assert board["flags"][0]["digest"] == expected


def test_decoy_flags_get_digests_too(db):
    seed_db(db, make_unit(flags=[flag("real"), flag("decoy-one", points=-50, decoy=True)]), [{"id": "wkoutaaaaa"}])
    make_event(db).create(UNIT_ID, user())
    flag_ids = {d["flag_id"] for d in db.collection(DbCollections.CTF_DIGEST).values()}
    assert flag_ids == {"real", "decoy-one"}


def test_event_is_written_last(db):
    # A failure before the final commit must never leave an event whose boards are missing.
    seed_db(db, make_unit(), [{"id": w} for w in workout_ids(5)])
    make_event(db).create(UNIT_ID, user())
    collections = [op[0] for op in db.written()]
    assert collections[-1] == DbCollections.CTF.value
    assert collections.count(DbCollections.CTF.value) == 1


def test_single_instructor_string_is_normalized_to_a_list(db):
    unit = make_unit()
    unit["instructor_id"] = GM
    seed_db(db, unit, [{"id": "wkoutaaaaa"}])
    ctf_id = make_event(db).create(UNIT_ID, user())
    assert db.get(DbCollections.CTF, ctf_id)["instructor_id"] == [GM]


def test_admin_not_on_the_unit_may_create(db):
    seed_db(db, make_unit(), [{"id": "wkoutaaaaa"}])
    ctf_id = make_event(db).create(UNIT_ID, user(email="root@example.edu", admin=True))
    assert db.get(DbCollections.CTF, ctf_id) is not None


def test_workouts_being_deleted_get_no_board(db):
    seed_db(db, make_unit(), [
        {"id": "wkoutaaaaa", "state": WorkoutStates.RUNNING.value},
        {"id": "wkoutbbbbb", "state": WorkoutStates.DELETED.value},
        {"id": "wkoutccccc", "state": WorkoutStates.DELETING_SERVERS.value},
    ])
    ctf_id = make_event(db).create(UNIT_ID, user())
    assert db.get(DbCollections.CTF, ctf_id)["board_ids"] == ["wkoutaaaaa"]


def test_workouts_of_other_units_are_ignored(db):
    seed_db(db, make_unit(), [{"id": "wkoutaaaaa"}])
    db.collection(DbCollections.WORKOUT)["wkoutzzzzz"] = {"id": "wkoutzzzzz", "parent_id": "otherunitx"}
    ctf_id = make_event(db).create(UNIT_ID, user())
    assert db.get(DbCollections.CTF, ctf_id)["board_ids"] == ["wkoutaaaaa"]


# --- commits of at most 500 writes ---------------------------------------------------

def test_large_event_is_split_into_commits_of_at_most_500(db):
    # 100 boards x 6 flags = 600 digests + 100 boards + 1 event = 701 writes.
    flags = [flag(f"flag-{i}") for i in range(6)]
    seed_db(db, make_unit(flags=flags), [{"id": w} for w in workout_ids(100)])

    make_event(db).create(UNIT_ID, user())

    assert [len(c) for c in db.commits] == [500, 201]
    assert len(db.collection(DbCollections.CTF_DIGEST)) == 600
    assert len(db.collection(DbCollections.CTF_BOARD)) == 100


def test_active_board_check_queries_in_chunks_of_30(db):
    seed_db(db, make_unit(), [{"id": w} for w in workout_ids(65)])
    make_event(db).create(UNIT_ID, user())
    board_queries = [f for c, f in db.queries if c == DbCollections.CTF_BOARD]
    assert [len(f[0][2]) for f in board_queries] == [30, 30, 5]
    for filters in board_queries:
        assert ("active", DbOperators.EQUAL, True) in filters


def test_failed_commit_rolls_back_earlier_commits_and_reraises():
    db = FakeDb(fail_on_commit=1)
    flags = [flag(f"flag-{i}") for i in range(6)]
    seed_db(db, make_unit(flags=flags), [{"id": w} for w in workout_ids(100)])

    with pytest.raises(RuntimeError, match="commit failed"):
        make_event(db).create(UNIT_ID, user())

    assert db.collection(DbCollections.CTF) == {}
    assert db.collection(DbCollections.CTF_BOARD) == {}
    assert db.collection(DbCollections.CTF_DIGEST) == {}


def test_failed_rollback_does_not_mask_the_original_error():
    db = FakeDb(fail_on_commit=1)
    seed_db(db, make_unit(flags=[flag(f"flag-{i}") for i in range(6)]), [{"id": w} for w in workout_ids(100)])
    original = db.batch_write
    calls = []

    def batch_write(operations):
        calls.append(operations)
        if operations[0][2] == DbOperationTypes.DELETE:
            raise OSError("rollback failed")
        original(operations)

    db.batch_write = batch_write
    with pytest.raises(RuntimeError, match="commit failed"):
        make_event(db).create(UNIT_ID, user())
    assert calls[-1][0][2] == DbOperationTypes.DELETE


# --- refusals, each before any write -------------------------------------------------

def assert_nothing_written(db):
    assert db.commits == []


def test_unknown_unit_raises_not_found(db):
    with pytest.raises(NotFound):
        make_event(db).create(UNIT_ID, user())
    assert_nothing_written(db)


@pytest.mark.parametrize("unit", [make_unit(ctf=False), make_unit(ctf=False, ctf_null=True)])
def test_unit_without_ctf_raises_bad_request(db, unit):
    # SC-2: absent and explicit-null ctf both refuse.
    unit = dict(unit)
    if unit.pop("ctf_null", False):
        unit["ctf"] = None
    seed_db(db, unit, [{"id": "wkoutaaaaa"}])
    with pytest.raises(BadRequest):
        make_event(db).create(UNIT_ID, user())
    assert_nothing_written(db)


def test_malformed_ctf_block_raises_bad_request(db):
    unit = make_unit()
    unit["ctf"]["flags"] = []
    seed_db(db, unit, [{"id": "wkoutaaaaa"}])
    with pytest.raises(BadRequest):
        make_event(db).create(UNIT_ID, user())
    assert_nothing_written(db)


def test_caller_not_on_the_unit_raises_unauthorized(db):
    seed_db(db, make_unit(), [{"id": "wkoutaaaaa"}])
    with pytest.raises(Unauthorized):
        make_event(db).create(UNIT_ID, user(email="other@example.edu"))
    assert_nothing_written(db)


def test_unit_with_no_workouts_raises_bad_request(db):
    seed_db(db, make_unit(), [])
    with pytest.raises(BadRequest):
        make_event(db).create(UNIT_ID, user())
    assert_nothing_written(db)


@pytest.mark.parametrize("env_dict, limit", [({}, 100), ({"ctf_max_boards": 3}, 3), ({"ctf_max_boards": "3"}, 3)])
def test_more_workouts_than_ctf_max_boards_raises_bad_request(db, env_dict, limit):
    seed_db(db, make_unit(), [{"id": w} for w in workout_ids(limit + 1)])
    with pytest.raises(BadRequest, match=f"at most {limit}"):
        make_event(db, env_dict=env_dict).create(UNIT_ID, user())
    assert_nothing_written(db)


def test_exactly_ctf_max_boards_workouts_is_allowed(db):
    seed_db(db, make_unit(), [{"id": w} for w in workout_ids(3)])
    make_event(db, env_dict={"ctf_max_boards": 3}).create(UNIT_ID, user())
    assert len(db.collection(DbCollections.CTF_BOARD)) == 3


@pytest.mark.parametrize("bad", [True, 0, -5, "many", None])
def test_invalid_ctf_max_boards_falls_back_to_100(db, bad):
    seed_db(db, make_unit(), [{"id": w} for w in workout_ids(2)])
    make_event(db, env_dict={"ctf_max_boards": bad}).create(UNIT_ID, user())
    assert len(db.collection(DbCollections.CTF_BOARD)) == 2


def test_workout_on_an_active_board_raises_conflict(db):
    seed_db(db, make_unit(), [{"id": "wkoutaaaaa"}, {"id": "wkoutbbbbb"}])
    db.collection(DbCollections.CTF_BOARD)["oldctfxxxx-wkoutbbbbb"] = {
        "id": "oldctfxxxx-wkoutbbbbb", "workout_id": "wkoutbbbbb", "active": True,
    }
    with pytest.raises(Conflict, match="wkoutbbbbb"):
        make_event(db).create(UNIT_ID, user())
    assert_nothing_written(db)


def test_workout_on_an_inactive_board_is_allowed(db):
    seed_db(db, make_unit(), [{"id": "wkoutaaaaa"}])
    db.collection(DbCollections.CTF_BOARD)["oldctfxxxx-wkoutaaaaa"] = {
        "id": "oldctfxxxx-wkoutaaaaa", "workout_id": "wkoutaaaaa", "active": False,
    }
    ctf_id = make_event(db).create(UNIT_ID, user())
    assert db.get(DbCollections.CTF_BOARD, f"{ctf_id}-wkoutaaaaa")["active"] is True


@pytest.mark.parametrize("seed", [None, ""])
def test_missing_seed_raises_service_unavailable(db, seed):
    seed_db(db, make_unit(), [{"id": "wkoutaaaaa"}])
    with pytest.raises(ServiceUnavailable) as exc:
        make_event(db, seed=seed).create(UNIT_ID, user())
    assert str(exc.value.message) == NOT_PROVISIONED_MESSAGE
    assert_nothing_written(db)


# --- SC-4: no flag value is ever stored ----------------------------------------------

def test_no_written_document_contains_a_flag_value(db):
    unit = make_unit(flags=[flag("user-flag"), flag("decoy-x", points=-5, decoy=True)])
    seed_db(db, unit, [{"id": w} for w in workout_ids(4)])

    make_event(db).create(UNIT_ID, user())

    writes = db.written()
    assert writes
    blob = json.dumps([data for *_, data in writes])
    assert not FLAG_PATTERN.search(blob)
    # And no derived value appears in any other form (e.g. without the prefix).
    for workout_id in workout_ids(4):
        for flag_id in ("user-flag", "decoy-x"):
            value = derive_flag_value(SEED, workout_id, flag_id, 1, "agoge")
            assert value[len("agoge{"):-1] not in blob
    assert SEED not in blob
