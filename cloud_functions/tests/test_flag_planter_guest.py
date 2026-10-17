"""FlagPlanter.build_guest_payload (N6): the body the parent relays into one nested guest."""
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
PRINT_COMMANDS = re.compile(
    r'\b(echo|cat\s+-|Write-Output|Write-Host|Write-Information|Write-Verbose|Write-Debug|Out-Host|Out-Default)\b'
)
# Anything that would reach a guest attribute; a nested guest has no metadata server
GUEST_ATTRIBUTE_WRITES = re.compile(r'guest-attributes|metadata\.google\.internal|\bcurl\b|Invoke-RestMethod|Invoke-WebRequest')


def _flag(flag_id, server, slot, location_type, path, operating_system='linux', guest=None, **extra):
    flag = {'id': flag_id, 'server': server, 'slot': slot, 'location_type': location_type, 'path': path,
            'operating_system': operating_system, 'points': 100, **extra}
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
    _guest('win-dc', 'hv-host', 'windows'),
    _guest('web', 'hv-host', 'linux'),
    _guest('web', 'hv-two', 'linux'),
]
FLAGS = [
    _flag('host-root', 'hv-host', 1, 'file', '/root/host.txt'),
    _flag('dc-file', 'hv-host', 1, 'file', 'C:\\Users\\Public\\flag.txt', 'windows', guest='win-dc'),
    _flag('dc-reg', 'hv-host', 2, 'registry', 'HKLM\\SOFTWARE\\Corp:Secret', 'windows', guest='win-dc'),
    _flag('dc-env', 'hv-host', 3, 'env', 'AGOGE_DC_FLAG', 'windows', guest='win-dc'),
    _flag('dc-ads', 'hv-host', 4, 'ads', 'C:\\Users\\Public\\notes.txt:hidden', 'windows', guest='win-dc'),
    _flag('web-user', 'hv-host', 1, 'file', '/home/student/user.txt', guest='web'),
    _flag('web-env', 'hv-host', 2, 'env', 'AGOGE_WEB_FLAG', guest='web'),
    # Same guest name on another parent: never part of hv-host's web payload
    _flag('two-web', 'hv-two', 1, 'file', '/root/two.txt', guest='web'),
]
ALL_IDS = [flag['id'] for flag in FLAGS]


@pytest.fixture
def planter():
    return FlagPlanter(_event(FLAGS, GUESTS))


# --- scope ---------------------------------------------------------------------------------------------

@pytest.mark.parametrize('guest,expected', [
    ('web', {'web-user', 'web-env'}),
    ('win-dc', {'dc-file', 'dc-reg', 'dc-env', 'dc-ads'}),
])
def test_guest_payload_holds_only_that_guests_flags(planter, guest, expected):
    payload = planter.build_guest_payload(_board(ALL_IDS), 'hv-host', guest, NONCE, SEED)
    for flag_id in ALL_IDS:
        assert (_value(flag_id) in payload) == (flag_id in expected), flag_id


def test_guest_payload_carries_only_the_boards_flags(planter):
    payload = planter.build_guest_payload(_board(['web-user', 'host-root']), 'hv-host', 'web', NONCE, SEED)
    assert _value('web-user') in payload
    assert _value('web-env') not in payload
    assert _value('host-root') not in payload


def test_guest_payload_uses_the_boards_workout_values(planter):
    payload = planter.build_guest_payload(_board(ALL_IDS, 'zyxwvutsrq'), 'hv-host', 'web', NONCE, SEED)
    assert _value('web-user', 'zyxwvutsrq') in payload
    assert _value('web-user') not in payload


# --- no guest attribute, no printed value --------------------------------------------------------------

@pytest.mark.parametrize('guest', ['web', 'win-dc'])
def test_guest_payload_writes_no_guest_attribute(planter, guest):
    payload = planter.build_guest_payload(_board(ALL_IDS), 'hv-host', guest, NONCE, SEED)
    assert not GUEST_ATTRIBUTE_WRITES.search(payload)


@pytest.mark.parametrize('guest,call_prefix', [('web', 'agoge_ctf_plant_'), ('win-dc', 'Set-AgogeCtf')])
def test_guest_payload_has_no_command_that_prints_a_value(planter, guest, call_prefix):
    payload = planter.build_guest_payload(_board(ALL_IDS), 'hv-host', guest, NONCE, SEED)
    assert not PRINT_COMMANDS.search(payload)
    value_lines = [line for line in payload.splitlines() if 'agoge{' in line]
    assert value_lines
    assert all(line.startswith(call_prefix) for line in value_lines)


