import os
import shutil
import stat
import subprocess
import textwrap

import pytest

from common.utilities import ctf_plant_contract as contract


def test_contract_names_match_the_prd():
    assert contract.PLANT_METADATA_KEY == "agoge-ctf-plant"
    assert contract.GUEST_ATTRIBUTES_ENABLE_KEY == "enable-guest-attributes"
    assert contract.GUEST_ATTRIBUTES_ENABLE_VALUE == "TRUE"
    assert contract.GUEST_ATTRIBUTE_NAMESPACE == "agoge-ctf/"
    assert contract.GUEST_ATTRIBUTE_PATH == "agoge-ctf/plant-result"
    assert contract.LINUX_LOADER_METADATA_KEY == "startup-script"
    assert contract.WINDOWS_LOADER_METADATA_KEY == "windows-startup-script-ps1"
    assert contract.MAX_RESULT_MESSAGE_LENGTH == 200


@pytest.mark.parametrize("loader", [contract.LINUX_LOADER, contract.WINDOWS_LOADER])
def test_loaders_fetch_the_plant_key_from_the_metadata_server(loader):
    assert ("http://metadata.google.internal/computeMetadata/v1/instance/attributes/agoge-ctf-plant"
            in loader)
    assert "Metadata-Flavor" in loader


def test_loaders_are_fixed_text():
    # Fixed text means no unformatted template braces survived the f-string.
    assert "{{" not in contract.LINUX_LOADER and "}}" not in contract.LINUX_LOADER
    assert "{{" not in contract.WINDOWS_LOADER and "}}" not in contract.WINDOWS_LOADER


def test_windows_loader_is_scoped_and_silenced():
    assert contract.WINDOWS_LOADER.lstrip().startswith("# agoge-ctf loader")
    assert "& {" in contract.WINDOWS_LOADER
    assert contract.WINDOWS_LOADER.rstrip().endswith("} *> $null")
    assert "*S-1-5-18:(OI)(CI)F" in contract.WINDOWS_LOADER
    assert "/inheritance:r" in contract.WINDOWS_LOADER
    assert "Remove-Item" in contract.WINDOWS_LOADER
    for printer in ("Write-Host", "Write-Output", "echo "):
        assert printer not in contract.WINDOWS_LOADER


@pytest.mark.parametrize("value, expected", [
    ("ok:n1", ("ok", None)),
    ("error:n1:disk full", ("error", "disk full")),
    ("error:n1:a:b", ("error", "a:b")),
    ("error:n1:", ("error", "")),
    ("ok:n0", None),               # an earlier plant's result
    ("error:n0:old", None),
    ("ok:n1x", None),
    ("ok", None),
    ("", None),
    (None, None),
])
def test_parse_plant_result(value, expected):
    assert contract.parse_plant_result(value, "n1") == expected


def test_parse_plant_result_truncates_the_message():
    result = contract.parse_plant_result("error:n1:" + "x" * 500, "n1")
    assert result == ("error", "x" * 200)


def test_parse_plant_result_requires_a_nonce():
    assert contract.parse_plant_result("ok:", "") is None


# --- The Linux loader, executed for real by bash with a fake curl on PATH -----------------

bash = shutil.which("bash")
pytestmark_bash = pytest.mark.skipif(bash is None, reason="bash is not installed")

FAKE_CURL = textwrap.dedent("""\
    #!/bin/bash
    # Stand-in for the metadata server: serve $FAKE_PAYLOAD, or 404 (exit 22, as curl -f does).
    out=""
    while [ $# -gt 0 ]; do
      case "$1" in
        -o) out="$2"; shift 2 ;;
        *) echo "$1" >> "$FAKE_CURL_ARGS"; shift ;;
      esac
    done
    [ -n "$FAKE_PAYLOAD" ] || exit 22
    cp "$FAKE_PAYLOAD" "$out"
""")


