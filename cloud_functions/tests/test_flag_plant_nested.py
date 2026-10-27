"""FlagPlanter.plant on a nested host (N9): watcher ack instead of a reset, guest scope, per-key status."""
import copy
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from cloud_fn_utilities.course_objects.ctf import flag_planter as flag_planter_module
from common.exceptions import NotFound
from common.models.agoge import CtfBoardModel
from common.utilities.ctf_plant_contract import (
    GUEST_ATTRIBUTE_ACK_KEY, GUEST_ATTRIBUTE_NAMESPACE, GUEST_ATTRIBUTE_RESULT_KEY, PLANT_METADATA_KEY,
    WATCHER_ACK_SECONDS, guest_result_key
)

FlagPlanter = flag_planter_module.FlagPlanter

SEED = "f" * 64
WORKOUT_ID = "abcdefghij"
BOARD_ID = f"ctfeventaa-{WORKOUT_ID}"
HV = f"{WORKOUT_ID}-hv-host"
WEB = f"{WORKOUT_ID}-web"
RESULT = GUEST_ATTRIBUTE_RESULT_KEY
ACK = GUEST_ATTRIBUTE_ACK_KEY
LIN = guest_result_key('lin')
WIN = guest_result_key('win-dc')
VAULT = guest_result_key('vault')


def _flag(flag_id, server, slot, path, operating_system='linux', guest=None, location_type='file'):
    flag = {'id': flag_id, 'server': server, 'slot': slot, 'location_type': location_type, 'path': path,
            'operating_system': operating_system, 'points': 100}
    if guest:
        flag['guest'] = guest
    return flag


FLAGS = [
    _flag('hv-root', 'hv-host', 1, '/root/hv.txt'),
    _flag('lin-user', 'hv-host', 1, '/home/student/user.txt', guest='lin'),
    _flag('lin-root', 'hv-host', 2, '/root/root.txt', guest='lin'),
    _flag('win-dc', 'hv-host', 1, 'HKLM\\SOFTWARE\\Corp:Secret', operating_system='windows', guest='win-dc',
          location_type='registry'),
    _flag('web-user', 'web', 1, '/home/student/web.txt'),
]
GUESTS = [
    {'name': 'lin', 'server': 'hv-host', 'domain': 'ubuntu-lin', 'operating_system': 'linux', 'driver': 'qemu-agent'},
    {'name': 'win-dc', 'server': 'hv-host', 'domain': 'win2019-dc', 'operating_system': 'windows',
     'driver': 'qemu-agent'},
]
GUEST_FLAGS = {'lin': ['lin-user', 'lin-root'], 'win-dc': ['win-dc']}


def _event(flags=FLAGS, guests=GUESTS):
    return {
        'id': 'ctfeventaa', 'unit_id': 'unitaaaaaa', 'instructor_id': ['gm@example.edu'],
        'spec': {'name': 'Spring CTF', 'flags': flags, 'nested_guests': guests, 'scoring': {'flag_prefix': 'agoge'}},
        'seed_version': 1, 'creation_timestamp': 1.0, 'state': 1, 'state_timestamp': '2026-10-16T00:00:00+00:00',
    }


def _board_doc(flags=FLAGS):
    return CtfBoardModel(**{'id': BOARD_ID, 'workout_id': WORKOUT_ID, 'ctf_id': 'ctfeventaa', 'team_name': 'Team 1',
            'flags': [{'flag_id': flag['id'], 'digest': '0' * 64} for flag in flags]}).model_dump()


class FakeDb:
    """FirestoreDatabase.transaction plus the raw `db.collection(...).document(...)` client, in memory."""
    def __init__(self, doc):
        self.doc = doc
        self.db = self

    def collection(self, name):
        return self

    def document(self, doc_id):
        assert doc_id == BOARD_ID
        return self

    def get(self, transaction=None):
        return SimpleNamespace(exists=True, to_dict=lambda: copy.deepcopy(self.doc))

    def transaction(self, operation):
        return operation(self)

    def update(self, doc_ref, data):
        self.doc.update(copy.deepcopy(data))


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


@pytest.fixture(autouse=True)
def nonces(monkeypatch):
    issued = iter(['nonce-1', 'nonce-2', 'nonce-3'])
    monkeypatch.setattr(flag_planter_module.IdGenerator, 'uuid', classmethod(lambda cls: next(issued)))


def _compute(attributes):
    """
    `attributes` maps instance name -> a function of the elapsed fake seconds returning the guest attribute
    dict under agoge-ctf/ (or raising), so tests describe what the VM has written by when.
    """
    calls = []
    compute = MagicMock()

    def get(name):
        calls.append(('get', name))
        return SimpleNamespace(status='RUNNING')

    def set_metadata(name, items=None, remove=None):
        calls.append(('set_metadata', name, dict(items or {}), list(remove or [])))

    def reset(name):
        calls.append(('reset', name))

    def guest_attributes(name, query_path):
        assert query_path == GUEST_ATTRIBUTE_NAMESPACE
        calls.append(('poll', name))
        return attributes[name](compute.clock.now - 1000.0)

    compute.get.side_effect = get
    compute.set_metadata.side_effect = set_metadata
    compute.reset.side_effect = reset
    compute.get_guest_attributes.side_effect = guest_attributes
    compute.calls = calls
    return compute


