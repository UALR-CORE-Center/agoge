"""CtfScoring.adjust (PRD H7): a manual score change on one board, audited as SCORE_ADJUST."""
import copy
import threading

import pytest

from common.constants.database import DbCollections
from common.constants.states import CtfStates
from common.exceptions.agoge import BadRequest, Conflict, NotFound, Unauthorized
from common.models.users import AgogeUser
from core.ctf.scoring import CtfScoring

CTF_ID = "ctfaaaaaaa"
A, B = "wkaaaaaaaa", "wkbbbbbbbb"
INSTRUCTOR = AgogeUser(uid="gm", email="gm@example.edu", permissions={"instructor": True, "admin": False})
STRANGER = AgogeUser(uid="other", email="other@example.edu", permissions={"instructor": True, "admin": False})
ADMIN = AgogeUser(uid="root", email="root@example.edu", permissions={"admin": True})
FLAGS = [
    {"id": "web1", "server": "web", "slot": 1, "points": 100,
     "location_type": "file", "path": "/root/flag.txt", "operating_system": "linux"},
]


class FakeSnapshot:
    def __init__(self, data):
        self._data = data
        self.exists = data is not None

    def to_dict(self):
        return copy.deepcopy(self._data)


class FakeDocRef:
    def __init__(self, store, collection, doc_id):
        self.store, self.collection, self.id = store, collection, doc_id

    def get(self, transaction=None):
        # A read outside the transaction could overrun a concurrent solve or archive.
        assert transaction is not None, "adjust must read inside its transaction"
        return FakeSnapshot(self.store.get(self.collection, {}).get(self.id))


class FakeClient:
    def __init__(self, store):
        self.store = store

    def collection(self, name):
        return type("Col", (), {"document": lambda _, doc_id: FakeDocRef(self.store, name, doc_id)})()


class FakeTransaction:
    def __init__(self):
        self.writes = []

    def update(self, doc_ref, data):
        self.writes.append((doc_ref, copy.deepcopy(dict(data))))


class FakeDb:
    """Transactions are serialized under a lock, which is the outcome Firestore's retries guarantee."""

    def __init__(self):
        self.store = {}
        self.db = FakeClient(self.store)
        self.inserted = []
        self.updates = []
        self._lock = threading.Lock()

    def col(self, collection):
        return self.store.setdefault(collection.value, {})

    def get(self, collection_name, doc_id):
        return copy.deepcopy(self.col(collection_name).get(doc_id))

    def query(self, collection_name, filters=None, limit=None):
        docs = self.col(collection_name).values()
        return [copy.deepcopy(d) for d in docs if all(d.get(field) == value for field, _, value in filters or [])]

    def insert(self, collection_name, data):
        self.inserted.append((collection_name, copy.deepcopy(data)))

    def transaction(self, operation_func):
        with self._lock:
            transaction = FakeTransaction()
            result = operation_func(transaction)
            for doc_ref, data in transaction.writes:
                self.updates.append((doc_ref.collection, doc_ref.id, data))
                self.store[doc_ref.collection][doc_ref.id].update(data)
            return result


def seed_event(db, state=CtfStates.RUNNING, score=300, flag_prefix="agoge"):
    db.col(DbCollections.CTF)[CTF_ID] = {
        "id": CTF_ID, "unit_id": "unitabcdef", "instructor_id": ["gm@example.edu"],
        "spec": {"name": "Spring CTF", "flags": FLAGS, "scoring": {"flag_prefix": flag_prefix}},
        "creation_timestamp": 1_700_000_000.0, "board_ids": [A, B],
        "state": state.value, "state_timestamp": "2026-10-16T00:00:00+00:00",
    }
    for workout_id in (A, B):
        db.col(DbCollections.CTF_BOARD)[f"{CTF_ID}-{workout_id}"] = {
            "id": f"{CTF_ID}-{workout_id}", "workout_id": workout_id, "ctf_id": CTF_ID,
            "team_name": workout_id, "active": True, "score": score, "solve_count": 1,
            "decoy_count": 0, "last_solve_at": 1_700_000_500.0,
            "flags": [{"flag_id": "web1", "digest": "d" * 64, "solved": True}],
        }


def board(db, workout_id=A):
    return db.col(DbCollections.CTF_BOARD)[f"{CTF_ID}-{workout_id}"]


def log_rows(db):
    return [row for collection, row in db.inserted if collection == DbCollections.CTF_LOG]


@pytest.fixture
def db():
    fake = FakeDb()
    seed_event(fake)
    return fake


def test_positive_delta_raises_score_and_returns_it(db):
    assert CtfScoring(db=db).adjust(CTF_ID, A, 50, "Bonus for the write-up", INSTRUCTOR) == 350
    assert board(db)["score"] == 350


def test_negative_delta_can_take_score_below_zero(db):
    assert CtfScoring(db=db).adjust(CTF_ID, A, -400, "Rules violation", INSTRUCTOR) == -100
    assert board(db)["score"] == -100


def test_writes_only_the_score_of_the_named_board(db):
    before_b = copy.deepcopy(board(db, B))
    CtfScoring(db=db).adjust(CTF_ID, A, 10, "Correction", INSTRUCTOR)

    # Only `score` is written, so solve fields set by a concurrent submission are not overrun.
    assert db.updates == [(DbCollections.CTF_BOARD.value, f"{CTF_ID}-{A}", {"score": 310})]
    assert board(db, B) == before_b
    assert board(db)["solve_count"] == 1


