"""
HostReset on a nested guest (N11): replant, restart and rebuild run through the parent's plant watcher with the
real FlagPlanter. GCE, Firestore and the clock are faked; the virsh sections also run against a fake virsh.
"""
import os
import re
import shutil
import subprocess
from types import SimpleNamespace
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from cloud_fn_utilities.course_objects.ctf import flag_planter as flag_planter_module
from cloud_fn_utilities.course_objects.ctf import host_reset as host_reset_module
from cloud_fn_utilities.course_objects.ctf.flag_planter import FlagPlanter
from cloud_fn_utilities.course_objects.ctf.host_reset import HostReset
from common.constants.database import DbCollections
from common.exceptions import BadRequest, NotFound
from common.models.agoge import CtfBoardModel
from common.utilities.ctf_flags import derive_flag_value
from common.utilities.ctf_plant_contract import LOCATION_PATH_PATTERNS, PLANT_METADATA_KEY

CTF_ID = "ctfeventaa"
WORKOUT_A = "aaaaaaaaaa"
WORKOUT_B = "bbbbbbbbbb"
BOARD_A = f"{CTF_ID}-{WORKOUT_A}"
BOARD_B = f"{CTF_ID}-{WORKOUT_B}"
HOST = f"{WORKOUT_A}-hv-host"
SEED = "f" * 64
NONCE = "0d4c1a52-6a8e-4c39-9d43-2b8f5f2a7e11"
ENV = {"project": "agoge-test-project"}
needs_bash = pytest.mark.skipif(shutil.which('bash') is None, reason="bash is not installed")


def _flag(flag_id, server, slot, path, operating_system='linux', guest=None):
    flag = {'id': flag_id, 'server': server, 'slot': slot, 'location_type': 'file', 'path': path,
            'operating_system': operating_system, 'points': 100}
    if guest:
        flag['guest'] = guest
    return flag


FLAGS = [
    _flag('host-root', 'hv-host', 1, '/root/host.txt'),
    _flag('web-user', 'hv-host', 1, '/home/student/user.txt', guest='web'),
    _flag('dc-file', 'hv-host', 1, 'C:\\Users\\Public\\flag.txt', 'windows', guest='win-dc'),
    _flag('db-root', 'db', 1, '/root/db.txt'),
]
GUESTS = [
    {'name': 'web', 'server': 'hv-host', 'domain': 'web-domain', 'operating_system': 'linux'},
    {'name': 'win-dc', 'server': 'hv-host', 'domain': 'win-dc-domain', 'operating_system': 'windows'},
    # Declared but carries no flags: its rebuild has nothing to plant
    {'name': 'spare', 'server': 'hv-host', 'domain': 'spare-domain', 'operating_system': 'linux'},
]
EVENT = {
    'id': CTF_ID, 'unit_id': 'unitaaaaaa', 'instructor_id': ['gm@example.edu'],
    'spec': {'name': 'Spring CTF', 'flags': FLAGS, 'nested_guests': GUESTS, 'scoring': {'flag_prefix': 'agoge'}},
    'seed_version': 1, 'creation_timestamp': 1.0, 'state': 4, 'state_timestamp': '2026-10-16T00:00:00+00:00',
}
ALL_IDS = [flag['id'] for flag in FLAGS]


def _board(board_id, workout_id):
    return CtfBoardModel(
        id=board_id, workout_id=workout_id, ctf_id=CTF_ID, team_name=workout_id,
        flags=[{'flag_id': fid, 'digest': '0' * 64, 'plant_status': 'planted', 'planted_at': 5.0} for fid in ALL_IDS],
    ).model_dump()


def _value(flag_id):
    return derive_flag_value(SEED, WORKOUT_A, flag_id, 1, 'agoge')


