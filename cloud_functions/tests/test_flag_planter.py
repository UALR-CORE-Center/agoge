import os
import re
import shutil
import stat
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
# Commands that would put a value on stdout/stderr (startup-script output reaches Cloud Logging)
PRINT_COMMANDS = re.compile(
    r'\b(echo|cat\s+-|Write-Output|Write-Host|Write-Information|Write-Verbose|Write-Debug|Out-Host|Out-Default)\b'
)


def _flag(flag_id, server, slot, location_type, path, operating_system='linux', **extra):
    return {'id': flag_id, 'server': server, 'slot': slot, 'location_type': location_type, 'path': path,
            'operating_system': operating_system, 'points': 100, **extra}


def _event(flags, prefix='agoge', seed_version=1):
    return {
        'id': 'ctfeventaa', 'unit_id': 'unitaaaaaa', 'instructor_id': ['gm@example.edu'],
        'spec': {'name': 'Spring CTF', 'flags': flags, 'scoring': {'flag_prefix': prefix}},
        'seed_version': seed_version, 'creation_timestamp': 1.0, 'state': 0,
        'state_timestamp': '2026-10-16T00:00:00+00:00',
    }


def _board(flag_ids, workout_id=WORKOUT_ID):
    return {'id': f"ctfeventaa-{workout_id}", 'workout_id': workout_id, 'ctf_id': 'ctfeventaa',
            'team_name': 'Team 1', 'flags': [{'flag_id': flag_id, 'digest': '0' * 64} for flag_id in flag_ids]}


def _value(flag_id, workout_id=WORKOUT_ID, prefix='agoge', seed_version=1):
    return derive_flag_value(SEED, workout_id, flag_id, seed_version, prefix)


MIXED_FLAGS = [
    _flag('web-user', 'web', 1, 'file', '/home/student/user.txt'),
    _flag('web-root', 'web', 2, 'env', 'AGOGE_ROOT_FLAG'),
    _flag('db-root', 'db', 1, 'file', '/root/db.txt'),
    _flag('dc-file', 'dc', 1, 'file', 'C:\\Users\\Public\\flag.txt', 'windows'),
    _flag('dc-reg', 'dc', 2, 'registry', 'HKLM\\SOFTWARE\\Agoge Lab:FlagValue', 'windows'),
    _flag('dc-env', 'dc', 3, 'env', 'AGOGE_DC_FLAG', 'windows'),
    _flag('dc-ads', 'dc', 4, 'ads', 'C:\\Users\\Public\\notes.txt:hidden', 'windows'),
]
ALL_IDS = [flag['id'] for flag in MIXED_FLAGS]


@pytest.fixture
def planter():
    return FlagPlanter(_event(MIXED_FLAGS))


# --- scope ---------------------------------------------------------------------------------------------

def test_linux_payload_contains_only_that_servers_flags(planter):
    payload = planter.build_payload(_board(ALL_IDS), 'web', NONCE, SEED)
    assert _value('web-user') in payload
    assert _value('web-root') in payload
    for other in ('db-root', 'dc-file', 'dc-reg', 'dc-env', 'dc-ads'):
        assert _value(other) not in payload
        assert other not in payload


def test_windows_payload_contains_only_that_servers_flags(planter):
    payload = planter.build_payload(_board(ALL_IDS), 'dc', NONCE, SEED)
    for flag_id in ('dc-file', 'dc-reg', 'dc-env', 'dc-ads'):
        assert _value(flag_id) in payload
    for other in ('web-user', 'web-root', 'db-root'):
        assert _value(other) not in payload


def test_payload_carries_only_the_boards_flags_and_that_boards_values(planter):
    payload = planter.build_payload(_board(['web-user'], workout_id='zyxwvutsrq'), 'web', NONCE, SEED)
    assert _value('web-user', workout_id='zyxwvutsrq') in payload
    assert _value('web-user') not in payload  # another team's value for the same flag
    assert 'web-root' not in payload  # on the server, but not on this board