def _planter(compute, clock, event=None):
    compute.clock = clock
    planter = FlagPlanter(event or _event(), env_dict={'project': 'p'}, compute_api=compute, db=FakeDb(_board_doc()))
    planter._env = SimpleNamespace(ctf_flag_seed=SEED)
    return planter


def _resets(compute):
    return [c[1] for c in compute.calls if c[0] == 'reset']


def _flags(board):
    return {flag.flag_id: flag for flag in board.flags}


def _all_ok(nonce):
    return {ACK: nonce, RESULT: f"ok:{nonce}", LIN: f"ok:{nonce}", WIN: f"ok:{nonce}"}


def test_acked_whole_server_plant_never_resets(clock):
    compute = _compute({HV: lambda t: _all_ok('nonce-1')})
    board = _planter(compute, clock).plant(_board_doc(), ['hv-host'])

    assert _resets(compute) == []
    flags = _flags(board)
    for flag_id in ['hv-root', 'lin-user', 'lin-root', 'win-dc']:
        assert flags[flag_id].plant_status == 'planted'
    # The payload key is still removed afterwards
    assert ('set_metadata', HV, {}, [PLANT_METADATA_KEY]) in compute.calls


def test_unacked_whole_server_plant_resets_the_parent_once(clock):
    # No watcher: nothing until the loader runs the payload after the fallback reset
    compute = _compute({HV: lambda t: {} if t <= WATCHER_ACK_SECONDS else _all_ok('nonce-1')})
    board = _planter(compute, clock).plant(_board_doc(), ['hv-host'])

    assert _resets(compute) == [HV]
    # The reset waits out the ack window, then comes before any result poll
    reset_at = compute.calls.index(('reset', HV))
    assert len([c for c in compute.calls[:reset_at] if c[0] == 'poll']) == WATCHER_ACK_SECONDS // 5
    assert {f.plant_status for f in board.flags if f.flag_id != 'web-user'} == {'planted'}


def test_ack_from_an_earlier_plant_does_not_count(clock):
    compute = _compute({HV: lambda t: {ACK: 'old-nonce'} if t <= WATCHER_ACK_SECONDS else _all_ok('nonce-1')})
    _planter(compute, clock).plant(_board_doc(), ['hv-host'])

    assert _resets(compute) == [HV]


def test_unacked_guest_plant_never_resets_and_fails_its_flags(clock):
    compute = _compute({HV: lambda t: {}})
    board = _planter(compute, clock).plant(_board_doc(), ['hv-host'], guest='lin')

    assert _resets(compute) == []
    flags = _flags(board)
    for flag_id in GUEST_FLAGS['lin']:
        assert flags[flag_id].plant_status == 'failed'
        assert flags[flag_id].plant_error == "Plant watcher did not respond"
    # Flags outside the guest are not touched
    for flag_id in ['hv-root', 'win-dc', 'web-user']:
        assert flags[flag_id].plant_status == 'pending'
    # It gives up after the ack window, without waiting for a result
    assert sum(clock.sleeps) == WATCHER_ACK_SECONDS
    assert ('set_metadata', HV, {}, [PLANT_METADATA_KEY]) in compute.calls


def test_guest_plant_targets_only_that_guest(clock):
    compute = _compute({HV: lambda t: {ACK: 'nonce-1', RESULT: 'ok:nonce-1', LIN: 'ok:nonce-1'}})
    planter = _planter(compute, clock)
    board = planter.plant(_board_doc(), ['hv-host'], guest='lin')

    assert _resets(compute) == []
    flags = _flags(board)
    assert {flags[f].plant_status for f in GUEST_FLAGS['lin']} == {'planted'}
    assert flags['hv-root'].plant_status == 'pending'
    assert flags['win-dc'].plant_status == 'pending'
    # The payload relays that guest only and plants nothing on the parent
    payload = next(c[2][PLANT_METADATA_KEY] for c in compute.calls if c[0] == 'set_metadata' and c[2])
    assert 'ubuntu-lin' in payload
    assert 'win2019-dc' not in payload
    assert '/root/hv.txt' not in payload


