import os
import shutil
import stat
import subprocess
import sys
import textwrap
import time
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from cloud_fn_utilities.course_objects.compute.lab_server_manager import LabServerManager
from common.utilities.ctf_plant_contract import (
    LAST_PAYLOAD_PATH,
    LINUX_LOADER,
    LINUX_LOADER_METADATA_KEY,
    PLANT_METADATA_KEY,
    RUN_DIR,
    RUN_LOCK_PATH,
    WATCHER_INSTALLER,
    WATCHER_SCRIPT,
    WATCHER_SCRIPT_PATH,
    WATCHER_UNIT,
    WATCHER_UNIT_NAME,
    WATCHER_UNIT_PATH,
)

needs_bash = pytest.mark.skipif(shutil.which("bash") is None, reason="needs bash")

CUSTOM_SCRIPT = "#!/bin/bash\necho custom > /tmp/custom-marker\n"
ALIAS_NIC = {'network': 'lab', 'subnet_name': 'default', 'ip_aliases': ['10.1.0.20']}
PLAIN_NIC = {'network': 'lab', 'subnet_name': 'default'}


# --- Merge into startup-script ---------------------------------------------------------------

def _manager(os_name='linux', nics=None, metadata=None, startup_script=None):
    # Build only what _add_metadata reads; the real __init__ needs GCP and Firestore.
    manager = object.__new__(LabServerManager)
    manager.server_spec = SimpleNamespace(
        name="abcdefghij-hv-host",
        os=os_name,
        nics=[ALIAS_NIC] if nics is None else nics,
        metadata=metadata,
        ssh_keys=[],
        startup_script=startup_script,
        guacamole_startup_script=None,
    )
    manager.assessment = MagicMock()
    manager.assessment.get_startup_scripts.return_value = None
    return manager


def _startup_script(manager):
    manager._add_metadata()
    matches = [item for item in manager.server_spec.metadata['items'] if item['key'] == LINUX_LOADER_METADATA_KEY]
    assert len(matches) == 1
    return matches[0]['value']


def test_linux_server_with_ip_aliases_gets_the_installer_before_the_loader():
    script = _startup_script(_manager())

    assert WATCHER_INSTALLER.strip() in script
    # The loader stays last, so it plants into a fully set-up server.
    assert script.index(WATCHER_INSTALLER.strip()) < script.index(LINUX_LOADER.strip())
    assert script.rstrip().endswith(LINUX_LOADER.strip())


@pytest.mark.parametrize("os_name, nics", [
    ('linux', [PLAIN_NIC]),                          # no nested virtualization
    ('linux', []),
    ('linux', [{**PLAIN_NIC, 'ip_aliases': []}]),
    ('windows', [ALIAS_NIC]),                        # no systemd to run a watcher
    (None, [ALIAS_NIC]),                             # OS unknown: N5 never allows guests here
])
def test_installer_is_merged_only_for_linux_servers_with_ip_aliases(os_name, nics):
    script = _startup_script(_manager(os_name=os_name, nics=nics))

    assert WATCHER_INSTALLER.strip() not in script
    assert script.strip() == LINUX_LOADER.strip()


def _unit_with_guests(*servers):
    return {'ctf': {'nested_guests': [
        {'name': f'guest-{i}', 'server': server, 'domain': f'guest-{i}', 'operating_system': 'linux'}
        for i, server in enumerate(servers)
    ]}}


def test_linux_server_named_by_nested_guests_gets_the_installer_without_ip_aliases():
    manager = _manager(nics=[PLAIN_NIC])
    manager.server_spec.parent_id = "abcdefghij"
    manager.assessment.unit = _unit_with_guests('hv-host')

    script = _startup_script(manager)

    assert script.count(WATCHER_INSTALLER.strip()) == 1
    assert script.index(WATCHER_INSTALLER.strip()) < script.index(LINUX_LOADER.strip())


