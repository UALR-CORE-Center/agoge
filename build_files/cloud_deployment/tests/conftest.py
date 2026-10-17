import pytest

from cloud_deployment.utilities import console as ui


@pytest.fixture(autouse=True)
def isolated_deploy_logs(tmp_path, monkeypatch):
    """Keep task-board logs out of the working tree."""
    monkeypatch.setattr(ui, 'LOG_ROOT', tmp_path / 'deploy_logs')
