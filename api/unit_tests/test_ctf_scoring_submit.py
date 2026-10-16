"""CtfScoring.submit (PRD Submission Algorithm steps 1, 3-7; SC-4, SC-10, SC-12)."""
import copy
import re
import threading

import pytest

from common.constants.database import DbCollections
from common.constants.states import CtfStates
from common.exceptions.agoge import Conflict, NotFound
from common.utilities.ctf_flags import derive_flag_value, flag_digest
from core.ctf.scoring import CtfScoring

SEED = "test-seed"
CTF_ID = "ctfaaaaaaa"
OTHER_CTF = "ctfzzzzzzz"
A, B = "wkaaaaaaaa", "wkbbbbbbbb"
FLAGS = [
    {"id": "web1", "server": "web", "slot": 1, "points": 100,
     "location_type": "file", "path": "/root/flag.txt", "operating_system": "linux"},
    {"id": "web2", "server": "web", "slot": 2, "points": 200,
     "location_type": "file", "path": "/root/flag2.txt", "operating_system": "linux"},
    {"id": "trap", "server": "web", "slot": 1, "points": -50, "decoy": True,
     "location_type": "file", "path": "/root/trap.txt", "operating_system": "linux"},
]


def flag(workout_id, flag_id, ctf_seed=SEED):
    return derive_flag_value(ctf_seed, workout_id, flag_id, 1)


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
        # Reading outside the transaction would let two submissions both see the flag unsolved.
        assert transaction is not None, "the award must read the board inside its transaction"
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

    def __init__(self, barrier=None):
        self.store = {}
        self.db = FakeClient(self.store)
        self.inserted = []
        self.transactions = 0
        self._lock = threading.Lock()
        self._barrier = barrier

    def col(self, collection):
        return self.store.setdefault(collection.value, {})

    def get(self, collection_name, doc_id):
        return copy.deepcopy(self.col(collection_name).get(doc_id))

    def query(self, collection_name, filters=None, limit=None):
        docs = self.col(collection_name).values()
        return [copy.deepcopy(d) for d in docs if all(d.get(field) == value for field, _, value in filters or [])]

    def insert(self, collection_name, data):
        self.inserted.append((collection_name, copy.deepcopy(data)))
        self.col(collection_name)[data["id"]] = copy.deepcopy(data)
        return data["id"]

    def transaction(self, operation_func):
        if self._barrier is not None:
            # Both submitters have done their board query before either transaction starts.
            self._barrier.wait(timeout=5)
        with self._lock:
            self.transactions += 1
            transaction = FakeTransaction()
            result = operation_func(transaction)
            for doc_ref, data in transaction.writes:
                self.store[doc_ref.collection][doc_ref.id].update(data)
            return result


def seed_event(db, state=CtfStates.RUNNING, ctf_id=CTF_ID, boards=(A, B), active=True, **scoring):
    db.col(DbCollections.CTF)[ctf_id] = {
        "id": ctf_id, "unit_id": "unitabcdef", "instructor_id": ["gm@example.edu"],
        "spec": {"name": "Spring CTF", "flags": FLAGS, "scoring": scoring},
        "creation_timestamp": 1_700_000_000.0, "board_ids": list(boards),
        "state": state.value, "state_timestamp": "2026-10-16T00:00:00+00:00",
    }
    for workout_id in boards:
        db.col(DbCollections.CTF_BOARD)[f"{ctf_id}-{workout_id}"] = {
            "id": f"{ctf_id}-{workout_id}", "workout_id": workout_id, "ctf_id": ctf_id,
            "team_name": workout_id, "active": active,
            "flags": [{"flag_id": f["id"], "digest": flag_digest(flag(workout_id, f["id"]))} for f in FLAGS],
        }
        for f in FLAGS:
            digest = flag_digest(flag(workout_id, f["id"]))
            db.col(DbCollections.CTF_DIGEST)[digest] = {
                "digest": digest, "ctf_id": ctf_id, "workout_id": workout_id, "flag_id": f["id"],
            }


def board(db, workout_id=A, ctf_id=CTF_ID):
    return db.col(DbCollections.CTF_BOARD)[f"{ctf_id}-{workout_id}"]


def flag_state(db, flag_id, workout_id=A):
    return next(f for f in board(db, workout_id)["flags"] if f["flag_id"] == flag_id)


def submissions(db):
    return [data for collection, data in db.inserted if collection == DbCollections.CTF_SUBMISSION]


@pytest.fixture
def db():
    store = FakeDb()
    seed_event(store)
    return store


def submit(db, workout_id, value, ip="10.0.0.1"):
    return CtfScoring(db=db).submit(workout_id, value, ip)


# SC-10
def test_cross_submission_answers_incorrect_and_records_matched_board(db):
    response = submit(db, A, flag(B, "web1"))

    assert response.verdict == "incorrect" and response.correct is False and response.points_awarded == 0
    [row] = submissions(db)
    assert row["verdict"] == "cross_submission"
    assert row["matched_workout_id"] == B
    assert row["workout_id"] == A and row["flag_id"] == "web1" and row["ctf_id"] == CTF_ID
    assert row["points_awarded"] == 0 and row["origin_ip"] == "10.0.0.1"
    # Neither board is scored or touched.
    assert db.transactions == 0
    assert board(db, A).get("score", 0) == 0 and board(db, B).get("score", 0) == 0


