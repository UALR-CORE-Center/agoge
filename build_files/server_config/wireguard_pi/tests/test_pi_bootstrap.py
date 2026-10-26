"""Hermetic tests: no root commands, real network, or host firewall changes."""
import base64
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import urllib.error
import urllib.request
from unittest.mock import Mock

import pytest


MODULE = Path(__file__).parents[1] / "agoge_wireguard_pi.py"
spec = importlib.util.spec_from_file_location("agoge_wireguard_pi", MODULE)
pi = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pi)
PUBLIC_KEY = base64.b64encode(b"p" * 32).decode("ascii")
GATEWAY_KEY = base64.b64encode(b"g" * 32).decode("ascii")
PRIVATE_KEY = base64.b64encode(b"s" * 32).decode("ascii")


def payload(**updates):
    data = {
        "unit_id": "abcdefghij", "kit_id": "factory-01", "device_id": "pi001",
        "hostname": "wg10000.example.edu.", "port": 51820,
        "gateway_public_key": GATEWAY_KEY, "peer_public_key": PUBLIC_KEY,
        "gateway_address": "10.254.254.1/30", "peer_address": "10.254.254.2/32",
        "equipment_subnet": "172.30.0.0/24", "student_subnets": ["10.20.0.0/24"],
        "allowed_ips": ["10.20.0.0/24", "10.254.254.1/32"],
        "service_ready": True, "tunnel_ready": False,
    }
    data.update(updates)
    return data


def config():
    return pi.validate_configuration(payload(), "factory-01", PUBLIC_KEY)


@pytest.mark.parametrize("updates", [
    {"kit_id": "factory-02"}, {"peer_public_key": GATEWAY_KEY},
    {"service_ready": False}, {"student_subnets": ["0.0.0.0/0"]},
    {"allowed_ips": ["0.0.0.0/0"]}, {"port": "51820; touch /tmp/pwn"},
    {"equipment_subnet": "10.20.0.0/24"}, {"equipment_subnet": "10.254.254.0/24"},
    {"hostname": "host\nPostUp=evil"}, {"unit_id": "../unit"},
    {"equipment_subnet": "127.0.0.0/8"}, {"student_subnets": ["192.0.2.0/24"]},
    {"peer_address": "10.254.254.1/32"}, {"peer_address": "10.99.0.1/32"},
])
def test_rejects_wrong_identity_or_unscoped_configuration(updates):
    with pytest.raises((ValueError, pi.ConfigurationUnavailable)):
        pi.validate_configuration(payload(**updates), "factory-01", PUBLIC_KEY)


def test_only_exact_lease_routes_are_rendered():
    rendered = pi.render_configuration(config(), PRIVATE_KEY, "8.8.8.8")
    assert "Address = 10.254.254.2/32" in rendered
    assert "AllowedIPs = 10.20.0.0/24, 10.254.254.1/32" in rendered
    assert "Endpoint = 8.8.8.8:51820" in rendered
    assert "PersistentKeepalive = 25" in rendered
    assert "PostUp" not in rendered
    assert "172.30.0.0/24" not in rendered


def test_keygen_retains_private_key_and_outputs_only_public_via_stdin(tmp_path, monkeypatch):
    key_path = tmp_path / "agoge.key"
    commands = []

    def runner(arguments, **kwargs):
        commands.append((arguments, kwargs))
        return PRIVATE_KEY if arguments == ["wg", "genkey"] else PUBLIC_KEY

    monkeypatch.setattr(pi, "run_command", runner)
    # Tests may run without root; emulate the owner's credential-file check.
    monkeypatch.setattr(pi, "private_file", lambda path: Path(path).read_text().strip())
    assert pi.ensure_key(key_path) == (PRIVATE_KEY, PUBLIC_KEY)
    assert pi.ensure_key(key_path) == (PRIVATE_KEY, PUBLIC_KEY)
    assert [arguments for arguments, _ in commands].count(["wg", "genkey"]) == 1
    assert key_path.stat().st_mode & 0o777 == 0o600
    assert all(PRIVATE_KEY not in str(arguments) for arguments, _ in commands)
    assert commands[-1][1]["input_text"] == PRIVATE_KEY + "\n"


