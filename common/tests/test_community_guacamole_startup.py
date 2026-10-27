import base64
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from common.services.community_guacamole_startup import COMMUNITY_GUAC_AGENT, render_community_guacamole_startup

UNIT = 'abcdefghij'
SECRET = f'projects/tenant-project/secrets/agoge-guac-{UNIT}/versions/1'
KEY = '00112233445566778899aabbccddeeff'
DOMAIN = 'tenant.example.test'
HOST = UNIT + '-display.' + DOMAIN


def agent():
    namespace = {'__name__': 'embedded_test'}
    exec(compile(COMMUNITY_GUAC_AGENT, 'embedded-community-guacamole.py', 'exec'), namespace)
    return namespace


def test_embedded_bootstrap_is_valid_shell_and_stdlib_python_with_only_reference():
    script = render_community_guacamole_startup(SECRET, UNIT, '.' + DOMAIN + '.')
    subprocess.run(['bash', '-n'], input=script, text=True, capture_output=True, check=True)
    compile(COMMUNITY_GUAC_AGENT, 'embedded-community-guacamole.py', 'exec')
    assert SECRET in script
    assert HOST in script
    assert KEY not in script
    assert 'startup-script-url' not in script
    assert 'set -x' not in script
    assert 'umask 077' in script


def test_shared_compose_pins_json_auth_for_one_service_and_preserves_tls_websockets():
    namespace = agent()
    value = namespace['compose'](KEY, HOST, DOMAIN)
    assert set(value['services']) == {'guacd', 'guacamole', 'nginx'}
    for name in ('guacamole', 'guacd'):
        assert value['services'][name]['image'] == f'guacamole/{name}:1.6.0'
    env = value['services']['guacamole']['environment']
    assert env['JSON_ENABLED'] == 'true'
    assert env['JSON_SECRET_KEY'] == KEY
    assert not any('MYSQL' in name for name in env)
    assert value['services']['nginx']['environment'] == {'GUAC_HOST': HOST, 'GUAC_DOMAIN': DOMAIN}
    assert '/etc/letsencrypt:/etc/letsencrypt:ro' in value['services']['nginx']['volumes']
    health = value['services']['guacd']['healthcheck']
    assert health['interval'] == '10s' and health['start_period'] == '5s'
    nginx = namespace['nginx_configuration'](HOST, DOMAIN)
    assert f'server_name {HOST};' in nginx
    assert f'/etc/letsencrypt/live/{DOMAIN}/privkey.pem' in nginx
    assert 'proxy_set_header Upgrade $http_upgrade;' in nginx
    assert 'proxy_set_header Connection "upgrade";' in nginx


def test_runtime_fetches_key_via_metadata_identity_and_secret_manager_only(tmp_path):
    namespace = agent()
    namespace['ROOT'] = tmp_path
    (tmp_path / 'secret-version').write_text(SECRET)
    responses = [json.dumps({'access_token': 'oauth-token'}).encode(),
                 json.dumps({'payload': {'data': base64.b64encode(json.dumps({'key': KEY}).encode()).decode()}}).encode()]
    namespace['request'] = MagicMock(side_effect=responses)
    assert namespace['signing_key']() == KEY
    assert namespace['request'].call_args_list[0].args == (
        namespace['METADATA'] + 'instance/service-accounts/default/token', {'Metadata-Flavor': 'Google'})
    assert namespace['request'].call_args_list[1].args == (
        'https://secretmanager.googleapis.com/v1/' + SECRET + ':access', {'Authorization': 'Bearer oauth-token'})


def test_private_compose_file_is_atomic_and_mode_600(tmp_path):
    namespace = agent()
    target = tmp_path / 'docker-compose.yml'
    namespace['atomic_write'](target, KEY)
    assert target.read_text() == KEY
    assert target.stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize('swarm, expected_reset', [
    ({'LocalNodeState': 'active', 'NodeAddr': '10.0.0.20'}, False),
    ({'LocalNodeState': 'active', 'NodeAddr': '10.99.0.2'}, True),
    ({'LocalNodeState': 'inactive'}, True),
    # A swarm baked into the image whose node certificate has expired.
    ({'LocalNodeState': 'error', 'NodeAddr': '10.128.0.56'}, True),
])
def test_boot_replaces_baked_stack_and_only_reinitializes_stale_swarm(tmp_path, capsys, swarm, expected_reset):
    namespace = agent()
    root, app = tmp_path / 'private', tmp_path / 'app'
    root.mkdir()
    app.mkdir()
    namespace['ROOT'], namespace['APP'] = root, app
    (root / 'host').write_text(HOST)
    (root / 'domain').write_text(DOMAIN)
    (app / 'docker-compose.yml').write_text('old MYSQL stack')
    (app / '.env').write_text('MYSQL_PASSWORD=old-secret')
    certificates = tmp_path / 'certificates'
    (certificates / DOMAIN).mkdir(parents=True)
    for name in ('privkey.pem', 'fullchain.pem'):
        (certificates / DOMAIN / name).write_text('certificate')
    service_file = tmp_path / 'guacamole.service'

    def local_path(value):
        if str(value) == '/etc/letsencrypt/live':
            return certificates
        if str(value) == '/etc/systemd/system/guacamole.service':
            return service_file
        return Path(value)

    def run(args, check=True):
        return SimpleNamespace(stdout=json.dumps(swarm).encode() if args[:2] == ['docker', 'info'] else b'')

    namespace['Path'] = local_path
    namespace['command'] = MagicMock(side_effect=run)
    namespace['signing_key'] = MagicMock(return_value=KEY)
    namespace['request'] = MagicMock(return_value=b'10.0.0.20')
    namespace['configure']()
    configured = json.loads((app / 'docker-compose.yml').read_text())
    assert configured['services']['guacamole']['environment']['JSON_SECRET_KEY'] == KEY
    assert (app / 'docker-compose.yml').stat().st_mode & 0o777 == 0o600
    assert 'MYSQL' not in (app / '.env').read_text()
    assert 'stack deploy --prune' in service_file.read_text()
    assert 'GUAC_DOMAIN' not in (app / 'nginx/conf.d/guacamole.conf').read_text()
    commands = [call.args[0] for call in namespace['command'].call_args_list]
    assert (['docker', 'swarm', 'init', '--advertise-addr', '10.0.0.20'] in commands) == expected_reset
    assert (['docker', 'swarm', 'leave', '--force'] in commands) == (
        expected_reset and swarm['LocalNodeState'] != 'inactive')
    assert commands[-1] == ['systemctl', 'enable', '--now', 'guacamole.service']
    assert KEY not in capsys.readouterr().out


