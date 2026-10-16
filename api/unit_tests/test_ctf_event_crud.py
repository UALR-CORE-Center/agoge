"""CtfEvent.get / list / update / delete (PRD F5 and the /ctf/{ctf_id}/ endpoint rows)."""
import copy

import pytest

from common.constants.database import DbCollections, DbOperationTypes, DbOperators
from common.constants.states import CtfStates
from common.exceptions.agoge import Conflict, NotFound, Unauthorized
from common.models.agoge import CtfEventModel, CtfUpdateRequest
from common.models.response import CtfEventSummary
from common.models.users import AgogeUser
from core.ctf.event import CtfEvent

GM = "gm@example.edu"
OTHER = "other@example.edu"
CTF_ID = "ctfaaaaaaa"


class FakeSnapshot:
    def __init__(self, doc_id, data):
        self.id = doc_id
        self._data = data
        self.exists = data is not None

    def to_dict(self):
        return copy.deepcopy(self._data)


class FakeDocRef:
    def __init__(self, store, collection, doc_id):
        self.store, self.collection, self.id = store, collection, doc_id

    def get(self, transaction=None):
        assert transaction is not None, "update must read inside its transaction"
        transaction.reads.append(self.id)
        return FakeSnapshot(self.id, self.store.setdefault(self.collection, {}).get(self.id))


class FakeRawQuery:
    """Evaluates the document-id range filters the way Firestore orders ids (lexicographically)."""
    def __init__(self, store, collection, filters=()):
        self.store, self.collection, self.filters = store, collection, list(filters)

    def where(self, filter):
        assert filter.field_path == "__name__", "rate-limit lookup must filter on the document id"
        assert isinstance(filter.value, FakeDocRef), "document-id filters take a DocumentReference"
        return FakeRawQuery(self.store, self.collection, [*self.filters, filter])

    def stream(self):
        ops = {">=": lambda a, b: a >= b, "<": lambda a, b: a < b}
        for doc_id, data in sorted(self.store.setdefault(self.collection, {}).items()):
            if all(ops[f.op_string](doc_id, f.value.id) for f in self.filters):
                yield FakeSnapshot(doc_id, data)


class FakeRawCollection(FakeRawQuery):
    def document(self, doc_id):
        return FakeDocRef(self.store, self.collection, doc_id)


class FakeClient:
    def __init__(self, store):
        self.store = store

    def collection(self, name):
        return FakeRawCollection(self.store, name)


class FakeTransaction:
    def __init__(self, store):
        self.store = store
        self.reads = []
        self.updates = []

    def update(self, doc_ref, data):
        self.updates.append((doc_ref.collection, doc_ref.id, dict(data)))
        self.store[doc_ref.collection][doc_ref.id].update(copy.deepcopy(data))


class FakeDb:
    """Wrapper API (get/query/operation/batch_write/transaction) plus `.db`, the raw client."""
    def __init__(self, fail_on_commit=None):
        self.store = {}
        self.db = FakeClient(self.store)
        self.commits = []
        self.queries = []
        self.transactions = []
        self.fail_on_commit = fail_on_commit

    def collection(self, name):
        return self.store.setdefault(getattr(name, "value", name), {})

    def get(self, collection_name, doc_id):
        doc = self.collection(collection_name).get(doc_id)
        return copy.deepcopy(doc) if doc is not None else None

    def query(self, collection_name, filters=None):
        self.queries.append((collection_name, filters))
        out = []
        for doc in self.collection(collection_name).values():
            ok = True
            for field, op, value in filters or []:
                if op == DbOperators.EQUAL:
                    ok &= doc.get(field) == value
                elif op == DbOperators.ARRAY_CONTAINS:
                    ok &= value in (doc.get(field) or [])
                else:
                    raise AssertionError(f"unexpected operator {op}")
            if ok:
                out.append(copy.deepcopy(doc))
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
        for collection, doc_id, op_type, _ in operations:
            assert op_type == DbOperationTypes.DELETE
            self.collection(collection).pop(doc_id, None)

    def transaction(self, operation_func, *args, **kwargs):
        transaction = FakeTransaction(self.store)
        self.transactions.append(transaction)
        return operation_func(transaction, *args, **kwargs)