class FakeDb:
    """Records every get and every transactional board write, so SC-9 can check nothing names board B."""
    def __init__(self):
        self.docs = {
            (DbCollections.CTF, CTF_ID): EVENT,
            (DbCollections.CTF_BOARD, BOARD_A): _board(BOARD_A, WORKOUT_A),
            (DbCollections.CTF_BOARD, BOARD_B): _board(BOARD_B, WORKOUT_B),
        }
        self.gets = []
        self.writes = []      # (collection, doc id, update)
        self.db = MagicMock()
        self.db.collection.side_effect = lambda name: SimpleNamespace(
            document=lambda doc_id: SimpleNamespace(collection=name, id=doc_id, get=self._snapshot(name, doc_id))
        )

    def get(self, collection, doc_id):
        self.gets.append((collection, doc_id))
        return self.docs.get((collection, doc_id)) or {}

    def _snapshot(self, collection, doc_id):
        def get(transaction=None):
            data = next((v for (c, d), v in self.docs.items() if c.value == collection and d == doc_id), None)
            return SimpleNamespace(exists=data is not None,
                                   to_dict=lambda: {**data, 'flags': [dict(f) for f in data['flags']]})
        return get

    def transaction(self, operation):
        db = self

        class Transaction:
            def update(self, ref, update):
                db.writes.append((ref.collection, ref.id, update))
                key = next(k for k in db.docs if k[0].value == ref.collection and k[1] == ref.id)
                db.docs[key] = {**db.docs[key], **update}
        return operation(Transaction())

    def flag(self, flag_id, board_id=BOARD_A):
        return next(f for f in self.docs[(DbCollections.CTF_BOARD, board_id)]['flags'] if f['flag_id'] == flag_id)


class FakeCompute:
    """
    Answers like a nested host whose watcher ran the latest payload: plant-ack, plant-result, and one
    plant-result-<guest> per relayed guest. `results` overrides a key with an error message. Any call other than
    get / set_metadata / get_guest_attributes (reset, stop, start, ...) fails the test.
    """
    def __init__(self, ack=True, results=None):
        self.ack, self.results = ack, results or {}
        self.calls = []
        self.payloads = []

    def get(self, name):
        self.calls.append(('get', name))
        return SimpleNamespace(status='RUNNING')

    def set_metadata(self, name, items=None, remove=None):
        self.calls.append(('set_metadata', name))
        if items:
            self.payloads.append(items[PLANT_METADATA_KEY])

    def get_guest_attributes(self, name, query_path=None):
        self.calls.append(('get_guest_attributes', name))
        if not self.ack:
            return {}
        payload = self.payloads[-1]
        nonce = re.search(r'^agoge_ctf_nonce=(\S+)$', payload, re.M).group(1)
        keys = ['plant-result'] + [f"plant-result-{g}" for g in
                                   re.findall(r"^agoge_ctf_(?:relay|rebuild)_qemu '?([a-z0-9-]+)", payload, re.M)]
        attributes = {'plant-ack': nonce}
        for key in keys:
            error = self.results.get(key)
            attributes[key] = f"error:{nonce}:{error}" if error else f"ok:{nonce}"
        return attributes

    def __getattr__(self, name):
        raise AssertionError(f"unexpected compute call: {name}")


@pytest.fixture(autouse=True)
def offline():
    clock = {'now': 0.0}

    def sleep(seconds):
        clock['now'] += seconds

    with (
        patch.object(host_reset_module, "Logger"),
        patch.object(flag_planter_module, "Logger"),
        patch.object(flag_planter_module, "time", SimpleNamespace(sleep=sleep, monotonic=lambda: clock['now'],
                                                                  time=lambda: 9.0)),
        patch.object(FlagPlanter, 'env', new_callable=PropertyMock, return_value=SimpleNamespace(ctf_flag_seed=SEED)),
    ):
        yield


@pytest.fixture
def factory():
    # Every compute manager path (stop, start, nuke) goes through ComputeManagerFactory
    with patch.object(host_reset_module, "ComputeManagerFactory") as factory_cls:
        yield factory_cls


def _compute(**kwargs):
    compute = FakeCompute(**kwargs)
    patcher = patch.object(FlagPlanter, 'compute_api', new_callable=PropertyMock, return_value=compute)
    patcher.start()
    return compute


@pytest.fixture(autouse=True)
def _stop_patches():
    yield
    patch.stopall()


def _reset(db, mode, guest, server='hv-host'):
    return HostReset(env_dict=ENV, db=db).run(CTF_ID, WORKOUT_A, server, mode, guest=guest)


# ---- no instance call, SC-9 ----

@pytest.mark.parametrize('mode,guest', [
    ('replant', 'web'), ('replant', 'win-dc'), ('restart', 'web'), ('rebuild', 'web'), ('rebuild', 'win-dc'),
    ('rebuild', 'spare'),
])
def test_guest_reset_of_any_mode_touches_no_instance_and_no_other_board(factory, mode, guest):
    db = FakeDb()
    compute = _compute()

    assert _reset(db, mode, guest) == mode

    # FakeCompute raises on reset/stop/start; nuke/stop/start on a manager would need the factory
    factory.create_manager_object.assert_not_called()
    assert {name for _, name in compute.calls} == {HOST}
    assert compute.calls[-1] == ('set_metadata', HOST)    # plant key removed last
    assert all(doc_id == BOARD_A for _, doc_id, _ in db.writes)
    assert all(doc_id != BOARD_B for _, doc_id in db.gets)
    assert (DbCollections.SERVER, HOST) not in db.gets