def test_values_use_event_prefix_and_seed_version():
    planter = FlagPlanter(_event([_flag('web-user', 'web', 1, 'env', 'AGOGE_FLAG')], prefix='spring', seed_version=3))
    payload = planter.build_payload(_board(['web-user']), 'web', NONCE, SEED)
    assert _value('web-user', prefix='spring', seed_version=3) in payload
    assert _value('web-user') not in payload


def test_decoy_flags_are_planted():
    flags = [_flag('web-user', 'web', 1, 'env', 'AGOGE_FLAG'),
             _flag('web-decoy', 'web', 2, 'env', 'AGOGE_DECOY', decoy=True, points=-50)]
    payload = FlagPlanter(_event(flags)).build_payload(_board(['web-user', 'web-decoy']), 'web', NONCE, SEED)
    assert _value('web-decoy') in payload


@pytest.mark.parametrize('server', ['web', 'dc'])
def test_payload_contains_the_nonce_in_its_result(planter, server):
    payload = planter.build_payload(_board(ALL_IDS), server, NONCE, SEED)
    assert NONCE in payload
    assert 'agoge-ctf/plant-result' in payload
    assert 'guest-attributes' in payload


def test_accepts_models_as_well_as_dicts():
    from common.models.agoge import CtfBoardModel, CtfEventModel
    planter = FlagPlanter(CtfEventModel(**_event(MIXED_FLAGS)))
    payload = planter.build_payload(CtfBoardModel(**_board(ALL_IDS)), 'web', NONCE, SEED)
    assert _value('web-user') in payload


# --- never prints ---------------------------------------------------------------------------------------

@pytest.mark.parametrize('server,call_prefix', [('web', 'agoge_ctf_plant_'), ('dc', 'Set-AgogeCtf')])
def test_payload_has_no_command_that_prints_a_value(planter, server, call_prefix):
    payload = planter.build_payload(_board(ALL_IDS), server, NONCE, SEED)
    assert not PRINT_COMMANDS.search(payload)
    # A value only ever appears as an argument to a planting function, never in a free-standing command
    value_lines = [line for line in payload.splitlines() if 'agoge{' in line]
    assert value_lines
    assert all(line.startswith(call_prefix) for line in value_lines)


def test_linux_payload_discards_all_output_before_doing_anything(planter):
    lines = planter.build_payload(_board(ALL_IDS), 'web', NONCE, SEED).splitlines()
    assert lines[0] == '#!/bin/bash'
    first_command = next(line for line in lines[1:] if line and not line.startswith('#'))
    assert first_command == 'exec >/dev/null 2>&1'


# --- re-checks the Flag Location Formats ----------------------------------------------------------------

@pytest.mark.parametrize('flag', [
    _flag('web-user', 'web', 1, 'file', "/tmp/x'; rm -rf / #"),
    _flag('web-user', 'web', 1, 'file', '/tmp/flag.txt\n'),
    _flag('web-user', 'web', 1, 'file', 'relative/flag.txt'),
    _flag('web-user', 'web', 1, 'env', 'lower_case'),
    _flag('web-user', 'web', 1, 'registry', 'HKLM\\SOFTWARE\\Agoge:Flag'),  # registry is Windows-only
    _flag('web-user', 'web', 1, 'file', 'C:\\Users\\$(whoami)\\flag.txt', 'windows'),
    _flag('web-user', 'web', 1, 'registry', 'HKCU\\SOFTWARE\\Agoge:Flag', 'windows'),
    _flag('web-user', 'web', 1, 'ads', 'C:\\Users\\Public\\notes.txt', 'windows'),
])
def test_path_not_matching_its_format_raises_bad_request(flag):
    with pytest.raises(BadRequest, match='web-user'):
        FlagPlanter(_event([flag])).build_payload(_board(['web-user']), 'web', NONCE, SEED)


def test_server_with_no_board_flags_raises_bad_request(planter):
    with pytest.raises(BadRequest):
        planter.build_payload(_board(['dc-file']), 'web', NONCE, SEED)
    with pytest.raises(BadRequest):
        planter.build_payload(_board(ALL_IDS), 'no-such-server', NONCE, SEED)


