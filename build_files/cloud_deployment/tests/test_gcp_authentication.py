import subprocess
from types import SimpleNamespace
from unittest.mock import MagicMock, call

import pytest

from cloud_deployment.operations.env_and_quotas import gcloud_environment_manager as auth_module
from cloud_deployment.operations.env_and_quotas.gcloud_environment_manager import (
    GcloudEnvironmentManager,
)
from cloud_deployment import setup_manager as setup_manager_module
from cloud_deployment.setup_manager import SetupManager
from cloud_deployment.utilities.menu_options import SetupOptions
from common.exceptions import AgogeValidationError


def _result(returncode=0, stdout="", stderr=""):
    return subprocess.CompletedProcess(
        args=["gcloud"],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


def test_refresh_credentials_keeps_interactive_prompts_visible(monkeypatch):
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    manager = GcloudEnvironmentManager(load_configurations=False)
    manager._run_gcloud = MagicMock(return_value=_result())
    manager.get_current_account = MagicMock(return_value="instructor@example.com")
    manager._credential_failures = MagicMock(return_value=[])
    manager.set_adc_quota_project = MagicMock()

    manager.refresh_credentials(
        account="instructor@example.com",
        quota_project="agoge-shared-resources",
        force=True,
    )

    assert manager._run_gcloud.call_args_list == [
        call(
            ["auth", "login", "instructor@example.com", "--force",
             "--project=agoge-shared-resources"],
            interactive=True,
        ),
        call(
            ["auth", "application-default", "login", "instructor@example.com",
             "--project=agoge-shared-resources"],
            interactive=True,
        ),
    ]
    manager.set_adc_quota_project.assert_called_once_with(
        "agoge-shared-resources"
    )


def test_ensure_credentials_synchronizes_adc_after_account_change():
    manager = GcloudEnvironmentManager(load_configurations=False)
    manager.refresh_credentials = MagicMock()

    manager.ensure_credentials(
        account="other@example.com",
        quota_project="agoge-shared-resources",
        synchronize=True,
    )

    manager.refresh_credentials.assert_called_once_with(
        account="other@example.com",
        quota_project="agoge-shared-resources",
        force=False,
    )


def test_ensure_credentials_rejects_invalid_noninteractive_credentials():
    manager = GcloudEnvironmentManager(load_configurations=False)
    manager._credential_failures = MagicMock(
        return_value=["Application Default Credentials are missing or expired"]
    )

    with pytest.raises(AgogeValidationError, match="--reauthenticate"):
        manager.ensure_credentials(
            account="instructor@example.com",
            prompt=False,
        )


def test_refresh_credentials_does_not_ignore_explicit_adc_override(monkeypatch):
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "stale-service-account.json")
    manager = GcloudEnvironmentManager(load_configurations=False)

    with pytest.raises(AgogeValidationError, match="GOOGLE_APPLICATION_CREDENTIALS"):
        manager.refresh_credentials(account="instructor@example.com")


def test_setup_manager_exposes_full_credential_refresh(monkeypatch):
    auth_manager = MagicMock()
    auth_manager.get_current_account.return_value = "instructor@example.com"
    factory = MagicMock(return_value=auth_manager)
    monkeypatch.setattr(setup_manager_module, "GcloudEnvironmentManager", factory)

    SetupManager(
        selection=SetupOptions.REFRESH_GCP_CREDENTIALS,
        project="agoge-test-project",
    ).run()

    factory.assert_called_once_with(load_configurations=False)
    auth_manager.refresh_credentials.assert_called_once_with(
        account="instructor@example.com",
        quota_project="agoge-test-project",
        force=True,
    )


@pytest.fixture
def credential_manager(monkeypatch):
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    manager = GcloudEnvironmentManager(load_configurations=False)
    manager.get_current_account = MagicMock(return_value="instructor@example.com")
    return manager


@pytest.mark.parametrize("initial_adc_account", [None, "old-account@example.com"])
def test_cached_cli_login_still_writes_selected_identity_to_adc(credential_manager, initial_adc_account):
    manager = credential_manager
    state = {"adc_account": initial_adc_account}
    events = []

    def run(args, **kwargs):
        if args[:2] == ["auth", "login"]:
            assert kwargs == {"interactive": True}
            assert "--force" not in args
            events.append("cached CLI login")
            # A cached CLI login succeeds without changing the ADC file.
            return _result(stderr="Re-using locally stored credentials")
        if args[:3] == ["auth", "application-default", "login"]:
            assert kwargs == {"interactive": True}
            state["adc_account"] = args[3]
            events.append("write ADC")
            return _result()
        if args[:2] == ["auth", "print-access-token"]:
            return _result(stdout="cli-token-do-not-print")
        if args[:3] == ["auth", "application-default", "print-access-token"]:
            events.append("validate ADC")
            if state["adc_account"]:
                return _result(stdout="adc-token-do-not-print")
            return _result(1, stderr="Your default credentials were not found")
        if args[:3] == ["auth", "application-default", "set-quota-project"]:
            assert state["adc_account"] == "instructor@example.com"
            events.append("set quota project")
            return _result()
        pytest.fail(f"Unexpected gcloud arguments: {args}")

    manager._run_gcloud = MagicMock(side_effect=run)
    manager.ensure_credentials(
        account="instructor@example.com", synchronize=True,
        quota_project="agoge-shared-resources",
    )

    assert state["adc_account"] == "instructor@example.com"
    assert events == ["cached CLI login", "write ADC", "validate ADC", "set quota project"]


