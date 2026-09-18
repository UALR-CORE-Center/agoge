from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from cloud_deployment.operations.images_and_specs import public_image_catalog as module
from cloud_deployment import setup_manager as setup_manager_module
from cloud_deployment.utilities.menu_options import SetupCategories, SetupOptions, category_menu


@pytest.fixture
def catalog(monkeypatch):
    env = SimpleNamespace(project='selected-child', get_env=lambda: {'project': 'selected-child'})
    environment = Mock(return_value=env)
    sync = Mock()
    sync.return_value.sync.return_value = {
        'image_count': 3, 'enabled_count': 3,
        'project_counts': {'ubuntu-os-cloud': 3}, 'failed_projects': {},
    }
    monkeypatch.setattr(module, 'CloudEnv', environment)
    monkeypatch.setattr(module, 'GoogleImageSyncManager', sync)
    return environment, sync


def test_catalog_sync_uses_selected_project_and_prints_counts(catalog, capsys):
    environment, sync = catalog

    assert module.PublicImageCatalog('selected-child').run() is True

    environment.assert_called_once_with(project='selected-child')
    sync.assert_called_once_with(env={'project': 'selected-child'})
    assert 'ubuntu-os-cloud: 3 image families refreshed' in capsys.readouterr().out


def test_mismatched_environment_stops_before_sync(catalog):
    environment, sync = catalog
    environment.return_value.project = 'wrong-child'

    assert module.PublicImageCatalog('selected-child').run() is False
    sync.assert_not_called()


def test_partial_sync_identifies_failed_publisher(catalog, capsys):
    _, sync = catalog
    sync.return_value.sync.return_value['failed_projects'] = {'cos-cloud': 'Access denied'}

    assert module.PublicImageCatalog('selected-child').run() is False
    assert 'Could not refresh cos-cloud: Access denied' in capsys.readouterr().out


def test_failed_sync_prints_recovery_command(catalog, capsys):
    _, sync = catalog
    sync.return_value.sync.side_effect = RuntimeError('Database unavailable')

    assert module.PublicImageCatalog('selected-child').run() is False
    output = capsys.readouterr().out
    assert 'Database unavailable' in output
    assert 'Synchronize Public OS Images' in output


def test_catalog_menu_runs_without_application_deployment(monkeypatch):
    catalog = Mock()
    app = Mock()
    monkeypatch.setattr(setup_manager_module, 'PublicImageCatalog', catalog)
    monkeypatch.setattr(setup_manager_module, 'AgogeApp', app)

    setup_manager_module.SetupManager(SetupOptions.SYNC_PUBLIC_IMAGES, 'selected-child').run()

    catalog.assert_called_once_with(project='selected-child')
    catalog.return_value.run.assert_called_once_with()
    app.assert_not_called()
    options = [option for option, _ in category_menu[SetupCategories.IMAGES_AND_SPECS]['options']]
    assert SetupOptions.SYNC_PUBLIC_IMAGES in options