def user(email=GM, admin=False):
    return AgogeUser(uid="uid", email=email, permissions={"instructor": True, "admin": admin})


ADMIN = user("admin@example.edu", admin=True)


def event_doc(ctf_id=CTF_ID, state=CtfStates.DRAFT, instructors=(GM,), board_ids=("wkaaaaaaaa", "wkbbbbbbbb"),
              created=1_700_000_000.0, **kw):
    return {
        "id": ctf_id, "unit_id": "unitabcdef", "instructor_id": list(instructors),
        "spec": {"name": f"CTF {ctf_id}", "flags": [{
            "id": "web1", "server": "web", "slot": 1, "points": 100,
            "location_type": "file", "path": "/root/flag.txt", "operating_system": "linux",
        }]},
        "creation_timestamp": created, "board_ids": list(board_ids),
        "state": state.value, "state_timestamp": "2026-10-16T00:00:00+00:00", **kw,
    }


def seed_event(db, ctf_id=CTF_ID, **kw):
    doc = event_doc(ctf_id, **kw)
    db.collection(DbCollections.CTF)[ctf_id] = doc
    for workout_id in doc["board_ids"]:
        db.collection(DbCollections.CTF_BOARD)[f"{ctf_id}-{workout_id}"] = {"ctf_id": ctf_id, "workout_id": workout_id}
        digest = f"{ctf_id}{workout_id}digest"
        db.collection(DbCollections.CTF_DIGEST)[digest] = {
            "digest": digest, "ctf_id": ctf_id, "workout_id": workout_id, "flag_id": "web1",
        }
        for bucket in ("web1", "unparsed", "made-up-id"):
            db.collection(DbCollections.CTF_RATE_LIMIT)[f"{ctf_id}-{workout_id}-{bucket}"] = {
                "id": f"{ctf_id}-{workout_id}-{bucket}", "window_start": 1.0, "count": 1,
            }
    return doc


@pytest.fixture
def db():
    return FakeDb()


def ctf(db):
    return CtfEvent(env_dict={}, db=db)


# --- get ----------------------------------------------------------------------------

def test_get_returns_event_model_for_an_instructor(db):
    seed_event(db)
    event = ctf(db).get(CTF_ID, user())
    assert isinstance(event, CtfEventModel)
    assert event.id == CTF_ID and event.spec.name == f"CTF {CTF_ID}"


def test_get_allows_an_admin_not_on_the_event(db):
    seed_event(db)
    assert ctf(db).get(CTF_ID, ADMIN).id == CTF_ID


def test_get_refuses_an_instructor_not_on_the_event(db):
    seed_event(db)
    with pytest.raises(Unauthorized):
        ctf(db).get(CTF_ID, user(OTHER))


def test_get_missing_event_is_not_found(db):
    with pytest.raises(NotFound):
        ctf(db).get(CTF_ID, ADMIN)


# --- list ---------------------------------------------------------------------------

def test_list_returns_only_the_callers_events_newest_first(db):
    seed_event(db, "ctfaaaaaaa", created=100.0)
    seed_event(db, "ctfbbbbbbb", created=300.0, instructors=(OTHER, GM))
    seed_event(db, "ctfccccccc", created=200.0, instructors=(OTHER,))
    items = ctf(db).list(user())
    assert [i.id for i in items] == ["ctfbbbbbbb", "ctfaaaaaaa"]
    # The instructor query is pushed to Firestore, not filtered in memory.
    assert db.queries[-1] == (DbCollections.CTF, [("instructor_id", DbOperators.ARRAY_CONTAINS, GM)])


def test_list_for_an_admin_returns_every_event(db):
    seed_event(db, "ctfaaaaaaa", created=100.0)
    seed_event(db, "ctfccccccc", created=200.0, instructors=(OTHER,))
    assert [i.id for i in ctf(db).list(ADMIN)] == ["ctfccccccc", "ctfaaaaaaa"]
    assert db.queries[-1] == (DbCollections.CTF, None)


def test_list_builds_summaries(db):
    seed_event(db, state=CtfStates.RUNNING, starts_at=500.0, ends_at=900.0)
    (summary,) = ctf(db).list(user())
    assert summary == CtfEventSummary(
        id=CTF_ID, name=f"CTF {CTF_ID}", unit_id="unitabcdef", state=CtfStates.RUNNING.value,
        state_name="RUNNING", board_count=2, creation_timestamp=1_700_000_000.0, starts_at=500.0, ends_at=900.0,
    )