@pytest.mark.parametrize("failed_step", ["cli", "adc"])
def test_failed_login_stops_before_validation_and_quota_update(credential_manager, failed_step):
    manager = credential_manager
    manager._run_gcloud = MagicMock(side_effect=[_result(1)] if failed_step == "cli" else [_result(), _result(1)])
    manager._credential_failures = MagicMock()
    manager.set_adc_quota_project = MagicMock()

    with pytest.raises(AgogeValidationError, match="--reauthenticate"):
        manager.refresh_credentials(account="instructor@example.com", force=False)

    assert manager._run_gcloud.call_count == (1 if failed_step == "cli" else 2)
    manager._credential_failures.assert_not_called()
    manager.set_adc_quota_project.assert_not_called()


def test_unexpected_login_identity_is_not_written_to_adc(credential_manager):
    manager = credential_manager
    manager.get_current_account.return_value = "unexpected@example.com"
    manager._run_gcloud = MagicMock(return_value=_result())
    manager.set_adc_quota_project = MagicMock()

    with pytest.raises(AgogeValidationError, match="selected account"):
        manager.refresh_credentials(account="instructor@example.com", force=False)

    manager._run_gcloud.assert_called_once()
    manager.set_adc_quota_project.assert_not_called()


def test_login_without_initial_account_uses_browser_selected_account_for_adc(credential_manager):
    manager = credential_manager
    manager._run_gcloud = MagicMock(return_value=_result())
    manager._credential_failures = MagicMock(return_value=[])

    manager.refresh_credentials(force=True)

    assert manager._run_gcloud.call_args_list == [
        call(["auth", "login", "--force"], interactive=True),
        call(["auth", "application-default", "login", "instructor@example.com"], interactive=True),
    ]


@pytest.mark.parametrize("stderr, expected", [
    ("invalid_grant: Token has been expired or revoked", "browser re-authentication"),
    ("invalid_rapt: reauth related error", "browser re-authentication"),
    ("Your default credentials were not found", "credential file was not found"),
    ("SSLError: certificate verify failed", "network, proxy, or TLS"),
    ("ConnectionError: connection reset", "network, proxy, or TLS"),
    ("PERMISSION_DENIED: serviceusage.services.use", "permission or quota-project"),
    ("JSONDecodeError: Expecting value", "credential file could not be parsed"),
    ("unexpected SDK failure", "gcloud exited with code 1"),
])
def test_adc_validation_reports_category_without_exposing_credentials(credential_manager, stderr, expected, capsys):
    manager = credential_manager
    manager._run_gcloud = MagicMock(side_effect=[
        _result(stdout="cli-access-token"),
        _result(1, stdout="adc-access-token", stderr=stderr + " refresh_token=secret-value"),
    ])

    failures = manager._credential_failures("instructor@example.com")

    assert len(failures) == 1
    assert "Application Default Credentials" in failures[0]
    assert expected in failures[0]
    assert "gcloud auth application-default print-access-token" in failures[0]
    output = " ".join(failures) + capsys.readouterr().out
    for secret in ["cli-access-token", "adc-access-token", "secret-value"]:
        assert secret not in output


def test_empty_token_output_is_reported_without_claiming_expiration(credential_manager):
    manager = credential_manager
    manager._run_gcloud = MagicMock(side_effect=[_result(stdout="cli-token"), _result(stdout=" \n")])
    failure, = manager._credential_failures("instructor@example.com")
    assert "no access token" in failure
    assert "expired" not in failure


def test_failed_validation_does_not_loop_or_set_quota_project(credential_manager, capsys):
    manager = credential_manager
    manager._run_gcloud = MagicMock(side_effect=[
        _result(), _result(), _result(stdout="cli-token"),
        _result(1, stderr="invalid_grant: expired or revoked"),
    ])
    manager.set_adc_quota_project = MagicMock()

    with pytest.raises(AgogeValidationError, match="browser re-authentication"):
        manager.refresh_credentials(account="instructor@example.com", force=False)

    assert manager._run_gcloud.call_count == 4
    manager.set_adc_quota_project.assert_not_called()
    assert "are ready" not in capsys.readouterr().out


@pytest.mark.parametrize("platform, redirect, terminal", [
    ("nt", "> $null", "PowerShell"),
    ("posix", "> /dev/null", "a terminal"),
])
def test_token_diagnostic_discards_stdout_in_the_correct_shell(monkeypatch, platform, redirect, terminal):
    monkeypatch.setattr(auth_module, "os", SimpleNamespace(name=platform))
    failure = GcloudEnvironmentManager._token_failure(
        "ADC", _result(1, stderr="unknown failure"),
        "gcloud auth application-default print-access-token",
    )
    assert f"print-access-token {redirect}` in {terminal}" in failure


@pytest.mark.parametrize("interactive", [True, False])
def test_gcloud_runner_preserves_command_arguments_and_prompt_visibility(credential_manager, monkeypatch, interactive):
    manager = credential_manager
    manager._gcloud = r"C:\Program Files\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd"
    run = MagicMock(return_value=_result())
    monkeypatch.setattr(auth_module.subprocess, "run", run)
    args = ["auth", "application-default", "login", "instructor@example.com"]

    manager._run_gcloud(args, interactive=interactive)

    run.assert_called_once_with(
        [manager._gcloud, *args], capture_output=not interactive,
        text=True, timeout=None, check=False,
    )
