"""CtfStateManager: allow-listed, transactional, field-masked CTF event transitions."""
from datetime import datetime, timedelta, timezone
from itertools import product

import pytest
from pydantic import ValidationError

from common.constants.database import DbCollections
from common.constants.states import CtfStates
from common.exceptions.agoge import Conflict, NotFound
from common.models.agoge import CtfEventModel
from common.utilities.ctf_state_manager import CtfStateManager

S = CtfStates
ALLOWED = [
    (S.DRAFT, S.ARMING), (S.DRAFT, S.ARCHIVED),
    (S.ARMING, S.ARMED), (S.ARMING, S.BROKEN),
    (S.ARMED, S.ARMING), (S.ARMED, S.RUNNING), (S.ARMED, S.ARCHIVED),
    (S.RUNNING, S.PAUSED), (S.RUNNING, S.ENDED),
    (S.PAUSED, S.RUNNING), (S.PAUSED, S.ENDED),
    (S.ENDED, S.ARCHIVED),
    (S.BROKEN, S.ARMING), (S.BROKEN, S.ARCHIVED),
]
DISALLOWED = [pair for pair in product(CtfStates, CtfStates) if pair not in ALLOWED]


class FakeSnapshot:
    def __init__(self, data):
        self._data = data
        self.exists = data is not None

    def to_dict(self):
        return dict(self._data)


class FakeDocRef:
    def __init__(self, store, collection, doc_id):
        self.store, self.collection, self.id = store, collection, doc_id

    def get(self, transaction=None):
        assert transaction is not None, 'event reads must happen inside the transaction'
        transaction.reads.append(self.id)
        return FakeSnapshot(self.store.get((self.collection, self.id)))


class FakeClient:
    def __init__(self, store):
        self.store = store

    def collection(self, name):
        client = self

        class _Collection:
            def document(self, doc_id):
                return FakeDocRef(client.store, name, doc_id)
        return _Collection()


class FakeTransaction:
    def __init__(self, store):
        self.store = store
        self.reads = []
        self.updates = []

    def update(self, doc_ref, data):
        self.updates.append((doc_ref.collection, doc_ref.id, dict(data)))
        self.store[(doc_ref.collection, doc_ref.id)].update(data)


class FakeDb:
    """Mirrors FirestoreDatabase: `.db` is the raw client, `.transaction(fn)` calls fn(transaction)."""
    def __init__(self):
        self.store = {}
        self.db = FakeClient(self.store)
        self.transactions = []

    def transaction(self, operation_func, *args, **kwargs):
        transaction = FakeTransaction(self.store)
        self.transactions.append(transaction)
        return operation_func(transaction, *args, **kwargs)


def _event(state: CtfStates, **overrides) -> dict:
    data = {
        'id': 'abcdefghij',
        'unit_id': 'unitunitun',
        'instructor_id': ['teacher@example.edu'],
        'spec': {'name': 'Spring CTF', 'flags': [{
            'id': 'web1', 'server': 'web', 'slot': 1, 'points': 100,
            'location_type': 'file', 'path': '/root/flag.txt', 'operating_system': 'linux',
        }]},
        'creation_timestamp': 1_700_000_000.0,
        'board_ids': ['boardoneaa', 'boardtwobb'],
        'state': state.value,
        'state_timestamp': '2026-01-01T00:00:00+00:00',
    }
    data.update(overrides)
    return data


@pytest.fixture
def db():
    return FakeDb()


@pytest.fixture
def manager(db):
    return CtfStateManager(db=db)


def _seed(db, state: CtfStates, **overrides):
    db.store[(DbCollections.CTF.value, 'abcdefghij')] = _event(state, **overrides)


def test_allow_list_matches_prd():
    assert CtfStateManager.VALID_TRANSITIONS == set(ALLOWED)


@pytest.mark.parametrize('current,new', ALLOWED, ids=lambda s: s.name)
def test_every_allowed_transition_is_written(db, manager, current, new):
    _seed(db, current)
    result = manager.transition('abcdefghij', new)

    assert isinstance(result, CtfEventModel)
    assert result.state == new.value
    stored = db.store[(DbCollections.CTF.value, 'abcdefghij')]
    assert stored['state'] == new.value
    [transaction] = db.transactions
    assert transaction.reads == ['abcdefghij']
    assert len(transaction.updates) == 1


@pytest.mark.parametrize('current,new', [(S.RUNNING, S.ARMING), (S.ENDED, S.RUNNING)], ids=lambda s: s.name)
def test_named_disallowed_transitions_raise_conflict(db, manager, current, new):
    _seed(db, current)
    with pytest.raises(Conflict):
        manager.transition('abcdefghij', new)
    assert db.transactions[0].updates == []
    assert db.store[(DbCollections.CTF.value, 'abcdefghij')]['state'] == current.value