def test_credential_file_rejects_permissions_and_symlinks(tmp_path):
    token = tmp_path / "token"
    token.write_text("SECRET")
    token.chmod(0o644)
    with pytest.raises(ValueError, match="0600"):
        pi.private_file(token)
    link = tmp_path / "linked-token"
    link.symlink_to(token)
    with pytest.raises(OSError):
        pi.private_file(link)


@pytest.mark.parametrize("url", [
    "http://api.example.edu", "https://token@api.example.edu",
    "https://api.example.edu?q=x", "https://api.example.edu/#fragment",
])
def test_only_trusted_https_base_url(url):
    with pytest.raises(ValueError):
        pi.configuration_url(url, "factory-01")


def test_site_prefix_is_preserved_and_kit_path_is_not_injectable():
    assert pi.configuration_url("https://api.example.edu/ualr/", "factory-01") == (
        "https://api.example.edu/ualr/wireguard/kits/factory-01/configuration/"
    )
    with pytest.raises(ValueError):
        pi.configuration_url("https://api.example.edu", "kit/../../another")


def test_redirect_is_never_followed_with_enrollment_bearer():
    with pytest.raises(pi.ConfigurationUnavailable):
        pi.NoRedirect().redirect_request(None, None, 302, "redirect", {}, "https://other.example")


def test_auth_failed_response_is_redacted_and_fails_closed(monkeypatch):
    monkeypatch.setattr(pi, "private_file", lambda path: "SECRET_ENROLLMENT_TOKEN")
    opener = Mock()
    opener.open.side_effect = urllib.error.HTTPError("url", 401, "SECRET_REMOTE_BODY", {}, None)
    monkeypatch.setattr(pi.urllib.request, "build_opener", lambda *args: opener)
    with pytest.raises(pi.ConfigurationUnavailable) as error:
        pi.fetch_configuration("https://api.example.edu/ualr", "factory-01", "token")
    assert str(error.value) == "Authenticated configuration is unavailable"
    assert "SECRET" not in str(error.value)
    request = opener.open.call_args.args[0]
    assert request.get_header("Authorization") == "Bearer SECRET_ENROLLMENT_TOKEN"
    assert opener.open.call_args.kwargs["timeout"] == 15


def test_success_api_response_unwrap_and_size_limit(monkeypatch):
    monkeypatch.setattr(pi, "private_file", lambda path: "secret")
    response = io.BytesIO(json.dumps({"data": payload()}).encode())
    monkeypatch.setattr(pi.urllib.request, "build_opener", lambda *args: Mock(open=lambda *a, **k: response))
    assert pi.fetch_configuration("https://api.example.edu", "factory-01", "token")["kit_id"] == "factory-01"
    response = io.BytesIO(b"x" * (pi.MAX_RESPONSE_BYTES + 1))
    with pytest.raises(pi.ConfigurationUnavailable):
        pi.fetch_configuration("https://api.example.edu", "factory-01", "token")


def test_dns_is_refreshed_and_private_destinations_rejected(monkeypatch):
    resolver = Mock(side_effect=[
        [(2, 2, 17, "", ("8.8.8.8", 51820))],
        [(2, 2, 17, "", ("8.8.4.4", 51820))],
        [(2, 2, 17, "", ("127.0.0.1", 51820))],
    ])
    monkeypatch.setattr(pi.socket, "getaddrinfo", resolver)
    assert pi.resolve_endpoint("wg.example.edu", 51820) == "8.8.8.8"
    assert pi.resolve_endpoint("wg.example.edu", 51820) == "8.8.4.4"
    with pytest.raises(pi.ConfigurationUnavailable):
        pi.resolve_endpoint("wg.example.edu", 51820)


