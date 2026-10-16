"""CtfEvent.process_action (PRD F6, the action map at PRD.md:709-720, SC-13 and SC-14)."""
import copy
from concurrent.futures import Future
from unittest.mock import patch

import pytest

from common.constants.database import DbCollections
from common.constants.pub_sub import PubSub
from common.constants.states import CtfStates
from common.exceptions.agoge import BadRequest, Conflict, NotFound, Unauthorized
from common.models.agoge import CtfActionRequest, CtfEventModel
from common.models.users import AgogeUser
from core.ctf.event import CtfEvent

GM = "gm@example.edu"
CTF_ID = "ctfaaaaaaa"
BOARDS = ("wkaaaaaaaa", "wkbbbbbbbb", "wkcccccccc")
NOW = 1_800_000_000.0


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
        assert transaction is not None, "actions must read inside their transaction"
        assert not transaction.writes, "Firestore needs every read before the first write"
        return FakeSnapshot(self.store.setdefault(self.collection, {}).get(self.id))


class FakeCollection:
    def __init__(self, store, name):
        self.store, self.name = store, name

    def document(self, doc_id):
        return FakeDocRef(self.store, self.name, doc_id)


class FakeClient:
    def __init__(self, store):
        self.store = store

    def collection(self, name):
        return FakeCollection(self.store, name)


class FakeTransaction:
    """Buffers writes and applies them only when the operation returns, like a Firestore commit."""
    def __init__(self):
        self.writes = []

    def update(self, doc_ref, data):
        assert doc_ref.id in doc_ref.store.get(doc_ref.collection, {}), "update of a missing document fails"
        self.writes.append((doc_ref, copy.deepcopy(dict(data))))


class FakeDb:
    def __init__(self):
        self.store = {}
        self.db = FakeClient(self.store)

    def collection(self, name):
        return self.store.setdefault(name.value, {})

    def transaction(self, operation_func):
        transaction = FakeTransaction()
        result = operation_func(transaction)
        for doc_ref, data in transaction.writes:
            self.store[doc_ref.collection][doc_ref.id].update(data)
        return result


class FakePubSub:
    """`fail_after` raises in-line; `future_errors` maps a workout to the error its publish future
    resolves with, which is how the real client reports network, permission and timeout failures."""

    def __init__(self, fail_after=None, future_errors=None):
        self.messages = []
        self.fail_after = fail_after
        self.future_errors = future_errors or {}

    def msg(self, **attrs):
        if self.fail_after is not None and len(self.messages) == self.fail_after:
            raise RuntimeError("publish failed")
        self.messages.append(attrs)
        future = Future()
        error = self.future_errors.get(attrs[PubSub.EventAttributes.WORKOUT_ID])
        if error is None:
            future.set_result("message-id")
        else:
            future.set_exception(error)
        return future


def user(email=GM, admin=False):
    return AgogeUser(uid="uid", email=email, permissions={"instructor": True, "admin": admin})


def seed(db, state, board_ids=BOARDS, **kw):
    db.collection(DbCollections.CTF)[CTF_ID] = {
        "id": CTF_ID, "unit_id": "unitabcdef", "instructor_id": [GM],
        "spec": {"name": "Spring CTF", "flags": [{
            "id": "web1", "server": "web", "slot": 1, "points": 100,
            "location_type": "file", "path": "/root/flag.txt", "operating_system": "linux",
        }]},
        "creation_timestamp": 1_700_000_000.0, "board_ids": list(board_ids),
        "state": state.value, "state_timestamp": "2026-10-16T00:00:00+00:00", **kw,
    }
    for workout_id in board_ids:
        db.collection(DbCollections.CTF_BOARD)[f"{CTF_ID}-{workout_id}"] = {
            "id": f"{CTF_ID}-{workout_id}", "workout_id": workout_id, "ctf_id": CTF_ID, "team_name": workout_id,
            "active": True, "arm_status": "armed", "arm_error": "old error",
        }


def event(db):
    return db.collection(DbCollections.CTF)[CTF_ID]


def boards(db):
    return [db.collection(DbCollections.CTF_BOARD)[f"{CTF_ID}-{w}"] for w in BOARDS]


@pytest.fixture
def db():
    return FakeDb()


@pytest.fixture
def pubsub():
    return FakePubSub()


def act(db, pubsub, action, who=None):
    with patch("core.ctf.event.time.time", return_value=NOW):
        return CtfEvent(env_dict={}, db=db, pubsub=pubsub).process_action(
            CTF_ID, CtfActionRequest(action=action), who or user()
        )


# --- SC-13: arm fans out one message per board --------------------------------------