def test_guest_and_parent_flags_take_status_from_their_own_keys(clock):
    compute = _compute({HV: lambda t: {
        ACK: 'nonce-1', RESULT: 'ok:nonce-1', LIN: 'error:nonce-1:lin: guest agent did not respond',
        WIN: 'ok:nonce-1',
    }})
    board = _planter(compute, clock).plant(_board_doc(), ['hv-host'])

    flags = _flags(board)
    assert flags['hv-root'].plant_status == 'planted'
    assert flags['win-dc'].plant_status == 'planted'
    for flag_id in GUEST_FLAGS['lin']:
        assert flags[flag_id].plant_status == 'failed'
        assert flags[flag_id].plant_error == 'lin: guest agent did not respond'


def test_parent_error_does_not_fail_guest_flags(clock):
    compute = _compute({HV: lambda t: {
        ACK: 'nonce-1', RESULT: 'error:nonce-1:hv-root: write failed', LIN: 'ok:nonce-1', WIN: 'ok:nonce-1',
    }})
    board = _planter(compute, clock).plant(_board_doc(), ['hv-host'])

    flags = _flags(board)
    assert flags['hv-root'].plant_status == 'failed'
    assert flags['hv-root'].plant_error == 'hv-root: write failed'
    assert {flags[f].plant_status for f in ['lin-user', 'lin-root', 'win-dc']} == {'planted'}


def test_guest_keys_arrive_independently(clock):
    # The Windows guest answers later than the parent's other keys; plant-result only once every section ends
    def attributes(t):
        if t < 60:
            return {ACK: 'nonce-1', LIN: 'ok:nonce-1'}
        return _all_ok('nonce-1')
    compute = _compute({HV: attributes})
    board = _planter(compute, clock).plant(_board_doc(), ['hv-host'])

    assert {f.plant_status for f in board.flags if f.flag_id != 'web-user'} == {'planted'}


def test_guest_key_missing_after_plant_result_fails_that_guest(clock):
    # plant-result is written last, so a guest key absent once it is present will never arrive
    compute = _compute({HV: lambda t: {ACK: 'nonce-1', RESULT: 'ok:nonce-1', LIN: 'ok:nonce-1'}})
    board = _planter(compute, clock).plant(_board_doc(), ['hv-host'])

    flags = _flags(board)
    assert flags['win-dc'].plant_status == 'failed'
    assert flags['win-dc'].plant_error == "Guest relay reported no result"
    assert flags['hv-root'].plant_status == 'planted'
    assert sum(clock.sleeps) < 60


def test_nested_host_confirmation_window_is_the_nested_timeout(clock):
    compute = _compute({HV: lambda t: {ACK: 'nonce-1'}})
    board = _planter(compute, clock).plant(_board_doc(), ['hv-host'])

    assert {f.plant_error for f in board.flags if f.flag_id != 'web-user'} == {'No plant confirmation within 420 s'}
    # Ack window (first ack poll answers at 5 s) plus the 420 s confirmation window
    assert sum(clock.sleeps) == 5 + 420


def test_plain_server_in_the_same_plant_is_still_reset_and_keeps_its_window(clock):
    compute = _compute({
        HV: lambda t: _all_ok('nonce-1'),
        WEB: lambda t: {},
    })
    board = _planter(compute, clock).plant(_board_doc(), ['hv-host', 'web'])

    assert _resets(compute) == [WEB]
    flags = _flags(board)
    assert flags['web-user'].plant_error == 'No plant confirmation within 240 s'
    assert flags['hv-root'].plant_status == 'planted'
    # The plain server is never polled for an ack
    assert compute.calls.index(('reset', WEB)) < compute.calls.index(('poll', HV))


def test_failed_fallback_reset_fails_the_server_flags(clock):
    compute = _compute({HV: lambda t: {}})
    compute.reset.side_effect = RuntimeError("boom")
    board = _planter(compute, clock).plant(_board_doc(), ['hv-host'])

    assert {f.plant_error for f in board.flags if f.flag_id != 'web-user'} == {"Could not deliver the plant payload"}
    assert sum(clock.sleeps) == WATCHER_ACK_SECONDS


def test_instance_missing_during_ack_wait_fails_its_flags(clock):
    def attributes(t):
        raise NotFound(HV)
    compute = _compute({HV: attributes})
    board = _planter(compute, clock).plant(_board_doc(), ['hv-host'])

    assert _resets(compute) == []
    assert {f.plant_error for f in board.flags if f.flag_id != 'web-user'} == {"Server instance not found"}


def test_guest_not_declared_on_the_server_is_skipped(clock):
    compute = _compute({HV: lambda t: {}, WEB: lambda t: {}})
    board = _planter(compute, clock).plant(_board_doc(), ['web', 'hv-host'], guest='nope')

    assert compute.calls == []
    assert {f.plant_status for f in board.flags} == {'pending'}


def test_build_payload_rejects_a_guest_on_a_plain_server(clock):
    planter = _planter(_compute({}), clock)
    with pytest.raises(Exception, match="has no nested guests"):
        planter.build_payload(_board_doc(), 'web', 'nonce-1', SEED, guest='lin')
