"""Render the boot-time installer for Secret Manager-backed Guacamole TLS."""

import json
import re
import shlex


GUACAMOLE_TLS_SECRET_METADATA_KEY = 'agoge-guacamole-tls-secret'
GUACAMOLE_TLS_HOST_METADATA_KEY = 'agoge-guacamole-tls-host'
GUACAMOLE_TLS_READER_METADATA_KEY = 'agoge-guacamole-tls-reader'
GUACAMOLE_TLS_METADATA_KEYS = frozenset({
    GUACAMOLE_TLS_SECRET_METADATA_KEY, GUACAMOLE_TLS_HOST_METADATA_KEY, GUACAMOLE_TLS_READER_METADATA_KEY,
})
GUACAMOLE_TLS_SECRET_PATTERN = r'projects/[a-z0-9-]+/secrets/[A-Za-z0-9_-]{1,255}'
GUACAMOLE_TLS_IMAGE_PATTERN = (r'(?:https://(?:www\.googleapis\.com|compute\.googleapis\.com)/compute/v1/)?'
                               r'projects/[a-z0-9-]+/global/images/[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?')
GUACAMOLE_TLS_SCOPE = 'https://www.googleapis.com/auth/cloud-platform'
_START = '# BEGIN AGOGE GUACAMOLE TLS'
_END = '# END AGOGE GUACAMOLE TLS'

_LABEL = r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?'
_DNS_NAME = re.compile(rf'{_LABEL}(?:\.{_LABEL})+')
_READER = re.compile(r'agoge-guac-tls@[a-z0-9-]+\.iam\.gserviceaccount\.com')
_PROXY_IDENTITY = re.compile(r'agoge-guac-(?:tls|[a-z]{10})@[a-z0-9-]+\.iam\.gserviceaccount\.com')


def guacamole_tls_reader_email(project: str) -> str:
    return f'agoge-guac-tls@{project}.iam.gserviceaccount.com'


def is_guacamole_tls_reader(email: str | None) -> bool:
    return bool(email and _READER.fullmatch(email))


def strip_guacamole_proxy_identities(record: dict, *, allowed_email: str | None = None) -> dict:
    """Keep catalog-provided servers from requesting generated Guacamole identities."""
    for key in ('service_accounts', 'serviceAccounts'):
        if accounts := record.get(key):
            record[key] = [
                account for account in accounts
                if account.get('email') == allowed_email or not _PROXY_IDENTITY.fullmatch(account.get('email') or '')
            ]
    return record


def guacamole_tls_boot_image(env: dict) -> str | None:
    image = env.get('guacamole_tls_image') if env.get('guacamole_tls_secret') else None
    if image and not re.fullmatch(GUACAMOLE_TLS_IMAGE_PATTERN, image):
        raise ValueError('Guacamole TLS image must be a project-qualified Compute image')
    return image


def guacamole_tls_metadata(secret_name: str, hostname: str, *, impersonate: str | None = None) -> dict:
    items = {
        GUACAMOLE_TLS_SECRET_METADATA_KEY: secret_name,
        GUACAMOLE_TLS_HOST_METADATA_KEY: hostname,
    }
    if impersonate:
        items[GUACAMOLE_TLS_READER_METADATA_KEY] = impersonate
    return items


