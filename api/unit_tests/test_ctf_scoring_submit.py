"""CtfScoring.submit (PRD Submission Algorithm steps 1-7; SC-4, SC-10, SC-11, SC-12)."""
import copy
import re
import threading

import pytest

from common.constants.database import DbCollections
from common.constants.states import CtfStates
from common.exceptions.agoge import Conflict, NotFound, RateLimitExceeded
from common.utilities.ctf_flags import derive_flag_value, flag_digest
from core.ctf import scoring
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
        transaction.read_collections.add(self.collection)
        return FakeSnapshot(self.store.get(self.collection, {}).get(self.id))


class FakeClient:
    def __init__(self, store):
        self.store = store

    def collection(self, name):
        return type("Col", (), {"document": lambda _, doc_id: FakeDocRef(self.store, name, doc_id)})()


class FakeTransaction:
    def __init__(self):
        self.writes = []
        self.read_collections = set()

    def update(self, doc_ref, data):
        self.writes.append(("update", doc_ref, copy.deepcopy(dict(data))))

    def set(self, doc_ref, data):
        self.writes.append(("set", doc_ref, copy.deepcopy(dict(data))))


class FakeDb:
    """Transactions are serialized under a lock, which is the outcome Firestore's retries guarantee."""

    def __init__(self, barrier=None):
        self.store = {}
        self.db = FakeClient(self.store)
        self.inserted = []
        # Board transactions only: every open-event submission also runs one rate-limit transaction.
        self.transactions = 0
        self.rate_limit_transactions = 0
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
            transaction = FakeTransaction()
            result = operation_func(transaction)
            if DbCollections.CTF_BOARD.value in transaction.read_collections:
                self.transactions += 1
            if DbCollections.CTF_RATE_LIMIT.value in transaction.read_collections:
                self.rate_limit_transactions += 1
            for kind, doc_ref, data in transaction.writes:
                docs = self.store.setdefault(doc_ref.collection, {})
                if kind == "set":
                    docs[doc_ref.id] = data
                else:
                    # Firestore's update fails on a missing document.
                    docs[doc_ref.id].update(data)
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
    # Step 1 precedes step 2: a closed event never touches the rate-limit counter.
    assert db.rate_limit_transactions == 0 and not db.store.get(DbCollections.CTF_RATE_LIMIT.value)


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


# SC-11 (step 2)
class Clock:
    def __init__(self, now=1_800_000_000.0):
        self.now = now

    def __call__(self):
        return self.now


@pytest.fixture
def clock(monkeypatch):
    fake = Clock()
    monkeypatch.setattr(scoring.time, "time", fake)
    return fake


def wrong(workout_id, flag_id):
    # Well-formed for flag_id, so it parses into that flag's bucket, but matches no digest.
    return flag(workout_id, flag_id, ctf_seed="other-seed")


def rate_doc(db, bucket, workout_id=A):
    return db.col(DbCollections.CTF_RATE_LIMIT).get(f"{CTF_ID}-{workout_id}-{bucket}")


def test_eleventh_submission_for_one_flag_in_a_minute_is_rate_limited(db, clock):
    for i in range(10):
        clock.now += 5
        assert submit(db, A, wrong(A, "web1")).verdict == "incorrect"

    with pytest.raises(RateLimitExceeded, match=r"^Too many submissions for this challenge\. Try again in \d+ seconds\.$"):
        submit(db, A, flag(A, "web1"))

    rows = submissions(db)
    assert len(rows) == 11
    assert rows[-1]["verdict"] == "rate_limited" and rows[-1]["flag_id"] == "web1" and rows[-1]["points_awarded"] == 0
    # The rate-limited correct value was neither digest-matched nor scored.
    assert db.transactions == 0 and flag_state(db, "web1").get("solved", False) is False
    assert rate_doc(db, "web1")["count"] == 10


def test_retry_after_counts_down_to_the_window_end(db, clock):
    window_start = clock.now
    for _ in range(10):
        submit(db, A, wrong(A, "web1"))
    clock.now = window_start + 45.5

    with pytest.raises(RateLimitExceeded, match="Try again in 15 seconds"):
        submit(db, A, wrong(A, "web1"))


