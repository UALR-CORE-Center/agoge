import re
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from google.api_core.exceptions import NotFound

from cloud_deployment.operations.project_manager import Environment, ProjectManager
from common.exceptions import AgogeValidationError


def _manager() -> ProjectManager:
    manager = object.__new__(ProjectManager)
    manager.production_folder_id = "267924026470"
    manager.development_folder_id = "997842458280"
    manager.billing_account_id = "01DA03-A4053E-869DE5"
    manager.folder_client = MagicMock()
    manager.resource_client = MagicMock()
    manager.billing_client = MagicMock()
    return manager


def test_project_id_is_normalized_for_gcp(monkeypatch):
    monkeypatch.setattr(
        "cloud_deployment.operations.project_manager.random.randint",
        lambda *_: 123456,
    )

    project_id = ProjectManager._generate_project_id("Test Client!", Environment.DEV)

    assert project_id == "test-client-dev-123456"
    assert len(project_id) <= 30
    assert re.fullmatch(r"[a-z][a-z0-9-]{4,28}[a-z0-9]", project_id)


def test_project_creation_checks_folder_permission_and_sets_real_labels():
    manager = _manager()
    manager.folder_client.test_iam_permissions.return_value = SimpleNamespace(
        permissions=["resourcemanager.projects.create"]
    )
    operation = MagicMock()
    manager.resource_client.create_project.return_value = operation

    manager._create_gcp_project(
        "test-client-dev-123456",
        "Test Client!",
        Environment.DEV,
    )

    manager.folder_client.test_iam_permissions.assert_called_once_with(
        resource="folders/997842458280",
        permissions=["resourcemanager.projects.create"],
    )
    request = manager.resource_client.create_project.call_args.kwargs["request"]
    assert request.project.project_id == "test-client-dev-123456"
    assert request.project.parent == "folders/997842458280"
    assert dict(request.project.labels) == {
        "customer": "test-client",
        "env": "dev",
    }
    operation.result.assert_called_once_with()


def test_project_creation_stops_before_api_call_when_permission_is_missing():
    manager = _manager()
    manager.folder_client.test_iam_permissions.return_value = SimpleNamespace(
        permissions=[]
    )

    with pytest.raises(
        AgogeValidationError,
        match="roles/resourcemanager.projectCreator",
    ):
        manager._create_gcp_project(
            "test-client-dev-123456",
            "Test Client",
            Environment.DEV,
        )

    manager.resource_client.create_project.assert_not_called()


def test_hidden_or_missing_folder_has_actionable_authentication_error():
    manager = _manager()
    manager.folder_client.test_iam_permissions.side_effect = NotFound(
        "Permission denied on resource or it may not exist"
    )

    with pytest.raises(AgogeValidationError) as error:
        manager._create_gcp_project(
            "test-client-dev-123456",
            "Test Client",
            Environment.DEV,
        )

    assert "folders/997842458280" in str(error.value)
    assert "python setup.py --reauthenticate" in str(error.value)
    assert "AGOGE_DEVELOPMENT_FOLDER_ID" in str(error.value)
    manager.resource_client.create_project.assert_not_called()


def test_folder_id_override_must_be_numeric():
    manager = _manager()
    manager.development_folder_id = "folders/not-a-number"

    with pytest.raises(AgogeValidationError, match="numeric GCP folder ID"):
        manager._create_gcp_project(
            "test-client-dev-123456",
            "Test Client",
            Environment.DEV,
        )

    manager.folder_client.test_iam_permissions.assert_not_called()