@pytest.mark.parametrize("os_name, unit", [
    ('linux', _unit_with_guests('other-host')),      # guests belong to a different server
    ('linux', {'ctf': {'nested_guests': []}}),
    ('linux', {'ctf': None}),                        # not a CTF unit
    ('linux', {}),
    ('windows', _unit_with_guests('hv-host')),       # no systemd to run a watcher
])
def test_nested_guests_installer_needs_a_linux_server_the_guests_name(os_name, unit):
    manager = _manager(os_name=os_name, nics=[PLAIN_NIC])
    manager.server_spec.parent_id = "abcdefghij"
    manager.assessment.unit = unit

    assert WATCHER_INSTALLER.strip() not in _startup_script(manager)


def test_existing_startup_script_is_kept_ahead_of_the_installer():
    script = _startup_script(_manager(startup_script=CUSTOM_SCRIPT))

    assert script.startswith(CUSTOM_SCRIPT.rstrip())
    assert script.index("echo custom") < script.index(WATCHER_INSTALLER.strip()) < script.index(LINUX_LOADER.strip())


def test_spec_metadata_startup_script_is_kept_with_the_installer():
    script = _startup_script(_manager(metadata={'items': [{'key': 'startup-script', 'value': CUSTOM_SCRIPT}]}))

    assert script.startswith(CUSTOM_SCRIPT.rstrip())
    assert WATCHER_INSTALLER.strip() in script


def test_installer_already_in_spec_metadata_is_not_duplicated():
    # Metadata copied from an already-built nested host carries the installer and the loader.
    built = _manager(startup_script=CUSTOM_SCRIPT)
    built._add_metadata()
    rebuilt = _manager(metadata={'items': [dict(item) for item in built.server_spec.metadata['items']]})

    script = _startup_script(rebuilt)

    assert script.count(WATCHER_INSTALLER.strip()) == 1
    assert script.count(LINUX_LOADER.strip()) == 1


def test_load_lab_server_reads_the_os_from_details_or_the_top_level_key():
    manager = object.__new__(LabServerManager)
    manager.server_spec = SimpleNamespace()
    base = {'parent_id': 'abcdefghij', 'nics': [ALIAS_NIC]}

    manager._load_lab_server('abcdefghij-hv-host', server_spec={**base, 'details': {'os': 'linux'}})
    assert manager.server_spec.os == 'linux'
    manager._load_lab_server('abcdefghij-hv-host', server_spec={**base, 'os': 'windows'})
    assert manager.server_spec.os == 'windows'
    manager._load_lab_server('abcdefghij-hv-host', server_spec=base)
    assert manager.server_spec.os is None


# --- Shared lock and dedupe file -------------------------------------------------------------

def test_loader_and_watcher_take_the_same_lock_and_dedupe_on_the_same_file():
    for script in (LINUX_LOADER, WATCHER_SCRIPT):
        assert f"exec 9>{RUN_LOCK_PATH}" in script
        assert "flock 9" in script
        assert f"> {LAST_PAYLOAD_PATH}" in script
        assert f"cat {LAST_PAYLOAD_PATH}" in script


def test_installer_writes_the_watcher_under_the_contract_names():
    assert f"cat > {WATCHER_SCRIPT_PATH}.new <<'AGOGE_CTF_WATCHER_SCRIPT'" in WATCHER_INSTALLER
    assert f"\n{WATCHER_SCRIPT}AGOGE_CTF_WATCHER_SCRIPT\n" in WATCHER_INSTALLER
    assert f"\n{WATCHER_UNIT}AGOGE_CTF_WATCHER_UNIT\n" in WATCHER_INSTALLER
    assert WATCHER_UNIT_PATH == f"/etc/systemd/system/{WATCHER_UNIT_NAME}"
    assert f"ExecStart={WATCHER_SCRIPT_PATH}" in WATCHER_UNIT
    assert f"systemctl enable --now {WATCHER_UNIT_NAME}" in WATCHER_INSTALLER