def test_correct_submission_solves_and_scores(db):
    response = submit(db, A, flag(A, "web1"))

    assert response.verdict == "correct" and response.correct is True and response.points_awarded == 100
    state = flag_state(db, "web1")
    assert state["solved"] is True and state["solved_at"] is not None and state["attempts"] == 1
    assert board(db)["score"] == 100 and board(db)["solve_count"] == 1
    assert board(db)["last_solve_at"] == state["solved_at"]
    [row] = submissions(db)
    assert row["verdict"] == "correct" and row["points_awarded"] == 100 and row["flag_id"] == "web1"


def test_submission_is_normalized_before_matching(db):
    assert submit(db, A, "  " + flag(A, "web1").upper() + "\n").verdict == "correct"


def test_second_submission_is_duplicate_and_scores_once(db):
    submit(db, A, flag(A, "web1"))
    response = submit(db, A, flag(A, "web1"))

    assert response.verdict == "duplicate" and response.correct is False and response.points_awarded == 0
    assert board(db)["score"] == 100 and board(db)["solve_count"] == 1
    assert flag_state(db, "web1")["attempts"] == 2
    assert [r["verdict"] for r in submissions(db)] == ["correct", "duplicate"]


# SC-12
def test_concurrent_correct_submissions_award_once():
    db = FakeDb(barrier=threading.Barrier(2))
    seed_event(db)
    results = []

    def worker():
        results.append(submit(db, A, flag(A, "web2")).verdict)

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    assert sorted(results) == ["correct", "duplicate"]
    assert board(db)["score"] == 200 and board(db)["solve_count"] == 1
    assert sorted(r["verdict"] for r in submissions(db)) == ["correct", "duplicate"]


def test_decoy_applies_points_and_counts_without_solving(db):
    response = submit(db, A, flag(A, "trap"))

    assert response.verdict == "decoy" and response.correct is False
    # Hidden unless reveal_decoy_penalty.
    assert response.points_awarded == 0
    assert board(db)["score"] == -50 and board(db)["decoy_count"] == 1
    assert board(db).get("solve_count", 0) == 0 and flag_state(db, "trap")["solved"] is False
    [row] = submissions(db)
    assert row["verdict"] == "decoy" and row["points_awarded"] == -50

    submit(db, A, flag(A, "trap"))
    assert board(db)["score"] == -100 and board(db)["decoy_count"] == 2


def test_decoy_penalty_shown_when_revealed():
    db = FakeDb()
    seed_event(db, reveal_decoy_penalty=True)
    assert submit(db, A, flag(A, "trap")).points_awarded == -50


def test_unknown_value_is_incorrect_with_null_flag_id(db):
    response = submit(db, A, "not a flag")

    assert response.verdict == "incorrect" and response.correct is False
    [row] = submissions(db)
    assert row["verdict"] == "incorrect" and row["flag_id"] is None and row["matched_workout_id"] is None
    assert db.transactions == 0


def test_well_formed_wrong_value_records_parsed_flag_id(db):
    response = submit(db, A, "agoge{web1_" + "0" * 20 + "}")

    assert response.verdict == "incorrect"
    assert submissions(db)[0]["flag_id"] == "web1"
    assert flag_state(db, "web1").get("attempts", 0) == 0


def test_digest_from_another_event_is_incorrect(db):
    seed_event(db, ctf_id=OTHER_CTF, boards=(A,), active=False)
    # Same workout, other event: its digest docs share ids with this event's, so make them differ.
    other_value = flag(A, "web1", ctf_seed="other-seed")
    digest = flag_digest(other_value)
    db.col(DbCollections.CTF_DIGEST)[digest] = {"digest": digest, "ctf_id": OTHER_CTF, "workout_id": A, "flag_id": "web1"}

    response = submit(db, A, other_value)

    assert response.verdict == "incorrect"
    assert submissions(db)[0]["verdict"] == "incorrect" and submissions(db)[0]["ctf_id"] == CTF_ID
    assert db.transactions == 0


@pytest.mark.parametrize("state", [s for s in CtfStates if s != CtfStates.RUNNING])
def test_closed_event_records_and_raises_conflict(state):
    db = FakeDb()
    seed_event(db, state=state)

    with pytest.raises(Conflict, match="^Submissions are closed.$"):
        submit(db, A, flag(A, "web1"))

    [row] = submissions(db)
    assert row["verdict"] == "closed" and row["flag_id"] == "web1" and row["points_awarded"] == 0
    assert db.transactions == 0 and flag_state(db, "web1").get("solved", False) is False


def test_no_active_board_is_not_found():
    db = FakeDb()
    seed_event(db, active=False)

    with pytest.raises(NotFound):
        submit(db, A, flag(A, "web1"))
    assert submissions(db) == []


def test_missing_event_is_not_found(db):
    del db.col(DbCollections.CTF)[CTF_ID]

    with pytest.raises(NotFound):
        submit(db, A, flag(A, "web1"))
    assert submissions(db) == []


def test_matched_flag_missing_from_board_is_incorrect(db):
    board(db)["flags"] = [f for f in board(db)["flags"] if f["flag_id"] != "web1"]

    assert submit(db, A, flag(A, "web1")).verdict == "incorrect"
    assert board(db).get("score", 0) == 0


# SC-4
@pytest.mark.parametrize("value_of", [
    lambda: flag(A, "web1"), lambda: flag(B, "web1"), lambda: flag(A, "trap"), lambda: "agoge{guess}",
])
def test_no_written_document_contains_a_flag_value(db, value_of):
    submit(db, A, value_of())
    submit(db, A, value_of())

    written = repr(db.inserted) + repr(db.store[DbCollections.CTF_BOARD.value])
    assert not re.search(r"agoge\{", written, re.IGNORECASE)