@pytest.mark.parametrize("start", [CtfStates.DRAFT, CtfStates.ARMED, CtfStates.BROKEN])
def test_arm_publishes_exactly_one_arm_board_message_per_board(db, pubsub, start):
    seed(db, start)
    result = act(db, pubsub, "arm")

    assert len(pubsub.messages) == len(BOARDS)
    assert pubsub.messages == [{
        "handler": PubSub.Handlers.CTF.value,
        "action": str(PubSub.Actions.CTF_ARM_BOARD.value),
        "ctf_id": CTF_ID,
        "workout_id": workout_id,
    } for workout_id in BOARDS]
    assert result.state == CtfStates.ARMING.value
    assert event(db)["state"] == CtfStates.ARMING.value
    assert event(db)["boards_pending"] == len(BOARDS)


def test_arm_resets_every_board_to_pending(db, pubsub):
    seed(db, CtfStates.ARMED)
    act(db, pubsub, "arm")
    assert all(b["arm_status"] == "pending" and b["arm_error"] is None for b in boards(db))
    assert all(b["active"] for b in boards(db))


def test_arm_publishes_only_after_the_event_is_arming(db):
    seed(db, CtfStates.DRAFT)
    seen = []

    class Recording(FakePubSub):
        def msg(self, **attrs):
            # An arm worker started by this message must find the event ARMING (it skips anything else).
            seen.append((event(db)["state"], event(db)["boards_pending"]))
            return super().msg(**attrs)

    act(db, Recording(), "arm")
    assert seen == [(CtfStates.ARMING.value, len(BOARDS))] * len(BOARDS)


def test_arm_publish_failure_is_raised_after_the_transition(db):
    seed(db, CtfStates.DRAFT)
    with pytest.raises(RuntimeError):
        act(db, FakePubSub(fail_after=1), "arm")
    assert event(db)["state"] == CtfStates.ARMING.value


# --- BUG3: a partial arm publish must not leave the event in ARMING for good ------------

def board(db, workout_id):
    return db.collection(DbCollections.CTF_BOARD)[f"{CTF_ID}-{workout_id}"]


def finish_board(db, workout_id, status):
    """What an arm worker's aggregation does for one board (ArmWorker._aggregate)."""
    board(db, workout_id)["arm_status"] = status
    event(db)["boards_pending"] -= 1


def test_arm_publish_failure_fails_the_unpublished_boards_and_counts_them_down(db):
    seed(db, CtfStates.DRAFT)
    with pytest.raises(RuntimeError, match="publish failed"):
        act(db, FakePubSub(fail_after=1), "arm")
    assert board(db, BOARDS[0])["arm_status"] == "pending"  # its worker will still count it down
    for workout_id in BOARDS[1:]:
        assert board(db, workout_id)["arm_status"] == "failed"
        assert board(db, workout_id)["arm_error"] == CtfEvent.ARM_PUBLISH_FAILED
    assert event(db)["state"] == CtfStates.ARMING.value
    assert event(db)["boards_pending"] == 1


def test_arm_publish_failing_on_the_first_board_moves_the_event_to_broken(db):
    seed(db, CtfStates.DRAFT)
    with pytest.raises(RuntimeError):
        act(db, FakePubSub(fail_after=0), "arm")
    assert all(b["arm_status"] == "failed" for b in boards(db))
    assert event(db)["state"] == CtfStates.BROKEN.value
    assert event(db)["boards_pending"] == 0


def test_arm_publish_failure_after_an_armed_board_moves_the_event_to_armed(db):
    seed(db, CtfStates.DRAFT)

    class FastWorker(FakePubSub):
        def msg(self, **attrs):
            future = super().msg(**attrs)
            finish_board(db, attrs[PubSub.EventAttributes.WORKOUT_ID], "armed")
            return future

    with pytest.raises(RuntimeError):
        act(db, FastWorker(fail_after=1), "arm")
    assert [b["arm_status"] for b in boards(db)] == ["armed", "failed", "failed"]
    assert event(db)["state"] == CtfStates.ARMED.value
    assert event(db)["boards_pending"] == 0


def test_arm_publish_failure_leaves_a_board_its_worker_already_finished(db):
    # The publish that raised may still have been delivered; that board must not be counted twice.
    seed(db, CtfStates.DRAFT)

    class DeliveredThenRaised(FakePubSub):
        def msg(self, **attrs):
            if len(self.messages) == 1:
                finish_board(db, attrs[PubSub.EventAttributes.WORKOUT_ID], "armed")
            return super().msg(**attrs)

    with pytest.raises(RuntimeError):
        act(db, DeliveredThenRaised(fail_after=1), "arm")
    assert [b["arm_status"] for b in boards(db)] == ["pending", "armed", "failed"]
    assert board(db, BOARDS[1])["arm_error"] is None  # arm reset it; recovery never wrote this board
    assert event(db)["state"] == CtfStates.ARMING.value
    assert event(db)["boards_pending"] == 1


