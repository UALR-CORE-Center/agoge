"""FlagPlanter.build_payload offline relay section (N12): libguestfs placements on a shut-off nested guest."""
import json
import os
import shlex
import shutil
import subprocess
import sys

import pytest

from cloud_fn_utilities.course_objects.ctf import flag_planter as flag_planter_module
from common.exceptions import BadRequest
from common.utilities.ctf_flags import derive_flag_value

FlagPlanter = flag_planter_module.FlagPlanter

SEED = "f" * 64
NONCE = "0d4c1a52-6a8e-4c39-9d43-2b8f5f2a7e11"
WORKOUT_ID = "abcdefghij"
needs_bash = pytest.mark.skipif(shutil.which('bash') is None, reason="bash is not installed")


def _flag(flag_id, slot, location_type, path, operating_system='linux', guest='web', **extra):
    flag = {'id': flag_id, 'server': 'hv-host', 'slot': slot, 'location_type': location_type, 'path': path,
            'operating_system': operating_system, 'points': 100, **extra}
    if guest:
        flag['guest'] = guest
    return flag


GUESTS = [
    {'name': 'web', 'server': 'hv-host', 'domain': 'web-domain', 'operating_system': 'linux', 'driver': 'offline'},
    {'name': 'dc', 'server': 'hv-host', 'domain': 'dc-domain', 'operating_system': 'windows', 'driver': 'offline'},
]
FLAGS = [
    _flag('web-root', 1, 'file', '/root/flag.txt', file_mode='0600', file_owner='root:root'),
    _flag('web-user', 2, 'file', '/home/student/new/user.txt'),
    _flag('web-env', 3, 'env', 'AGOGE_WEB_FLAG'),
    # Lower case on purpose: the disk has Users/Public/Desktop
    _flag('dc-file', 1, 'file', 'C:\\users\\public\\desktop\\flag.txt', 'windows', guest='dc'),
    _flag('dc-reg', 2, 'registry', 'HKLM\\SOFTWARE\\Corp:Secret', 'windows', guest='dc'),
    _flag('dc-ccs', 3, 'registry', 'HKLM\\SYSTEM\\CurrentControlSet\\Services\\Corp:Token', 'windows', guest='dc'),
    _flag('dc-env', 4, 'env', 'AGOGE_DC_FLAG', 'windows', guest='dc'),
]
ALL_IDS = [flag['id'] for flag in FLAGS]
LINUX_IDS = [fid for fid in ALL_IDS if fid.startswith('web-')]
WINDOWS_IDS = [fid for fid in ALL_IDS if fid.startswith('dc-')]


def _event(flags=FLAGS, guests=GUESTS):
    return {
        'id': 'ctfeventaa', 'unit_id': 'unitaaaaaa', 'instructor_id': ['gm@example.edu'],
        'spec': {'name': 'Spring CTF', 'flags': flags, 'nested_guests': guests},
        'seed_version': 1, 'creation_timestamp': 1.0, 'state': 0,
        'state_timestamp': '2026-10-16T00:00:00+00:00',
    }


def _board(flag_ids=ALL_IDS):
    return {'id': f"ctfeventaa-{WORKOUT_ID}", 'workout_id': WORKOUT_ID, 'ctf_id': 'ctfeventaa',
            'team_name': 'Team 1', 'flags': [{'flag_id': flag_id, 'digest': '0' * 64} for flag_id in flag_ids]}


def _value(flag_id):
    return derive_flag_value(SEED, WORKOUT_ID, flag_id, 1, 'agoge')


def _payload(flag_ids=ALL_IDS, guest=None, revert=False, flags=FLAGS):
    return FlagPlanter(_event(flags)).build_payload(_board(flag_ids), 'hv-host', NONCE, SEED, guest=guest, revert=revert)


# --- shape -------------------------------------------------------------------------------------------------