def test_mixed_operating_systems_on_one_server_raise_bad_request():
    flags = [_flag('web-user', 'web', 1, 'env', 'AGOGE_A'), _flag('web-win', 'web', 2, 'env', 'AGOGE_B', 'windows')]
    with pytest.raises(BadRequest):
        FlagPlanter(_event(flags)).build_payload(_board(['web-user', 'web-win']), 'web', NONCE, SEED)


@pytest.mark.parametrize('nonce', ['', "abc'; reboot", 'a' * 65])
def test_unsafe_nonce_raises_bad_request(planter, nonce):
    with pytest.raises(BadRequest):
        planter.build_payload(_board(ALL_IDS), 'web', nonce, SEED)


@pytest.mark.parametrize('seed', [None, ''])
def test_missing_seed_raises(planter, seed):
    with pytest.raises(ValueError):
        planter.build_payload(_board(ALL_IDS), 'web', NONCE, seed)


# --- Windows placements ---------------------------------------------------------------------------------

def test_windows_payload_covers_every_windows_location_row(planter):
    payload = planter.build_payload(_board(ALL_IDS), 'dc', NONCE, SEED)
    assert f"Set-AgogeCtfFile 'C:\\Users\\Public\\flag.txt' '{_value('dc-file')}' 'dc-file'" in payload
    # HKLM\<key>:<name> becomes the HKLM: drive path plus a separate value name
    assert f"Set-AgogeCtfRegistry 'HKLM:\\SOFTWARE\\Agoge Lab' 'FlagValue' '{_value('dc-reg')}' 'dc-reg'" in payload
    assert f"Set-AgogeCtfEnv 'AGOGE_DC_FLAG' '{_value('dc-env')}' 'dc-env'" in payload
    # Only the last colon splits off the stream; the drive colon stays with the file
    assert f"Set-AgogeCtfStream 'C:\\Users\\Public\\notes.txt' 'hidden' '{_value('dc-ads')}' 'dc-ads'" in payload
    assert '[System.EnvironmentVariableTarget]::Machine' in payload
    # New-Item -Force wipes an existing registry key / truncates an existing file, so each is guarded
    assert "if (-not (Test-Path -LiteralPath $Key)) { New-Item -Path $Key -Force | Out-Null }" in payload
    assert "if (-not (Test-Path -LiteralPath $Path)) { New-Item -ItemType File -Force -Path $Path | Out-Null }" in payload


def test_windows_payload_ignores_linux_only_file_mode_and_owner():
    flags = [_flag('dc-file', 'dc', 1, 'file', 'C:\\flag.txt', 'windows', file_mode='0600', file_owner='a:b')]
    payload = FlagPlanter(_event(flags)).build_payload(_board(['dc-file']), 'dc', NONCE, SEED)
    assert '0600' not in payload
    assert 'a:b' not in payload


@pytest.mark.skipif(shutil.which('pwsh') is None, reason="PowerShell is not installed")
def test_windows_payload_parses_as_powershell(planter, tmp_path):
    script = tmp_path / 'payload.ps1'
    script.write_text(planter.build_payload(_board(ALL_IDS), 'dc', NONCE, SEED))
    check = (
        "$errors = $null; "
        f"[System.Management.Automation.Language.Parser]::ParseFile('{script}', [ref]$null, [ref]$errors) | Out-Null; "
        "$errors.Count"
    )
    result = subprocess.run(['pwsh', '-NoProfile', '-NonInteractive', '-Command', check],
                            capture_output=True, text=True, timeout=60)
    assert result.stdout.strip() == '0', result.stdout + result.stderr


# --- the Linux payload, run under bash -----------------------------------------------------------------