def test_linux_guest_payload_saves_stdout_before_silencing_everything(planter):
    lines = planter.build_guest_payload(_board(ALL_IDS), 'hv-host', 'web', NONCE, SEED).splitlines()
    commands = [line for line in lines if line and not line.startswith('#')]
    assert commands[:2] == ['exec 3>&1', 'exec >/dev/null 2>&1']
    # fd 3 is written exactly once, by the result line
    writes = [line for line in lines if '>&3' in line]
    assert writes == ["printf '%s\\n' \"$agoge_ctf_result\" >&3"]


def test_windows_guest_payload_writes_only_the_result_to_saved_stdout(planter):
    payload = planter.build_guest_payload(_board(ALL_IDS), 'hv-host', 'win-dc', NONCE, SEED)
    lines = payload.splitlines()
    save = lines.index('$agogeCtfStdout = [Console]::Out')
    assert lines[save + 1] == '[Console]::SetOut([System.IO.TextWriter]::Null)'
    assert save < next(i for i, line in enumerate(lines) if line.startswith('Set-AgogeCtf'))
    writes = [line for line in lines if '$agogeCtfStdout.Write' in line]
    assert writes == ['$agogeCtfStdout.WriteLine($agogeCtfResult)']


def test_server_payload_is_unchanged_by_the_guest_variant():
    # The parent's own payload still reports through the guest attribute and keeps no saved stdout
    planter = FlagPlanter(_event([_flag('host-root', 'hv-host', 1, 'file', '/root/host.txt')], GUESTS))
    payload = planter.build_payload(_board(['host-root']), 'hv-host', NONCE, SEED)
    assert 'exec 3>&1' not in payload and '>&3' not in payload
    assert 'guest-attributes/agoge-ctf/plant-result' in payload


# --- rejections ----------------------------------------------------------------------------------------

def test_undeclared_guest_raises_bad_request(planter):
    with pytest.raises(BadRequest, match="not declared"):
        planter.build_guest_payload(_board(ALL_IDS), 'hv-host', 'nope', NONCE, SEED)


def test_guest_declared_on_another_server_raises_bad_request(planter):
    with pytest.raises(BadRequest, match="not declared"):
        planter.build_guest_payload(_board(ALL_IDS), 'hv-two', 'win-dc', NONCE, SEED)


def test_guest_with_no_board_flags_raises_bad_request(planter):
    with pytest.raises(BadRequest, match="no flags on guest"):
        planter.build_guest_payload(_board(['host-root', 'web-user']), 'hv-host', 'win-dc', NONCE, SEED)


def test_flag_os_differing_from_guest_raises_bad_request():
    # The validator rejects this spec; the builder refuses it too rather than emit the wrong script
    planter = FlagPlanter(_event(
        [_flag('web-user', 'hv-host', 1, 'file', '/home/student/user.txt', guest='win-dc')], GUESTS
    ))
    with pytest.raises(BadRequest, match="web-user"):
        planter.build_guest_payload(_board(['web-user']), 'hv-host', 'win-dc', NONCE, SEED)


@pytest.mark.parametrize('nonce', ['', 'bad nonce', "x'; rm -rf /", 'a' * 65])
def test_unsafe_nonce_raises_bad_request(planter, nonce):
    with pytest.raises(BadRequest):
        planter.build_guest_payload(_board(ALL_IDS), 'hv-host', 'web', nonce, SEED)


@pytest.mark.parametrize('seed', ['', None])
def test_missing_seed_raises(planter, seed):
    with pytest.raises(ValueError):
        planter.build_guest_payload(_board(ALL_IDS), 'hv-host', 'web', NONCE, seed)


def test_bad_path_raises_bad_request():
    planter = FlagPlanter(_event([_flag('web-user', 'hv-host', 1, 'file', 'relative/path', guest='web')], GUESTS))
    with pytest.raises(BadRequest, match="web-user"):
        planter.build_guest_payload(_board(['web-user']), 'hv-host', 'web', NONCE, SEED)


# --- syntax --------------------------------------------------------------------------------------------