def test_arm_publish_failure_after_the_event_left_arming_only_marks_boards(db):
    seed(db, CtfStates.DRAFT)

    class ArchivedMeanwhile(FakePubSub):
        def msg(self, **attrs):
            event(db)["state"] = CtfStates.BROKEN.value
            return super().msg(**attrs)

    with pytest.raises(RuntimeError):
        act(db, ArchivedMeanwhile(fail_after=0), "arm")
    assert all(b["arm_status"] == "failed" for b in boards(db))
    assert event(db)["state"] == CtfStates.BROKEN.value
    assert event(db)["boards_pending"] == len(BOARDS)


def test_arm_publish_failure_still_raises_the_publish_error_when_recovery_fails(db):
    seed(db, CtfStates.DRAFT)
    transaction = db.transaction
    calls = []

    def failing_recovery(operation_func):
        calls.append(operation_func)
        if len(calls) > 1:
            raise OSError("firestore unavailable")
        return transaction(operation_func)

    db.transaction = failing_recovery
    with pytest.raises(RuntimeError, match="publish failed"):
        act(db, FakePubSub(fail_after=1), "arm")
    assert len(calls) == 2
    assert event(db)["state"] == CtfStates.ARMING.value


def test_arm_publish_future_failure_fails_only_that_board(db):
    # The real client never raises from publish(); a failed publish surfaces through its future.
    seed(db, CtfStates.DRAFT)
    pubsub = FakePubSub(future_errors={BOARDS[1]: PermissionError("pubsub denied")})
    with pytest.raises(PermissionError, match="pubsub denied"):
        act(db, pubsub, "arm")
    assert len(pubsub.messages) == len(BOARDS)
    assert [b["arm_status"] for b in boards(db)] == ["pending", "failed", "pending"]
    assert board(db, BOARDS[1])["arm_error"] == CtfEvent.ARM_PUBLISH_FAILED
    assert event(db)["state"] == CtfStates.ARMING.value
    assert event(db)["boards_pending"] == len(BOARDS) - 1


def test_arm_publish_futures_all_failing_move_the_event_to_broken(db):
    seed(db, CtfStates.DRAFT)
    errors = {workout_id: OSError("network down") for workout_id in BOARDS}
    with pytest.raises(OSError, match="network down"):
        act(db, FakePubSub(future_errors=errors), "arm")
    assert all(b["arm_status"] == "failed" for b in boards(db))
    assert event(db)["state"] == CtfStates.BROKEN.value
    assert event(db)["boards_pending"] == 0


def test_arm_publish_future_that_never_resolves_counts_as_unpublished(db):
    seed(db, CtfStates.DRAFT)

    class Hanging(FakePubSub):
        def msg(self, **attrs):
            super().msg(**attrs)
            return Future()  # never resolves

    with patch.object(CtfEvent, "ARM_PUBLISH_TIMEOUT_SECONDS", 0), pytest.raises(TimeoutError):
        act(db, Hanging(), "arm")
    assert all(b["arm_status"] == "failed" for b in boards(db))
    assert event(db)["state"] == CtfStates.BROKEN.value


def test_arm_in_line_failure_still_checks_the_futures_already_returned(db):
    seed(db, CtfStates.DRAFT)
    pubsub = FakePubSub(fail_after=2, future_errors={BOARDS[0]: OSError("network down")})
    with pytest.raises(RuntimeError, match="publish failed"):  # the in-line error is the one raised
        act(db, pubsub, "arm")
    assert [b["arm_status"] for b in boards(db)] == ["failed", "pending", "failed"]
    assert event(db)["state"] == CtfStates.ARMING.value
    assert event(db)["boards_pending"] == 1


def test_arm_with_no_boards_is_refused_without_a_write(db, pubsub):
    seed(db, CtfStates.DRAFT, board_ids=())
    with pytest.raises(BadRequest):
        act(db, pubsub, "arm")
    assert event(db)["state"] == CtfStates.DRAFT.value
    assert pubsub.messages == []


# --- SC-14: the other five actions publish nothing ----------------------------------

@pytest.mark.parametrize("action, start, end", [
    ("start", CtfStates.ARMED, CtfStates.RUNNING),
    ("pause", CtfStates.RUNNING, CtfStates.PAUSED),
    ("resume", CtfStates.PAUSED, CtfStates.RUNNING),
    ("end", CtfStates.RUNNING, CtfStates.ENDED),
    ("end", CtfStates.PAUSED, CtfStates.ENDED),
    ("archive", CtfStates.DRAFT, CtfStates.ARCHIVED),
    ("archive", CtfStates.ARMED, CtfStates.ARCHIVED),
    ("archive", CtfStates.ENDED, CtfStates.ARCHIVED),
    ("archive", CtfStates.BROKEN, CtfStates.ARCHIVED),
])
def test_non_arm_actions_change_state_in_the_request_and_publish_nothing(db, pubsub, action, start, end):
    seed(db, start, paused_at=NOW - 10 if start == CtfStates.PAUSED else None)
    result = act(db, pubsub, action)

    assert pubsub.messages == []
    assert isinstance(result, CtfEventModel) and result.state == end.value
    assert event(db)["state"] == end.value
    assert event(db)["state_timestamp"] != "2026-10-16T00:00:00+00:00"