def _write_tool(bin_dir, name, body):
    tool = bin_dir / name
    tool.write_text(f"#!/bin/bash\n{body}\n")
    tool.chmod(0o755)


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    """Scratch flag paths plus fake curl/iptables/chown on PATH that record their arguments."""
    root = tmp_path / 'host'
    root.mkdir()
    if not re.fullmatch(LOCATION_PATH_PATTERNS[('file', 'linux')], str(root)):
        pytest.skip(f"tmp_path {root} does not match the Linux file path format")
    bin_dir = tmp_path / 'bin'
    bin_dir.mkdir()
    calls = tmp_path / 'calls'
    _write_tool(bin_dir, 'curl', f'printf "%s\\n" "$*" >> {calls}/curl')
    _write_tool(bin_dir, 'chown', f'printf "%s\\n" "$*" >> {calls}/chown')
    # -C (check) says the rule is absent, so the payload inserts it
    _write_tool(bin_dir, 'iptables', f'printf "%s\\n" "$*" >> {calls}/iptables; [ "$1" != "-C" ]')
    calls.mkdir()
    env_file = tmp_path / 'environment'
    env_file.write_text('PATH="/usr/local/bin:/usr/bin"\nAGOGE_ROOT_FLAG=stale\nLANG=C\n')
    monkeypatch.setattr(flag_planter_module, 'LINUX_ENVIRONMENT_FILE', str(env_file))
    return {'root': root, 'bin': bin_dir, 'calls': calls, 'env_file': env_file}


def _run(payload, sandbox):
    env = {**os.environ, 'PATH': f"{sandbox['bin']}:{os.environ['PATH']}"}
    return subprocess.run(['bash', '-c', payload], capture_output=True, text=True, env=env, timeout=30)


def _linux_planter(root):
    return FlagPlanter(_event([
        _flag('web-user', 'web', 1, 'file', f"{root}/home/student/user.txt", file_mode='0640',
              file_owner='student:student'),
        _flag('web-root', 'web', 2, 'file', f"{root}/root/root.txt"),
        _flag('web-env', 'web', 3, 'env', 'AGOGE_ROOT_FLAG'),
    ]))


BOARD_IDS = ['web-user', 'web-root', 'web-env']


@pytest.mark.skipif(shutil.which('bash') is None, reason="bash is not installed")
def test_linux_payload_plants_every_linux_row_silently(sandbox):
    root = sandbox['root']
    payload = _linux_planter(root).build_payload(_board(BOARD_IDS), 'web', NONCE, SEED)
    result = _run(payload, sandbox)

    assert result.returncode == 0
    assert result.stdout == '' and result.stderr == ''
    user_file = root / 'home/student/user.txt'
    assert user_file.read_text() == _value('web-user')
    assert stat.S_IMODE(user_file.stat().st_mode) == 0o640
    assert (root / 'root/root.txt').read_text() == _value('web-root')
    assert stat.S_IMODE((root / 'root/root.txt').stat().st_mode) == 0o644  # default without file_mode
    assert (sandbox['calls'] / 'chown').read_text() == f"student:student {user_file}\n"
    # /etc/environment: the existing line is replaced, the others are kept
    assert sandbox['env_file'].read_text() == (
        f'PATH="/usr/local/bin:/usr/bin"\nLANG=C\nAGOGE_ROOT_FLAG={_value("web-env")}\n'
    )
    iptables = (sandbox['calls'] / 'iptables').read_text().splitlines()
    assert '-I OUTPUT -d 169.254.169.254 -m owner ! --uid-owner 0 -j REJECT' in iptables
    assert '-I FORWARD -d 169.254.169.254 -j REJECT' in iptables
    curl = (sandbox['calls'] / 'curl').read_text()
    assert f"--data ok:{NONCE} " in curl
    assert curl.rstrip().endswith('instance/guest-attributes/agoge-ctf/plant-result')


@pytest.mark.skipif(shutil.which('bash') is None, reason="bash is not installed")
def test_linux_payload_is_silent_even_without_its_output_redirect(sandbox):
    # The exec redirect is a safety net; no command in the payload prints in the first place
    payload = _linux_planter(sandbox['root']).build_payload(_board(BOARD_IDS), 'web', NONCE, SEED)
    unguarded = payload.replace('exec >/dev/null 2>&1\n', '', 1)
    assert unguarded != payload
    result = _run(unguarded, sandbox)
    assert result.stdout == '' and result.stderr == ''


@pytest.mark.skipif(shutil.which('bash') is None, reason="bash is not installed")
def test_linux_payload_is_idempotent(sandbox):
    payload = _linux_planter(sandbox['root']).build_payload(_board(BOARD_IDS), 'web', NONCE, SEED)
    _run(payload, sandbox)
    _run(payload, sandbox)
    env_lines = sandbox['env_file'].read_text().splitlines()
    assert env_lines.count(f"AGOGE_ROOT_FLAG={_value('web-env')}") == 1
    assert len(env_lines) == 3
    assert (sandbox['root'] / 'root/root.txt').read_text() == _value('web-root')


