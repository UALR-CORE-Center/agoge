"""FlagPlanter.build_payload for a nested host (N7): ack, parent flags, parallel qemu-agent relays, plant-result last."""
import base64
import os
import re
import shutil
import subprocess

import pytest

from cloud_fn_utilities.course_objects.ctf import flag_planter as flag_planter_module
from common.exceptions import BadRequest
from common.utilities.ctf_flags import derive_flag_value
from common.utilities.ctf_plant_contract import LOCATION_PATH_PATTERNS

FlagPlanter = flag_planter_module.FlagPlanter

SEED = "f" * 64
NONCE = "0d4c1a52-6a8e-4c39-9d43-2b8f5f2a7e11"
WORKOUT_ID = "abcdefghij"
needs_bash = pytest.mark.skipif(shutil.which('bash') is None, reason="bash is not installed")


def _flag(flag_id, server, slot, location_type, path, operating_system='linux', guest=None):
    flag = {'id': flag_id, 'server': server, 'slot': slot, 'location_type': location_type, 'path': path,
            'operating_system': operating_system, 'points': 100}
    if guest:
        flag['guest'] = guest
    return flag


def _guest(name, server, operating_system, driver='qemu-agent'):
    return {'name': name, 'server': server, 'domain': f"{name}-domain", 'operating_system': operating_system,
            'driver': driver}


def _event(flags, guests):
    return {
        'id': 'ctfeventaa', 'unit_id': 'unitaaaaaa', 'instructor_id': ['gm@example.edu'],
        'spec': {'name': 'Spring CTF', 'flags': flags, 'nested_guests': guests},
        'seed_version': 1, 'creation_timestamp': 1.0, 'state': 0,
        'state_timestamp': '2026-10-16T00:00:00+00:00',
    }


def _board(flag_ids, workout_id=WORKOUT_ID):
    return {'id': f"ctfeventaa-{workout_id}", 'workout_id': workout_id, 'ctf_id': 'ctfeventaa',
            'team_name': 'Team 1', 'flags': [{'flag_id': flag_id, 'digest': '0' * 64} for flag_id in flag_ids]}


def _value(flag_id, workout_id=WORKOUT_ID):
    return derive_flag_value(SEED, workout_id, flag_id, 1, 'agoge')


GUESTS = [
    _guest('web', 'hv-host', 'linux'),
    _guest('win-dc', 'hv-host', 'windows'),
    # Not relayed by this builder: the offline driver is a separate section (N12)
    _guest('vault', 'hv-host', 'linux', driver='offline'),
    _guest('web', 'hv-two', 'linux'),
]


def _flags(root='/root'):
    return [
        _flag('host-root', 'hv-host', 1, 'file', f"{root}/host.txt"),
        _flag('web-user', 'hv-host', 1, 'file', f"{root}/home/student/user.txt", guest='web'),
        _flag('web-env', 'hv-host', 2, 'env', 'AGOGE_WEB_FLAG', guest='web'),
        _flag('dc-reg', 'hv-host', 1, 'registry', 'HKLM\\SOFTWARE\\Corp:Secret', 'windows', guest='win-dc'),
        _flag('vault-env', 'hv-host', 1, 'env', 'AGOGE_VAULT_FLAG', guest='vault'),
        _flag('two-web', 'hv-two', 1, 'file', f"{root}/two.txt", guest='web'),
        _flag('plain', 'plain-box', 1, 'file', f"{root}/plain.txt"),
    ]


ALL_IDS = [flag['id'] for flag in _flags()]


@pytest.fixture
def planter():
    return FlagPlanter(_event(_flags(), GUESTS))


def _payload(planter, flag_ids=ALL_IDS, server='hv-host'):
    return planter.build_payload(_board(flag_ids), server, NONCE, SEED)


def _relayed(payload):
    """Decoded guest-exec input-data of every relay section, by domain (the command is shell-quoted)."""
    relayed = {}
    for domain, data in re.findall(r'qemu-agent-command ([A-Za-z0-9_.-]+) \S*?"input-data":"([A-Za-z0-9+/=]+)"', payload):
        relayed[domain] = base64.b64decode(data).decode('utf-8')
    return relayed


# --- shape -------------------------------------------------------------------------------------------------