# This is embedded in VM startup metadata so existing Guacamole images need no
# package install to adopt managed TLS.
GUACAMOLE_TLS_AGENT = r'''#!/usr/bin/env python3
import base64
import ctypes
import fcntl
import json
import os
from pathlib import Path
import shutil
import socket
import ssl
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT = Path('/etc/agoge-guacamole-tls')
CERTBOT = Path('/etc/letsencrypt')
TOKEN_ENDPOINT = 'http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token'
SECRET_ENDPOINT = 'https://secretmanager.googleapis.com/v1/'
IAM_ENDPOINT = 'https://iamcredentials.googleapis.com/v1/projects/-/serviceAccounts/'
NAMES = ('fullchain.pem', 'privkey.pem')


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_):
        raise ValueError('Unexpected credential endpoint redirect')


def request(url, headers, body=None):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect)
    with opener.open(urllib.request.Request(url, headers=headers, data=body), timeout=15) as response:
        data = response.read(131073)
    if len(data) > 131072:
        raise ValueError('Credential response is too large')
    return json.loads(data)


def certificate_bundle(config):
    token = request(TOKEN_ENDPOINT, {'Metadata-Flavor': 'Google'})['access_token']
    if config['impersonate']:
        response = request(
            IAM_ENDPOINT + config['impersonate'] + ':generateAccessToken',
            {'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'},
            json.dumps({'scope': ['https://www.googleapis.com/auth/cloud-platform'],
                        'lifetime': '600s'}).encode(),
        )
        token = response['accessToken']
    response = request(
        SECRET_ENDPOINT + config['secret'] + '/versions/active:access',
        {'Authorization': 'Bearer ' + token},
    )
    payload = json.loads(base64.b64decode(response['payload']['data'], validate=True))
    return tuple(payload[key].encode('ascii') for key in ('fullchain', 'privkey'))


def command(*args):
    # Explicitly discard stderr. OpenSSL and Docker errors may expose sensitive
    # data supplied to the command.
    return subprocess.run(args, check=True, capture_output=True, timeout=20).stdout


def restrict_metadata():
    # The certificate reader belongs to the host agent. Prevent containers and
    # unprivileged host processes from reaching the metadata credential endpoint.
    rules = (
        ('FORWARD', '-d', '169.254.169.254', '-j', 'REJECT'),
        ('OUTPUT', '-d', '169.254.169.254', '-m', 'owner', '!', '--uid-owner', '0', '-j', 'REJECT'),
    )
    for rule in rules:
        try:
            command('iptables', '-w', '-C', *rule)
        except subprocess.CalledProcessError:
            command('iptables', '-w', '-I', *rule)


def validate(directory, host, minimum_lifetime):
    chain, key = (str(directory / name) for name in NAMES)
    command('openssl', 'x509', '-in', chain, '-noout', '-checkend', str(minimum_lifetime))
    command('openssl', 'verify', '-purpose', 'sslserver', '-verify_hostname', host, '-untrusted', chain, chain)
    certificate_public_key = command('openssl', 'x509', '-in', chain, '-noout', '-pubkey')
    private_public_key = command('openssl', 'pkey', '-in', key, '-passin', 'pass:', '-pubout')
    if certificate_public_key != private_public_key:
        raise ValueError('Certificate and private key do not match')


def nginx_tasks():
    return command('docker', 'ps', '--filter', 'label=com.docker.swarm.service.name=guacamole_nginx',
                   '--format', '{{.ID}}').decode().split()


def certificate_served(directory, host, attempts):
    expected = command('openssl', 'x509', '-in', str(directory / NAMES[0]), '-outform', 'DER')
    context = ssl.create_default_context()
    for attempt in range(attempts):
        try:
            with socket.create_connection(('127.0.0.1', 443), timeout=3) as connection:
                with context.wrap_socket(connection, server_hostname=host) as tls:
                    if tls.getpeercert(binary_form=True) == expected:
                        return True
        except OSError:
            pass
        if attempt + 1 < attempts:
            time.sleep(1)
    return False


def reload_and_verify(tasks, directory, host):
    if not tasks:
        return
    for task in tasks:
        command('docker', 'exec', task, 'nginx', '-t')
    for task in tasks:
        command('docker', 'exec', task, 'nginx', '-s', 'reload')
    if not certificate_served(directory, host, 5):
        raise ValueError('Nginx did not serve the activated certificate')


def exchange(first, second):
    # On migration, the Certbot live name can be a real directory. A Linux
    # atomic exchange can swap a directory and a symlink without ever leaving
    # Nginx's existing certificate paths absent.
    rename = ctypes.CDLL(None, use_errno=True).renameat2
    rename.argtypes = (ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint)
    rename.restype = ctypes.c_int
    if rename(-100, os.fsencode(first), -100, os.fsencode(second), 2) != 0:
        raise OSError(ctypes.get_errno(), 'Could not atomically switch the Guacamole certificate')


def activate(staged, live, versions, host):
    tasks = nginx_tasks()
    # The exchange path must be on the same filesystem as the public live name.
    with tempfile.TemporaryDirectory(prefix='.agoge-swap-', dir=live.parent) as scratch:
        replacement = Path(scratch) / 'next'
        replacement.symlink_to(staged)
        previous = live.resolve() if os.path.lexists(live) else None
        if previous is None:
            os.replace(replacement, live)
        else:
            exchange(replacement, live)
        try:
            reload_and_verify(tasks, live, host)
        except Exception:
            if previous is None:
                live.unlink()
            else:
                exchange(replacement, live)
                for task in tasks:
                    command('docker', 'exec', task, 'nginx', '-s', 'reload')
            raise

        if replacement.is_dir() and not replacement.is_symlink():
            # Retain the original Certbot lineage for recovery.
            # Certbot uses relative symlinks into ../../archive, so retain it
            # at the same depth as the previous live directory.
            legacy = live.with_name('.agoge-legacy-' + live.name)
            if not legacy.exists():
                os.replace(replacement, legacy)
        else:
            for version in versions.iterdir():
                if version not in (staged, previous):
                    shutil.rmtree(version)


def synchronize(config, live):
    versions = CERTBOT / 'agoge-tls' / config['domain'] / 'versions'
    versions.mkdir(mode=0o700, parents=True, exist_ok=True)
    bundle = certificate_bundle(config)
    # Reusing the active certificate is cheap and causes no Nginx reload.
    if all((live / name).is_file() and (live / name).read_bytes() == value
           for name, value in zip(NAMES, bundle)):
        validate(live, config['host'], 0)
        tasks = nginx_tasks()
        if tasks and not certificate_served(live, config['host'], 1):
            reload_and_verify(tasks, live, config['host'])
        return False
    staged = Path(tempfile.mkdtemp(prefix='tls-', dir=versions))
    try:
        for name, value in zip(NAMES, bundle):
            file = staged / name
            descriptor = os.open(file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, 'wb') as output:
                output.write(value)
        validate(staged, config['host'], 86400)
        live.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        activate(staged, live, versions, config['host'])
    except Exception:
        if live.resolve() != staged:
            shutil.rmtree(staged)
        raise
    return True


def main():
    config = json.loads((ROOT / 'configuration.json').read_text())
    live = CERTBOT / 'live' / config['domain']
    with (ROOT / 'lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        restrict_metadata()
        if sys.argv[1:] == ['--check-current']:
            validate(live, config['host'], 0)
            return
        if synchronize(config, live):
            print('Guacamole TLS certificate updated.')
        else:
            print('Guacamole TLS certificate is current.')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        # Exception bodies can contain response content or command output.
        print('Guacamole TLS sync failed (' + type(error).__name__ + ').', file=sys.stderr)
        sys.exit(1)
'''