@pytest.mark.skipif(shutil.which('bash') is None, reason="bash is not installed")
def test_linux_payload_reports_errors_without_values_and_keeps_planting(sandbox):
    root = sandbox['root']
    (root / 'blocker').write_text('not a directory')
    planter = FlagPlanter(_event([
        _flag('web-user', 'web', 1, 'file', f"{root}/blocker/user.txt"),
        _flag('web-root', 'web', 2, 'file', f"{root}/root.txt"),
    ]))
    payload = planter.build_payload(_board(['web-user', 'web-root']), 'web', NONCE, SEED)
    result = _run(payload, sandbox)

    assert result.stdout == '' and result.stderr == ''
    assert (root / 'root.txt').read_text() == _value('web-root')
    curl = (sandbox['calls'] / 'curl').read_text()
    assert f"--data error:{NONCE}:web-user: could not create directory " in curl
    assert 'agoge{' not in curl


@pytest.mark.skipif(shutil.which('bash') is None, reason="bash is not installed")
def test_linux_payload_failing_iptables_is_not_a_plant_failure(sandbox):
    _write_tool(sandbox['bin'], 'iptables', 'exit 1')
    payload = _linux_planter(sandbox['root']).build_payload(_board(BOARD_IDS), 'web', NONCE, SEED)
    _run(payload, sandbox)
    assert f"--data ok:{NONCE} " in (sandbox['calls'] / 'curl').read_text()


# --- N1: nested guests NAT'd through the host must not reach its metadata server ---------------------

FORWARD_CHECK = 'iptables -C FORWARD -d 169.254.169.254 -j REJECT'
FORWARD_INSERT = 'iptables -I FORWARD -d 169.254.169.254 -j REJECT'


@pytest.mark.parametrize('flags, ids', [
    ([_flag('web-user', 'web', 1, 'file', '/home/student/user.txt')], ['web-user']),
    ([_flag('web-env', 'web', 1, 'env', 'AGOGE_FLAG')], ['web-env']),
    ([_flag('web-env', 'web', 1, 'env', 'AGOGE_FLAG'),
      _flag('web-root', 'web', 2, 'file', '/root/root.txt')], ['web-env', 'web-root']),
])
def test_every_linux_payload_blocks_forwarded_metadata_before_the_first_placement(flags, ids):
    payload = FlagPlanter(_event(flags)).build_payload(_board(ids), 'web', NONCE, SEED)
    # The planting helpers are defined in the prologue; a placement is a call line that starts with one
    first_placement = min(
        payload.index(line) for line in payload.splitlines()
        if line.startswith(('agoge_ctf_plant_file ', 'agoge_ctf_plant_env '))
    )
    check = payload.index(FORWARD_CHECK)
    assert check < payload.index(FORWARD_INSERT, check) < first_placement


@pytest.mark.skipif(shutil.which('bash') is None, reason="bash is not installed")
def test_linux_payload_skips_the_forward_insert_when_the_rule_exists(sandbox):
    # -C succeeds: the rule is already there, so nothing is inserted twice
    _write_tool(sandbox['bin'], 'iptables', f'printf "%s\\n" "$*" >> {sandbox["calls"]}/iptables')
    payload = _linux_planter(sandbox['root']).build_payload(_board(BOARD_IDS), 'web', NONCE, SEED)
    _run(payload, sandbox)
    iptables = (sandbox['calls'] / 'iptables').read_text().splitlines()
    assert '-C FORWARD -d 169.254.169.254 -j REJECT' in iptables
    assert not any(call.startswith('-I ') for call in iptables)


