"""FlagPlanter.plant against a mocked ComputeInstanceAPI and an in-memory board document (SC-5, SC-6, SC-7)."""
import copy
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from cloud_fn_utilities.course_objects.ctf import flag_planter as flag_planter_module
from common.exceptions import NotFound
from common.models.agoge import CtfBoardModel
from common.utilities.ctf_plant_contract import (
    GUEST_ATTRIBUTE_NAMESPACE, GUEST_ATTRIBUTE_RESULT_KEY, GUEST_ATTRIBUTES_ENABLE_KEY, PLANT_METADATA_KEY
)

FlagPlanter = flag_planter_module.FlagPlanter

SEED = "f" * 64
WORKOUT_ID = "abcdefghij"
BOARD_ID = f"ctfeventaa-{WORKOUT_ID}"
WEB = f"{WORKOUT_ID}-web"
DB = f"{WORKOUT_ID}-db"

FLAGS = [
    {'id': 'web-user', 'server': 'web', 'slot': 1, 'location_type': 'file', 'path': '/home/student/user.txt',
     'operating_system': 'linux', 'points': 100},
    {'id': 'web-root', 'server': 'web', 'slot': 2, 'location_type': 'env', 'path': 'AGOGE_ROOT_FLAG',
     'operating_system': 'linux', 'points': 200},
    {'id': 'db-root', 'server': 'db', 'slot': 1, 'location_type': 'file', 'path': '/root/db.txt',
     'operating_system': 'linux', 'points': 300},
]
EVENT = {
    'id': 'ctfeventaa', 'unit_id': 'unitaaaaaa', 'instructor_id': ['gm@example.edu'],
    'spec': {'name': 'Spring CTF', 'flags': FLAGS, 'scoring': {'flag_prefix': 'agoge'}},
    'seed_version': 1, 'creation_timestamp': 1.0, 'state': 1, 'state_timestamp': '2026-10-16T00:00:00+00:00',
}


def _board_doc():
    # Stored as a full model dump, the way the board is written at event creation
    return CtfBoardModel(**{'id': BOARD_ID, 'workout_id': WORKOUT_ID, 'ctf_id': 'ctfeventaa', 'team_name': 'Team 1',
            'flags': [{'flag_id': flag['id'], 'digest': '0' * 64} for flag in FLAGS]}).model_dump()


class FakeDb:
    """Mimics FirestoreDatabase.transaction plus the raw `db.collection(...).document(...)` client."""
    def __init__(self, doc):
        self.doc = doc
        self.writes = []      # every dict written, for SC-4 and ordering checks
        self.db = self
        self.calls = None     # shared call log with the compute fake

    def collection(self, name):
        assert name == 'agoge-ctf-board'
        return self

    def document(self, doc_id):
        assert doc_id == BOARD_ID
        return self

    def get(self, transaction=None):
        return SimpleNamespace(exists=self.doc is not None, to_dict=lambda: copy.deepcopy(self.doc))

    def transaction(self, operation):
        return operation(self)

    def update(self, doc_ref, data):
        self.doc.update(copy.deepcopy(data))
        self.writes.append(copy.deepcopy(data))
        if self.calls is not None:
            self.calls.append(('db', [f.get('plant_status') for f in data['flags']]))


class FakeClock:
    def __init__(self):
        self.now = 1000.0
        self.sleeps = []

    def monotonic(self):
        return self.now

    def time(self):
        return 1_800_000_000.0 + self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


@pytest.fixture
def clock(monkeypatch):
    fake = FakeClock()
    monkeypatch.setattr(flag_planter_module, 'time', fake)
    return fake


@pytest.fixture
def nonces(monkeypatch):
    issued = iter(['nonce-1', 'nonce-2', 'nonce-3'])
    monkeypatch.setattr(flag_planter_module.IdGenerator, 'uuid', classmethod(lambda cls: next(issued)))


def _compute(results, status=None, calls=None):
    """`results` maps instance name -> list of plant-result values returned on successive polls (last repeats)."""
    status = status or {}
    calls = calls if calls is not None else []
    compute = MagicMock()
    polls = {name: list(values) for name, values in results.items()}

    def get(name):
        calls.append(('get', name))
        if status.get(name) == 'missing':
            raise NotFound(name)
        return SimpleNamespace(status=status.get(name, 'RUNNING'))

    def set_metadata(name, items=None, remove=None):
        calls.append(('set_metadata', name, dict(items or {}), list(remove or [])))

    def reset(name):
        calls.append(('reset', name))

    def guest(name, query_path):
        assert query_path == GUEST_ATTRIBUTE_NAMESPACE
        calls.append(('poll', name))
        values = polls[name]
        value = values.pop(0) if len(values) > 1 else values[0]
        if isinstance(value, Exception):
            raise value
        return {} if value is None else {GUEST_ATTRIBUTE_RESULT_KEY: value}

    compute.get.side_effect = get
    compute.set_metadata.side_effect = set_metadata
    compute.reset.side_effect = reset
    compute.get_guest_attributes.side_effect = guest
    compute.calls = calls
    return compute