def test_undeclared_guest_raises_not_found_before_any_compute_call(factory):
    db = FakeDb()
    compute = _compute()
    with pytest.raises(NotFound, match="Guest ghost"):
        _reset(db, 'restart', 'ghost')
    # Declared on hv-host only, so not a guest of db
    with pytest.raises(NotFound):
        _reset(db, 'replant', 'web', server='db')
    assert compute.calls == [] and db.writes == []
    factory.create_manager_object.assert_not_called()


def test_unknown_guest_mode_raises_value_error_before_any_read():
    db = FakeDb()
    with pytest.raises(ValueError, match="Unsupported CTF host reset mode"):
        _reset(db, 'nuke', 'web')
    assert db.gets == []


def test_inactive_board_skips_a_guest_reset():
    db = FakeDb()
    db.docs[(DbCollections.CTF_BOARD, BOARD_A)]['active'] = False
    compute = _compute()
    assert _reset(db, 'rebuild', 'web') is None
    assert compute.calls == [] and db.writes == []


# ---- replant ----

def test_guest_replant_plants_only_that_guests_flags(factory):
    db = FakeDb()
    compute = _compute()

    _reset(db, 'replant', 'web')

    payload, = compute.payloads
    assert re.findall(r"^agoge_ctf_(\w+)_qemu (\S+) ", payload, re.M) == [('relay', 'web')]
    assert _value('host-root') not in payload
    assert db.flag('web-user')['plant_status'] == 'planted' and db.flag('web-user')['planted_at'] == 9.0
    # The parent's and the other guest's flags keep their earlier plant
    assert db.flag('host-root')['planted_at'] == 5.0 and db.flag('dc-file')['planted_at'] == 5.0


# ---- rebuild ----

def test_guest_rebuild_reverts_then_plants_in_one_payload(factory):
    db = FakeDb()
    compute = _compute()

    _reset(db, 'rebuild', 'win-dc')

    payload, = compute.payloads
    assert re.search(r"^agoge_ctf_rebuild_qemu win-dc win-dc-domain ", payload, re.M)
    assert not re.search(r"^agoge_ctf_relay_qemu ", payload, re.M)
    assert db.flag('dc-file')['plant_status'] == 'planted' and db.flag('dc-file')['planted_at'] == 9.0
    assert db.flag('web-user')['planted_at'] == 5.0


def test_guest_rebuild_without_snapshot_fails_that_guests_flags(factory):
    db = FakeDb()
    _compute(results={'plant-result-web': 'web: no agoge-pristine snapshot'})

    _reset(db, 'rebuild', 'web')

    assert db.flag('web-user')['plant_status'] == 'failed'
    assert db.flag('web-user')['plant_error'] == 'web: no agoge-pristine snapshot'
    assert db.flag('host-root')['plant_status'] == 'planted'


def test_guest_rebuild_without_ack_fails_flags_and_never_resets(factory):
    db = FakeDb()
    compute = _compute(ack=False)

    _reset(db, 'rebuild', 'web')

    assert db.flag('web-user')['plant_error'] == FlagPlanter.MSG_NO_WATCHER
    assert {call for call, _ in compute.calls} == {'get', 'set_metadata', 'get_guest_attributes'}


def test_flagless_guest_rebuild_only_reverts_and_writes_no_flag(factory):
    db = FakeDb()
    compute = _compute()

    _reset(db, 'rebuild', 'spare')

    payload, = compute.payloads
    assert "virsh -q snapshot-revert spare-domain agoge-pristine --running" in payload
    assert 'agoge{' not in payload
    assert db.writes == []


# ---- restart ----

def test_guest_restart_reboots_the_domain_and_leaves_flags_alone(factory):
    db = FakeDb()
    compute = _compute()

    _reset(db, 'restart', 'web')

    payload, = compute.payloads
    assert "virsh -q reboot web-domain" in payload
    assert 'agoge{' not in payload and 'snapshot-revert' not in payload
    assert db.writes == []