@pytest.mark.skipif(shutil.which('bash') is None, reason="bash is not installed")
def test_linux_payload_reports_ok_when_iptables_is_absent(sandbox, tmp_path):
    # A PATH holding only the tools the payload needs, so a real /usr/sbin/iptables cannot leak in
    (sandbox['bin'] / 'iptables').unlink()
    for tool in ('mkdir', 'dirname', 'chmod', 'grep', 'mktemp', 'cat', 'rm'):
        found = shutil.which(tool)
        if found is None:
            pytest.skip(f"{tool} is not installed")
        (sandbox['bin'] / tool).symlink_to(found)
    payload = _linux_planter(sandbox['root']).build_payload(_board(BOARD_IDS), 'web', NONCE, SEED)
    result = subprocess.run([shutil.which('bash'), '-c', payload], capture_output=True, text=True,
                            env={**os.environ, 'PATH': str(sandbox['bin'])}, timeout=30)

    assert result.returncode == 0
    assert not (sandbox['calls'] / 'iptables').exists()
    assert (sandbox['root'] / 'root/root.txt').read_text() == _value('web-root')
    assert f"--data ok:{NONCE} " in (sandbox['calls'] / 'curl').read_text()


# --- Windows access and hidden -------------------------------------------------------------------------

def _windows_planter(**options):
    flags = [
        _flag('dc-file', 'dc', 1, 'file', 'C:\\Secrets\\flag.txt', 'windows', **options),
        _flag('dc-ads', 'dc', 2, 'ads', 'C:\\Windows\\Temp\\notes.txt:hidden', 'windows', **options),
    ]
    return FlagPlanter(_event(flags))


def test_windows_payload_sets_access_and_hidden_on_file_and_ads_host():
    payload = _windows_planter(windows_access='user', windows_user='student', hidden=True).build_payload(
        _board(['dc-file', 'dc-ads']), 'dc', NONCE, SEED)
    assert "Set-AgogeCtfAccess 'C:\\Secrets\\flag.txt' 'user' 'student' 'dc-file'" in payload
    assert "Set-AgogeCtfHidden 'C:\\Secrets\\flag.txt' 'dc-file'" in payload
    # The stream's permissions and attributes live on its host file
    assert "Set-AgogeCtfAccess 'C:\\Windows\\Temp\\notes.txt' 'user' 'student' 'dc-ads'" in payload
    assert "Set-AgogeCtfHidden 'C:\\Windows\\Temp\\notes.txt' 'dc-ads'" in payload
    # Access is applied after the write, and Hidden last
    lines = payload.splitlines()
    write = lines.index(next(line for line in lines if line.startswith("Set-AgogeCtfFile ")))
    access = lines.index("Set-AgogeCtfAccess 'C:\\Secrets\\flag.txt' 'user' 'student' 'dc-file'")
    hidden = lines.index("Set-AgogeCtfHidden 'C:\\Secrets\\flag.txt' 'dc-file'")
    assert write < access < hidden


def test_windows_payload_without_options_keeps_inherited_access():
    payload = _windows_planter().build_payload(_board(['dc-file', 'dc-ads']), 'dc', NONCE, SEED)
    assert "Set-AgogeCtfAccess '" not in payload
    assert "Set-AgogeCtfHidden '" not in payload


def test_windows_access_grants_use_well_known_sids():
    payload = _windows_planter(windows_access='everyone').build_payload(_board(['dc-file']), 'dc', NONCE, SEED)
    for sid in ('*S-1-5-18:(F)', '*S-1-5-32-544:(F)', '*S-1-1-0:(R)'):
        assert sid in payload
    # A replant must be able to overwrite a file an earlier plant hid
    assert "Clear-AgogeCtfAttributes $Path" in payload


def test_windows_payload_with_access_parses_as_powershell(tmp_path):
    if shutil.which('pwsh') is None:
        pytest.skip("PowerShell is not installed")
    script = tmp_path / 'payload.ps1'
    script.write_text(_windows_planter(windows_access='user', windows_user='student', hidden=True).build_payload(
        _board(['dc-file', 'dc-ads']), 'dc', NONCE, SEED))
    check = (
        "$errors = $null; "
        f"[System.Management.Automation.Language.Parser]::ParseFile('{script}', [ref]$null, [ref]$errors) | Out-Null; "
        "$errors.Count"
    )
    result = subprocess.run(['pwsh', '-NoProfile', '-NonInteractive', '-Command', check],
                            capture_output=True, text=True, timeout=60)
    assert result.stdout.strip() == '0', result.stdout + result.stderr
