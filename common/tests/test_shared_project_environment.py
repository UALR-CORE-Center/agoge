from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from google.api_core.exceptions import NotFound, PermissionDenied

from common.models.agoge import CloudEnvModel
from common.utilities.gcp import cloud_env as cloud_env_module
from common.utilities.gcp.cloud_env import CloudEnv
from common.utilities.gcp.shared_secrets import SHARED_API_SECRET_NAMES


@pytest.fixture
def make_env(monkeypatch):
    monkeypatch.setattr(cloud_env_module.secretmanager, 'SecretManagerServiceClient', MagicMock)
    monkeypatch.setattr(cloud_env_module, 'Logger', lambda *args, **kwargs: MagicMock())

    def create(**overrides):
        return CloudEnv(env_dict={
            'project': 'tenant-project',
            'project_path': '/class-a/',
            'region': 'us-central1',
            'zone': 'us-central1-a',
            'parent_project': 'parent-project',
            'parent_dnszone': 'shared-zone',
            'parent_dns_suffix': 'example.edu.',
            **overrides,
        })
    return create


def test_shared_project_needs_no_legacy_domain_settings(make_env):
    env = make_env()
    assert env.main_app_url == 'https://app.example.edu/class-a'
    assert env.project_path == 'class-a'
    assert env.dns_suffix == env.parent_dns_suffix == '.example.edu'
    assert env.dnszone == env.parent_zone == 'shared-zone'
    assert env.firebase_auth_domain == 'tenant-project.firebaseapp.com'
    assert env.rubric_support is False
    env._api_key = 'tenant-firebase-key'
    assert env.auth_config == {
        'api_key': 'tenant-firebase-key',
        'auth_domain': 'tenant-project.firebaseapp.com',
        'project_id': 'tenant-project',
    }
    assert 'main_app_url' not in env.get_env()  # Derived values are not persisted.


def test_existing_domain_and_firebase_overrides_still_work(make_env):
    env = make_env(
        main_app_url='portal.tenant.edu/custom/', dns_suffix='.tenant.edu',
        dnszone='tenant-zone', firebase_auth_domain='auth.tenant.edu', app_sub_domain='portal',
    )
    assert env.main_app_url == 'https://portal.tenant.edu/custom'
    assert env.dns_suffix == '.tenant.edu'
    assert env.dnszone == 'tenant-zone'
    assert env.firebase_auth_domain == 'auth.tenant.edu'
    assert env.app_sub_domain == 'portal'
    assert env._get_auth_config()['auth_domain'] == 'auth.tenant.edu'


def test_root_project_has_no_double_slashes(make_env):
    assert make_env(project_path='/').main_app_url == 'https://app.example.edu'


@pytest.mark.parametrize('name', SHARED_API_SECRET_NAMES)
def test_selected_parent_source_is_authoritative(make_env, name):
    env = make_env(shared_api_secrets=[name])
    env.secret_client.access_secret_version.return_value = SimpleNamespace(
        payload=SimpleNamespace(data=b'parent-key')
    )
    assert getattr(env, name) == 'parent-key'
    env.secret_client.access_secret_version.assert_called_once_with(
        name=f'projects/parent-project/secrets/{name}/versions/latest'
    )


@pytest.mark.parametrize('name', [
    'api_key', 'jwt_private_key', 'jwt_public_key', 'guac_sql_password',
    'guac_admin_password', 'google_dns_service_key', 'groove_api_key',
])
def test_other_credentials_stay_tenant_local(make_env, name):
    env = make_env(shared_api_secrets=list(SHARED_API_SECRET_NAMES))
    env.get_secret(name)
    env.secret_client.access_secret_version.assert_called_once_with(
        name=f'projects/tenant-project/secrets/{name}/versions/latest'
    )


def test_existing_projects_do_not_implicitly_share_keys(make_env):
    env = make_env()
    env.secret_client.access_secret_version.side_effect = NotFound('no local key')
    assert env.openai_api_key is None
    env.secret_client.access_secret_version.assert_called_once_with(
        name='projects/tenant-project/secrets/openai_api_key/versions/latest'
    )


@pytest.mark.parametrize('error', [NotFound('missing'), PermissionDenied('denied')])
def test_parent_failures_do_not_fall_back_to_old_local_credentials(make_env, error):
    env = make_env(shared_api_secrets=['openai_api_key'])
    env.secret_client.access_secret_version.side_effect = error
    with pytest.raises(RuntimeError, match='Cannot access shared API secret'):
        env.openai_api_key
    assert env.secret_client.access_secret_version.call_count == 1


@pytest.mark.parametrize('settings', [
    {'shared_api_secrets': 'openai_api_key'},
    {'shared_api_secrets': ['jwt_private_key']},
    {'shared_api_secrets': ['openai_api_key'], 'parent_project': None},
    {'shared_api_secrets': ['openai_api_key'], 'parent_project': 'tenant-project'},
])
def test_invalid_sources_rejected_in_runtime_and_project_updates(make_env, settings):
    with pytest.raises(ValueError):
        make_env(**settings)
    with pytest.raises(ValueError):
        CloudEnvModel.model_validate({
            'project': 'tenant-project', 'parent_project': 'parent-project', **settings,
        })