def test_apply_updates_dns_then_revokes_only_managed_rules(tmp_path):
    commands = []
    controller = pi.Controller(tmp_path / "agoge.conf", "eth0", nat=True, runner=commands.append)
    assert controller.apply(config(), PRIVATE_KEY, "8.8.8.8")
    assert (tmp_path / "agoge.conf").stat().st_mode & 0o777 == 0o600
    assert any(command[-1] == "MASQUERADE" and "172.30.0.0/24" in command for command in commands)
    assert any("ESTABLISHED,RELATED" in command for command in commands)
    assert not any(PRIVATE_KEY in str(command) for command in commands)
    assert not controller.apply(config(), PRIVATE_KEY, "8.8.8.8")
    assert controller.apply(config(), PRIVATE_KEY, "8.8.4.4")
    assert "Endpoint = 8.8.4.4:51820" in (tmp_path / "agoge.conf").read_text()
    controller.deactivate()
    assert not (tmp_path / "agoge.conf").exists()
    assert controller.current is None
    assert not any(command == ["iptables", "-F"] for command in commands)


def test_failed_config_apply_disconnects_and_removes_secret_file(tmp_path):
    commands = []

    def runner(arguments):
        commands.append(arguments)
        if arguments[:2] == ["wg-quick", "up"]:
            raise RuntimeError("network command failed")

    controller = pi.Controller(tmp_path / "agoge.conf", "eth0", runner=runner)
    with pytest.raises(RuntimeError):
        controller.apply(config(), PRIVATE_KEY, "8.8.8.8")
    assert controller.current is None
    assert not (tmp_path / "agoge.conf").exists()
    assert commands.count(["wg-quick", "down", str(tmp_path / "agoge.conf")]) == 2


def test_failed_interface_teardown_retains_drop_guards(tmp_path):
    commands = []

    def runner(arguments):
        commands.append(arguments)
        if arguments[:2] == ["wg-quick", "down"] or arguments[:3] == ["ip", "link", "delete"]:
            raise RuntimeError("teardown failure")

    controller = pi.Controller(tmp_path / "agoge.conf", "eth0", runner=runner)
    with pytest.raises(RuntimeError, match="deactivate"):
        controller.deactivate()
    assert not any(arguments[0] == "iptables" for arguments in commands)


def test_poll_revokes_on_auth_or_network_failure_and_never_logs_secret(monkeypatch, caplog):
    stop = Mock()
    stop.is_set.side_effect = [False, False, True]
    monkeypatch.setattr(pi, "ensure_key", lambda path: (PRIVATE_KEY, PUBLIC_KEY))
    controller = Mock()
    monkeypatch.setattr(pi, "Controller", lambda *a, **k: controller)
    fetch = Mock(side_effect=[payload(), pi.ConfigurationUnavailable("SECRET REMOTE TOKEN")])
    monkeypatch.setattr(pi, "fetch_configuration", fetch)
    monkeypatch.setattr(pi, "resolve_endpoint", lambda *a: "8.8.8.8")
    pi.poll({"api_url": "https://api.example.edu", "kit_id": "factory-01", "token_file": "token",
             "equipment_interface": "eth0"}, stop)
    assert controller.apply.call_count == 1
    assert controller.deactivate.call_count == 3  # startup, failed auth, shutdown
    assert "SECRET" not in caplog.text
    assert "disconnected" in caplog.text


def test_commands_do_not_use_shell_or_emit_sensitive_output(monkeypatch):
    run = Mock(return_value=Mock(returncode=0, stdout=PUBLIC_KEY + "\n"))
    monkeypatch.setattr(pi.subprocess, "run", run)
    assert pi.run_command(["wg", "pubkey"], input_text=PRIVATE_KEY, capture=True) == PUBLIC_KEY
    assert "shell" not in run.call_args.kwargs
    assert PRIVATE_KEY not in str(run.call_args.args)
    assert run.call_args.kwargs["stderr"] == subprocess.DEVNULL


def test_installer_bash_syntax():
    subprocess.run(["bash", "-n", str(MODULE.parent / "install.sh")], check=True)