@pytest.mark.parametrize('current,new', DISALLOWED, ids=lambda s: s.name)
def test_every_other_pair_raises_conflict(db, manager, current, new):
    # Includes self-transitions such as RUNNING -> RUNNING: a repeated start is a conflict, not a no-op.
    _seed(db, current)
    with pytest.raises(Conflict):
        manager.transition('abcdefghij', new)
    assert db.transactions[0].updates == []


def test_state_timestamp_is_stamped_with_current_utc(db, manager):
    _seed(db, S.DRAFT)
    before = datetime.now(timezone.utc)
    result = manager.transition('abcdefghij', S.ARMING)
    after = datetime.now(timezone.utc)

    stamped = datetime.fromisoformat(db.store[(DbCollections.CTF.value, 'abcdefghij')]['state_timestamp'])
    assert stamped.tzinfo is not None and stamped.utcoffset() == timedelta(0)
    assert before <= stamped <= after
    assert result.state_timestamp == stamped.isoformat()


def test_write_is_field_masked_to_state_timestamp_and_extra_fields(db, manager):
    _seed(db, S.DRAFT)
    manager.transition('abcdefghij', S.ARMING, boards_pending=2)

    [(collection, doc_id, written)] = db.transactions[0].updates
    assert collection == DbCollections.CTF.value and doc_id == 'abcdefghij'
    # Only the masked keys are sent; spec, board_ids, etc. are never rewritten.
    assert set(written) == {'state', 'state_timestamp', 'boards_pending'}
    assert written['boards_pending'] == 2


def test_extra_fields_are_returned_on_the_model(db, manager):
    _seed(db, S.ARMED)
    result = manager.transition('abcdefghij', S.RUNNING, starts_at=1_800_000_000.0)
    assert result.starts_at == 1_800_000_000.0
    assert result.board_ids == ['boardoneaa', 'boardtwobb']


def test_extra_field_can_be_cleared_to_none(db, manager):
    _seed(db, S.PAUSED, paused_at=1_800_000_100.0)
    manager.transition('abcdefghij', S.RUNNING, paused_at=None, accumulated_pause_seconds=60.0)
    stored = db.store[(DbCollections.CTF.value, 'abcdefghij')]
    assert stored['paused_at'] is None
    assert stored['accumulated_pause_seconds'] == 60.0


def test_accepts_int_state(db, manager):
    _seed(db, S.ARMED)
    assert manager.transition('abcdefghij', S.RUNNING.value).state == S.RUNNING.value


def test_missing_event_raises_not_found(db, manager):
    with pytest.raises(NotFound):
        manager.transition('abcdefghij', S.ARMING)


def test_invalid_extra_field_value_fails_revalidation_without_writing(db, manager):
    _seed(db, S.DRAFT)
    with pytest.raises(ValidationError):
        manager.transition('abcdefghij', S.ARMING, boards_pending='not-a-number')
    assert db.transactions[0].updates == []


def test_unknown_extra_field_is_rejected(db, manager):
    # CtfEventModel ignores unknown keys, so the manager must refuse them or they'd reach Firestore.
    _seed(db, S.DRAFT)
    with pytest.raises(ValueError, match='boards_pendng'):
        manager.transition('abcdefghij', S.ARMING, boards_pendng=2)
    assert db.transactions[0].updates == []


@pytest.mark.parametrize('field', ['id', 'state_timestamp'])
def test_protected_fields_are_rejected(db, manager, field):
    _seed(db, S.DRAFT)
    with pytest.raises(ValueError):
        manager.transition('abcdefghij', S.ARMING, **{field: 'x'})


def test_corrupt_stored_state_raises_conflict(db, manager):
    _seed(db, S.DRAFT)
    db.store[(DbCollections.CTF.value, 'abcdefghij')]['state'] = 99
    with pytest.raises(Conflict):
        manager.transition('abcdefghij', S.ARMING)


def test_transition_in_callers_transaction_with_pre_read_event_does_not_read_again(db, manager):
    # Arm aggregation writes its board first; Firestore forbids reads after writes, so it passes the event.
    _seed(db, S.ARMING, boards_pending=1)
    event = dict(db.store[(DbCollections.CTF.value, 'abcdefghij')])

    def aggregate(transaction):
        return manager.transition_in_transaction(transaction, 'abcdefghij', S.ARMED, event=event, boards_pending=0)

    result = db.transaction(aggregate)
    assert result.state == S.ARMED.value and result.boards_pending == 0
    assert db.transactions[0].reads == []


def test_is_valid_transition():
    assert CtfStateManager.is_valid_transition(S.ARMED, S.RUNNING)
    assert CtfStateManager.is_valid_transition(2, 3)
    assert not CtfStateManager.is_valid_transition(S.RUNNING, S.ARMING)
    assert not CtfStateManager.is_valid_transition(99, S.ARMING)
