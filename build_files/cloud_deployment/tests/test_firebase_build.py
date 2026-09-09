from unittest.mock import MagicMock
from types import SimpleNamespace
import traceback

import pytest
import requests
from google.api_core.exceptions import PermissionDenied

from cloud_deployment.operations.app_install_updates import agoge_app as app_module
from cloud_deployment.operations.app_install_updates import firebase_build as firebase_module
from cloud_deployment.operations.app_install_updates.agoge_app import AgogeApp, Commands
from common.constants.database import ADMIN_INFO_DOCUMENT, DbCollections
from common.exceptions import AgogeValidationError
from common.utilities.gcp.cloud_env import CloudEnv


@pytest.fixture
def firebase_cloud(monkeypatch):
    client = MagicMock()
    client.get_project.return_value = SimpleNamespace(project_id='tenant-project', name='projects/123456789')
    factory = MagicMock()
    factory.return_value.__enter__.return_value = client
    monkeypatch.setattr(firebase_module.resourcemanager_v3, 'ProjectsClient', factory)
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {'projectId': '123456789', 'authorizedDomains': ['app.example.edu']}
    response.__enter__.return_value = response
    request = MagicMock(return_value=response)
    monkeypatch.setattr(firebase_module.requests, 'get', request)
    return SimpleNamespace(client=client, response=response, request=request)


@pytest.fixture
def app(tmp_path, firebase_cloud):
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


@pytest.mark.parametrize('selection', [['0'], ['1', '1']])
def test_foreign_firebase_key_stops_deployment_even_with_matching_copied_number(
    app, firebase_cloud, monkeypatch, selection, capsys,
):
    # Reproduce the reported UALR response with the child's auth domain.
    app.env.project_number = '866926764305'
    firebase_cloud.response.json.return_value = {
        'projectId': '866926764305',
        'authorizedDomains': ['agoge-ualr.firebaseapp.com', 'app.example.edu'],
    }
    replies(monkeypatch, selection)
    app._deploy_react = MagicMock()
    with pytest.raises(AgogeValidationError, match='selects project 866926764305') as error:
        app.deploy_main_app()
    assert 'tenant-project (123456789)' in str(error.value)
    app._deploy_api.assert_not_called()
    app._deploy_react.assert_not_called()
    app.env.db.update.assert_not_called()
    assert not app.react_vite_env_file.exists()
    assert 'tenant-firebase-key' not in str(error.value) + capsys.readouterr().out
    firebase_cloud.client.get_project.assert_called_once_with(
        name='projects/tenant-project', retry=None, timeout=20,
    )


@pytest.mark.parametrize('project_id', ['123456789', 123456789, 'tenant-project'])
def test_key_validation_uses_metadata_and_browser_origin_without_key_in_url(
    app, firebase_cloud, project_id, capsys,
):
    app.env.main_app_url = 'https://old-tenant.example.edu'
    firebase_cloud.response.json.return_value['projectId'] = project_id
    firebase_module.validate_firebase_project(app.env)
    firebase_cloud.request.assert_called_once_with(
        'https://identitytoolkit.googleapis.com/v1/projects',
        headers={'X-Goog-Api-Key': 'tenant-firebase-key', 'Referer': 'https://app.example.edu/'},
        timeout=(5, 15), allow_redirects=False,
    )
    assert 'tenant-firebase-key' not in capsys.readouterr().out


@pytest.mark.parametrize('status', [302, 400, 403, 429, 500])
def test_firebase_http_failure_stops_build_without_revealing_response(app, firebase_cloud, monkeypatch, status):
    firebase_cloud.response.status_code = status
    firebase_cloud.response.json.side_effect = AssertionError('Do not log error response bodies or keys')
    replies(monkeypatch, ['0'])
    with pytest.raises(AgogeValidationError, match=f'HTTP {status}'):
        app.deploy_main_app()
    app._deploy_api.assert_not_called()
    app.env.db.update.assert_not_called()


@pytest.mark.parametrize('value', [{}, [], {'authorizedDomains': ['tenant-project.firebaseapp.com']}])
def test_incomplete_firebase_response_never_counts_as_key_verification(app, firebase_cloud, value):
    firebase_cloud.response.json.return_value = value
    with pytest.raises(AgogeValidationError, match='no project ID'):
        firebase_module.validate_firebase_project(app.env)


def test_network_error_suppresses_underlying_key_text(app, firebase_cloud):
    firebase_cloud.request.side_effect = requests.Timeout('request with tenant-firebase-key failed')
    with pytest.raises(AgogeValidationError) as error:
        firebase_module.validate_firebase_project(app.env)
    assert 'tenant-firebase-key' not in ''.join(traceback.format_exception(error.value))


def test_unavailable_project_metadata_stops_before_firebase_request(app, firebase_cloud):
    firebase_cloud.client.get_project.side_effect = PermissionDenied('denied')
    with pytest.raises(AgogeValidationError, match='project metadata'):
        firebase_module.validate_firebase_project(app.env)
    firebase_cloud.request.assert_not_called()


def test_missing_firebase_key_stops_before_cloud_verification(app, firebase_cloud):
    app.env._api_key = None
    app.env.get_secret = MagicMock(return_value=None)
    with pytest.raises(AgogeValidationError, match='Missing Firebase api_key'):
        firebase_module.validate_firebase_project(app.env)
    firebase_cloud.client.get_project.assert_not_called()
    firebase_cloud.request.assert_not_called()
