"""ArmWorker.run: workout check, planting, and the arm aggregation transaction (E4, SC-15). FlagPlanter is faked."""
import copy
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from cloud_fn_utilities.course_objects.ctf import arm_worker as arm_worker_module
from cloud_fn_utilities.course_objects.ctf.arm_worker import ArmWorker
from common.constants.database import DbCollections
from common.constants.states import CtfStates, WorkoutStates
from common.exceptions import NotFound
from common.models.agoge import CtfBoardModel

CTF_ID = "ctfeventaa"
WORKOUTS = ["workoutaaa", "workoutbbb", "workoutccc"]

FLAGS = [
    {'id': 'web-user', 'server': 'web', 'slot': 1, 'location_type': 'file', 'path': '/home/student/user.txt',
     'operating_system': 'linux', 'points': 100},
    {'id': 'db-root', 'server': 'db', 'slot': 1, 'location_type': 'file', 'path': '/root/db.txt',
     'operating_system': 'linux', 'points': 300},
    {'id': 'web-root', 'server': 'web', 'slot': 2, 'location_type': 'env', 'path': 'AGOGE_ROOT_FLAG',
     'operating_system': 'linux', 'points': 200},
]


def _event(state=CtfStates.ARMING, board_ids=WORKOUTS, boards_pending=None):
    return {
        'id': CTF_ID, 'unit_id': 'unitaaaaaa', 'instructor_id': ['gm@example.edu'],
        'spec': {'name': 'Spring CTF', 'flags': FLAGS, 'scoring': {'flag_prefix': 'agoge'}},
        'creation_timestamp': 1.0, 'state': state.value, 'state_timestamp': '2026-10-16T00:00:00+00:00',
        'board_ids': list(board_ids),
        'boards_pending': len(board_ids) if boards_pending is None else boards_pending,
    }


def _board(workout_id, **extra):
    return CtfBoardModel(id=f"{CTF_ID}-{workout_id}", workout_id=workout_id, ctf_id=CTF_ID, team_name=workout_id,
                         flags=[{'flag_id': f['id'], 'digest': '0' * 64} for f in FLAGS], **extra).model_dump()


class FakeTransaction:
    """Enforces Firestore's rule that every read in a transaction happens before the first write."""
    def __init__(self, store):
        self.store = store
        self.wrote = False

    def update(self, ref, data):
        self.wrote = True
        self.store.docs[ref.key].update(copy.deepcopy(data))
        self.store.writes.append((ref.key, copy.deepcopy(data)))


class FakeRef:
    def __init__(self, store, key):
        self.store = store
        self.key = key

    def get(self, transaction=None):
        assert transaction is not None, "reads in the aggregation must go through the transaction"
        assert not transaction.wrote, "read after write inside a Firestore transaction"
        doc = self.store.docs.get(self.key)
        return SimpleNamespace(exists=doc is not None, to_dict=lambda: copy.deepcopy(doc))


class FakeDb:
    """FirestoreDatabase.get / .transaction plus the raw `db.collection(...).document(...)` client."""
    def __init__(self, docs):
        self.docs = docs
        self.writes = []
        self.db = SimpleNamespace(
            collection=lambda name: SimpleNamespace(document=lambda doc_id: FakeRef(self, (name, doc_id)))
        )

    def get(self, collection, doc_id):
        # FirestoreDatabase.get returns {} for a missing document
        return copy.deepcopy(self.docs.get((collection.value, doc_id))) or {}

    def transaction(self, operation):
        return operation(FakeTransaction(self))


def _store(event=None, boards=None, workouts=None):
    docs = {(DbCollections.CTF.value, CTF_ID): event or _event()}
    for workout_id in WORKOUTS:
        board = (boards or {}).get(workout_id, _board(workout_id))
        if board is not None:
            docs[(DbCollections.CTF_BOARD.value, f"{CTF_ID}-{workout_id}")] = board
        state = (workouts or {}).get(workout_id, WorkoutStates.RUNNING.value)
        if state is not None:
            docs[(DbCollections.WORKOUT.value, workout_id)] = {'id': workout_id, 'state': state}
    return FakeDb(docs)


class FakePlanter:
    """Marks flags planted or failed per workout; `outcomes[workout_id]` is a list of planted flag ids or an exception."""
    outcomes = {}
    calls = []

    def __init__(self, event, env_dict=None, compute_api=None, db=None):
        self.db = db

    def plant(self, board, servers):
        FakePlanter.calls.append((board.workout_id, list(servers)))
        outcome = FakePlanter.outcomes.get(board.workout_id, [f['id'] for f in FLAGS])
        if isinstance(outcome, Exception):
            raise outcome
        for flag in board.flags:
            if flag.flag_id in outcome:
                flag.plant_status, flag.planted_at = 'planted', 1.0
            else:
                flag.plant_status, flag.plant_error = 'failed', 'Server is not running'
        return board


