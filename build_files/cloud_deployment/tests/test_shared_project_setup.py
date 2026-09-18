from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from google.api_core.exceptions import NotFound, PermissionDenied
from google.cloud import secretmanager
from google.iam.v1 import policy_pb2

from api.app_config import AppConfig
from cloud_deployment.operations.app_install_updates import agoge_app as app_module
from cloud_deployment.operations.app_install_updates.agoge_app import AgogeApp
from cloud_deployment.operations.env_and_quotas import environment_variables as env_module
from cloud_deployment.operations.env_and_quotas import shared_api_secrets as secret_module
from cloud_deployment.operations.env_and_quotas.environment_variables import EnvironmentVariables
from common.utilities.gcp.cloud_env import CloudEnv


@pytest.fixture
def environment():
    env = object.__new__(EnvironmentVariables)
    env.project = 'tenant-project'
    env.env = {'project': env.project, 'parent_project': 'parent-project', 'rubric_support': False}
    env.db = MagicMock()
    env.secret_client = MagicMock()
    env.secret_client.get_secret_version.return_value = secretmanager.SecretVersion(
        state=secretmanager.SecretVersion.State.ENABLED,
    )
    return env


def test_all_setup_skips_legacy_fields(environment, monkeypatch):
    monkeypatch.setattr('builtins.input', lambda _: 'A')
    environment.set_variable = MagicMock()
    for method in ('_set_region', '_set_zone', '_set_timezone', '_set_guacamole_variables'):
        monkeypatch.setattr(environment, method, MagicMock())
    environment.run()
    prompted = {call.args[0] for call in environment.set_variable.call_args_list}
    assert not prompted.intersection({
        'dns_suffix', 'dnszone', 'dns_zone', 'app_sub_domain',
        'main_app_url', 'firebase_auth_subdomain', 'firebase_auth_domain',
    })
    assert {'parent_project', 'parent_dnszone', 'parent_dns_suffix', 'project_path'} <= prompted


def test_parent_selection_uses_metadata_only(environment, monkeypatch, capsys):
    monkeypatch.setattr('builtins.input', lambda _: 'P')
    environment.set_variable('openai_api_key')
    assert environment.env['shared_api_secrets'] == ['openai_api_key']
    assert environment.env['rubric_support'] is False
    environment.secret_client.access_secret_version.assert_not_called()
    environment.secret_client.add_secret_version.assert_not_called()
    assert 'parent reference' in capsys.readouterr().out


def test_copy_stores_locally_then_disables_parent_reference(environment, monkeypatch, capsys):
    environment.env['shared_api_secrets'] = ['sendgrid_api_key', 'openai_api_key']
    environment.secret_client.access_secret_version.return_value = SimpleNamespace(
        payload=SimpleNamespace(data=b'sensitive-parent-key')
    )
    monkeypatch.setattr('builtins.input', lambda _: 'C')
    environment.set_variable('openai_api_key')
    environment.secret_client.access_secret_version.assert_called_once_with(request={
        'name': 'projects/parent-project/secrets/openai_api_key/versions/latest',
    })
    environment.secret_client.add_secret_version.assert_called_once_with(request={
        'parent': 'projects/tenant-project/secrets/openai_api_key',
        'payload': {'data': b'sensitive-parent-key'},
    })
    assert environment.env['shared_api_secrets'] == ['sendgrid_api_key']
    assert environment.env['rubric_support'] is False
    assert 'sensitive-parent-key' not in capsys.readouterr().out


def test_copy_failure_leaves_source_unchanged(environment, monkeypatch):
    environment.env['shared_api_secrets'] = ['openai_api_key']
    environment.secret_client.access_secret_version.side_effect = PermissionDenied('denied')
    monkeypatch.setattr('builtins.input', lambda _: 'C')
    with pytest.raises(PermissionDenied):
        environment.set_variable('openai_api_key')
    assert environment.env['shared_api_secrets'] == ['openai_api_key']
    environment.db.update.assert_not_called()
    environment.secret_client.add_secret_version.assert_not_called()