@needs_bash
def test_nested_host_payload_passes_bash_n(planter):
    result = subprocess.run(['bash', '-n'], input=_payload(planter), capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr


def test_parent_body_holds_parent_flags_and_relays_each_qemu_agent_guest(planter):
    payload = _payload(planter)
    assert _value('host-root') in payload
    # Guest values travel only inside their guest's base64 input-data, never as parent placements
    for flag_id in ('web-user', 'web-env', 'dc-reg', 'vault-env', 'two-web', 'plain'):
        assert _value(flag_id) not in payload, flag_id
    relayed = _relayed(payload)
    assert set(relayed) == {'web-domain', 'win-dc-domain'}
    assert relayed['web-domain'] == planter.build_guest_payload(_board(ALL_IDS), 'hv-host', 'web', NONCE, SEED)
    assert relayed['win-dc-domain'] == planter.build_guest_payload(_board(ALL_IDS), 'hv-host', 'win-dc', NONCE, SEED)


def test_relay_sections_run_in_parallel_and_finish_before_plant_result(planter):
    lines = _payload(planter).splitlines()
    launches = [i for i, line in enumerate(lines) if line.startswith('agoge_ctf_relay_qemu ')]
    assert len(launches) == 2 and all(lines[i].endswith(' &') for i in launches)
    wait = lines.index('wait')
    result_write = next(i for i, line in enumerate(lines) if line.startswith('curl ') and line.endswith('plant-result'))
    assert max(launches) < wait < result_write
    # plant-result is the payload's last write
    assert result_write == max(i for i, line in enumerate(lines) if line.startswith('curl '))


def test_ack_is_the_first_action_after_the_redirect(planter):
    commands = [line for line in _payload(planter).splitlines() if line and not line.startswith('#')]
    assert commands[0] == 'exec >/dev/null 2>&1'
    assert commands[1].startswith('curl ') and commands[1].endswith('guest-attributes/agoge-ctf/plant-ack')
    assert f"--data {NONCE}" in commands[1]


def test_windows_guest_runs_the_fixed_bootstrap_with_encoded_command(planter):
    payload = _payload(planter)
    encoded = re.search(r'"-EncodedCommand","([A-Za-z0-9+/=]+)"', payload).group(1)
    assert base64.b64decode(encoded).decode('utf-16-le') == flag_planter_module._WINDOWS_GUEST_BOOTSTRAP
    assert '"path":"powershell.exe"' in payload and '"path":"/bin/bash","arg":["-s"]' in payload


@pytest.mark.skipif(shutil.which('pwsh') is None, reason="pwsh is not installed")
def test_windows_guest_bootstrap_parses_as_powershell(tmp_path):
    script = tmp_path / 'bootstrap.ps1'
    script.write_text(flag_planter_module._WINDOWS_GUEST_BOOTSTRAP)
    check = (f"$e = $null; [System.Management.Automation.Language.Parser]::ParseFile('{script}', [ref]$null, [ref]$e)"
             " | Out-Null; if ($e.Count) { $e | ForEach-Object { $_.Message }; exit 1 }")
    result = subprocess.run(['pwsh', '-NoProfile', '-NonInteractive', '-Command', check],
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout


def test_board_with_only_guest_flags_still_builds(planter):
    payload = _payload(planter, ['web-user'])
    assert set(_relayed(payload)) == {'web-domain'}
    assert _value('host-root') not in payload
    # No parent placement call, only the helper definitions
    assert not [line for line in payload.splitlines() if re.match(r'agoge_ctf_plant_(file|env) ', line)]


def test_board_with_no_flags_on_the_nested_host_raises(planter):
    with pytest.raises(BadRequest):
        _payload(planter, ['plain', 'two-web'])


def test_non_linux_parent_flag_raises():
    flags = [_flag('host-reg', 'hv-host', 1, 'registry', 'HKLM\\SOFTWARE\\Corp:Secret', 'windows')]
    with pytest.raises(BadRequest, match='must be linux'):
        FlagPlanter(_event(flags, GUESTS)).build_payload(_board(['host-reg']), 'hv-host', NONCE, SEED)


def test_server_without_nested_guests_is_unchanged(planter):
    plain = FlagPlanter(_event(_flags(), [])).build_payload(_board(ALL_IDS), 'plain-box', NONCE, SEED)
    assert _payload(planter, server='plain-box') == plain
    assert 'plant-ack' not in plain and 'virsh' not in plain


def test_payload_over_the_metadata_limit_raises(planter, monkeypatch):
    size = len(_payload(planter).encode('utf-8'))
    monkeypatch.setattr(flag_planter_module, 'PLANT_PAYLOAD_MAX_BYTES', size - 1)
    with pytest.raises(BadRequest, match='Plant payload exceeds the metadata size limit'):
        _payload(planter)
    monkeypatch.setattr(flag_planter_module, 'PLANT_PAYLOAD_MAX_BYTES', size)
    _payload(planter)


# --- run the parent payload against fake virsh/curl ---------------------------------------------------------

# Logs its argv, answers domstate from argv, and reads agent commands from stdin like `virsh -q` in shell
# mode, echoing each command line after a prompt. guest-exec runs a Linux guest payload with bash -s and
# keeps its stdout for guest-exec-status; a Windows guest answers $FAKE_WINDOWS_OUT. Agent JSON is only
# recognised inside single quotes, because virsh's tokenizer strips the double quotes of an unquoted one.
FAKE_VIRSH = r'''#!/bin/bash
printf 'virsh-args:%s\n' "$*" >> "$FAKE_LOG"
if [ "$2" = domstate ]; then
  case " $FAKE_STOPPED " in *" $3 "*) printf 'shut off\n\n' ;; *) printf 'running\n\n' ;; esac
  exit 0
fi
while IFS= read -r line; do
  printf 'virsh # %s\n' "$line"
  domain="$(printf '%s' "$line" | awk '{print $2}')"
  case "$line" in
    *" '{\"execute\":\"guest-ping\"}' "*)
      if [ -n "$FAKE_NO_AGENT" ]; then echo 'error: Guest agent is not responding' >&2; else echo '{"return":{}}'; fi ;;
    *" '{\"execute\":\"guest-exec-status\",\"arguments\":{\"pid\":"[0-9]*"}}' "*)
      pid="$(printf '%s' "$line" | grep -o '"pid":[0-9]*' | tr -dc 0-9)"
      printf '{"return":{"exitcode":0,"out-data":"%s","exited":true}}\n' "$(cat "$FAKE_DIR/out-$pid")" ;;
    *" '{\"execute\":\"guest-exec\","*"}}' "*)
      printf 'virsh-exec:%s\n' "$domain" >> "$FAKE_LOG"
      printf '%s' "$line" | grep -o '"input-data":"[A-Za-z0-9+/=]*' | sed 's/^.*"//' | base64 -d > "$FAKE_DIR/in-$domain"
      case "$line" in
        *powershell.exe*) printf "$FAKE_WINDOWS_OUT" | base64 | tr -d '\n' > "$FAKE_DIR/out-$$" ;;
        *) bash -s < "$FAKE_DIR/in-$domain" | base64 | tr -d '\n' > "$FAKE_DIR/out-$$" ;;
      esac
      printf '{"return":{"pid":%s}}\n' "$$" ;;
  esac
done
'''
FAKE_CURL = r'''#!/bin/bash
printf 'curl-args:%s\n' "$*" >> "$FAKE_LOG"
data=''; url=''
while [ $# -gt 0 ]; do
  case "$1" in --data) data="$2"; shift 2 ;; -X|-H) shift 2 ;; *) url="$1"; shift ;; esac
done
printf 'put:%s %s\n' "${url##*/guest-attributes/}" "$data" >> "$FAKE_LOG"
'''
FAKE_TOOLS = {
    'virsh': FAKE_VIRSH,
    'curl': FAKE_CURL,
    'timeout': '#!/bin/bash\nprintf \'timeout-args:%s\\n\' "$*" >> "$FAKE_LOG"\nshift\nexec "$@"\n',
    'sleep': '#!/bin/bash\nprintf \'sleep-args:%s\\n\' "$*" >> "$FAKE_LOG"\n',
    'iptables': '#!/bin/bash\n[ "$1" != "-C" ]\n',
}


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    root = tmp_path / 'host'
    root.mkdir()
    if not re.fullmatch(LOCATION_PATH_PATTERNS[('file', 'linux')], str(root)):
        pytest.skip(f"tmp_path {root} does not match the Linux file path format")
    bin_dir = tmp_path / 'bin'
    bin_dir.mkdir()
    for name, body in FAKE_TOOLS.items():
        (bin_dir / name).write_text(body)
        (bin_dir / name).chmod(0o755)
    env_file = tmp_path / 'environment'
    env_file.write_text('LANG=C\n')
    monkeypatch.setattr(flag_planter_module, 'LINUX_ENVIRONMENT_FILE', str(env_file))
    fake_dir = tmp_path / 'fake'
    fake_dir.mkdir()
    return {'root': root, 'bin': bin_dir, 'env_file': env_file, 'dir': fake_dir, 'log': tmp_path / 'log'}


def _run(payload, sandbox, **env_extra):
    env = {**os.environ, 'PATH': f"{sandbox['bin']}:{os.environ['PATH']}", 'FAKE_LOG': str(sandbox['log']),
           'FAKE_DIR': str(sandbox['dir']), 'FAKE_WINDOWS_OUT': f"ok:{NONCE}\\r\\n", **env_extra}
    result = subprocess.run(['bash', '-s'], input=payload, capture_output=True, text=True, env=env, timeout=60)
    log = sandbox['log'].read_text().splitlines() if sandbox['log'].exists() else []
    return result, log


def _puts(log):
    return [line[len('put:'):].split(' ', 1) for line in log if line.startswith('put:')]


def _sandbox_planter(sandbox):
    return FlagPlanter(_event(_flags(str(sandbox['root'])), GUESTS))


@needs_bash
def test_relay_plants_every_guest_and_writes_plant_result_last(sandbox):
    planter = _sandbox_planter(sandbox)
    result, log = _run(_payload(planter), sandbox)

    assert result.returncode == 0
    assert result.stdout == '' and result.stderr == ''
    puts = _puts(log)
    assert puts[0] == ['agoge-ctf/plant-ack', NONCE]
    assert sorted(puts[1:-1]) == [['agoge-ctf/plant-result-web', f"ok:{NONCE}"],
                                  ['agoge-ctf/plant-result-win-dc', f"ok:{NONCE}"]]
    assert puts[-1] == ['agoge-ctf/plant-result', f"ok:{NONCE}"]
    # The parent's own flag and the Linux guest's flags (run here by the fake guest agent) all landed
    root = sandbox['root']
    assert (root / 'host.txt').read_text() == _value('host-root')
    assert (root / 'home/student/user.txt').read_text() == _value('web-user')
    assert f"AGOGE_WEB_FLAG={_value('web-env')}\n" in sandbox['env_file'].read_text()
    assert sorted(line for line in log if line.startswith('virsh-exec:')) == [
        'virsh-exec:web-domain', 'virsh-exec:win-dc-domain'
    ]
    win = (sandbox['dir'] / 'in-win-dc-domain').read_text()
    assert win == planter.build_guest_payload(_board(ALL_IDS), 'hv-host', 'win-dc', NONCE, SEED)


@needs_bash
def test_virsh_is_only_ever_fed_on_stdin(sandbox):
    planter = _sandbox_planter(sandbox)
    _, log = _run(_payload(planter), sandbox)

    argv_lines = [line for line in log if line.split(':', 1)[0] in ('virsh-args', 'curl-args', 'timeout-args')]
    assert any(line.startswith('virsh-args:') for line in argv_lines)
    assert all('input-data' not in line for line in argv_lines)
    # Agent commands only ever reach a bare `virsh -q`, whose input is stdin
    assert {line for line in argv_lines if line.startswith('virsh-args:')} == {
        'virsh-args:-q', 'virsh-args:-q domstate web-domain', 'virsh-args:-q domstate win-dc-domain'
    }
    for flag_id in ALL_IDS:
        assert all(_value(flag_id) not in line for line in argv_lines), flag_id


@needs_bash
def test_stopped_guest_reports_not_running_and_is_never_started(sandbox):
    _, log = _run(_payload(_sandbox_planter(sandbox)), sandbox, FAKE_STOPPED='web-domain')

    puts = dict(map(tuple, _puts(log)))
    assert puts['agoge-ctf/plant-result-web'] == f"error:{NONCE}:web: guest is not running"
    assert puts['agoge-ctf/plant-result-win-dc'] == f"ok:{NONCE}"
    assert 'virsh-exec:web-domain' not in log
    assert not any(re.search(r'\b(start|create|resume)\b', line) for line in log if line.startswith('virsh-args:'))
    assert _puts(log)[-1] == ['agoge-ctf/plant-result', f"ok:{NONCE}"]


@needs_bash
def test_silent_agent_reports_no_response_when_the_budget_ends(sandbox, monkeypatch):
    monkeypatch.setattr(flag_planter_module, 'RELAY_BUDGET_SECONDS', 0)
    _, log = _run(_payload(_sandbox_planter(sandbox)), sandbox, FAKE_NO_AGENT='1')

    puts = dict(map(tuple, _puts(log)))
    assert puts['agoge-ctf/plant-result-web'] == f"error:{NONCE}:web: guest agent did not respond"
    assert puts['agoge-ctf/plant-result-win-dc'] == f"error:{NONCE}:win-dc: guest agent did not respond"
    assert not any(line.startswith('virsh-exec:') for line in log)


@needs_bash
@pytest.mark.parametrize('out', ['', 'garbage\\n', "ok:someone-else\\r\\n", 'error:\\n'])
def test_out_data_outside_the_result_grammar_is_reported_as_no_result(sandbox, out):
    _, log = _run(_payload(_sandbox_planter(sandbox)), sandbox, FAKE_WINDOWS_OUT=out)

    puts = dict(map(tuple, _puts(log)))
    assert puts['agoge-ctf/plant-result-win-dc'] == f"error:{NONCE}:win-dc: guest payload returned no result"


@needs_bash
def test_guest_error_line_is_passed_through_with_crlf_stripped(sandbox):
    _, log = _run(_payload(_sandbox_planter(sandbox)), sandbox,
                  FAKE_WINDOWS_OUT=f"error:{NONCE}:dc-reg: could not write registry value\\r\\nextra\\r\\n")

    puts = dict(map(tuple, _puts(log)))
    assert puts['agoge-ctf/plant-result-win-dc'] == f"error:{NONCE}:dc-reg: could not write registry value"