@pytest.fixture(autouse=True)
def planter():
    FakePlanter.outcomes = {}
    FakePlanter.calls = []
    with patch.object(arm_worker_module, 'FlagPlanter', FakePlanter), patch.object(arm_worker_module, 'Logger'):
        yield FakePlanter


def _run_all(db):
    return [ArmWorker(env_dict={'project': 'p'}, db=db).run(CTF_ID, workout_id) for workout_id in WORKOUTS]


def _event_doc(db):
    return db.docs[(DbCollections.CTF.value, CTF_ID)]


def _board_doc(db, workout_id):
    return db.docs[(DbCollections.CTF_BOARD.value, f"{CTF_ID}-{workout_id}")]


# --- SC-15 -------------------------------------------------------------------------------------------------------

def test_all_boards_armed_moves_event_to_armed():
    db = _store()
    assert _run_all(db) == ['armed', 'armed', 'armed']
    event = _event_doc(db)
    assert event['state'] == CtfStates.ARMED.value
    assert event['boards_pending'] == 0
    for workout_id in WORKOUTS:
        assert _board_doc(db, workout_id)['arm_status'] == 'armed'
        assert _board_doc(db, workout_id)['arm_error'] is None


def test_mixed_outcome_moves_event_to_armed_with_each_board_visible(planter):
    planter.outcomes = {WORKOUTS[1]: []}
    db = _store(workouts={WORKOUTS[2]: WorkoutStates.STOPPING.value})
    assert _run_all(db) == ['armed', 'failed', 'failed']
    assert _event_doc(db)['state'] == CtfStates.ARMED.value
    assert _board_doc(db, WORKOUTS[1])['arm_error'] == "No flags planted: Server is not running"
    assert _board_doc(db, WORKOUTS[2])['arm_error'] == "Workout is not running"
    # The stopped workout is never planted
    assert [call[0] for call in planter.calls] == WORKOUTS[:2]


def test_armed_board_finishing_first_still_counts_when_last_board_fails(planter):
    # The last worker's own result is failed, so ARMED must come from reading the other boards in the transaction
    planter.outcomes = {WORKOUTS[1]: [], WORKOUTS[2]: []}
    db = _store()
    assert _run_all(db) == ['armed', 'failed', 'failed']
    assert _event_doc(db)['state'] == CtfStates.ARMED.value


def test_zero_boards_armed_moves_event_to_broken(planter):
    planter.outcomes = {WORKOUTS[0]: [], WORKOUTS[1]: RuntimeError("compute exploded")}
    db = _store(workouts={WORKOUTS[2]: WorkoutStates.READY.value})
    worker = ArmWorker(db=db)
    assert worker.run(CTF_ID, WORKOUTS[0]) == 'failed'
    with pytest.raises(RuntimeError):
        worker.run(CTF_ID, WORKOUTS[1])
    assert worker.run(CTF_ID, WORKOUTS[2]) == 'failed'
    event = _event_doc(db)
    assert event['state'] == CtfStates.BROKEN.value
    assert event['boards_pending'] == 0
    assert _board_doc(db, WORKOUTS[1])['arm_error'] == ArmWorker.MSG_ABORTED


# --- one worker --------------------------------------------------------------------------------------------------

def test_non_last_board_only_decrements_pending():
    db = _store()
    ArmWorker(db=db).run(CTF_ID, WORKOUTS[0])
    event = _event_doc(db)
    assert event['state'] == CtfStates.ARMING.value
    assert event['boards_pending'] == 2
    # Field-masked writes: the event write touches only boards_pending
    event_writes = [data for key, data in db.writes if key[0] == DbCollections.CTF.value]
    assert event_writes == [{'boards_pending': 2}]


def test_board_marked_arming_before_planting(planter):
    db = _store()
    seen = []
    original = FakePlanter.plant

    def spy(self, board, servers):
        seen.append(_board_doc(db, board.workout_id)['arm_status'])
        return original(self, board, servers)

    with patch.object(FakePlanter, 'plant', spy):
        ArmWorker(db=db).run(CTF_ID, WORKOUTS[0])
    assert seen == ['arming']


def test_plants_every_flag_bearing_server_in_spec_order(planter):
    db = _store()
    ArmWorker(db=db).run(CTF_ID, WORKOUTS[0])
    assert planter.calls == [(WORKOUTS[0], ['web', 'db'])]


def test_partial_plant_arms_board_and_reports_failures(planter):
    planter.outcomes = {WORKOUTS[0]: ['web-user', 'web-root']}
    db = _store()
    assert ArmWorker(db=db).run(CTF_ID, WORKOUTS[0]) == 'armed'
    assert _board_doc(db, WORKOUTS[0])['arm_error'] == "1 of 3 flags failed to plant"


