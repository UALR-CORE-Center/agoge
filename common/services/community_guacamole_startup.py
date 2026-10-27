"""Embedded, root-only JSON authentication bootstrap for shared Guacamole VMs."""
import re
import shlex


COMMUNITY_GUAC_AGENT = r'''#!/usr/bin/env python3
import base64
import ipaddress
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import urllib.request

ROOT = Path('/etc/agoge-community-guacamole')
APP = Path('/opt/guacamole')
METADATA = 'http://metadata.google.internal/computeMetadata/v1/'


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('Unexpected configuration redirect')


def request(url, headers):
    with urllib.request.build_opener(NoRedirect).open(
            urllib.request.Request(url, headers=headers), timeout=15) as response:
        data = response.read(65537)
        if len(data) > 65536:
            raise ValueError('Configuration response is too large')
        return data


def command(args, check=True):
    # Docker may include environment secrets in failures. Capture all output,
    # and never echo arguments or exception bodies to the startup log.
    return subprocess.run(args, check=check, capture_output=True, timeout=180)


def atomic_write(path, value, mode=0o600):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=path.parent)
    try:
        os.fchmod(descriptor, mode)
        with os.fdopen(descriptor, 'w') as output:
            output.write(value)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def signing_key():
    reference = (ROOT / 'secret-version').read_text().strip()
    if not re.fullmatch(r'projects/[a-z0-9-]+/secrets/agoge-guac-[a-z]{10}/versions/[1-9][0-9]*', reference):
        raise ValueError('Invalid secret reference')
    token = json.loads(request(
        METADATA + 'instance/service-accounts/default/token',
        {'Metadata-Flavor': 'Google'}))['access_token']
    response = json.loads(request(
        'https://secretmanager.googleapis.com/v1/' + reference + ':access',
        {'Authorization': 'Bearer ' + token}))
    secret = json.loads(base64.b64decode(response['payload']['data'], validate=True))
    key = secret['key']
    if not isinstance(key, str) or not re.fullmatch(r'[a-fA-F0-9]{32}', key):
        raise ValueError('Invalid signing configuration')
    return key


def compose(key, host, domain):
    return {
        'version': '3.7',
        'services': {
            'guacd': {
                'image': 'guacamole/guacd:1.6.0',
                # The image's own check runs every 300s, so Swarm withholds guacd
                # for five minutes after every lab start.
                'healthcheck': {
                    'test': ['CMD-SHELL', 'nc -z 127.0.0.1 4822 || exit 1'],
                    'interval': '10s', 'timeout': '5s', 'retries': 3, 'start_period': '5s',
                },
                'networks': ['guacnet'],
                'volumes': ['guac_recordings:/record'],
                'deploy': {'replicas': 1, 'restart_policy': {'condition': 'on-failure'}},
            },
            'guacamole': {
                'image': 'guacamole/guacamole:1.6.0',
                'environment': {
                    'GUACD_HOSTNAME': 'guacd', 'GUACD_PORT': '4822',
                    'JSON_ENABLED': 'true', 'JSON_SECRET_KEY': key,
                },
                'networks': ['guacnet'],
                'volumes': ['guac_recordings:/record'],
                'deploy': {'replicas': 1, 'restart_policy': {'condition': 'on-failure'}},
            },
            'nginx': {
                'image': 'nginx:alpine',
                'ports': ['80:80', '443:443'],
                'environment': {'GUAC_HOST': host, 'GUAC_DOMAIN': domain},
                'volumes': [
                    '/opt/guacamole/nginx/conf.d:/etc/nginx/conf.d:ro',
                    '/etc/letsencrypt:/etc/letsencrypt:ro',
                ],
                'networks': ['guacnet'],
                'deploy': {'replicas': 1, 'restart_policy': {'condition': 'on-failure'}},
            },
        },
        'networks': {'guacnet': {'driver': 'overlay', 'attachable': True}},
        'volumes': {'guac_recordings': {}},
    }


def nginx_configuration(host, domain):
    return """server {
    listen 80;
    server_name GUAC_HOST;
    return 301 https://$host$request_uri;
}
server {
    listen 443 ssl;
    server_name GUAC_HOST;
    ssl_certificate /etc/letsencrypt/live/GUAC_DOMAIN/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/GUAC_DOMAIN/privkey.pem;
    location / {
        proxy_pass http://guacamole:8080/;
        proxy_buffering off;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 3600s;
    }
}
""".replace('GUAC_HOST', host).replace('GUAC_DOMAIN', domain)


def certificate_usable(certificate):
    """Present and valid for at least another day; images can outlive their certificate."""
    if not (certificate / 'fullchain.pem').is_file() or not (certificate / 'privkey.pem').is_file():
        return False
    return command(['openssl', 'x509', '-checkend', '86400', '-noout',
                    '-in', str(certificate / 'fullchain.pem')], check=False).returncode == 0


def configure():
    host = (ROOT / 'host').read_text().strip()
    domain = (ROOT / 'domain').read_text().strip()
    if (not re.fullmatch(r'[a-z]{10}-display\.[a-z0-9][a-z0-9.-]+', host)
            or not re.fullmatch(r'[a-z0-9][a-z0-9.-]+', domain)
            or not host.endswith('.' + domain)):
        raise ValueError('Invalid proxy DNS configuration')
    key = signing_key()
    command(['systemctl', 'stop', 'guacamole.service'], check=False)
    command(['systemctl', 'start', 'docker'])
    address = request(METADATA + 'instance/network-interfaces/0/ip',
                      {'Metadata-Flavor': 'Google'}).decode().strip()
    ipaddress.ip_address(address)
    swarm = json.loads(command(['docker', 'info', '--format', '{{json .Swarm}}']).stdout)
    if swarm.get('LocalNodeState') != 'active' or swarm.get('NodeAddr') != address:
        # An image can carry its build host's swarm, whose node certificate
        # expires and leaves it in the 'error' state; init fails until it is left.
        if swarm.get('LocalNodeState') != 'inactive':
            command(['docker', 'swarm', 'leave', '--force'])
        command(['docker', 'swarm', 'init', '--advertise-addr', address])
    certificate = Path('/etc/letsencrypt/live') / domain
    if not certificate_usable(certificate):
        # The project image should carry a valid wildcard certificate. Without one,
        # issue a certificate for this host only (HTTP-01 on port 80), stored
        # under the same lineage name so the nginx paths do not change. This
        # runs after the swarm reset so no baked stack still holds port 80.
        if not shutil.which('certbot'):
            raise ValueError('The shared proxy TLS certificate is unavailable and certbot is not installed')
        # Let's Encrypt allows few failed validations per host per hour; do not
        # spend one before the proxy's DNS record points at this VM.
        external = request(METADATA + 'instance/network-interfaces/0/access-configs/0/external-ip',
                           {'Metadata-Flavor': 'Google'}).decode().strip()
        try:
            resolved = {info[4][0] for info in socket.getaddrinfo(host, 80, socket.AF_INET)}
        except OSError:
            resolved = set()
        if external not in resolved:
            raise ValueError('The shared proxy TLS certificate is unavailable; ' + host
                             + ' does not resolve to this VM yet')
        if certificate.exists():
            # An expired wildcard lineage of the same name would otherwise make
            # certbot ask whether to change its domains.
            command(['certbot', 'delete', '--non-interactive', '--cert-name', domain], check=False)
        result = command(['certbot', 'certonly', '--standalone', '--preferred-challenges', 'http',
                          '--non-interactive', '--agree-tos', '--register-unsafely-without-email',
                          '--cert-name', domain, '-d', host], check=False)
        if result.returncode != 0:
            raise ValueError('The shared proxy TLS certificate is unavailable; certbot could not issue one for '
                             + host)
        print('Issued a host certificate for ' + host + ' because the image has no wildcard certificate.')
    atomic_write(APP / 'docker-compose.yml', json.dumps(compose(key, host, domain)))
    atomic_write(APP / '.env', 'GUAC_HOST=' + host + '\nGUAC_DOMAIN=' + domain + '\n')
    atomic_write(APP / 'nginx/conf.d/guacamole.conf', nginx_configuration(host, domain), 0o644)
    unit = """[Unit]
Description=Agoge shared community Guacamole
After=docker.service network-online.target
Requires=docker.service
Wants=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/guacamole
ExecStart=/usr/bin/docker stack deploy --prune -c /opt/guacamole/docker-compose.yml guacamole

[Install]
WantedBy=multi-user.target
"""
    atomic_write('/etc/systemd/system/guacamole.service', unit, 0o644)
    command(['systemctl', 'daemon-reload'])
    command(['systemctl', 'enable', '--now', 'guacamole.service'])
    print('Shared community Guacamole configuration deployed.')


def failure_reason(error):
    # Only messages and command names this script controls are printed; Docker
    # output and exception bodies can carry the signing key.
    if type(error) is ValueError:
        return str(error)
    if isinstance(error, subprocess.CalledProcessError):
        return ' '.join(error.cmd[:3]) + ' exited with ' + str(error.returncode)
    return type(error).__name__


if __name__ == '__main__':
    try:
        configure()
    except Exception as error:
        print('Shared community Guacamole bootstrap is not ready (' + failure_reason(error)
              + '); retrying is safe.', file=sys.stderr)
        sys.exit(1)
'''