def test_watcher_long_polls_the_plant_key_with_the_etag():
    assert f"attributes/{PLANT_METADATA_KEY}?wait_for_change=true" in WATCHER_SCRIPT
    assert "last_etag=$agoge_ctf_etag" in WATCHER_SCRIPT


@needs_bash
@pytest.mark.parametrize("script", [LINUX_LOADER, WATCHER_SCRIPT, WATCHER_INSTALLER])
def test_scripts_pass_bash_syntax_check(script, tmp_path):
    path = tmp_path / "script.sh"
    path.write_text(script)

    result = subprocess.run(["bash", "-n", str(path)], capture_output=True, text=True, timeout=30)

    assert result.returncode == 0, result.stderr


# --- Executed for real, with fakes for root-only paths and the metadata server ---------------

# Real flock(2) on the inherited fd: the lock belongs to the shell's open file description, so it
# outlives this process and is held until the locked subshell exits, as util-linux flock's is.
FAKE_FLOCK = f"#!{sys.executable}\nimport fcntl, sys\nfcntl.flock(int(sys.argv[-1]), fcntl.LOCK_EX)\n"

# Serves the loader (curl -sf -o FILE URL) from $FAKE_PAYLOAD.
FAKE_LOADER_CURL = textwrap.dedent("""\
    #!/bin/bash
    out=""
    while [ $# -gt 0 ]; do
      case "$1" in -o) out="$2"; shift 2 ;; *) shift ;; esac
    done
    cp "$FAKE_PAYLOAD" "$out"
""")

# Serves the watcher from $FAKE_RESPONSES/<n> ("<code> <etag> <payload file>"), one per call;
# past the last one it answers 404. Each call's URL is logged to $FAKE_CURL_LOG.
FAKE_WATCHER_CURL = textwrap.dedent("""\
    #!/bin/bash
    out=""; headers=""; url=""
    while [ $# -gt 0 ]; do
      case "$1" in
        -o) out="$2"; shift 2 ;;
        -D) headers="$2"; shift 2 ;;
        -w|-H|--max-time) shift 2 ;;
        -*) shift ;;
        *) url="$1"; shift ;;
      esac
    done
    echo "$url" >> "$FAKE_CURL_LOG"
    n=$(wc -l < "$FAKE_CURL_LOG" | tr -d ' ')
    if [ -f "$FAKE_RESPONSES/$n" ]; then
      read -r code etag payload < "$FAKE_RESPONSES/$n"
      printf 'HTTP/1.1 %s OK\\r\\nETag: %s\\r\\n\\r\\n' "$code" "$etag" > "$headers"
      cp "$payload" "$out"
      printf '%s' "$code"
    else
      : > "$out"
      printf '404'
    fi
""")


def _executable(path, text):
    path.write_text(text)
    path.chmod(path.stat().st_mode | stat.S_IEXEC)