@pytest.mark.parametrize('kwargs,message', [
    ({'ack': False}, FlagPlanter.MSG_NO_WATCHER),
    ({'results': {'plant-result': 'web: guest reboot failed'}}, 'web: guest reboot failed'),
])
def test_failed_guest_restart_raises_and_never_resets(factory, kwargs, message):
    db = FakeDb()
    compute = _compute(**kwargs)

    with pytest.raises(RuntimeError, match=re.escape(message)):
        _reset(db, 'restart', 'web')
    assert compute.calls[-1] == ('set_metadata', HOST)
    assert db.writes == []


def test_guest_restart_on_a_stopped_host_fails_without_writing_metadata(factory):
    compute = _compute()
    compute.get = lambda name: SimpleNamespace(status='TERMINATED')
    with pytest.raises(RuntimeError, match=FlagPlanter.MSG_NOT_RUNNING):
        _reset(FakeDb(), 'restart', 'web')
    assert compute.payloads == []


# ---- payload builders ----

def test_revert_needs_a_guest():
    planter = FlagPlanter(EVENT)
    with pytest.raises(ValueError, match="needs a guest"):
        planter.plant(_board(BOARD_A, WORKOUT_A), ['hv-host'], revert=True)
    with pytest.raises(BadRequest, match="needs a guest"):
        planter.build_payload(_board(BOARD_A, WORKOUT_A), 'hv-host', NONCE, SEED, revert=True)


def test_guest_action_rejects_unknown_actions_and_undeclared_guests():
    planter = FlagPlanter(EVENT)
    with pytest.raises(ValueError, match="Unsupported guest action"):
        planter.build_guest_action_payload('hv-host', 'web', 'nuke', NONCE)
    with pytest.raises(BadRequest, match="not declared"):
        planter.build_guest_action_payload('db', 'web', 'restart', NONCE)


# --- run the payloads against fake virsh/curl --------------------------------------------------------------

# Answers argv calls (domstate, snapshot-info, snapshot-revert, reboot) and logs them; agent commands on stdin
# answer guest-ping, and guest-exec runs a Linux guest payload with bash -s, as in test_flag_planter_relay.
FAKE_VIRSH = r'''#!/bin/bash
printf 'virsh-args:%s\n' "$*" >> "$FAKE_LOG"
case "$2" in
  domstate) printf 'running\n\n'; exit 0 ;;
  snapshot-info) [ -z "$FAKE_NO_SNAPSHOT" ]; exit ;;
  snapshot-revert) [ -z "$FAKE_REVERT_FAILS" ]; exit ;;
  reboot) [ -z "$FAKE_REBOOT_FAILS" ]; exit ;;
esac
while IFS= read -r line; do
  case "$line" in
    *guest-ping*) echo '{"return":{}}' ;;
    *guest-exec-status*)
      printf '{"return":{"exitcode":0,"out-data":"%s","exited":true}}\n' "$(cat "$FAKE_DIR/out")" ;;
    *guest-exec*)
      printf 'virsh-exec\n' >> "$FAKE_LOG"
      printf '%s' "$line" | grep -o '"input-data":"[A-Za-z0-9+/=]*' | sed 's/^.*"//' | base64 -d \
        | bash -s | base64 | tr -d '\n' > "$FAKE_DIR/out"
      echo '{"return":{"pid":7}}' ;;
  esac
done
'''
FAKE_TOOLS = {
    'virsh': FAKE_VIRSH,
    'curl': '#!/bin/bash\nwhile [ $# -gt 0 ]; do case "$1" in --data) d="$2"; shift 2 ;; -X|-H) shift 2 ;; '
            '*) u="$1"; shift ;; esac; done\nprintf \'put:%s %s\\n\' "${u##*/guest-attributes/}" "$d" >> "$FAKE_LOG"\n',
    'timeout': '#!/bin/bash\nshift\nexec "$@"\n',
    'sleep': '#!/bin/bash\n',
    'iptables': '#!/bin/bash\n[ "$1" != "-C" ]\n',
}


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    bin_dir = tmp_path / 'bin'
    bin_dir.mkdir()
    for name, body in FAKE_TOOLS.items():
        (bin_dir / name).write_text(body)
        (bin_dir / name).chmod(0o755)
    env_file = tmp_path / 'environment'
    env_file.write_text('LANG=C\n')
    monkeypatch.setattr(flag_planter_module, 'LINUX_ENVIRONMENT_FILE', str(env_file))
    return tmp_path