@pytest.fixture
def loader_env(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    curl = bin_dir / "curl"
    curl.write_text(FAKE_CURL)
    curl.chmod(curl.stat().st_mode | stat.S_IEXEC)
    work = tmp_path / "tmp"
    work.mkdir()
    env = {
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "TMPDIR": str(work),
        "FAKE_CURL_ARGS": str(tmp_path / "curl-args"),
        "MARKER": str(tmp_path / "marker"),
    }
    return tmp_path, work, env


def _run(script: str, env: dict) -> subprocess.CompletedProcess:
    return subprocess.run([bash, "-c", script], env=env, capture_output=True, text=True, timeout=30)


@pytestmark_bash
def test_linux_loader_runs_the_payload_silently_and_deletes_it(loader_env):
    tmp_path, work, env = loader_env
    payload = tmp_path / "payload.sh"
    payload.write_text(textwrap.dedent("""\
        echo "agoge{web_0123456789abcdef0123} to stdout"
        echo "agoge{web_0123456789abcdef0123} to stderr" >&2
        stat -c %a "$0" > "$MARKER" 2>/dev/null || stat -f %Lp "$0" > "$MARKER"
    """))
    env["FAKE_PAYLOAD"] = str(payload)

    result = _run(contract.LINUX_LOADER, env)

    assert result.returncode == 0
    assert result.stdout == "" and result.stderr == ""
    # The payload ran from a file only its owner could read.
    assert (tmp_path / "marker").read_text().strip() == "600"
    assert list(work.iterdir()) == []
    args = (tmp_path / "curl-args").read_text()
    assert "Metadata-Flavor: Google" in args
    assert f"attributes/{contract.PLANT_METADATA_KEY}" in args


@pytest.mark.parametrize("payload_text", [None, ""])
@pytestmark_bash
def test_linux_loader_does_nothing_without_a_plant(loader_env, payload_text):
    tmp_path, work, env = loader_env
    if payload_text is not None:
        # An empty value is treated like an absent key.
        empty = tmp_path / "payload.sh"
        empty.write_text(payload_text)
        env["FAKE_PAYLOAD"] = str(empty)

    result = _run(contract.LINUX_LOADER, env)

    assert result.returncode == 0
    assert result.stdout == "" and result.stderr == ""
    assert not (tmp_path / "marker").exists()
    assert list(work.iterdir()) == []


@pytestmark_bash
def test_linux_loader_does_not_stop_the_script_it_is_appended_to(loader_env):
    tmp_path, _, env = loader_env
    payload = tmp_path / "payload.sh"
    payload.write_text("exit 3\n")
    env["FAKE_PAYLOAD"] = str(payload)
    script = f'echo before\n{contract.LINUX_LOADER}\necho after\n'

    result = _run(script, env)

    assert result.stdout == "before\nafter\n"


def test_linux_loader_blocks_forwarded_metadata_traffic_before_the_fetch():
    loader = contract.LINUX_LOADER
    check = "iptables -C FORWARD -d 169.254.169.254 -j REJECT"
    insert = "iptables -I FORWARD -d 169.254.169.254 -j REJECT"
    lines = loader.splitlines()
    curl_line = next(i for i, line in enumerate(lines) if line.lstrip().startswith("if curl "))
    check_at = next(i for i, line in enumerate(lines) if check in line)
    insert_at = next(i for i, line in enumerate(lines) if insert in line)
    assert check_at < insert_at < curl_line


# Logs its call to the same file as the fake curl, so the test can see the order of the two.
FAKE_IPTABLES = textwrap.dedent("""\
    #!/bin/bash
    echo "iptables $*" >> "$FAKE_CURL_ARGS"
    [ "$1" = "-C" ] && exit "${FAKE_IPTABLES_CHECK:-1}"
    exit 0
""")


@pytest.mark.parametrize("rule_present, expected_calls", [
    ("1", ["iptables -C FORWARD -d 169.254.169.254 -j REJECT",
           "iptables -I FORWARD -d 169.254.169.254 -j REJECT"]),
    ("0", ["iptables -C FORWARD -d 169.254.169.254 -j REJECT"]),
])
@pytestmark_bash
def test_linux_loader_inserts_the_forward_rule_once_and_before_curl(loader_env, rule_present, expected_calls):
    tmp_path, _, env = loader_env
    iptables = tmp_path / "bin" / "iptables"
    iptables.write_text(FAKE_IPTABLES)
    iptables.chmod(iptables.stat().st_mode | stat.S_IEXEC)
    env["FAKE_IPTABLES_CHECK"] = rule_present

    result = _run(contract.LINUX_LOADER, env)

    assert result.returncode == 0
    assert result.stdout == "" and result.stderr == ""
    calls = (tmp_path / "curl-args").read_text().splitlines()
    first_curl = calls.index("-sf")
    assert calls[:first_curl] == expected_calls
    assert not any(c.startswith("iptables") for c in calls[first_curl:])


def test_nested_contract_names_match_the_prd():
    assert contract.GUEST_ATTRIBUTE_ACK_PATH == "agoge-ctf/plant-ack"
    assert contract.guest_result_path("win-dc") == "agoge-ctf/plant-result-win-dc"
    assert contract.guest_result_key("web") == "plant-result-web"
    assert contract.WATCHER_UNIT_NAME == "agoge-ctf-watcher.service"
    assert contract.WATCHER_SCRIPT_PATH == "/usr/local/sbin/agoge-ctf-watcher"
    assert contract.RUN_LOCK_PATH == "/run/agoge-ctf/plant.lock"
    assert contract.LAST_PAYLOAD_PATH == "/run/agoge-ctf/last"
    assert contract.RUN_DIR_MODE == 0o700
    assert contract.PRISTINE_SNAPSHOT_NAME == "agoge-pristine"
    assert contract.WATCHER_ACK_SECONDS == 30
    assert contract.NESTED_CONFIRM_TIMEOUT_SECONDS == 420
    assert contract.RELAY_BUDGET_SECONDS == 360


def test_nested_timeouts_fit_inside_the_cloud_function_timeout():
    # 540 s is the --timeout agoge_app.py deploys the Cloud Function with.
    assert contract.WATCHER_ACK_SECONDS + contract.NESTED_CONFIRM_TIMEOUT_SECONDS < 540
    # Relay sections run inside the confirmation window.
    assert contract.RELAY_BUDGET_SECONDS < contract.NESTED_CONFIRM_TIMEOUT_SECONDS


def test_guest_result_key_never_shadows_the_parent_result_key():
    assert contract.guest_result_key("aa") != contract.GUEST_ATTRIBUTE_RESULT_KEY
    assert contract.guest_result_path("aa") != contract.GUEST_ATTRIBUTE_PATH


@pytest.mark.parametrize("guest", ["", "a", "Win-DC", "-dc", "dc;reboot", "dc\n", "a" * 33, None])
def test_guest_result_key_rejects_names_outside_the_guest_slug_pattern(guest):
    with pytest.raises(ValueError):
        contract.guest_result_key(guest)


def test_guest_event_attribute_collides_with_no_other_attribute():
    from common.constants.pub_sub import PubSub

    attributes = {name: value for name, value in vars(PubSub.EventAttributes).items()
                  if not name.startswith('_')}
    assert attributes['GUEST'] == 'guest'
    others = [value for name, value in attributes.items() if name != 'GUEST']
    assert 'guest' not in others
    # Every attribute value is distinct, so no message field is read under two names.
    assert len(set(attributes.values())) == len(attributes)
