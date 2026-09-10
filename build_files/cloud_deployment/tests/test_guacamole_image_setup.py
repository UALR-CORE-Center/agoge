from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from google.api_core.exceptions import NotFound, PermissionDenied
from google.cloud import compute_v1

from cloud_deployment.operations.guacamole_image_management import guacamole_image_manager as guac_module
from cloud_deployment.operations.guacamole_image_management.guacamole_image_manager import GuacamoleImageManager
from common.constants.database import DbCollections


@pytest.fixture
def setup(monkeypatch):
    manager = object.__new__(GuacamoleImageManager)
    manager.project = 'tenant-project'
    manager.env = SimpleNamespace(
        project=manager.project, default_server_image_project='shared-images', parent_project='parent-project',
    )
    manager.db = MagicMock()
    manager.image_manager = MagicMock()
    manager._get_guac_startup_script = MagicMock(return_value='#!/bin/bash\necho setup')
    manager._verify_certificate_operation = MagicMock()
    client = MagicMock()
    client.get.return_value = compute_v1.Image(
        status='READY',
        self_link='https://www.googleapis.com/compute/v1/projects/shared-images/global/images/image-guac-base',
    )
    monkeypatch.setattr(guac_module.compute_v1, 'ImagesClient', lambda: client)
    monkeypatch.setattr(guac_module.time, 'sleep', lambda _: None)
    return manager, client


def test_shared_image_source_and_tenant_vm_identity_are_kept_separate(setup):
    manager, client = setup
    assert manager.create_guac_project_image() is True
    client.get.assert_called_once_with(project='shared-images', image='image-guac-base')
    inserted = manager.db.insert.call_args.kwargs
    assert inserted['collection_name'] == DbCollections.IMAGE
    assert inserted['data']['self_link'] == client.get.return_value.self_link
    assert inserted['data']['name'] == 'guac-tenant-project'
    assert inserted['data']['image'] == 'image-guac-base'
    manager.image_manager.load.assert_called_once_with(server_name='guac-tenant-project')
    manager.image_manager.check_out.assert_called_once_with()
    manager.image_manager.check_in.assert_called_once_with()


@pytest.mark.parametrize('parent, expected', [('parent-project', 'parent-project'), (None, 'tenant-project')])
def test_image_project_fallbacks(setup, parent, expected):
    manager, client = setup
    manager.env.default_server_image_project = None
    manager.env.parent_project = parent
    manager._resolve_base_image()
    client.get.assert_called_once_with(project=expected, image='image-guac-base')


@pytest.mark.parametrize('error, message', [
    (NotFound('missing'), 'was not found'),
    (PermissionDenied('denied'), 'Cannot access'),
])
def test_missing_or_inaccessible_source_stops_before_secret_reads_and_writes(setup, error, message):
    manager, client = setup
    client.get.side_effect = error
    with pytest.raises(RuntimeError, match=message) as raised:
        manager.create_guac_project_image()
    assert 'projects/shared-images/global/images/image-guac-base' in str(raised.value)
    assert raised.value.__cause__ is error
    # Do not silently try an unrelated image in the tenant or another project.
    assert client.get.call_count == 1
    manager._get_guac_startup_script.assert_not_called()
    manager.db.insert.assert_not_called()
    manager.image_manager.load.assert_not_called()
    manager.image_manager.check_out.assert_not_called()


@pytest.mark.parametrize('status', ['PENDING', 'FAILED'])
def test_unready_source_does_not_replace_the_existing_image_record(setup, status):
    manager, client = setup
    client.get.return_value.status = status
    with pytest.raises(RuntimeError, match='not ready'):
        manager.create_guac_project_image()
    manager._get_guac_startup_script.assert_not_called()
    manager.db.insert.assert_not_called()
    manager.image_manager.check_out.assert_not_called()