def render_community_guacamole_startup(secret_version_name, unit_id, dns_suffix):
    """Render code and immutable references, never the JSON signing key."""
    if not isinstance(unit_id, str) or not re.fullmatch(r'[a-z]{10}', unit_id):
        raise ValueError('Invalid community lab ID')
    if (not isinstance(secret_version_name, str) or not re.fullmatch(
            r'projects/[a-z0-9-]+/secrets/agoge-guac-' + unit_id + r'/versions/[1-9][0-9]*',
            secret_version_name)):
        raise ValueError('Invalid community proxy secret reference')
    domain = dns_suffix.strip('.').lower()
    if not re.fullmatch(r'[a-z0-9][a-z0-9.-]+', domain) or '..' in domain:
        raise ValueError('Invalid community proxy DNS suffix')
    host = unit_id + '-display.' + domain
    root = '/etc/agoge-community-guacamole'
    return '\n'.join([
        '#!/bin/bash', 'set -euo pipefail', 'umask 077',
        'install -d -m 0700 ' + root,
        'printf %s ' + shlex.quote(secret_version_name) + ' > ' + root + '/secret-version',
        'printf %s ' + shlex.quote(host) + ' > ' + root + '/host',
        'printf %s ' + shlex.quote(domain) + ' > ' + root + '/domain',
        "cat > " + root + "/configure.py <<'AGOGE_COMMUNITY_GUAC_PY'",
        COMMUNITY_GUAC_AGENT, 'AGOGE_COMMUNITY_GUAC_PY',
        'chmod 0700 ' + root + '/configure.py',
        # A host certificate needs the proxy's DNS record, which can be
        # published shortly after the VM boots.
        'for attempt in $(seq 1 12); do',
        '  if python3 ' + root + '/configure.py; then exit 0; fi',
        '  sleep 10', 'done', 'exit 1', '',
    ])
