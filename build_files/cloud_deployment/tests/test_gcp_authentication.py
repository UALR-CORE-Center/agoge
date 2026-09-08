import subprocess
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

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

    manager._run_gcloud.assert_called_once_with(
        [
            "auth",
            "login",
            "instructor@example.com",
            "--update-adc",
            "--force",
            "--project=agoge-shared-resources",
        ],
        interactive=True,
    )
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
