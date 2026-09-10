from copy import deepcopy
import importlib.util
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from cloud_deployment.operations.env_and_quotas import project_menu as menu_module
from cloud_deployment.operations.env_and_quotas.gcloud_environment_manager import GcloudEnvironmentManager
from cloud_deployment.operations.env_and_quotas.project_menu import ProjectMenu
from common.constants.build_constants import BuildConstants
from common.constants.database import DATABASE_NAME, DatabaseTypes, DbCollections
from common.exceptions import AgogeValidationError


@pytest.fixture
def registry(monkeypatch):
    records = {
        'old-test-project': {'tenant_name': 'Agoge Test'},
        'test-dev-787001': {'tenant_name': 'Test'},
        'other-project': {'tenant_name': 'Other'},
    }
    for project_id, record in records.items():
        record.update(project_name=project_id, impersonation_account=f'agoge-service@{project_id}.iam.gserviceaccount.com')
    db = MagicMock()
    db.query.side_effect = lambda **_: deepcopy(list(records.values()))
    db.get.side_effect = lambda doc_id, **_: deepcopy(records.get(doc_id, {}))
    db.update.side_effect = lambda doc_id, data, **_: records[doc_id].update(data)
    factory = MagicMock(return_value=db)
    monkeypatch.setattr(menu_module.DocumentDatabaseFactory, 'create_db_object', factory)
    return records, db, factory


def test_requested_menu_edits_persist_without_deleting_or_renaming_projects(registry):
    records, db, factory = registry
    original = deepcopy(records)
    menu = ProjectMenu()
    factory.assert_called_once_with(
        db_type=DatabaseTypes.firestore, database_name=DATABASE_NAME,
        project_id=BuildConstants.SharedResourceProjects.MAIN_SHARED_RESOURCE_PROJECT,
    )
    menu.update(hide=['Agoge Test'], rename=[('test-dev-787001', 'test-dev')])
    configurations = GcloudEnvironmentManager().configurations
    assert list(configurations) == ['test-dev', 'Other']
    assert configurations['test-dev']['project_id'] == 'test-dev-787001'
    assert records['test-dev-787001']['tenant_name'] == 'Test'
    assert records['other-project'] == original['other-project']
    assert db.update.call_count == 2
    for call in db.update.call_args_list:
        assert set(call.kwargs['data']) <= {'setup_menu_hidden', 'setup_menu_name'}
        assert call.kwargs['collection_name'] == DbCollections.PROJECT_INFO
    db.delete.assert_not_called()
    # Re-running the same command, even by the old label, is a no-op.
    menu.update(hide=['Agoge Test'], rename=[('Test', 'test-dev')])
    assert db.update.call_count == 2
    menu.update(show=['old-test-project'])
    assert 'Agoge Test' in menu.configurations()


@pytest.mark.parametrize('rename', [[('missing', 'test-dev')], [('Test', '')]])
def test_invalid_rename_does_not_partially_apply_hide(registry, rename):
    _, db, _ = registry
    with pytest.raises(AgogeValidationError):
        ProjectMenu().update(hide=['Agoge Test'], rename=rename)
    db.update.assert_not_called()


def test_duplicate_labels_remain_selectable_and_name_updates_require_unique_match(registry):
    records, db, _ = registry
    records['other-project']['tenant_name'] = 'Test'
    menu = ProjectMenu()
    names = menu.configurations()
    assert names['Test [test-dev-787001]']['project_id'] == 'test-dev-787001'
    assert names['Test [other-project]']['project_id'] == 'other-project'
    with pytest.raises(AgogeValidationError, match='matched 2'):
        menu.update(rename=[('Test', 'test-dev')])
    db.update.assert_not_called()


def test_missing_registry_document_prevents_partial_writes(registry):
    _, db, _ = registry
    db.get.return_value = {}
    db.get.side_effect = None
    with pytest.raises(AgogeValidationError, match='No matching'):
        ProjectMenu().update(hide=['Agoge Test'], rename=[('Test', 'test-dev')])
    db.update.assert_not_called()


def test_empty_menu_does_not_prompt_forever(registry, monkeypatch):
    records, _, _ = registry
    for record in records.values():
        record['setup_menu_hidden'] = True
    monkeypatch.setattr('builtins.input', lambda _: pytest.fail('No menu to select'))
    with pytest.raises(AgogeValidationError, match='No visible environments'):
        GcloudEnvironmentManager().select_environment()


def test_setup_flags_authenticate_apply_edits_and_exit_without_deployment(registry, monkeypatch):
    records, _, _ = registry
    spec = importlib.util.spec_from_file_location('agoge_setup_cli', Path(__file__).resolve().parents[3] / 'setup.py')
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    manager = MagicMock()
    manager.get_current_account.return_value = 'admin@example.edu'
    manager.set_account.return_value = 'admin@example.edu'
    events = []
    manager.ensure_credentials.side_effect = lambda **_: events.append('authenticated')
    monkeypatch.setattr(cli, 'GcloudEnvironmentManager', lambda **_: manager)
    real_menu = ProjectMenu()

    def menu_factory():
        assert events == ['authenticated']
        return real_menu

    monkeypatch.setattr(cli, 'ProjectMenu', menu_factory)
    deployment = MagicMock()
    monkeypatch.setattr(cli, 'SetupManager', deployment)
    monkeypatch.setattr('sys.argv', [
        'setup.py', '--hide-environment', 'Agoge Test',
        '--rename-environment', 'test-dev-787001', 'test-dev',
    ])
    cli.main()
    assert records['old-test-project']['setup_menu_hidden'] is True
    assert records['test-dev-787001']['setup_menu_name'] == 'test-dev'
    manager.display_menu.assert_called_once()
    manager.select_environment.assert_not_called()
    manager.switch_environment.assert_not_called()
    deployment.assert_not_called()