def test_refused_submissions_do_not_extend_the_window(db, clock):
    window_start = clock.now
    for _ in range(10):
        submit(db, A, wrong(A, "web1"))
    for _ in range(5):
        clock.now += 10
        with pytest.raises(RateLimitExceeded):
            submit(db, A, wrong(A, "web1"))

    assert rate_doc(db, "web1") == {"id": f"{CTF_ID}-{A}-web1", "window_start": window_start, "count": 10}


def test_new_window_resets_the_count(db, clock):
    window_start = clock.now
    for _ in range(10):
        submit(db, A, wrong(A, "web1"))
    clock.now = window_start + 60

    assert submit(db, A, flag(A, "web1")).verdict == "correct"
    assert rate_doc(db, "web1") == {"id": f"{CTF_ID}-{A}-web1", "window_start": window_start + 60, "count": 1}


def test_limit_is_per_flag_id(db, clock):
    for _ in range(10):
        submit(db, A, wrong(A, "web1"))

    assert submit(db, A, flag(A, "web2")).verdict == "correct"
    assert rate_doc(db, "web2")["count"] == 1


def test_limit_is_per_board(db, clock):
    for _ in range(10):
        submit(db, A, wrong(A, "web1"))

    assert submit(db, B, flag(B, "web1")).verdict == "correct"
    assert rate_doc(db, "web1", workout_id=B)["count"] == 1


def test_unparsed_values_share_one_bucket(db, clock):
    for i in range(10):
        submit(db, A, f"guess-{i}")

    with pytest.raises(RateLimitExceeded):
        submit(db, A, "agoge{not-a-real-format}")
    assert submissions(db)[-1]["verdict"] == "rate_limited" and submissions(db)[-1]["flag_id"] is None
    assert rate_doc(db, "unparsed")["count"] == 10


def test_configured_limit_is_honoured(clock):
    db = FakeDb()
    seed_event(db, submission_rate_limit=2)
    submit(db, A, wrong(A, "web1"))
    submit(db, A, wrong(A, "web1"))

    with pytest.raises(RateLimitExceeded):
        submit(db, A, wrong(A, "web1"))


def test_unreadable_counter_starts_a_fresh_window(db, clock):
    db.col(DbCollections.CTF_RATE_LIMIT)[f"{CTF_ID}-{A}-web1"] = {"id": f"{CTF_ID}-{A}-web1", "count": "lots"}

    assert submit(db, A, flag(A, "web1")).verdict == "correct"
    assert rate_doc(db, "web1") == {"id": f"{CTF_ID}-{A}-web1", "window_start": clock.now, "count": 1}


def test_rate_limit_is_one_transaction_per_submission(db, clock):
    submit(db, A, flag(A, "web1"))
    submit(db, A, flag(B, "web1"))
    submit(db, A, "guess")

    assert db.rate_limit_transactions == 3


def test_decoy_points_accumulate_across_decoys_of_different_values(monkeypatch):
    trap2 = {"id": "trap2", "server": "web", "slot": 2, "points": -30, "decoy": True,
             "location_type": "file", "path": "/root/t2.txt", "operating_system": "linux"}
    monkeypatch.setitem(globals(), "FLAGS", FLAGS + [trap2])
    db = FakeDb()
    seed_event(db)

    submit(db, A, flag(A, "trap"))
    assert board(db)["decoy_points"] == -50
    submit(db, A, flag(A, "trap2"))

    assert board(db)["decoy_points"] == -80
    assert board(db)["score"] == -80 and board(db)["decoy_count"] == 2


def test_decoy_points_stay_out_of_correct_submissions_and_survive_them(db):
    submit(db, A, flag(A, "trap"))
    submit(db, A, flag(A, "web1"))

    assert board(db)["decoy_points"] == -50
    assert board(db)["score"] == 50


def test_correct_submission_does_not_write_decoy_points(db):
    submit(db, A, flag(A, "web1"))

    assert board(db).get("decoy_points", 0) == 0
