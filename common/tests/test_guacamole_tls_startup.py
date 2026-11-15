import base64
import json
from pathlib import Path
import subprocess
from unittest.mock import Mock

import pytest

from common.services.guacamole_tls_startup import (
    GUACAMOLE_TLS_AGENT,
    install_guacamole_tls_in_startup,
    strip_guacamole_proxy_identities,
)


DOMAIN = 'tenant.example.test'
HOST = 'abcdefghij-display.' + DOMAIN
SECRET = 'projects/shared-project/secrets/tenant-guacamole-tls'
READER = 'agoge-guac-tls@tenant-project.iam.gserviceaccount.com'
SIGNER = 'agoge-guac-abcdefghij@tenant-project.iam.gserviceaccount.com'


@pytest.fixture
def agent():
    scope = {'__name__': 'embedded_test'}
    exec(compile(GUACAMOLE_TLS_AGENT, 'embedded-guacamole-tls.py', 'exec'), scope)
    return scope


def test_installer_is_valid_shell_and_replaces_its_block_before_one_time_init():
    startup = '#!/bin/bash\nif [ -f /etc/guac_init_done ]; then exit 0; fi\n'
    enrolled = install_guacamole_tls_in_startup(startup, SECRET, HOST, DOMAIN)
    rotated = install_guacamole_tls_in_startup(enrolled, SECRET, HOST, DOMAIN, impersonate=READER)
    subprocess.run(['bash', '-n'], input=rotated, text=True, capture_output=True, check=True)
    assert rotated.count('BEGIN AGOGE GUACAMOLE TLS') == 1
    assert rotated.index('END AGOGE GUACAMOLE TLS') < rotated.index('/etc/guac_init_done')
    assert READER in rotated and SECRET in rotated
    assert 'BEGIN PRIVATE KEY' not in rotated


def test_community_fetch_uses_its_identity_only_to_impersonate_the_reader(agent):
    payload = json.dumps({'fullchain': 'test chain', 'privkey': 'test key'}).encode()
    agent['request'] = request = Mock(side_effect=[
        {'access_token': 'vm-token'},
        {'accessToken': 'reader-token'},
        {'payload': {'data': base64.b64encode(payload).decode()}},
    ])
    assert agent['certificate_bundle']({'secret': SECRET, 'impersonate': READER}) == (
        b'test chain', b'test key',
    )
    metadata, iam, secret = (call.args for call in request.call_args_list)
    assert metadata == (agent['TOKEN_ENDPOINT'], {'Metadata-Flavor': 'Google'})
    assert iam[0].endswith(READER + ':generateAccessToken')
    assert iam[1]['Authorization'] == 'Bearer vm-token'
    assert secret == (f'https://secretmanager.googleapis.com/v1/{SECRET}/versions/active:access',
                      {'Authorization': 'Bearer reader-token'})


@pytest.mark.parametrize('reload_succeeds', [True, False])
def test_activate_validates_and_atomically_rolls_out_or_restores_certbot_pair(
    agent, tmp_path, reload_succeeds,
):
    agent['CERTBOT'] = tmp_path
    archive = tmp_path / 'archive' / DOMAIN
    live = tmp_path / 'live' / DOMAIN
    archive.mkdir(parents=True)
    live.mkdir(parents=True)
    for name, content in zip(agent['NAMES'], (b'old chain', b'old key')):
        (archive / name).write_bytes(content)
        (live / name).symlink_to(Path('../../archive') / DOMAIN / name)
    agent['certificate_bundle'] = Mock(return_value=(b'new chain', b'new key'))
    agent['nginx_tasks'] = Mock(return_value=['nginx-task'])
    agent['command'] = Mock()
    agent['validate'] = Mock()

    def reload(tasks, directory, hostname):
        assert tasks == ['nginx-task'] and hostname == HOST
        assert directory == live
        assert (live / 'fullchain.pem').read_bytes() == b'new chain'
        assert (live / 'privkey.pem').read_bytes() == b'new key'
        if not reload_succeeds:
            raise ValueError('test reload failure')

    agent['reload_and_verify'] = reload
    config = {'secret': SECRET, 'host': HOST, 'domain': DOMAIN, 'impersonate': None}
    if reload_succeeds:
        assert agent['synchronize'](config, live)
        assert live.is_symlink()
        assert (live / 'privkey.pem').stat().st_mode & 0o777 == 0o600
        legacy = live.with_name('.agoge-legacy-' + DOMAIN)
        assert (legacy / 'privkey.pem').read_bytes() == b'old key'
    else:
        with pytest.raises(ValueError, match='test reload failure'):
            agent['synchronize'](config, live)
        assert not live.is_symlink()
        assert (live / 'fullchain.pem').read_bytes() == b'old chain'
        assert (live / 'privkey.pem').read_bytes() == b'old key'
        agent['command'].assert_called_once_with('docker', 'exec', 'nginx-task', 'nginx', '-s', 'reload')
    assert agent['validate'].call_args.args[1:] == (HOST, 86400)


def test_catalog_accounts_cannot_request_any_guacamole_identity():
    accounts = [{'email': READER}, {'email': SIGNER}, {'email': 'default'}]
    assert strip_guacamole_proxy_identities({'service_accounts': accounts}) == {
        'service_accounts': [{'email': 'default'}],
    }
    assert strip_guacamole_proxy_identities({'serviceAccounts': accounts}, allowed_email=SIGNER) == {
        'serviceAccounts': [{'email': SIGNER}, {'email': 'default'}],
    }