@pytest.mark.parametrize('suffix', ['evil; echo secret', 'two..dots', '', 'test/escape'])
def test_invalid_dns_never_reaches_shell(suffix):
    with pytest.raises(ValueError):
        render_community_guacamole_startup(SECRET, UNIT, suffix)


def test_forged_unit_secret_is_rejected():
    with pytest.raises(ValueError):
        render_community_guacamole_startup(SECRET.replace(UNIT, 'klmnopqrst'), UNIT, DOMAIN)


def _configure_without_certificate(tmp_path, certbot_rc, certbot_path='/usr/bin/certbot'):
    namespace = agent()
    root, app = tmp_path / 'private', tmp_path / 'app'
    root.mkdir()
    app.mkdir()
    namespace['ROOT'], namespace['APP'] = root, app
    (root / 'host').write_text(HOST)
    (root / 'domain').write_text(DOMAIN)
    certificates = tmp_path / 'certificates'
    certificates.mkdir()

    def local_path(value):
        if str(value) == '/etc/letsencrypt/live':
            return certificates
        if str(value) == '/etc/systemd/system/guacamole.service':
            return tmp_path / 'guacamole.service'
        return Path(value)

    def run(args, check=True):
        if args[0] == 'certbot':
            return SimpleNamespace(returncode=certbot_rc, stdout=b'')
        swarm = {'LocalNodeState': 'active', 'NodeAddr': '10.0.0.20'}
        return SimpleNamespace(returncode=0, stdout=json.dumps(swarm).encode() if args[:2] == ['docker', 'info'] else b'')

    namespace['Path'] = local_path
    namespace['shutil'] = SimpleNamespace(which=lambda name: certbot_path)
    namespace['command'] = MagicMock(side_effect=run)
    namespace['signing_key'] = MagicMock(return_value=KEY)
    namespace['request'] = MagicMock(return_value=b'10.0.0.20')
    return namespace


def test_missing_wildcard_certificate_issues_a_host_certificate_under_the_domain_lineage(tmp_path):
    namespace = _configure_without_certificate(tmp_path, certbot_rc=0)
    namespace['configure']()
    commands = [call.args[0] for call in namespace['command'].call_args_list]
    certbot = next(args for args in commands if args[0] == 'certbot')
    assert certbot[certbot.index('--cert-name') + 1] == DOMAIN
    assert certbot[certbot.index('-d') + 1] == HOST
    assert '--standalone' in certbot and '--dns-google' not in certbot
    # The certificate is in place before the stack (and nginx on port 80) starts.
    assert commands.index(certbot) < commands.index(['systemctl', 'enable', '--now', 'guacamole.service'])


@pytest.mark.parametrize('certbot_rc, certbot_path', [(1, '/usr/bin/certbot'), (0, None)])
def test_missing_certificate_that_cannot_be_issued_stops_before_deploying(tmp_path, certbot_rc, certbot_path):
    namespace = _configure_without_certificate(tmp_path, certbot_rc, certbot_path)
    with pytest.raises(ValueError, match='TLS certificate is unavailable'):
        namespace['configure']()
    commands = [call.args[0] for call in namespace['command'].call_args_list]
    assert ['systemctl', 'enable', '--now', 'guacamole.service'] not in commands


def test_failure_reason_names_the_step_without_command_output():
    namespace = agent()
    error = subprocess.CalledProcessError(1, ['docker', 'swarm', 'init', '--advertise-addr', '10.0.0.20'],
                                          stderr=KEY.encode())
    assert namespace['failure_reason'](error) == 'docker swarm init exited with 1'
    assert namespace['failure_reason'](ValueError('Invalid proxy DNS configuration')) == \
        'Invalid proxy DNS configuration'
    assert namespace['failure_reason'](KeyError(KEY)) == 'KeyError'