@pytest.mark.parametrize('rubric_support', [False, True])
def test_local_key_is_hidden_and_does_not_change_rubric_setting(environment, monkeypatch, rubric_support):
    environment.env['rubric_support'] = rubric_support
    environment.env['shared_api_secrets'] = ['openai_api_key']
    replies = iter(['L', 'Y'])
    prompts = []

    def answer(prompt):
        prompts.append(prompt)
        return next(replies)

    monkeypatch.setattr('builtins.input', answer)
    monkeypatch.setattr(env_module, 'getpass', lambda _: 'sensitive-local-key')
    environment.set_variable('openai_api_key')
    assert environment.env['rubric_support'] is rubric_support
    assert environment.env['shared_api_secrets'] == []
    assert all('sensitive-local-key' not in prompt for prompt in prompts)
    environment.secret_client.access_secret_version.assert_not_called()


def test_empty_local_key_does_not_change_source(environment, monkeypatch):
    environment.env['shared_api_secrets'] = ['openai_api_key']
    replies = iter(['L', 'Y'])
    monkeypatch.setattr('builtins.input', lambda _: next(replies))
    monkeypatch.setattr(env_module, 'getpass', lambda _: '')
    environment.set_variable('openai_api_key')
    assert environment.env['shared_api_secrets'] == ['openai_api_key']
    environment.db.update.assert_not_called()
    environment.secret_client.add_secret_version.assert_not_called()


def test_keep_does_not_access_secrets_or_write_config(environment, monkeypatch):
    monkeypatch.setattr('builtins.input', lambda _: '')
    environment.set_variable('shared_api_secrets')
    assert environment.secret_client.mock_calls == []
    environment.db.update.assert_not_called()


@pytest.mark.parametrize('error', [NotFound('missing'), PermissionDenied('denied')])
def test_unavailable_parent_does_not_change_configuration(environment, monkeypatch, error):
    environment.secret_client.get_secret_version.side_effect = error
    monkeypatch.setattr('builtins.input', lambda _: 'P')
    with pytest.raises(type(error)):
        environment.set_variable('shodan_api_key')
    assert 'shared_api_secrets' not in environment.env
    environment.db.update.assert_not_called()


def test_store_does_not_create_a_secret_on_permission_errors(environment):
    environment.secret_client.get_secret.side_effect = PermissionDenied('denied')
    with pytest.raises(PermissionDenied):
        environment.store_secret('openai_api_key', 'new-key')
    environment.secret_client.create_secret.assert_not_called()
    environment.secret_client.add_secret_version.assert_not_called()


def test_secret_iam_is_scoped_preserves_conditions_and_is_idempotent(environment, monkeypatch):
    role = 'roles/secretmanager.secretAccessor'
    conditional = policy_pb2.Binding(
        role=role, members=['serviceAccount:existing@example.com'],
        condition={'title': 'temporary', 'expression': 'request.time < timestamp("2030-01-01T00:00:00Z")'},
    )
    original = policy_pb2.Policy(version=3, etag=b'original-etag', bindings=[conditional])
    policy = deepcopy(original)
    environment.secret_client.get_iam_policy.return_value = policy
    monkeypatch.setattr(secret_module.secretmanager, 'SecretManagerServiceClient', lambda: environment.secret_client)
    env = SimpleNamespace(
        project=environment.project, parent_project='parent-project', shared_api_secrets=['openai_api_key'],
    )
    secret_module.ensure_shared_api_secret_access(env)
    resource = 'projects/parent-project/secrets/openai_api_key'
    environment.secret_client.get_iam_policy.assert_called_once_with(request={
        'resource': resource, 'options': {'requested_policy_version': 3},
    })
    environment.secret_client.set_iam_policy.assert_called_once_with(request={'resource': resource, 'policy': policy})
    assert policy.bindings[0] == conditional
    assert policy.etag == b'original-etag' and policy.version == 3
    assert policy.bindings[1].role == role
    assert list(policy.bindings[1].members) == [
        'serviceAccount:agoge-service@tenant-project.iam.gserviceaccount.com',
    ]
    assert not policy.bindings[1].HasField('condition')
    secret_module.ensure_shared_api_secret_access(env)
    assert environment.secret_client.set_iam_policy.call_count == 1
    environment.secret_client.access_secret_version.assert_not_called()