def test_writes_one_ok_score_adjust_row(db):
    CtfScoring(db=db).adjust(CTF_ID, A, -25, "Shared a flag in chat", INSTRUCTOR)

    rows = log_rows(db)
    assert len(rows) == 1
    row = rows[0]
    assert row["ctf_id"] == CTF_ID
    assert row["action"] == "SCORE_ADJUST"
    assert row["actor"] == "gm@example.edu"
    assert row["target"] == A
    assert row["result"] == "OK"
    assert row["detail"] == {"delta": -25, "reason": "Shared a flag in chat", "previous_score": 300, "score": 275}


def test_successive_adjustments_accumulate(db):
    scoring = CtfScoring(db=db)
    scoring.adjust(CTF_ID, A, 10, "First", INSTRUCTOR)
    assert scoring.adjust(CTF_ID, A, 5, "Second", INSTRUCTOR) == 315
    assert [row["detail"]["previous_score"] for row in log_rows(db)] == [300, 310]


def test_admin_not_on_the_event_may_adjust(db):
    assert CtfScoring(db=db).adjust(CTF_ID, A, 1, "Admin fix", ADMIN) == 301
    assert log_rows(db)[0]["actor"] == "root@example.edu"


def test_non_instructor_is_refused_and_logged_denied(db):
    with pytest.raises(Unauthorized):
        CtfScoring(db=db).adjust(CTF_ID, A, 100, "Please", STRANGER)

    assert board(db)["score"] == 300
    assert db.updates == []
    [row] = log_rows(db)
    assert row["result"] == "DENIED"
    assert row["actor"] == "other@example.edu"
    # The reason is recorded only for an adjustment that happened.
    assert row["detail"] == {"delta": 100}


@pytest.mark.parametrize("state", [s for s in CtfStates if s != CtfStates.ARCHIVED])
def test_allowed_in_every_state_but_archived(state):
    db = FakeDb()
    seed_event(db, state=state)
    assert CtfScoring(db=db).adjust(CTF_ID, A, 7, "Correction", INSTRUCTOR) == 307


def test_archived_event_is_read_only():
    db = FakeDb()
    seed_event(db, state=CtfStates.ARCHIVED)

    with pytest.raises(Conflict):
        CtfScoring(db=db).adjust(CTF_ID, A, 7, "Too late", INSTRUCTOR)

    assert db.updates == []
    assert [row["result"] for row in log_rows(db)] == ["DENIED"]


def test_missing_event_is_not_found_and_logged(db):
    with pytest.raises(NotFound):
        CtfScoring(db=db).adjust("ctfzzzzzzz", A, 7, "Correction", INSTRUCTOR)

    assert db.updates == []
    # SC-18 counts NotFound as ERROR, not DENIED.
    [row] = log_rows(db)
    assert (row["ctf_id"], row["result"]) == ("ctfzzzzzzz", "ERROR")


def test_workout_not_on_the_event_is_not_found(db):
    # A board document that exists but is not in board_ids is not this event's board.
    db.col(DbCollections.CTF_BOARD)[f"{CTF_ID}-wkcccccccc"] = {**copy.deepcopy(board(db)), "workout_id": "wkcccccccc"}

    with pytest.raises(NotFound):
        CtfScoring(db=db).adjust(CTF_ID, "wkcccccccc", 7, "Correction", INSTRUCTOR)

    assert db.updates == []
    assert [row["result"] for row in log_rows(db)] == ["ERROR"]


def test_missing_board_document_is_not_found(db):
    del db.col(DbCollections.CTF_BOARD)[f"{CTF_ID}-{A}"]

    with pytest.raises(NotFound):
        CtfScoring(db=db).adjust(CTF_ID, A, 7, "Correction", INSTRUCTOR)

    assert db.updates == []


@pytest.mark.parametrize("reason", [
    "Pasted agoge{web1_0123456789abcdef0123} in chat",
    "AGOGE{WEB1_X}",
    "spring{web1_0123456789abcdef0123}",
])
def test_reason_holding_a_flag_is_refused_before_any_write(reason):
    db = FakeDb()
    seed_event(db, flag_prefix="spring")

    with pytest.raises(BadRequest):
        CtfScoring(db=db).adjust(CTF_ID, A, -50, reason, INSTRUCTOR)

    assert board(db)["score"] == 300
    assert db.updates == []
    [row] = log_rows(db)
    assert row["result"] == "DENIED"
    # The flag must never reach an audit row.
    assert row["detail"] == {"delta": -50}
    assert not any("{" in str(value) for value in row.values() if not isinstance(value, dict))


def test_prefix_without_a_brace_is_an_ordinary_reason():
    db = FakeDb()
    seed_event(db, flag_prefix="spring")
    CtfScoring(db=db).adjust(CTF_ID, A, 5, "Spring agoge event bonus", INSTRUCTOR)
    assert log_rows(db)[0]["detail"]["reason"] == "Spring agoge event bonus"


def test_concurrent_adjustments_both_apply(db):
    # Each adjustment re-reads the board inside its transaction, so neither overwrites the other.
    scoring = CtfScoring(db=db)
    threads = [threading.Thread(target=scoring.adjust, args=(CTF_ID, A, delta, "Race", INSTRUCTOR))
               for delta in (10, 20)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert board(db)["score"] == 330
    assert len(log_rows(db)) == 2