_SERVICE = '''[Unit]
Description=Synchronize the Agoge Guacamole TLS certificate
Wants=network-online.target
After=network-online.target docker.service

[Service]
Type=oneshot
UMask=0077
ExecStart=/usr/bin/python3 /etc/agoge-guacamole-tls/sync.py
TimeoutStartSec=3min
'''

_TIMER = '''[Unit]
Description=Refresh the Agoge Guacamole TLS certificate

[Timer]
OnBootSec=2min
OnUnitActiveSec=1h
RandomizedDelaySec=10min

[Install]
WantedBy=timers.target
'''


def render_guacamole_tls_install(
    secret_name: str, hostname: str, domain: str, *, impersonate: str | None = None,
) -> str:
    """Render a root installer with a public reference and no key material."""
    if not isinstance(secret_name, str) or not re.fullmatch(GUACAMOLE_TLS_SECRET_PATTERN, secret_name):
        raise ValueError('Invalid Guacamole TLS secret resource name')
    hostname, domain = (value.strip('.').lower() for value in (hostname, domain))
    if any(len(value) > 253 or not _DNS_NAME.fullmatch(value) for value in (hostname, domain)):
        raise ValueError('Invalid Guacamole TLS hostname or domain')
    if not hostname.endswith('.' + domain):
        raise ValueError('Guacamole TLS hostname must be within its configured domain')
    if impersonate and not _READER.fullmatch(impersonate):
        raise ValueError('Invalid Guacamole TLS reader service account')
    config = shlex.quote(json.dumps({
        'secret': secret_name, 'host': hostname, 'domain': domain, 'impersonate': impersonate,
    }))
    return '\n'.join([
        _START, '(', 'set -eu', 'umask 077',
        'install -d -m 0700 /etc/agoge-guacamole-tls',
        'agoge_tls_write() {',
        '  agoge_tls_tmp=$(mktemp "$1.XXXXXX")',
        '  cat > "$agoge_tls_tmp"',
        '  mv -f "$agoge_tls_tmp" "$1"',
        '}',
        'agoge_tls_write /etc/agoge-guacamole-tls/sync.py <<\'AGOGE_TLS_AGENT\'',
        GUACAMOLE_TLS_AGENT, 'AGOGE_TLS_AGENT',
        f'printf %s {config} | agoge_tls_write /etc/agoge-guacamole-tls/configuration.json',
        'agoge_tls_write /etc/systemd/system/agoge-guacamole-tls.service <<\'AGOGE_TLS_SERVICE\'',
        _SERVICE, 'AGOGE_TLS_SERVICE',
        'agoge_tls_write /etc/systemd/system/agoge-guacamole-tls.timer <<\'AGOGE_TLS_TIMER\'',
        _TIMER, 'AGOGE_TLS_TIMER',
        'systemctl daemon-reload',
        # The old timer could overwrite the same managed Certbot live lineage.
        'for agoge_certbot_timer in certbot.timer snap.certbot.renew.timer; do',
        '  systemctl disable --now "$agoge_certbot_timer" >/dev/null 2>&1 || true',
        'done',
        'systemctl enable --now agoge-guacamole-tls.timer',
        'for agoge_tls_attempt in $(seq 1 12); do',
        '  if systemctl start agoge-guacamole-tls.service || '
        '/usr/bin/python3 /etc/agoge-guacamole-tls/sync.py --check-current; then exit 0; fi',
        '  sleep 10',
        'done',
        'exit 1',
        ')', 'agoge_tls_status=$?', '[ "$agoge_tls_status" -eq 0 ] || exit "$agoge_tls_status"', _END, '',
    ])


def install_guacamole_tls_in_startup(
    script: str, secret_name: str, hostname: str, domain: str, *, impersonate: str | None = None,
) -> str:
    """Install TLS ahead of an existing startup script's one-time setup guard."""
    install = render_guacamole_tls_install(secret_name, hostname, domain, impersonate=impersonate)
    start = script.find(_START + '\n')
    if start != -1:
        _, marker, suffix = script[start:].partition(_END + '\n')
        if not marker:
            raise ValueError('Existing Guacamole TLS startup segment is incomplete')
        return script[:start] + install + suffix
    if not script.startswith('#!'):
        raise ValueError('Guacamole startup script needs a shell shebang')
    shebang, _, body = script.partition('\n')
    return shebang + '\n' + install + body
