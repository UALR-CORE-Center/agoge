from unittest.mock import MagicMock

import pytest
from google.api_core.exceptions import NotFound

from common.constants.database import ADMIN_INFO_DOCUMENT, DbCollections
from cloud_deployment.operations.env_and_quotas import environment_variables as env_module
from cloud_deployment.operations.env_and_quotas.environment_variables import EnvironmentVariables

SEED_SECRET = 'projects/tenant-project/secrets/ctf_flag_seed'


class FakeSecretManager:
    """In-memory Secret Manager covering the calls EnvironmentVariables makes."""

    def __init__(self):
        self.versions = {}  # secret name -> list of payload bytes
        self.create_secret = MagicMock(side_effect=self._create_secret)
        self.add_secret_version = MagicMock(side_effect=self._add_secret_version)

    def _create_secret(self, request):
        self.versions[f"{request['parent']}/secrets/{request['secret_id']}"] = []

    def _add_secret_version(self, request):
        self.versions[request['parent']].append(request['payload']['data'])

    def get_secret(self, name):
        if name not in self.versions:
            raise NotFound(name)

    def access_secret_version(self, name):
        secret = name.rsplit('/versions/', 1)[0]
        if not self.versions.get(secret):
            raise NotFound(name)
        payload = MagicMock()
        payload.payload.data = self.versions[secret][-1]
        return payload


def _environment(env=None):
    environment = object.__new__(EnvironmentVariables)
    environment.project = 'tenant-project'
    environment.env = env if env is not None else {}
    environment.db = MagicMock()
    environment.secret_client = FakeSecretManager()
    return environment


def _no_prompt(prompt=''):
    raise AssertionError(f'unexpected prompt: {prompt}')


def test_enabling_creates_seed_once_and_second_enable_keeps_it(monkeypatch):
    environment = _environment()
    secret_client = environment.secret_client
    replies = iter(['y', 'y'])
    monkeypatch.setattr('builtins.input', lambda prompt='': next(replies))

    environment.set_variable('ctf_enabled')

    secret_client.create_secret.assert_called_once()
    assert secret_client.create_secret.call_args.kwargs['request']['secret_id'] == 'ctf_flag_seed'
    assert len(secret_client.versions[SEED_SECRET]) == 1
    seed = secret_client.versions[SEED_SECRET][0].decode()
    # secrets.token_hex(32): 64 lowercase hex characters.
    assert len(seed) == 64 and int(seed, 16) >= 0 and seed == seed.lower()

    environment.set_variable('ctf_enabled')

    secret_client.create_secret.assert_called_once()
    secret_client.add_secret_version.assert_called_once()
    assert secret_client.versions[SEED_SECRET] == [seed.encode()]


def test_enable_with_existing_seed_does_not_overwrite_it(monkeypatch):
    environment = _environment()
    secret_client = environment.secret_client
    secret_client.versions[SEED_SECRET] = [b'existing-seed']
    monkeypatch.setattr('builtins.input', _no_prompt)

    environment.set_variable('ctf_enabled', True)

    secret_client.create_secret.assert_not_called()
    secret_client.add_secret_version.assert_not_called()
    assert secret_client.versions[SEED_SECRET] == [b'existing-seed']


def test_enable_writes_flag_after_seed_exists(monkeypatch):
    environment = _environment({'project': 'tenant-project'})
    secret_client = environment.secret_client
    seed_present_at_write = []
    environment.db.update.side_effect = lambda **kwargs: seed_present_at_write.append(
        bool(secret_client.versions.get(SEED_SECRET)))
    monkeypatch.setattr('builtins.input', _no_prompt)

    environment.set_variable('ctf_enabled', True)

    # Only the flag is written, so a concurrent admin-info edit is not clobbered.
    environment.db.update.assert_called_once_with(
        collection_name=DbCollections.ADMIN_INFO, doc_id=ADMIN_INFO_DOCUMENT,
        data={'ctf_enabled': True},
    )
    assert seed_present_at_write == [True]
    assert environment.env['ctf_enabled'] is True


def test_secret_without_version_gets_a_seed_version(monkeypatch):
    # A create that failed before add_secret_version leaves an empty secret.
    environment = _environment()
    secret_client = environment.secret_client
    secret_client.versions[SEED_SECRET] = []
    monkeypatch.setattr('builtins.input', _no_prompt)

    environment.set_variable('ctf_enabled', True)

    secret_client.create_secret.assert_not_called()
    assert len(secret_client.versions[SEED_SECRET]) == 1


def test_disabling_never_touches_secret_manager(monkeypatch):
    environment = _environment({'ctf_enabled': True})
    environment.secret_client = MagicMock()
    monkeypatch.setattr('builtins.input', lambda prompt='': 'n')

    environment.set_variable('ctf_enabled')

    assert environment.secret_client.mock_calls == []
    environment.db.update.assert_called_once_with(
        collection_name=DbCollections.ADMIN_INFO, doc_id=ADMIN_INFO_DOCUMENT,
        data={'ctf_enabled': False},
    )
    assert environment.env['ctf_enabled'] is False


def test_unrecognized_reply_changes_nothing(monkeypatch):
    environment = _environment()
    environment.secret_client = MagicMock()
    monkeypatch.setattr('builtins.input', lambda prompt='': 'maybe')

    environment.set_variable('ctf_enabled')

    assert environment.secret_client.mock_calls == []
    environment.db.update.assert_not_called()
    assert 'ctf_enabled' not in environment.env


@pytest.mark.parametrize('value, expected', [('false', False), ('TRUE', True), (False, False)])
def test_programmatic_values_parse_strictly(monkeypatch, value, expected):
    environment = _environment()
    monkeypatch.setattr('builtins.input', _no_prompt)

    environment.set_variable('ctf_enabled', value)

    assert environment.env['ctf_enabled'] is expected


def test_invalid_string_value_raises(monkeypatch):
    environment = _environment()
    monkeypatch.setattr('builtins.input', _no_prompt)

    with pytest.raises(ValueError):
        environment.set_variable('ctf_enabled', 'yes please')
    environment.db.update.assert_not_called()


def test_seed_is_never_printed(monkeypatch, capsys):
    environment = _environment()
    monkeypatch.setattr(env_module.secrets, 'token_hex', lambda nbytes: 'f' * (nbytes * 2))
    monkeypatch.setattr('builtins.input', _no_prompt)

    environment.set_variable('ctf_enabled', True)

    assert environment.secret_client.versions[SEED_SECRET] == [b'f' * 64]
    assert 'f' * 64 not in capsys.readouterr().out