@pytest.mark.skipif(shutil.which('bash') is None, reason="bash is not installed")
def test_linux_guest_payload_passes_bash_n(planter):
    payload = planter.build_guest_payload(_board(ALL_IDS), 'hv-host', 'web', NONCE, SEED)
    result = subprocess.run(['bash', '-n'], input=payload, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr


@pytest.mark.skipif(shutil.which('pwsh') is None, reason="PowerShell is not installed")
def test_windows_guest_payload_parses_as_powershell(planter, tmp_path):
    script = tmp_path / 'payload.ps1'
    script.write_text(planter.build_guest_payload(_board(ALL_IDS), 'hv-host', 'win-dc', NONCE, SEED))
    check = (
        "$errors = $null; "
        f"[System.Management.Automation.Language.Parser]::ParseFile('{script}', [ref]$null, [ref]$errors) | Out-Null; "
        "$errors.Count"
    )
    result = subprocess.run(['pwsh', '-NoProfile', '-NonInteractive', '-Command', check],
                            capture_output=True, text=True, timeout=60)
    assert result.stdout.strip() == '0', result.stdout + result.stderr


# Off Windows the registry and ADS writes fail, which exercises the error line; on Windows it would write HKLM
@pytest.mark.skipif(shutil.which('pwsh') is None or os.name == 'nt', reason="needs pwsh on a non-Windows host")
def test_windows_guest_payload_prints_exactly_one_result_line(planter, tmp_path):
    script = tmp_path / 'payload.ps1'
    script.write_text(planter.build_guest_payload(_board(['dc-reg', 'dc-ads']), 'hv-host', 'win-dc', NONCE, SEED))
    result = subprocess.run(['pwsh', '-NoProfile', '-NonInteractive', '-File', str(script)],
                            capture_output=True, text=True, timeout=60, cwd=tmp_path)
    assert result.stdout.count('\n') == 1
    assert result.stdout.startswith(f"error:{NONCE}:dc-reg: ")
    assert result.stderr == ''
    assert _value('dc-reg') not in result.stdout and _value('dc-ads') not in result.stdout


# --- the Linux guest payload, run the way the relay runs it (bash -s, payload on stdin) ----------------

@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    root = tmp_path / 'guest'
    root.mkdir()
    if not re.fullmatch(LOCATION_PATH_PATTERNS[('file', 'linux')], str(root)):
        pytest.skip(f"tmp_path {root} does not match the Linux file path format")
    bin_dir = tmp_path / 'bin'
    bin_dir.mkdir()
    # Noisy fake iptables: proves the payload's own stdout/stderr stay silent whatever its tools print
    tool = bin_dir / 'iptables'
    tool.write_text('#!/bin/bash\necho iptables-noise\necho iptables-err >&2\n[ "$1" != "-C" ]\n')
    tool.chmod(0o755)
    env_file = tmp_path / 'environment'
    env_file.write_text('LANG=C\n')
    monkeypatch.setattr(flag_planter_module, 'LINUX_ENVIRONMENT_FILE', str(env_file))
    return {'root': root, 'bin': bin_dir, 'env_file': env_file}


def _run_guest(payload, sandbox):
    env = {**os.environ, 'PATH': f"{sandbox['bin']}:{os.environ['PATH']}"}
    return subprocess.run(['bash', '-s'], input=payload, capture_output=True, text=True, env=env, timeout=30)


def _guest_planter(root, extra_flags=()):
    return FlagPlanter(_event([
        _flag('web-user', 'hv-host', 1, 'file', f"{root}/home/student/user.txt", guest='web'),
        _flag('web-env', 'hv-host', 2, 'env', 'AGOGE_WEB_FLAG', guest='web'),
        *extra_flags,
    ], GUESTS))


@pytest.mark.skipif(shutil.which('bash') is None, reason="bash is not installed")
def test_linux_guest_payload_plants_and_prints_exactly_one_result_line(sandbox):
    root = sandbox['root']
    payload = _guest_planter(root).build_guest_payload(_board(['web-user', 'web-env']), 'hv-host', 'web', NONCE, SEED)
    result = _run_guest(payload, sandbox)

    assert result.returncode == 0
    assert result.stdout == f"ok:{NONCE}\n"
    assert result.stderr == ''
    assert (root / 'home/student/user.txt').read_text() == _value('web-user')
    assert sandbox['env_file'].read_text() == f"LANG=C\nAGOGE_WEB_FLAG={_value('web-env')}\n"


@pytest.mark.skipif(shutil.which('bash') is None, reason="bash is not installed")
def test_linux_guest_payload_reports_errors_on_its_one_line_without_values(sandbox):
    root = sandbox['root']
    blocker = root / 'blocked'
    blocker.write_text('a file, not a directory')
    planter = _guest_planter(root, [_flag('web-bad', 'hv-host', 3, 'file', f"{blocker}/flag.txt", guest='web')])
    ids = ['web-user', 'web-env', 'web-bad']
    result = _run_guest(planter.build_guest_payload(_board(ids), 'hv-host', 'web', NONCE, SEED), sandbox)

    assert result.stdout.count('\n') == 1
    assert result.stdout.startswith(f"error:{NONCE}:web-bad: ")
    assert result.stderr == ''
    assert all(_value(flag_id) not in result.stdout for flag_id in ids)
    # The other placements still landed
    assert (root / 'home/student/user.txt').read_text() == _value('web-user')