def test_disabled_latest_version_stops_iam_changes(environment, monkeypatch):
    environment.secret_client.get_secret_version.return_value.state = secretmanager.SecretVersion.State.DISABLED
    monkeypatch.setattr(secret_module.secretmanager, 'SecretManagerServiceClient', lambda: environment.secret_client)
    env = SimpleNamespace(project=environment.project, parent_project='parent-project', shared_api_secrets=['openai_api_key'])
    with pytest.raises(ValueError, match='enabled latest version'):
        secret_module.ensure_shared_api_secret_access(env)
    environment.secret_client.get_iam_policy.assert_not_called()


@pytest.mark.parametrize('method', ['_deploy_api', 'deploy_cloud_functions'])
def test_api_and_function_deployment_stop_before_build_on_secret_failure(monkeypatch, method):
    app = object.__new__(AgogeApp)
    app.env = MagicMock()
    app._stage_build = MagicMock()
    app._stream_command_output = MagicMock()
    preflight = MagicMock(side_effect=PermissionDenied('denied'))
    monkeypatch.setattr(app_module, 'ensure_shared_api_secret_access', preflight)
    with pytest.raises(PermissionDenied):
        getattr(app, method)()
    preflight.assert_called_once_with(app.env)
    app._stage_build.assert_not_called()
    app._stream_command_output.assert_not_called()


def test_local_only_deployments_need_no_parent_secret_permissions(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr(secret_module.secretmanager, 'SecretManagerServiceClient', client)
    secret_module.ensure_shared_api_secret_access(SimpleNamespace(shared_api_secrets=[]))
    client.assert_not_called()


def test_shared_build_and_api_accept_only_parent_domain(tmp_path, monkeypatch):
    env = object.__new__(CloudEnv)
    env.env_dict = {
        'project': 'tenant-project', 'region': 'us-central1', 'zone': 'us-central1-a',
        'project_path': '/class-a/', 'parent_project': 'parent-project',
        'parent_dns_suffix': '.example.edu.', 'parent_dnszone': 'shared-zone',
        'shared_api_secrets': ['openai_api_key'],
    }
    env._assign_variables()
    env._api_key = 'tenant-firebase-key'
    app = object.__new__(AgogeApp)
    app.env = env
    app.fastapi_env_file = tmp_path / 'api.env'
    app.react_vite_env_file = tmp_path / 'frontend.env'
    app.fastapi_env_file.write_text('DOMAIN=obsolete.edu\nSUB_DOMAIN=old\nOTHER=keep\n')
    app._write_env_files()
    api_vars = app._read_env_file(app.fastapi_env_file)
    assert api_vars == {'OTHER': 'keep', 'DEVELOPMENT': 'false', 'PARENT_DOMAIN': 'example.edu'}
    frontend_vars = app._read_env_file(app.react_vite_env_file)
    assert frontend_vars['VITE_PROJECT_PATH'] == '/class-a/'
    assert frontend_vars['VITE_FIREBASE_AUTH_DOMAIN'] == 'tenant-project.firebaseapp.com'
    assert frontend_vars['VITE_FIREBASE_KEY'] == 'tenant-firebase-key'
    assert frontend_vars['VITE_AGOGE_API_URL'] == 'https://api.example.edu/'
    assert 'openai' not in app.react_vite_env_file.read_text()
    for key in ('DOMAIN', 'SUB_DOMAIN'):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv('PARENT_DOMAIN', api_vars['PARENT_DOMAIN'])
    monkeypatch.setenv('DEVELOPMENT', 'false')
    config = AppConfig()
    assert config.hosts() == ['example.edu', '*.example.edu']
    assert config.origins() == ['https://example.edu', 'https://app.example.edu', 'https://auth.example.edu']