def test_workout_not_running_fails_board_without_planting(planter):
    db = _store(workouts={WORKOUTS[0]: WorkoutStates.EXPIRED.value})
    assert ArmWorker(db=db).run(CTF_ID, WORKOUTS[0]) == 'failed'
    assert _board_doc(db, WORKOUTS[0])['arm_error'] == "Workout is not running"
    assert planter.calls == []
    assert _event_doc(db)['boards_pending'] == 2


def test_missing_workout_fails_board(planter):
    db = _store(workouts={WORKOUTS[0]: None})
    assert ArmWorker(db=db).run(CTF_ID, WORKOUTS[0]) == 'failed'
    assert _board_doc(db, WORKOUTS[0])['arm_error'] == ArmWorker.MSG_WORKOUT_NOT_FOUND
    assert planter.calls == []


def test_inactive_board_fails_without_planting(planter):
    db = _store(boards={WORKOUTS[0]: _board(WORKOUTS[0], active=False)})
    assert ArmWorker(db=db).run(CTF_ID, WORKOUTS[0]) == 'failed'
    assert _board_doc(db, WORKOUTS[0])['arm_error'] == ArmWorker.MSG_BOARD_INACTIVE
    assert planter.calls == []


def test_internal_error_aggregates_then_reraises(planter):
    planter.outcomes = {WORKOUTS[0]: RuntimeError("boom")}
    db = _store(event=_event(board_ids=WORKOUTS[:1]))
    with pytest.raises(RuntimeError, match="boom"):
        ArmWorker(db=db).run(CTF_ID, WORKOUTS[0])
    # The event is not left in ARMING
    assert _event_doc(db)['state'] == CtfStates.BROKEN.value
    assert _board_doc(db, WORKOUTS[0])['arm_status'] == 'failed'


# --- redelivery and stale messages -------------------------------------------------------------------------------

@pytest.mark.parametrize('state', [CtfStates.ARMED, CtfStates.RUNNING, CtfStates.DRAFT, CtfStates.BROKEN])
def test_event_not_arming_is_skipped_with_no_writes(planter, state):
    db = _store(event=_event(state=state))
    assert ArmWorker(db=db).run(CTF_ID, WORKOUTS[0]) is None
    assert planter.calls == []
    assert db.writes == []


def test_redelivered_message_for_finished_board_does_not_decrement_twice(planter):
    db = _store()
    worker = ArmWorker(db=db)
    worker.run(CTF_ID, WORKOUTS[0])
    writes = len(db.writes)
    assert worker.run(CTF_ID, WORKOUTS[0]) == 'armed'
    assert _event_doc(db)['boards_pending'] == 2
    assert len(db.writes) == writes
    assert len(planter.calls) == 1


def test_concurrent_duplicate_finishing_second_does_not_decrement(planter):
    # Both deliveries passed the up-front check; the second to aggregate finds the board terminal
    db = _store()
    worker = ArmWorker(db=db)
    worker.run(CTF_ID, WORKOUTS[0])
    _board_doc(db, WORKOUTS[0])['arm_status'] = 'armed'
    assert worker._aggregate(CTF_ID, f"{CTF_ID}-{WORKOUTS[0]}", 'failed', 'late') == 'armed'
    assert _event_doc(db)['boards_pending'] == 2
    assert _board_doc(db, WORKOUTS[0])['arm_error'] is None


def test_event_leaving_arming_mid_run_records_board_without_touching_event():
    db = _store()
    _event_doc(db)['state'] = CtfStates.ARMED.value
    assert ArmWorker(db=db)._aggregate(CTF_ID, f"{CTF_ID}-{WORKOUTS[0]}", 'armed', None) == 'armed'
    assert _board_doc(db, WORKOUTS[0])['arm_status'] == 'armed'
    assert [key[0] for key, _ in db.writes] == [DbCollections.CTF_BOARD.value]
    assert _event_doc(db)['boards_pending'] == 3


def test_missing_event_or_board_raises_not_found():
    db = _store(boards={WORKOUTS[0]: None})
    with pytest.raises(NotFound):
        ArmWorker(db=db).run(CTF_ID, WORKOUTS[0])
    with pytest.raises(NotFound):
        ArmWorker(db=db).run("otherevent", WORKOUTS[1])


# --- arm_result ---------------------------------------------------------------------------------------------------

def test_arm_result_with_no_errors_recorded():
    board = CtfBoardModel(**_board(WORKOUTS[0]))
    assert ArmWorker.arm_result(board) == ('failed', ArmWorker.MSG_NO_FLAGS_PLANTED)