def test_list_skips_an_invalid_document(db):
    seed_event(db, "ctfaaaaaaa")
    db.collection(DbCollections.CTF)["ctfbroken1"] = {"id": "ctfbroken1", "instructor_id": [GM]}
    assert [i.id for i in ctf(db).list(user())] == ["ctfaaaaaaa"]


def test_list_with_no_events_is_empty(db):
    assert ctf(db).list(user()) == []


# --- update -------------------------------------------------------------------------

def test_update_applies_only_fields_in_the_body(db):
    seed_event(db, scoreboard_frozen_at=400.0, ends_at=900.0)
    updated = ctf(db).update(CTF_ID, CtfUpdateRequest(public_scoreboard_enabled=True), user())
    (transaction,) = db.transactions
    # Field mask: only the sent field is written; the freeze and ends_at stay as they were.
    assert transaction.updates == [(DbCollections.CTF.value, CTF_ID, {"public_scoreboard_enabled": True})]
    assert transaction.reads == [CTF_ID]
    stored = db.collection(DbCollections.CTF)[CTF_ID]
    assert stored["scoreboard_frozen_at"] == 400.0 and stored["ends_at"] == 900.0
    assert updated.public_scoreboard_enabled is True and updated.scoreboard_frozen_at == 400.0


def test_update_explicit_null_unfreezes(db):
    seed_event(db, state=CtfStates.RUNNING, scoreboard_frozen_at=400.0)
    request = CtfUpdateRequest.model_validate({"scoreboard_frozen_at": None})
    updated = ctf(db).update(CTF_ID, request, user())
    assert db.transactions[0].updates == [(DbCollections.CTF.value, CTF_ID, {"scoreboard_frozen_at": None})]
    assert updated.scoreboard_frozen_at is None
    assert db.collection(DbCollections.CTF)[CTF_ID]["scoreboard_frozen_at"] is None


def test_update_several_fields(db):
    seed_event(db, state=CtfStates.PAUSED)
    request = CtfUpdateRequest(ends_at=1234.5, scoreboard_frozen_at=1000.0)
    ctf(db).update(CTF_ID, request, ADMIN)
    assert db.transactions[0].updates[0][2] == {"ends_at": 1234.5, "scoreboard_frozen_at": 1000.0}


def test_update_with_an_empty_body_writes_nothing(db):
    seed_event(db)
    event = ctf(db).update(CTF_ID, CtfUpdateRequest(), user())
    assert db.transactions[0].updates == []
    assert event.id == CTF_ID


def test_update_refuses_an_archived_event(db):
    seed_event(db, state=CtfStates.ARCHIVED)
    with pytest.raises(Conflict, match="ARCHIVED"):
        ctf(db).update(CTF_ID, CtfUpdateRequest(public_scoreboard_enabled=True), ADMIN)
    assert db.transactions[0].updates == []


def test_update_refuses_an_instructor_not_on_the_event(db):
    seed_event(db)
    with pytest.raises(Unauthorized):
        ctf(db).update(CTF_ID, CtfUpdateRequest(ends_at=5.0), user(OTHER))
    assert db.transactions[0].updates == []


def test_update_missing_event_is_not_found(db):
    with pytest.raises(NotFound):
        ctf(db).update(CTF_ID, CtfUpdateRequest(ends_at=5.0), ADMIN)


# --- delete -------------------------------------------------------------------------

