"""CloudEnv.ctf_flag_seed: lazy, cached, read from the tenant project's Secret Manager."""
from unittest.mock import MagicMock, patch

import pytest

from common.utilities.gcp.cloud_env import CloudEnv

ENV_DICT = {
    'project': 'tenant-project',
    'parent_project': 'parent-project',
    'region': 'us-central1',
    'zone': 'us-central1-a',
    'parent_dns_suffix': 'example.edu',
}


def _secret_response(value: str) -> MagicMock:
    response = MagicMock()
    response.payload.data = value.encode('UTF-8')
    return response


@pytest.fixture
def secret_client():
    with patch('common.utilities.gcp.cloud_env.secretmanager.SecretManagerServiceClient') as client_cls:
        client = client_cls.return_value
        client.access_secret_version.return_value = _secret_response('ab' * 32)
        yield client


def test_seed_is_not_read_at_construction(secret_client):
    # Lazy like openai_api_key: most CloudEnv users never need the seed.
    CloudEnv(env_dict=dict(ENV_DICT))
    secret_client.access_secret_version.assert_not_called()


def test_seed_is_read_from_tenant_project_latest_version(secret_client):
    env = CloudEnv(env_dict=dict(ENV_DICT))
    assert env.ctf_flag_seed == 'ab' * 32
    secret_client.access_secret_version.assert_called_once_with(
        name='projects/tenant-project/secrets/ctf_flag_seed/versions/latest'
    )


def test_seed_is_cached_after_first_read(secret_client):
    env = CloudEnv(env_dict=dict(ENV_DICT))
    first = env.ctf_flag_seed
    second = env.ctf_flag_seed
    assert first == second
    assert secret_client.access_secret_version.call_count == 1


def test_seed_cannot_be_configured_as_shared(secret_client):
    # The seed is per-tenant; sharing it from the parent would let tenants derive each other's flags.
    with pytest.raises(ValueError):
        CloudEnv(env_dict={**ENV_DICT, 'shared_api_secrets': ['ctf_flag_seed']})


def test_seed_stays_tenant_local_when_other_secrets_are_shared(secret_client):
    env = CloudEnv(env_dict={**ENV_DICT, 'shared_api_secrets': ['openai_api_key']})
    env.ctf_flag_seed
    name = secret_client.access_secret_version.call_args.kwargs['name']
    assert name == 'projects/tenant-project/secrets/ctf_flag_seed/versions/latest'


def test_missing_seed_returns_none_and_retries(secret_client):
    # get_secret swallows non-shared errors; None is not cached so a later provisioning is picked up.
    secret_client.access_secret_version.side_effect = [Exception('NotFound'), _secret_response('cd' * 32)]
    env = CloudEnv(env_dict=dict(ENV_DICT))
    assert env.ctf_flag_seed is None
    assert env.ctf_flag_seed == 'cd' * 32
