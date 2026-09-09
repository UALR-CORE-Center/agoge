from unittest.mock import MagicMock

import pytest
from google.api_core.exceptions import PermissionDenied

from cloud_deployment.operations.app_install_updates import agoge_app as app_module
from cloud_deployment.operations.app_install_updates.agoge_app import AgogeApp, Commands
from common.constants.database import ADMIN_INFO_DOCUMENT, DbCollections
from common.exceptions import AgogeValidationError
from common.utilities.gcp.cloud_env import CloudEnv


@pytest.fixture
def app(tmp_path):
    env = object.__new__(CloudEnv)
    env.env_dict = {
        'project': 'tenant-project', 'parent_project': 'parent-project',
        'parent_dns_suffix': '.example.edu', 'project_path': 'test-dev',
        'region': 'us-central1', 'zone': 'us-central1-a',
    }
    env._assign_variables()
    env._api_key = 'tenant-firebase-key'
    env.db = MagicMock()
    result = object.__new__(AgogeApp)
    result.env = env
    result.commands = Commands(env)
    result.fastapi_env_file = tmp_path / 'api.env'
    result.react_vite_env_file = tmp_path / '.env.production'
    result._deploy_api = MagicMock(return_value=True)
    return result


def replies(monkeypatch, values):
    answers = iter(values)
    monkeypatch.setattr('builtins.input', lambda _: next(answers))


@pytest.mark.parametrize('selection', [['0'], ['1', '1']])
@pytest.mark.parametrize('existing', [None, 'auth.example.edu'])
@pytest.mark.parametrize('build_succeeds', [True, False])
def test_generated_tenant_settings_reach_build_and_original_files_are_restored(
    app, monkeypatch, selection, existing, build_succeeds,
):
    if existing:
        app.env.env_dict['firebase_auth_domain'] = existing
        app.env.firebase_auth_domain = existing
    old_contents = 'VITE_FIREBASE_AUTH_DOMAIN=stale.example.edu\nVITE_PROJECT_ID=wrong-project\n'
    app.react_vite_env_file.write_text(old_contents)
    replies(monkeypatch, selection + ([''] if existing else []))

    def build(command):
        # Run through the real _deploy_react/_deploy_cloud_run path and
        # inspect the file at the exact point it is submitted to Cloud Build.
        assert '--project=tenant-project' in command
        if command.startswith('gcloud builds submit'):
            values = app._read_env_file(app.react_vite_env_file)
            assert values['VITE_FIREBASE_AUTH_DOMAIN'] == 'tenant-project.firebaseapp.com'
            assert values['VITE_PROJECT_ID'] == 'tenant-project'
            assert values['VITE_FIREBASE_KEY'] == 'tenant-firebase-key'
            assert values['VITE_PROJECT_PATH'] == '/test-dev/'
            assert values['VITE_AGOGE_API_URL'] == 'https://api.example.edu/'
            return build_succeeds
        return True

    app._stream_command_output = MagicMock(side_effect=build)
    assert app.deploy_main_app() is build_succeeds
    assert app.react_vite_env_file.read_text() == old_contents
    assert not app.fastapi_env_file.exists()
    app.env.db.update.assert_called_once_with(
        collection_name=DbCollections.ADMIN_INFO, doc_id=ADMIN_INFO_DOCUMENT,
        data={'firebase_auth_domain': 'tenant-project.firebaseapp.com'},
    )
    if not build_succeeds:
        assert app._stream_command_output.call_count == 1


def test_first_install_removes_generated_files_even_if_build_raises(app, monkeypatch):
    replies(monkeypatch, ['1', '1'])
    app._stream_command_output = MagicMock(side_effect=RuntimeError('build interrupted'))
    with pytest.raises(RuntimeError, match='interrupted'):
        app.deploy_main_app()
    assert not app.fastapi_env_file.exists()
    assert not app.react_vite_env_file.exists()


def test_custom_domain_can_be_kept(app, monkeypatch, capsys):
    app.env.env_dict['firebase_auth_domain'] = 'auth.tenant.example.edu'
    replies(monkeypatch, ['1', '1', 'K'])

    def deploy():
        assert app._read_env_file(app.react_vite_env_file)['VITE_FIREBASE_AUTH_DOMAIN'] == 'auth.tenant.example.edu'
        return True

    app._deploy_react = deploy
    assert app.deploy_main_app()
    app.env.db.update.assert_not_called()
    assert 'https://auth.tenant.example.edu/__/auth/handler' in capsys.readouterr().out


@pytest.mark.parametrize('cause', ['cancel', 'permission', 'invalid-domain'])
def test_preflight_failure_stops_before_files_or_build_change(app, monkeypatch, cause):
    app.env.env_dict['firebase_auth_domain'] = 'auth.example.edu'
    if cause == 'invalid-domain':
        app.env.env_dict['firebase_auth_domain'] = 'https://auth.example.edu/path'
    if cause == 'permission':
        app.env.db.update.side_effect = PermissionDenied('denied')
    replies(monkeypatch, ['0', {'cancel': 'C', 'permission': '', 'invalid-domain': 'K'}[cause]])
    with pytest.raises((AgogeValidationError, PermissionDenied)):
        app.deploy_main_app()
    assert not app.react_vite_env_file.exists()
    app._deploy_api.assert_not_called()


def test_api_only_does_not_prompt_for_or_read_firebase_key(app, monkeypatch):
    app.env.env_dict['firebase_auth_domain'] = 'auth.example.edu'
    app.env._api_key = None
    app.env.get_secret = MagicMock(side_effect=AssertionError('Firebase key must not be read'))
    replies(monkeypatch, ['1', '0'])
    assert app.deploy_main_app()
    app.env.db.update.assert_not_called()
    app.env.get_secret.assert_not_called()


def test_copied_environment_with_wrong_project_cannot_target_another_tenant(app, monkeypatch):
    monkeypatch.setattr(app_module, 'CloudEnv', lambda **_: app.env)
    with pytest.raises(AgogeValidationError, match='does not match'):
        AgogeApp(project='different-project')