@pytest.mark.parametrize("state", [CtfStates.DRAFT, CtfStates.ARCHIVED])
def test_delete_removes_event_boards_digests_and_rate_limits(db, state):
    seed_event(db, state=state)
    seed_event(db, "ctfzzzzzzz")  # an unrelated event must survive untouched
    submissions = {"sub1": {"ctf_id": CTF_ID}}
    log = {"log1": {"ctf_id": CTF_ID}}
    db.store[DbCollections.CTF_SUBMISSION.value] = copy.deepcopy(submissions)
    db.store[DbCollections.CTF_LOG.value] = copy.deepcopy(log)

    ctf(db).delete(CTF_ID, ADMIN)

    for collection in (DbCollections.CTF, DbCollections.CTF_BOARD, DbCollections.CTF_DIGEST,
                       DbCollections.CTF_RATE_LIMIT):
        remaining = db.collection(collection)
        assert all(not doc_id.startswith(CTF_ID) for doc_id in remaining), collection
        assert any(doc_id.startswith("ctfzzzzzzz") for doc_id in remaining), collection
    # Submissions and the event log are kept.
    assert db.store[DbCollections.CTF_SUBMISSION.value] == submissions
    assert db.store[DbCollections.CTF_LOG.value] == log


def test_delete_removes_the_event_last(db):
    seed_event(db)
    ctf(db).delete(CTF_ID, ADMIN)
    ops = [op for commit in db.commits for op in commit]
    assert ops[-1][:2] == (DbCollections.CTF.value, CTF_ID)
    assert sum(1 for op in ops if op[0] == DbCollections.CTF.value) == 1


def test_delete_keeps_digests_now_owned_by_a_later_event(db):
    # Digest ids don't depend on the event, so a later event on the same workout overwrites them.
    seed_event(db, state=CtfStates.ARCHIVED)
    digest = f"{CTF_ID}wkaaaaaaaadigest"
    db.collection(DbCollections.CTF_DIGEST)[digest]["ctf_id"] = "ctfnewernnn"
    ctf(db).delete(CTF_ID, ADMIN)
    assert db.collection(DbCollections.CTF_DIGEST)[digest]["ctf_id"] == "ctfnewernnn"


def test_delete_rate_limit_range_does_not_reach_a_neighbouring_id(db):
    seed_event(db)
    # Ids that sort right next to this event's range but belong to other events.
    neighbours = [f"{CTF_ID}.x", "ctfaaaaaab-wkaaaaaaaa-web1", "ctfaaaaaa-wk"]
    for doc_id in neighbours:
        db.collection(DbCollections.CTF_RATE_LIMIT)[doc_id] = {"id": doc_id, "window_start": 1.0, "count": 1}
    ctf(db).delete(CTF_ID, ADMIN)
    assert sorted(db.collection(DbCollections.CTF_RATE_LIMIT)) == sorted(neighbours)


def test_delete_splits_commits_at_500(db):
    workout_ids = [f"wk{i:08d}" for i in range(120)]
    seed_event(db, board_ids=workout_ids)  # 120 boards + 120 digests + 360 rate limits + 1 event
    ctf(db).delete(CTF_ID, ADMIN)
    assert [len(c) for c in db.commits] == [500, 101]
    assert db.collection(DbCollections.CTF) == {}


def test_delete_failed_commit_leaves_event_and_retry_finishes(db):
    seed_event(db, board_ids=[f"wk{i:08d}" for i in range(120)])
    db.fail_on_commit = 1
    with pytest.raises(RuntimeError):
        ctf(db).delete(CTF_ID, ADMIN)
    assert CTF_ID in db.collection(DbCollections.CTF)
    ctf(db).delete(CTF_ID, ADMIN)
    for collection in (DbCollections.CTF, DbCollections.CTF_BOARD, DbCollections.CTF_DIGEST,
                       DbCollections.CTF_RATE_LIMIT):
        assert db.collection(collection) == {}, collection


@pytest.mark.parametrize("state", [CtfStates.ARMING, CtfStates.ARMED, CtfStates.RUNNING, CtfStates.PAUSED,
                                   CtfStates.ENDED, CtfStates.BROKEN])
def test_delete_refuses_live_states_naming_the_state(db, state):
    seed_event(db, state=state)
    with pytest.raises(Conflict, match=state.name):
        ctf(db).delete(CTF_ID, ADMIN)
    assert db.commits == []


def test_delete_requires_an_admin_even_on_the_event(db):
    seed_event(db)
    with pytest.raises(Unauthorized):
        ctf(db).delete(CTF_ID, user())
    assert db.commits == []
    assert CTF_ID in db.collection(DbCollections.CTF)


def test_delete_missing_event_is_not_found(db):
    with pytest.raises(NotFound):
        ctf(db).delete(CTF_ID, ADMIN)
    assert db.commits == []