@needs_bash
@pytest.mark.parametrize('revert', [False, True])
def test_offline_payload_passes_bash_n(revert):
    payload = _payload(['web-root'], guest='web', revert=revert) if revert else _payload()
    result = subprocess.run(['bash', '-n'], input=payload, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr


def test_virsh_destroy_never_appears():
    for payload in (_payload(), _payload(['web-root'], guest='web', revert=True)):
        assert 'destroy' not in payload


def test_virsh_start_appears_only_in_the_exit_trap():
    lines = _payload().splitlines()
    starts = [i for i, line in enumerate(lines) if 'virsh' in line and ' start ' in line]
    assert len(starts) == 1
    # The one start is inside agoge_ctf_offline_end, which begin installs as the section's EXIT trap
    end = lines.index('agoge_ctf_offline_end() {')
    assert end < starts[0] < lines.index('}', end)
    assert '  trap agoge_ctf_offline_end EXIT' in lines


def test_each_offline_guest_is_its_own_background_subshell_before_plant_result():
    lines = _payload().splitlines()
    opens = [i for i, line in enumerate(lines) if line == '(']
    closes = [i for i, line in enumerate(lines) if line == ') &']
    assert len(opens) == len(closes) == 2
    begins = [line for line in lines if line.startswith('agoge_ctf_offline_begin ')]
    assert begins == [
        "agoge_ctf_offline_begin web web-domain "
        "http://metadata.google.internal/computeMetadata/v1/instance/guest-attributes/agoge-ctf/plant-result-web "
        "0 linux || exit 0",
        "agoge_ctf_offline_begin dc dc-domain "
        "http://metadata.google.internal/computeMetadata/v1/instance/guest-attributes/agoge-ctf/plant-result-dc "
        "0 windows || exit 0",
    ]
    wait = lines.index('wait')
    assert max(closes) < wait


def test_registry_calls_map_current_control_set_and_environment():
    lines = [line for line in _payload().splitlines() if line.startswith('agoge_ctf_offline_windows_reg ')]
    assert lines == [
        f"agoge_ctf_offline_windows_reg 0 'SOFTWARE\\Corp' Secret {shlex.quote(_value('dc-reg'))} dc-reg",
        f"agoge_ctf_offline_windows_reg 1 'Services\\Corp' Token {shlex.quote(_value('dc-ccs'))} dc-ccs",
        f"agoge_ctf_offline_windows_reg 1 'Control\\Session Manager\\Environment' AGOGE_DC_FLAG "
        f"{shlex.quote(_value('dc-env'))} dc-env",
    ]


def test_revert_passes_through_to_the_offline_section():
    begin = next(line for line in _payload(['web-root'], guest='web', revert=True).splitlines()
                 if line.startswith('agoge_ctf_offline_begin '))
    assert begin.endswith(' 1 linux || exit 0')


@pytest.mark.parametrize('extra', [
    {'location_type': 'ads', 'path': 'C:\\Users\\Public\\a.txt:hidden'},
    {'windows_access': 'everyone'},
    {'hidden': True},
    {'location_type': 'registry', 'path': 'HKLM\\HARDWARE\\Corp:Secret'},
])
def test_windows_placement_libguestfs_cannot_make_raises(extra):
    flag = {**_flag('dc-file', 1, 'file', 'C:\\Users\\Public\\flag.txt', 'windows', guest='dc'), **extra}
    with pytest.raises(BadRequest, match='cannot be planted by the offline driver'):
        _payload(['dc-file'], flags=[flag])


# --- run against fake virsh / libguestfs --------------------------------------------------------------------

# One Python fake for every tool, dispatched on its name. Guest disks are directories under $FAKE_DISKS/<domain>;
# guest state lives in $FAKE_DIR/state-<domain>. Every argv, and every guestfish stdin line, goes to $FAKE_LOG.
FAKE_TOOL = r'''
import json, os, shlex, shutil, sys
name, args = os.path.basename(sys.argv[0]), sys.argv[1:]
fake_dir, disks = os.environ['FAKE_DIR'], os.environ['FAKE_DISKS']
def log(kind, text):
    with open(os.environ['FAKE_LOG'], 'a') as f:
        f.write(f"{kind}:{text}\n")
def state_file(domain):
    return os.path.join(fake_dir, 'state-' + domain)
def state(domain):
    return open(state_file(domain)).read() if os.path.exists(state_file(domain)) else 'running'
def set_state(domain, value):
    open(state_file(domain), 'w').write(value)
def disk(domain, path):
    return os.path.join(disks, domain, path.lstrip('/'))
def domain_arg():
    return args[args.index('-d') + 1]
def need_off(domain):
    if state(domain) != 'shut off':
        sys.stderr.write('disk in use\n')
        sys.exit(1)
log(name + '-args', ' '.join(args))
if name == 'virsh':
    command, domain = args[1], args[2]
    if command == 'domstate':
        print(state(domain))
    elif command == 'shutdown':
        if not os.environ.get('FAKE_NO_SHUTDOWN'):
            set_state(domain, 'shut off')
    elif command == 'start':
        set_state(domain, 'running')
    elif command == 'snapshot-info':
        sys.exit(0 if os.environ.get('FAKE_SNAPSHOT') else 1)
    elif command == 'snapshot-revert':
        set_state(domain, 'running')
        log('reverted', domain)
elif name == 'virt-customize':
    domain = domain_arg()
    need_off(domain)
    if os.environ.get('FAKE_CUSTOMIZE_FAILS'):
        sys.exit(1)
    i = args.index('-d') + 2
    while i < len(args):
        option, value = args[i], args[i + 1]
        i += 2
        if option == '--mkdir':
            os.makedirs(disk(domain, value), exist_ok=True)
        elif option == '--upload':
            source, dest = value.split(':', 1)
            log('upload-source', source)
            shutil.copyfile(source, disk(domain, dest))
        elif option == '--chmod':
            mode, path = value.split(':', 1)
            os.chmod(disk(domain, path), int(mode, 8))
        elif option == '--run-command':
            log('guest-run', value)
elif name == 'guestfish':
    domain = domain_arg()
    if '--ro' not in args:
        need_off(domain)
    def resolve(path):
        # Case-insensitive walk, as for NTFS through ntfs-3g; the missing tail is appended unmodified
        parts, real = [p for p in path.split('/') if p], ''
        for k, part in enumerate(parts):
            here = disk(domain, real)
            match = next((e for e in os.listdir(here) if e.lower() == part.lower()), None) if os.path.isdir(here) else None
            if match is None:
                return real + '/' + part if k == len(parts) - 1 else None
            real += '/' + match
        return real
    for line in sys.stdin:
        log('guestfish-stdin', line.rstrip('\n'))
        words = shlex.split(line)
        if not words:
            continue
        command = words[0].lstrip('-')
        if command == 'echo':
            print(' '.join(words[1:]))
        elif command == 'exists':
            print('true' if os.path.exists(disk(domain, words[1])) else 'false')
        elif command == 'case-sensitive-path':
            found = resolve(words[1])
            print(found.lstrip('/')) if found else sys.stderr.write('no such directory\n')
        elif command == 'download':
            if os.path.exists(disk(domain, words[1])):
                shutil.copyfile(disk(domain, words[1]), words[2])
        elif command == 'mkdir-p':
            os.makedirs(disk(domain, words[1]), exist_ok=True)
        elif command == 'upload':
            log('upload-source', words[1])
            shutil.copyfile(words[1], disk(domain, words[2]))
elif name == 'virt-win-reg':
    store = os.path.join(fake_dir, 'registry.json')
    registry = json.load(open(store)) if os.path.exists(store) else {}
    if args[0] == '--merge':
        need_off(args[1])
        log('upload-source', args[2])
        key = None
        for line in open(args[2]):
            line = line.rstrip('\n')
            if line.startswith('[') and line.endswith(']'):
                key = line[1:-1].replace('HKEY_LOCAL_MACHINE\\', 'HKLM\\', 1)
            elif line.startswith('"'):
                value_name, value = line.split('=', 1)
                registry[f"{args[1]}|{key.upper()}|{value_name.strip('\"').upper()}"] = value.strip('"')
        json.dump(registry, open(store, 'w'))
    elif args[1:] == ['HKLM\\SYSTEM\\Select', 'Current']:
        print(os.environ.get('FAKE_CURRENT_SET', 'dword:00000002'))
    else:
        found = registry.get(f"{args[0]}|{args[1].upper()}|{args[2].upper()}")
        if found is None:
            sys.exit(1)
        print(found + '\r')
'''
FAKE_SHELL = {
    'curl': r'''#!/bin/bash
printf 'curl-args:%s\n' "$*" >> "$FAKE_LOG"
data=''; url=''
while [ $# -gt 0 ]; do
  case "$1" in --data) data="$2"; shift 2 ;; -X|-H) shift 2 ;; *) url="$1"; shift ;; esac
done
printf 'put:%s %s\n' "${url##*/guest-attributes/}" "$data" >> "$FAKE_LOG"
''',
    'timeout': '#!/bin/bash\nprintf \'timeout-args:%s\\n\' "$*" >> "$FAKE_LOG"\nshift\nexec "$@"\n',
    'sleep': '#!/bin/bash\nprintf \'sleep-args:%s\\n\' "$*" >> "$FAKE_LOG"\n',
    'iptables': '#!/bin/bash\n[ "$1" != "-C" ]\n',
}


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    bin_dir = tmp_path / 'bin'
    bin_dir.mkdir()
    tool = bin_dir / 'fake_tool.py'
    tool.write_text(f"#!{sys.executable}\n{FAKE_TOOL}")
    tool.chmod(0o755)
    for name in ('virsh', 'virt-customize', 'guestfish', 'virt-win-reg'):
        (bin_dir / name).symlink_to(tool)
    for name, body in FAKE_SHELL.items():
        (bin_dir / name).write_text(body)
        (bin_dir / name).chmod(0o755)
    disks = tmp_path / 'disks'
    (disks / 'web-domain' / 'etc').mkdir(parents=True)
    (disks / 'web-domain' / 'root').mkdir()
    (disks / 'web-domain' / 'home' / 'student').mkdir(parents=True)
    (disks / 'web-domain' / 'etc' / 'environment').write_text('LANG=C\nAGOGE_WEB_FLAG=old\n')
    (disks / 'dc-domain' / 'Users' / 'Public' / 'Desktop').mkdir(parents=True)
    run_dir = tmp_path / 'run'
    monkeypatch.setattr(flag_planter_module, 'OFFLINE_TEMP_DIR', str(run_dir))
    fake_dir = tmp_path / 'fake'
    fake_dir.mkdir()
    return {'bin': bin_dir, 'disks': disks, 'run': run_dir, 'dir': fake_dir, 'log': tmp_path / 'log'}


def _run(payload, sandbox, **env_extra):
    env = {**os.environ, 'PATH': f"{sandbox['bin']}:{os.environ['PATH']}", 'FAKE_LOG': str(sandbox['log']),
           'FAKE_DIR': str(sandbox['dir']), 'FAKE_DISKS': str(sandbox['disks']), **env_extra}
    result = subprocess.run(['bash', '-s'], input=payload, capture_output=True, text=True, env=env, timeout=120)
    assert result.returncode == 0 and result.stdout == '' and result.stderr == '', result
    return sandbox['log'].read_text().splitlines() if sandbox['log'].exists() else []


def _puts(log):
    return dict(line[len('put:'):].split(' ', 1) for line in log if line.startswith('put:'))


def _calls(log, tool, command=None):
    calls = [line.split(':', 1)[1] for line in log if line.startswith(f"{tool}-args:")]
    return [c for c in calls if command is None or c.split()[1:2] == [command]]


@needs_bash
def test_offline_plant_writes_verifies_and_restarts_both_guests(sandbox):
    log = _run(_payload(), sandbox)

    puts = _puts(log)
    assert puts['agoge-ctf/plant-result-web'] == f"ok:{NONCE}"
    assert puts['agoge-ctf/plant-result-dc'] == f"ok:{NONCE}"
    assert puts['agoge-ctf/plant-result'] == f"ok:{NONCE}"
    web, dc = sandbox['disks'] / 'web-domain', sandbox['disks'] / 'dc-domain'
    assert (web / 'root/flag.txt').read_text() == _value('web-root')
    assert oct((web / 'root/flag.txt').stat().st_mode & 0o777) == '0o600'
    assert (web / 'home/student/new/user.txt').read_text() == _value('web-user')
    assert (web / 'etc/environment').read_text() == f"LANG=C\nAGOGE_WEB_FLAG={_value('web-env')}\n"
    assert 'guest-run:chown root:root /root/flag.txt' in log
    # Case-insensitive resolution: written into the existing Users/Public/Desktop
    assert (dc / 'Users/Public/Desktop/flag.txt').read_text() == _value('dc-file')
    # The host filesystem may be case-insensitive itself, so check the path guestfish was given
    assert any(line.startswith('guestfish-stdin:-upload ') and line.endswith(' "/Users/Public/Desktop/flag.txt"')
               for line in log)
    registry = json.loads((sandbox['dir'] / 'registry.json').read_text())
    assert registry == {
        'dc-domain|HKLM\\SOFTWARE\\CORP|SECRET': _value('dc-reg'),
        'dc-domain|HKLM\\SYSTEM\\CONTROLSET002\\SERVICES\\CORP|TOKEN': _value('dc-ccs'),
        'dc-domain|HKLM\\SYSTEM\\CONTROLSET002\\CONTROL\\SESSION MANAGER\\ENVIRONMENT|AGOGE_DC_FLAG': _value('dc-env'),
    }
    for domain in ('web-domain', 'dc-domain'):
        assert _calls(log, 'virsh', 'shutdown') and (sandbox['dir'] / f"state-{domain}").read_text() == 'running'
    assert len(_calls(log, 'virsh', 'start')) == 2


@needs_bash
def test_values_reach_libguestfs_only_through_temp_files_that_are_removed(sandbox):
    log = _run(_payload(), sandbox)

    values = [_value(fid) for fid in ALL_IDS]
    for line in log:
        kind = line.split(':', 1)[0]
        if kind.endswith('-args') or kind == 'guestfish-stdin':
            assert not any(value in line for value in values), line
    sources = [line.split(':', 1)[1] for line in log if line.startswith('upload-source:')]
    assert sources and all(source.startswith(str(sandbox['run']) + '/offline.') for source in sources)
    # Every section's temp directory is gone; the run directory itself is root-only
    assert os.listdir(sandbox['run']) == []
    assert oct(sandbox['run'].stat().st_mode & 0o777) == '0o700'


@needs_bash
def test_guest_that_will_not_shut_down_fails_and_is_still_started(sandbox, monkeypatch):
    # The fake sleep returns at once, so keep the real-time shutdown window short
    monkeypatch.setattr(flag_planter_module, '_OFFLINE_SHUTDOWN_SECONDS', 2)
    log = _run(_payload(LINUX_IDS), sandbox, FAKE_NO_SHUTDOWN='1')

    assert _puts(log)['agoge-ctf/plant-result-web'] == f"error:{NONCE}:web: guest did not shut down"
    assert not _calls(log, 'virt-customize')
    assert _calls(log, 'virsh', 'start') == ['-q start web-domain']
    assert not any('destroy' in line for line in log)


@needs_bash
def test_failed_write_reports_verification_failed_and_still_starts(sandbox):
    log = _run(_payload(LINUX_IDS), sandbox, FAKE_CUSTOMIZE_FAILS='1')

    assert _puts(log)['agoge-ctf/plant-result-web'] == (
        f"error:{NONCE}:web-root: verification failed; web-user: verification failed; web-env: verification failed"
    )
    assert _calls(log, 'virsh', 'start') == ['-q start web-domain']
    assert (sandbox['disks'] / 'web-domain/etc/environment').read_text() == 'LANG=C\nAGOGE_WEB_FLAG=old\n'


@needs_bash
def test_guest_already_shut_off_is_planted_without_shutdown_and_started(sandbox):
    (sandbox['dir'] / 'state-web-domain').write_text('shut off')
    log = _run(_payload(LINUX_IDS), sandbox)

    assert _puts(log)['agoge-ctf/plant-result-web'] == f"ok:{NONCE}"
    assert not _calls(log, 'virsh', 'shutdown')
    # Contract step 4: virsh start whatever the outcome
    assert _calls(log, 'virsh', 'start') == ['-q start web-domain']
    assert (sandbox['dir'] / 'state-web-domain').read_text() == 'running'


@needs_bash
def test_missing_control_set_fails_only_the_control_set_flags(sandbox):
    log = _run(_payload(WINDOWS_IDS), sandbox, FAKE_CURRENT_SET='')

    assert _puts(log)['agoge-ctf/plant-result-dc'] == (
        f"error:{NONCE}:dc-ccs: could not find the current control set; "
        f"dc-env: could not find the current control set"
    )


@needs_bash
def test_rebuild_reverts_then_plants_offline(sandbox):
    log = _run(_payload(['web-root'], guest='web', revert=True), sandbox, FAKE_SNAPSHOT='1')

    assert _puts(log)['agoge-ctf/plant-result-web'] == f"ok:{NONCE}"
    order = [line for line in log if line.startswith(('reverted:', 'virsh-args:-q shutdown', 'virt-customize-args'))]
    assert [line.split(':')[0] for line in order] == ['reverted', 'virsh-args', 'virt-customize-args']
    assert _calls(log, 'virsh', 'start') == ['-q start web-domain']


@needs_bash
def test_rebuild_without_snapshot_fails_without_writing(sandbox):
    log = _run(_payload(['web-root'], guest='web', revert=True), sandbox)

    assert _puts(log)['agoge-ctf/plant-result-web'] == f"error:{NONCE}:web: no agoge-pristine snapshot"
    assert not _calls(log, 'virt-customize') and not _calls(log, 'virsh', 'shutdown')
    assert _calls(log, 'virsh', 'start') == ['-q start web-domain']