def _planter(compute, db, seed=SEED):
    planter = FlagPlanter(EVENT, env_dict={'project': 'p'}, compute_api=compute, db=db)
    planter._env = SimpleNamespace(ctf_flag_seed=seed)
    return planter


def _flags(board):
    return {flag.flag_id: flag for flag in board.flags}


def _removals(compute):
    return [c[1] for c in compute.calls if c[0] == 'set_metadata' and c[3] == [PLANT_METADATA_KEY]]


def _plants(compute):
    return [c for c in compute.calls if c[0] == 'set_metadata' and PLANT_METADATA_KEY in c[2]]


def test_sc5_every_flag_planted_when_hosts_confirm(clock, nonces):
    compute = _compute({WEB: [None, 'ok:nonce-1'], DB: ['ok:nonce-2']})
    db = FakeDb(_board_doc())

    board = _planter(compute, db).plant(_board_doc(), ['web', 'db'])

    for flag in board.flags:
        assert flag.plant_status == 'planted'
        assert flag.planted_at is not None
        assert flag.plant_error is None
    # The board document, not just the returned model, carries the result
    assert {f['plant_status'] for f in db.doc['flags']} == {'planted'}
    assert all(f['planted_at'] for f in db.doc['flags'])


def test_payload_and_reset_reach_every_server_before_any_poll(clock, nonces):
    compute = _compute({WEB: ['ok:nonce-1'], DB: ['ok:nonce-2']})
    _planter(compute, FakeDb(_board_doc())).plant(_board_doc(), ['web', 'db'])

    kinds = [c[0] for c in compute.calls]
    first_poll = kinds.index('poll')
    assert [c[1] for c in compute.calls[:first_poll] if c[0] == 'reset'] == [WEB, DB]
    plant = _plants(compute)[0][2]
    assert plant[GUEST_ATTRIBUTES_ENABLE_KEY] == 'TRUE'
    assert 'nonce-1' in plant[PLANT_METADATA_KEY]


def test_flags_marked_planting_before_the_payload_is_written(clock, nonces):
    calls = []
    compute = _compute({WEB: ['ok:nonce-1']}, calls=calls)
    db = FakeDb(_board_doc())
    db.calls = calls

    _planter(compute, db).plant(_board_doc(), ['web'])

    first_db = calls.index(next(c for c in calls if c[0] == 'db'))
    first_plant = calls.index(_plants(compute)[0])
    assert first_db < first_plant
    assert calls[first_db][1] == ['planting', 'planting', 'pending']


def test_sc6_plant_key_removed_after_success(clock, nonces):
    compute = _compute({WEB: ['ok:nonce-1']})
    _planter(compute, FakeDb(_board_doc())).plant(_board_doc(), ['web'])

    assert _removals(compute) == [WEB]
    assert compute.calls[-1][0] == 'set_metadata' and compute.calls[-1][3] == [PLANT_METADATA_KEY]


def test_sc6_plant_key_removed_after_error_result(clock, nonces):
    compute = _compute({WEB: ['error:nonce-1:web-user: could not write file']})
    board = _planter(compute, FakeDb(_board_doc())).plant(_board_doc(), ['web'])

    flags = _flags(board)
    assert flags['web-user'].plant_status == 'failed'
    assert flags['web-user'].plant_error == 'web-user: could not write file'
    assert flags['web-root'].plant_status == 'failed'
    assert flags['web-user'].planted_at is None
    assert _removals(compute) == [WEB]


def test_sc6_plant_key_removed_after_confirmation_timeout(clock, nonces):
    compute = _compute({WEB: [None]})
    board = _planter(compute, FakeDb(_board_doc())).plant(_board_doc(), ['web'])

    flags = _flags(board)
    assert flags['web-user'].plant_status == 'failed'
    assert flags['web-user'].plant_error == 'No plant confirmation within 240 s'
    assert _removals(compute) == [WEB]
    # Every 10 s for up to 240 s
    assert set(clock.sleeps) == {10}
    assert sum(clock.sleeps) == 240
    assert len([c for c in compute.calls if c[0] == 'poll']) == 24


def test_sc7_single_server_replant_never_deletes_the_instance(clock, nonces):
    compute = _compute({DB: ['ok:nonce-1']})
    db = FakeDb(_board_doc())

    board = _planter(compute, db).plant(_board_doc(), ['db'])

    assert [c[1] for c in _plants(compute)] == [DB]
    assert [c[1] for c in compute.calls if c[0] == 'reset'] == [DB]
    for forbidden in ('delete', 'nuke', 'stop', 'start', 'create'):
        assert not getattr(compute, forbidden).called, forbidden
    flags = _flags(board)
    assert flags['db-root'].plant_status == 'planted'
    # The other server's flags are untouched
    assert flags['web-user'].plant_status == 'pending'
    assert flags['web-root'].plant_status == 'pending'