@pytest.fixture
def sandbox(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _executable(bin_dir / "flock", FAKE_FLOCK)
    # The watcher sleeps 5 s after a 404; keep the loop fast.
    _executable(bin_dir / "sleep", "#!/bin/bash\nexec /bin/sleep 0.05\n")
    work = tmp_path / "tmp"
    work.mkdir()
    env = {
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "TMPDIR": str(work),
        "RAN": str(tmp_path / "ran"),
        "FAKE_CURL_LOG": str(tmp_path / "curl-log"),
        "FAKE_RESPONSES": str(tmp_path / "responses"),
    }
    (tmp_path / "responses").mkdir()
    return SimpleNamespace(root=tmp_path, bin=bin_dir, env=env, run_dir=tmp_path / "run")


def _local(script, sandbox):
    return script.replace(RUN_DIR, str(sandbox.run_dir))


def _payload(sandbox, name, delay="0"):
    path = sandbox.root / f"{name}.sh"
    # Sleeps so two concurrent runs overlap unless the lock serializes them.
    path.write_text(f'/bin/sleep {delay}\necho {name} >> "$RAN"\n')
    return path


def _ran(sandbox):
    path = sandbox.root / "ran"
    return path.read_text().split() if path.exists() else []


def _run_loader(sandbox):
    _executable(sandbox.bin / "curl", FAKE_LOADER_CURL)
    return subprocess.run(
        ["bash", "-c", _local(LINUX_LOADER, sandbox)], env=sandbox.env, capture_output=True, text=True, timeout=30
    )


def _run_watcher(sandbox, until_calls):
    _executable(sandbox.bin / "curl", FAKE_WATCHER_CURL)
    script = sandbox.root / "watcher.sh"
    script.write_text(_local(WATCHER_SCRIPT, sandbox))
    process = subprocess.Popen(["bash", str(script)], env=sandbox.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    log = sandbox.root / "curl-log"
    deadline = time.monotonic() + 30
    try:
        while time.monotonic() < deadline:
            if log.exists() and len(log.read_text().splitlines()) >= until_calls:
                break
            time.sleep(0.05)
        else:
            pytest.fail("watcher did not poll the metadata server enough times")
    finally:
        # TERM, as systemctl stop sends: the watcher's trap removes its in-flight temp files.
        process.terminate()
        stdout, stderr = process.communicate(timeout=10)
    assert stdout == b"" and stderr == b""
    return log.read_text().splitlines()


def _respond(sandbox, n, code, etag, payload):
    (sandbox.root / "responses" / str(n)).write_text(f"{code} {etag} {payload}\n")


@needs_bash
def test_loader_runs_a_payload_once_and_records_its_hash(sandbox):
    sandbox.env["FAKE_PAYLOAD"] = str(_payload(sandbox, "first"))

    assert _run_loader(sandbox).returncode == 0
    assert _run_loader(sandbox).returncode == 0

    assert _ran(sandbox) == ["first"]
    last = (sandbox.run_dir / "last").read_text().strip()
    assert len(last) == 64
    assert stat.S_IMODE(sandbox.run_dir.stat().st_mode) == 0o700


@needs_bash
def test_concurrent_loaders_serialize_on_the_lock_and_run_the_payload_once(sandbox):
    sandbox.env["FAKE_PAYLOAD"] = str(_payload(sandbox, "first", delay="0.5"))
    _executable(sandbox.bin / "curl", FAKE_LOADER_CURL)
    script = _local(LINUX_LOADER, sandbox)

    runs = [subprocess.Popen(["bash", "-c", script], env=sandbox.env) for _ in range(3)]
    for run in runs:
        assert run.wait(timeout=30) == 0

    assert _ran(sandbox) == ["first"]


@needs_bash
def test_a_process_the_payload_leaves_running_does_not_hold_the_lock(sandbox):
    first = sandbox.root / "first.sh"
    # Mirrors a detached child (e.g. a relay job): if it inherited fd 9 the second plant would block.
    first.write_text('/bin/sleep 20 >/dev/null 2>&1 &\necho first >> "$RAN"\n')
    sandbox.env["FAKE_PAYLOAD"] = str(first)
    assert _run_loader(sandbox).returncode == 0
    sandbox.env["FAKE_PAYLOAD"] = str(_payload(sandbox, "second"))

    started = time.monotonic()
    assert _run_loader(sandbox).returncode == 0

    assert time.monotonic() - started < 10, "second plant waited on the first payload's child"
    assert _ran(sandbox) == ["first", "second"]


@needs_bash
def test_watcher_runs_each_new_payload_once_and_follows_the_etag(sandbox):
    first, second = _payload(sandbox, "first"), _payload(sandbox, "second")
    _respond(sandbox, 1, 200, "e1", first)
    _respond(sandbox, 2, 200, "e2", first)       # same value again: deduped
    _respond(sandbox, 3, 200, "e3", second)

    urls = _run_watcher(sandbox, until_calls=5)

    assert _ran(sandbox) == ["first", "second"]
    assert all(f"attributes/{PLANT_METADATA_KEY}?wait_for_change=true" in url for url in urls)
    assert [url.rsplit("last_etag=", 1)[1] for url in urls[:5]] == ["0", "e1", "e2", "e3", "0"]
    # Its temp files are cleaned up, even when stopped mid-poll; only the lock and the dedupe file stay.
    assert sorted(p.name for p in sandbox.run_dir.iterdir()) == ["last", "plant.lock"]


@needs_bash
def test_watcher_does_not_rerun_a_payload_the_loader_already_ran_this_boot(sandbox):
    payload = _payload(sandbox, "first")
    sandbox.env["FAKE_PAYLOAD"] = str(payload)
    assert _run_loader(sandbox).returncode == 0
    _respond(sandbox, 1, 200, "e1", payload)

    _run_watcher(sandbox, until_calls=3)

    assert _ran(sandbox) == ["first"]


@needs_bash
def test_watcher_ignores_an_empty_value_and_an_unsafe_etag(sandbox):
    empty = sandbox.root / "empty.sh"
    empty.write_text("")
    _respond(sandbox, 1, 200, "e1;rm$IFS-rf", empty)

    urls = _run_watcher(sandbox, until_calls=2)

    assert _ran(sandbox) == []
    assert urls[1].endswith("last_etag=e1rmIFSrf")


@needs_bash
def test_installer_writes_the_watcher_and_unit_and_enables_it(sandbox):
    _executable(sandbox.bin / "systemctl", '#!/bin/bash\necho "$*" >> "$SYSTEMCTL_LOG"\n')
    sandbox.env["SYSTEMCTL_LOG"] = str(sandbox.root / "systemctl-log")
    script_path, unit_path = sandbox.root / "sbin" / "agoge-ctf-watcher", sandbox.root / "units" / WATCHER_UNIT_NAME
    installer = WATCHER_INSTALLER.replace(WATCHER_SCRIPT_PATH, str(script_path)).replace(
        WATCHER_UNIT_PATH, str(unit_path)
    )

    for _ in range(2):  # every boot reinstalls
        result = subprocess.run(["bash", "-c", installer], env=sandbox.env, capture_output=True, text=True, timeout=30)
        assert result.returncode == 0
        assert result.stdout == "" and result.stderr == ""

    assert script_path.read_text() == WATCHER_SCRIPT
    assert stat.S_IMODE(script_path.stat().st_mode) == 0o700
    assert unit_path.read_text() == WATCHER_UNIT.replace(WATCHER_SCRIPT_PATH, str(script_path))
    assert sorted(p.name for p in script_path.parent.iterdir()) == ["agoge-ctf-watcher"]
    assert (sandbox.root / "systemctl-log").read_text().splitlines() == [
        "daemon-reload", f"enable --now {WATCHER_UNIT_NAME}"
    ] * 2


@needs_bash
def test_installer_installs_nothing_without_flock(sandbox):
    (sandbox.bin / "flock").unlink()
    _executable(sandbox.bin / "systemctl", '#!/bin/bash\necho "$*" >> "$SYSTEMCTL_LOG"\n')
    sandbox.env["SYSTEMCTL_LOG"] = str(sandbox.root / "systemctl-log")
    # Hide any real flock on this machine's PATH.
    sandbox.env["PATH"] = f"{sandbox.bin}{os.pathsep}/bin"
    script_path = sandbox.root / "sbin" / "agoge-ctf-watcher"
    installer = WATCHER_INSTALLER.replace(WATCHER_SCRIPT_PATH, str(script_path)).replace(
        WATCHER_UNIT_PATH, str(sandbox.root / "units" / WATCHER_UNIT_NAME)
    )

    result = subprocess.run(["bash", "-c", installer], env=sandbox.env, capture_output=True, text=True, timeout=30)

    assert result.returncode == 0
    assert not script_path.exists()
    assert not (sandbox.root / "systemctl-log").exists()
