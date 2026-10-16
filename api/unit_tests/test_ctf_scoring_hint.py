"""CtfScoring.hint (PRD H4): deducts hint_cost once; a second call returns the hint without deducting."""
import copy
import threading

import pytest

from common.constants.database import DbCollections
from common.constants.states import CtfStates
from common.exceptions.agoge import Conflict, NotFound
from common.models.response import CtfHintResponse
from core.ctf.scoring import CtfScoring

CTF_ID = "ctfaaaaaaa"
A, B = "wkaaaaaaaa", "wkbbbbbbbb"
FLAGS = [
    {"id": "web1", "server": "web", "slot": 1, "points": 100, "hint": "Look at robots.txt", "hint_cost": 25,
     "location_type": "file", "path": "/root/flag.txt", "operating_system": "linux"},
    {"id": "web2", "server": "web", "slot": 2, "points": 200, "hint": "Check sudo -l", "hint_cost": 50,
     "unlocks_after": ["web1"],
     "location_type": "file", "path": "/root/flag2.txt", "operating_system": "linux"},
    {"id": "free", "server": "web", "slot": 1, "points": 50, "hint": "It is in /tmp",
     "location_type": "file", "path": "/tmp/flag.txt", "operating_system": "linux"},
    {"id": "nohint", "server": "web", "slot": 1, "points": 50,
     "location_type": "file", "path": "/root/n.txt", "operating_system": "linux"},
    {"id": "trap", "server": "web", "slot": 1, "points": -50, "decoy": True, "hint": "Secret", "hint_cost": 5,
     "location_type": "file", "path": "/root/trap.txt", "operating_system": "linux"},
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
        # Reading outside the transaction would let two requests both see the hint untaken.
        assert transaction is not None, "the hint must read the board inside its transaction"
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
        self.updates = []
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

    def transaction(self, operation_func):
        if self._barrier is not None:
            # Both requesters have done their board query before either transaction starts.
            self._barrier.wait(timeout=5)
        with self._lock:
            transaction = FakeTransaction()
            result = operation_func(transaction)
            for doc_ref, data in transaction.writes:
                self.updates.append((doc_ref.collection, doc_ref.id, data))
                self.store[doc_ref.collection][doc_ref.id].update(data)
            return result


def seed_event(db, state=CtfStates.RUNNING, score=300, solved=()):
    db.col(DbCollections.CTF)[CTF_ID] = {
        "id": CTF_ID, "unit_id": "unitabcdef", "instructor_id": ["gm@example.edu"],
        "spec": {"name": "Spring CTF", "flags": FLAGS},
        "creation_timestamp": 1_700_000_000.0, "board_ids": [A, B],
        "state": state.value, "state_timestamp": "2026-10-16T00:00:00+00:00",
    }
    for workout_id in (A, B):
        db.col(DbCollections.CTF_BOARD)[f"{CTF_ID}-{workout_id}"] = {
            "id": f"{CTF_ID}-{workout_id}", "workout_id": workout_id, "ctf_id": CTF_ID,
            "team_name": workout_id, "active": True, "score": score,
            "flags": [{"flag_id": f["id"], "digest": "d" * 64, "solved": f["id"] in solved} for f in FLAGS],
        }


def board(db, workout_id=A):
    return db.col(DbCollections.CTF_BOARD)[f"{CTF_ID}-{workout_id}"]


def flag_state(db, flag_id, workout_id=A):
    return next(f for f in board(db, workout_id)["flags"] if f["flag_id"] == flag_id)


@pytest.fixture
def db():
    fake = FakeDb()
    seed_event(fake)
    return fake


def test_first_hint_deducts_cost_and_marks_taken(db):
    response = CtfScoring(db=db).hint(A, "web1")

    assert response == CtfHintResponse(flag_id="web1", hint="Look at robots.txt", hint_cost=25, score=275)
    assert board(db)["score"] == 275
    state = flag_state(db, "web1")
    assert state["hint_taken"] is True
    assert isinstance(state["hint_taken_at"], float)


def test_second_hint_returns_hint_without_deducting(db):
    scoring = CtfScoring(db=db)
    scoring.hint(A, "web1")
    writes = len(db.updates)

    again = scoring.hint(A, "web1")

    assert again == CtfHintResponse(flag_id="web1", hint="Look at robots.txt", hint_cost=25, score=275)
    assert board(db)["score"] == 275
    assert len(db.updates) == writes, "a repeat hint must not write"


def test_concurrent_first_hints_deduct_once():
    db = FakeDb(barrier=threading.Barrier(2))
    seed_event(db)
    results, errors = [], []

    def take():
        try:
            results.append(CtfScoring(db=db).hint(A, "web1"))
        except Exception as error:  # pragma: no cover - surfaced by the assertion below
            errors.append(error)

    threads = [threading.Thread(target=take) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert errors == []
    assert [r.score for r in results] == [275, 275]
    assert board(db)["score"] == 275
    assert len(db.updates) == 1


def test_hint_touches_only_the_callers_board(db):
    CtfScoring(db=db).hint(A, "web1")

    assert {(collection, doc_id) for collection, doc_id, _ in db.updates} == {
        (DbCollections.CTF_BOARD.value, f"{CTF_ID}-{A}")
    }
    assert board(db, B)["score"] == 300
    assert "hint_taken" not in flag_state(db, "web1", B)


def test_hint_keeps_other_flag_state(db):
    seed_event(db, solved=("web1",))
    CtfScoring(db=db).hint(A, "web2")

    assert flag_state(db, "web1")["solved"] is True
    assert flag_state(db, "web1")["hint_taken"] is False
    assert flag_state(db, "web2")["hint_taken"] is True


def test_zero_cost_hint_is_marked_taken_without_changing_score(db):
    response = CtfScoring(db=db).hint(A, "free")

    assert response.hint_cost == 0
    assert response.score == 300
    assert flag_state(db, "free")["hint_taken"] is True


def test_hint_may_take_score_below_zero(db):
    seed_event(db, score=10)

    assert CtfScoring(db=db).hint(A, "web1").score == -15


def test_hint_does_not_record_a_submission(db):
    CtfScoring(db=db).hint(A, "web1")

    assert db.inserted == []


@pytest.mark.parametrize("flag_id", ["missing", "nohint", "trap"])
def test_unknown_hintless_or_decoy_flag_is_not_found_without_a_write(db, flag_id):
    # Decoys answer exactly like an unknown id, so the route can't be used to discover them.
    with pytest.raises(NotFound, match="Hint not found"):
        CtfScoring(db=db).hint(A, flag_id)

    assert db.updates == []


def test_locked_flag_hint_is_not_found(db):
    with pytest.raises(NotFound, match="Hint not found"):
        CtfScoring(db=db).hint(A, "web2")

    assert db.updates == []


def test_unlocked_flag_hint_is_available(db):
    seed_event(db, solved=("web1",))

    assert CtfScoring(db=db).hint(A, "web2").score == 250


def test_flag_missing_from_board_is_not_found(db):
    board(db)["flags"] = [f for f in board(db)["flags"] if f["flag_id"] != "web1"]

    with pytest.raises(NotFound, match="Hint not found"):
        CtfScoring(db=db).hint(A, "web1")


@pytest.mark.parametrize("state", [s for s in CtfStates if s != CtfStates.RUNNING])
def test_new_hint_outside_running_is_conflict_without_a_write(db, state):
    seed_event(db, state=state)

    with pytest.raises(Conflict, match="only be taken while the event is running"):
        CtfScoring(db=db).hint(A, "web1")

    assert db.updates == []
    assert board(db)["score"] == 300


def test_taken_hint_is_still_returned_after_the_event_stops(db):
    scoring = CtfScoring(db=db)
    scoring.hint(A, "web1")
    db.col(DbCollections.CTF)[CTF_ID]["state"] = CtfStates.ENDED.value

    assert scoring.hint(A, "web1").score == 275
    assert len(db.updates) == 1


def test_no_active_board_is_not_found(db):
    for doc in db.col(DbCollections.CTF_BOARD).values():
        doc["active"] = False

    with pytest.raises(NotFound, match="CTF board not found"):
        CtfScoring(db=db).hint(A, "web1")


def test_missing_event_is_not_found(db):
    del db.col(DbCollections.CTF)[CTF_ID]

    with pytest.raises(NotFound, match="CTF event not found"):
        CtfScoring(db=db).hint(A, "web1")