def test_stale_result_from_an_earlier_plant_is_ignored(clock, nonces):
    compute = _compute({WEB: ['ok:old-nonce', 'error:old-nonce:boom', 'ok:nonce-1']})
    board = _planter(compute, FakeDb(_board_doc())).plant(_board_doc(), ['web'])

    assert _flags(board)['web-user'].plant_status == 'planted'
    assert len([c for c in compute.calls if c[0] == 'poll']) == 3


def test_stopped_server_is_not_reset_or_started(clock, nonces):
    compute = _compute({WEB: ['ok:nonce-1'], DB: ['ok:nonce-2']}, status={DB: 'TERMINATED'})
    board = _planter(compute, FakeDb(_board_doc())).plant(_board_doc(), ['web', 'db'])

    flags = _flags(board)
    assert flags['db-root'].plant_status == 'failed'
    assert flags['db-root'].plant_error == 'Server is not running'
    assert flags['web-user'].plant_status == 'planted'
    assert DB not in [c[1] for c in compute.calls if c[0] in ('reset', 'set_metadata', 'poll')]
    assert not compute.start.called


def test_missing_instance_fails_its_flags(clock, nonces):
    compute = _compute({DB: ['ok:nonce-1']}, status={DB: 'missing'})
    board = _planter(compute, FakeDb(_board_doc())).plant(_board_doc(), ['db'])

    assert _flags(board)['db-root'].plant_error == 'Server instance not found'
    assert _plants(compute) == []
    assert _removals(compute) == []


def test_instance_deleted_while_polling_fails_and_still_cleans_up(clock, nonces):
    compute = _compute({WEB: [NotFound(WEB)]})
    board = _planter(compute, FakeDb(_board_doc())).plant(_board_doc(), ['web'])

    assert _flags(board)['web-user'].plant_error == 'Server instance not found'
    assert len([c for c in compute.calls if c[0] == 'poll']) == 1
    assert _removals(compute) == [WEB]


def test_transient_poll_error_keeps_polling(clock, nonces):
    compute = _compute({WEB: [RuntimeError('503'), 'ok:nonce-1']})
    board = _planter(compute, FakeDb(_board_doc())).plant(_board_doc(), ['web'])

    assert _flags(board)['web-user'].plant_status == 'planted'


def test_reset_failure_fails_flags_and_removes_the_key(clock, nonces):
    compute = _compute({WEB: ['ok:nonce-1']})
    compute.reset.side_effect = RuntimeError('reset failed')
    board = _planter(compute, FakeDb(_board_doc())).plant(_board_doc(), ['web'])

    assert _flags(board)['web-user'].plant_error == 'Could not deliver the plant payload'
    assert _removals(compute) == [WEB]
    assert not compute.get_guest_attributes.called


def test_unexpected_error_still_removes_the_plant_key(clock, nonces):
    compute = _compute({WEB: ['ok:nonce-1']})
    db = FakeDb(_board_doc())
    planter = _planter(compute, db)
    real_record = planter._record

    def record(board, updates):
        if any(u.get('plant_status') == 'planted' for u in updates.values()):
            raise RuntimeError('firestore down')
        return real_record(board, updates)

    planter._record = record
    with pytest.raises(RuntimeError):
        planter.plant(_board_doc(), ['web'])
    assert _removals(compute) == [WEB]
    # No flag is left stuck in `planting`
    web = [f for f in db.doc['flags'] if f['flag_id'].startswith('web-')]
    assert {f['plant_status'] for f in web} == {'failed'}
    assert {f['plant_error'] for f in web} == {'Plant aborted by an internal error'}


def test_missing_seed_fails_flags_without_touching_compute(clock, nonces):
    compute = _compute({WEB: ['ok:nonce-1']})
    board = _planter(compute, FakeDb(_board_doc()), seed=None).plant(_board_doc(), ['web'])

    assert _flags(board)['web-user'].plant_error == 'CTF flag seed is not configured'
    assert compute.calls == []


def test_concurrent_solve_on_the_board_is_preserved(clock, nonces):
    stored = _board_doc()
    stored['flags'][2].update({'solved': True, 'solved_at': 5.0})   # db-root solved since the board was read
    db = FakeDb(stored)
    compute = _compute({WEB: ['ok:nonce-1']})

    _planter(compute, db).plant(_board_doc(), ['web'])

    assert db.doc['flags'][2]['solved'] is True
    assert db.doc['flags'][2]['solved_at'] == 5.0


def test_sc4_no_flag_value_written_to_the_board(clock, nonces):
    compute = _compute({WEB: ['ok:nonce-1'], DB: ['error:nonce-2:db-root: could not write file']})
    db = FakeDb(_board_doc())

    _planter(compute, db).plant(_board_doc(), ['web', 'db'])

    assert db.writes
    assert 'agoge{' not in json.dumps(db.writes)


def test_server_without_board_flags_is_skipped(clock, nonces):
    compute = _compute({})
    db = FakeDb(_board_doc())

    board = _planter(compute, db).plant(_board_doc(), ['mail'])

    assert compute.calls == []
    assert db.writes == []
    assert {flag.plant_status for flag in board.flags} == {'pending'}