def test_start_stamps_starts_at(db, pubsub):
    seed(db, CtfStates.ARMED)
    act(db, pubsub, "start")
    assert event(db)["starts_at"] == NOW


def test_pause_stamps_paused_at(db, pubsub):
    seed(db, CtfStates.RUNNING, starts_at=NOW - 100)
    act(db, pubsub, "pause")
    assert event(db)["paused_at"] == NOW


def test_resume_accumulates_the_pause_and_extends_ends_at(db, pubsub):
    seed(db, CtfStates.PAUSED, paused_at=NOW - 30, accumulated_pause_seconds=5.0, ends_at=NOW + 600)
    act(db, pubsub, "resume")
    assert event(db)["accumulated_pause_seconds"] == 35.0
    assert event(db)["ends_at"] == NOW + 630
    assert event(db)["paused_at"] is None


def test_resume_leaves_an_open_ended_event_open_ended(db, pubsub):
    seed(db, CtfStates.PAUSED, paused_at=NOW - 30)
    act(db, pubsub, "resume")
    assert "ends_at" not in event(db)  # not written: the stored event stays open-ended
    assert event(db)["accumulated_pause_seconds"] == 30.0


def test_end_stamps_ends_at(db, pubsub):
    seed(db, CtfStates.RUNNING, ends_at=NOW + 600)
    act(db, pubsub, "end")
    assert event(db)["ends_at"] == NOW


def test_archive_deactivates_every_board(db, pubsub):
    seed(db, CtfStates.ENDED)
    act(db, pubsub, "archive")
    assert all(b["active"] is False for b in boards(db))
    # Arm results stay for the record.
    assert all(b["arm_status"] == "armed" for b in boards(db))


def test_non_arm_actions_leave_boards_alone(db, pubsub):
    seed(db, CtfStates.ARMED)
    before = copy.deepcopy(boards(db))
    act(db, pubsub, "start")
    assert boards(db) == before


# --- illegal actions ----------------------------------------------------------------

ILLEGAL = [
    ("arm", CtfStates.RUNNING), ("arm", CtfStates.ARMING), ("arm", CtfStates.ARCHIVED),
    ("start", CtfStates.DRAFT), ("start", CtfStates.PAUSED), ("start", CtfStates.RUNNING),
    ("pause", CtfStates.ARMED), ("pause", CtfStates.PAUSED),
    ("resume", CtfStates.ARMED), ("resume", CtfStates.RUNNING),
    ("end", CtfStates.ARMED), ("end", CtfStates.ENDED),
    ("archive", CtfStates.RUNNING), ("archive", CtfStates.PAUSED), ("archive", CtfStates.ARMING),
    ("archive", CtfStates.ARCHIVED),
]


@pytest.mark.parametrize("action, start", ILLEGAL)
def test_illegal_action_raises_conflict_naming_the_state_and_writes_nothing(db, pubsub, action, start):
    seed(db, start)
    before = copy.deepcopy(db.store)
    with pytest.raises(Conflict) as excinfo:
        act(db, pubsub, action)
    assert start.name in str(excinfo.value)
    assert db.store == before
    assert pubsub.messages == []


def test_start_from_paused_is_refused_although_the_state_manager_allows_paused_to_running(db, pubsub):
    seed(db, CtfStates.PAUSED, paused_at=NOW - 30)
    with pytest.raises(Conflict, match="PAUSED"):
        act(db, pubsub, "start")
    assert event(db)["paused_at"] == NOW - 30


# --- lookup and authorization ---------------------------------------------------------

def test_missing_event_is_not_found(db, pubsub):
    with pytest.raises(NotFound):
        act(db, pubsub, "start")


def test_instructor_not_on_the_event_is_refused(db, pubsub):
    seed(db, CtfStates.DRAFT)
    with pytest.raises(Unauthorized):
        act(db, pubsub, "arm", who=user("other@example.edu"))
    assert event(db)["state"] == CtfStates.DRAFT.value
    assert pubsub.messages == []


def test_admin_not_on_the_event_may_act(db, pubsub):
    seed(db, CtfStates.ARMED)
    assert act(db, pubsub, "start", who=user("admin@example.edu", admin=True)).state == CtfStates.RUNNING.value