def _run(payload, sandbox, **env_extra):
    env = {**os.environ, 'PATH': f"{sandbox / 'bin'}:{os.environ['PATH']}", 'FAKE_LOG': str(sandbox / 'log'),
           'FAKE_DIR': str(sandbox), **env_extra}
    result = subprocess.run(['bash', '-s'], input=payload, capture_output=True, text=True, env=env, timeout=60)
    log = (sandbox / 'log').read_text().splitlines() if (sandbox / 'log').exists() else []
    puts = [line[len('put:'):].split(' ', 1) for line in log if line.startswith('put:')]
    return result, log, puts


def _sandbox_event(root):
    # The Linux guest's flag is written under the sandbox, since the fake agent runs the guest payload here
    if not re.fullmatch(LOCATION_PATH_PATTERNS[('file', 'linux')], f"{root}/user.txt"):
        pytest.skip(f"tmp_path {root} does not match the Linux file path format")
    flags = [dict(f, path=f"{root}/user.txt") if f['id'] == 'web-user' else f for f in FLAGS]
    return {**EVENT, 'spec': {**EVENT['spec'], 'flags': flags}}


@needs_bash
@pytest.mark.parametrize('action,env_extra,expected,argv', [
    ('restart', {}, f"ok:{NONCE}", ['-q reboot web-domain']),
    ('restart', {'FAKE_REBOOT_FAILS': '1'}, f"error:{NONCE}:web: guest reboot failed", ['-q reboot web-domain']),
    ('revert', {}, f"ok:{NONCE}",
     ['-q snapshot-info web-domain agoge-pristine', '-q snapshot-revert web-domain agoge-pristine --running']),
    ('revert', {'FAKE_NO_SNAPSHOT': '1'}, f"error:{NONCE}:web: no agoge-pristine snapshot",
     ['-q snapshot-info web-domain agoge-pristine']),
    ('revert', {'FAKE_REVERT_FAILS': '1'}, f"error:{NONCE}:web: snapshot revert failed",
     ['-q snapshot-info web-domain agoge-pristine', '-q snapshot-revert web-domain agoge-pristine --running']),
])
def test_guest_action_payload_reports_through_plant_result(sandbox, action, env_extra, expected, argv):
    payload = FlagPlanter(EVENT).build_guest_action_payload('hv-host', 'web', action, NONCE)
    result, log, puts = _run(payload, sandbox, **env_extra)

    assert result.returncode == 0 and result.stdout == '' and result.stderr == ''
    assert puts == [['agoge-ctf/plant-ack', NONCE], ['agoge-ctf/plant-result', expected]]
    assert [line[len('virsh-args:'):] for line in log if line.startswith('virsh-args:')] == argv


@needs_bash
def test_guest_rebuild_relay_reverts_before_planting(sandbox):
    planter = FlagPlanter(_sandbox_event(sandbox))
    payload = planter.build_payload(_board(BOARD_A, WORKOUT_A), 'hv-host', NONCE, SEED, guest='web', revert=True)
    _, log, puts = _run(payload, sandbox)

    assert puts == [['agoge-ctf/plant-ack', NONCE], ['agoge-ctf/plant-result-web', f"ok:{NONCE}"],
                    ['agoge-ctf/plant-result', f"ok:{NONCE}"]]
    revert = log.index('virsh-args:-q snapshot-revert web-domain agoge-pristine --running')
    assert revert < log.index('virsh-exec')
    assert (sandbox / 'user.txt').read_text() == _value('web-user')


@needs_bash
@pytest.mark.parametrize('env_extra,message', [
    ({'FAKE_NO_SNAPSHOT': '1'}, 'web: no agoge-pristine snapshot'),
    ({'FAKE_REVERT_FAILS': '1'}, 'web: snapshot revert failed'),
])
def test_guest_rebuild_relay_without_a_revert_plants_nothing(sandbox, env_extra, message):
    planter = FlagPlanter(_sandbox_event(sandbox))
    payload = planter.build_payload(_board(BOARD_A, WORKOUT_A), 'hv-host', NONCE, SEED, guest='web', revert=True)
    _, log, puts = _run(payload, sandbox, **env_extra)

    assert dict(map(tuple, puts))['agoge-ctf/plant-result-web'] == f"error:{NONCE}:{message}"
    assert 'virsh-exec' not in log
    assert not (sandbox / 'user.txt').exists()
