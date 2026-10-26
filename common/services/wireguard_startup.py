"""Self-contained Ubuntu WireGuard bootstrap, carried in GCE instance metadata.

Only a Secret Manager version reference and a public boot nonce are rendered into
metadata. Package downloads use Ubuntu's repositories; executable application code
is embedded below rather than fetched from a bucket or a remote script URL.
"""

import re
import shlex


# Keep the guest agent stdlib-only: Ubuntu's python3 is its only Python dependency.
GUEST_AGENT = r'''#!/usr/bin/python3
import base64
import ipaddress
import json
import os
import re
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

ROOT = Path('/etc/agoge-wireguard')
METADATA = 'http://metadata.google.internal/computeMetadata/v1/'
MAX_RESPONSE = 1048576


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeError('redirect_rejected')


HTTP = urllib.request.build_opener(NoRedirect())


def request_json(url, headers=None, data=None):
    request = urllib.request.Request(url, headers=headers or {}, data=data)
    with HTTP.open(request, timeout=15) as response:
        raw = response.read(MAX_RESPONSE + 1)
        if len(raw) > MAX_RESPONSE:
            raise ValueError('response_too_large')
        return json.loads(raw)


def secret_payload():
    version = (ROOT / 'secret-version').read_text().strip()
    # This file is deployed by the renderer and root-only, but validate it before
    # attaching the metadata access token to a network request.
    import re
    if not re.fullmatch(r'projects/[A-Za-z0-9_-]+/secrets/[A-Za-z0-9_-]+/versions/(?:[1-9][0-9]*|latest)', version):
        raise ValueError('invalid_secret_reference')
    token = request_json(METADATA + 'instance/service-accounts/default/token',
                         {'Metadata-Flavor': 'Google'})['access_token']
    response = request_json('https://secretmanager.googleapis.com/v1/' + version + ':access',
                            {'Authorization': 'Bearer ' + token})
    raw = base64.b64decode(response['payload']['data'], validate=True)
    return validate(json.loads(raw))


def key(value):
    if not isinstance(value, str) or len(value) != 44:
        raise ValueError('invalid_wireguard_key')
    if len(base64.b64decode(value, validate=True)) != 32:
        raise ValueError('invalid_wireguard_key')
    return value


def network(value):
    result = ipaddress.ip_network(value, strict=True)
    if result.version != 4:
        raise ValueError('ipv4_required')
    return result


def validate(payload):
    # Revalidate before writing configuration or invoking commands. In particular,
    # no supplied string may introduce a WireGuard config line or shell command.
    config = dict(payload)
    config['private_key'] = key(config['private_key'])
    config['peer_public_key'] = key(config['peer_public_key'])
    gateway = ipaddress.ip_interface(config['gateway_address'])
    peer = ipaddress.ip_interface(config['peer_address'])
    equipment = network(config['equipment_subnet'])
    students = [network(item) for item in config['student_subnets']]
    if gateway.version != 4 or peer.version != 4 or peer.network.prefixlen != 32:
        raise ValueError('invalid_tunnel_address')
    if gateway.network.prefixlen != 30 or peer.ip not in gateway.network or peer.ip == gateway.ip:
        raise ValueError('invalid_tunnel_address')
    if gateway.ip in (gateway.network.network_address, gateway.network.broadcast_address) or peer.ip in (gateway.network.network_address, gateway.network.broadcast_address):
        raise ValueError('invalid_tunnel_address')
    if not students or len(students) > 16:
        raise ValueError('invalid_student_networks')
    if equipment.overlaps(gateway.network) or any(item.overlaps(equipment) or item.overlaps(gateway.network) for item in students):
        raise ValueError('overlapping_networks')
    if equipment.prefixlen == 0 or any(item.prefixlen == 0 for item in students):
        raise ValueError('default_route_forbidden')
    port = config['listen_port']
    if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
        raise ValueError('invalid_listen_port')
    from urllib.parse import urlsplit
    url = urlsplit(config['health_url'])
    if url.scheme != 'https' or not url.hostname or url.username or url.password or url.fragment:
        raise ValueError('invalid_health_url')
    token = config['callback_token']
    if not isinstance(token, str) or not token or len(token) > 512 or any(ord(char) < 33 or ord(char) > 126 for char in token):
        raise ValueError('invalid_callback_token')
    config.update(gateway_address=str(gateway), peer_address=str(peer),
                  equipment_subnet=str(equipment), student_subnets=[str(item) for item in students])
    return config


def command(args, input_text=None, check=True):
    return subprocess.run(args, input=input_text, text=True, capture_output=True,
                          check=check, timeout=30)


def atomic_write(path, content, mode=0o600):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix='.' + path.name)
    try:
        os.fchmod(descriptor, mode)
        with os.fdopen(descriptor, 'w') as output:
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def configuration(config):
    return ('[Interface]\nPrivateKey = ' + config['private_key'] +
            '\nAddress = ' + config['gateway_address'] +
            '\nListenPort = ' + str(config['listen_port']) +
            '\n\n[Peer]\nPublicKey = ' + config['peer_public_key'] +
            '\nAllowedIPs = ' + config['peer_address'] + ', ' + config['equipment_subnet'] + '\n')


def forwarding_rules(config):
    # Only student-initiated connections to this lease's equipment may traverse
    # wg0. An explicit tunnel INPUT drop also blocks access to gateway services.
    rules = []
    for subnet in config['student_subnets']:
        rules.append(['-o', 'wg0', '-s', subnet, '-d', config['equipment_subnet'], '-j', 'ACCEPT'])
        rules.append(['-i', 'wg0', '-s', config['equipment_subnet'], '-d', subnet,
                      '-m', 'conntrack', '--ctstate', 'ESTABLISHED,RELATED', '-j', 'ACCEPT'])
    rules.append(['-j', 'DROP'])
    return rules


def install_boot_guard():
    # wg-quick's persistent ExecStartPre runs this before bringing up a cached
    # interface on every reboot, even if startup or Secret Manager is unavailable.
    # iptables-restore commits the chain and jumps together, never flushing a
    # live forwarding chain into an implicit ACCEPT state.
    lines = ['*filter', ':AGOGE-WG-BOOT - [0:0]', '-F AGOGE-WG-BOOT',
             '-A AGOGE-WG-BOOT -j DROP']
    for direction in ('-i', '-o'):
        rule = ['FORWARD', direction, 'wg0', '-j', 'AGOGE-WG-BOOT']
        if command(['iptables', '-w', '-C'] + rule, check=False).returncode != 0:
            lines.append('-I FORWARD 1 ' + ' '.join(rule[1:]))
    rule = ['INPUT', '-i', 'wg0', '-j', 'DROP']
    if command(['iptables', '-w', '-C'] + rule, check=False).returncode != 0:
        lines.append('-I INPUT 1 ' + ' '.join(rule[1:]))
    lines.append('COMMIT')
    command(['iptables-restore', '--wait', '10', '--noflush'],
            input_text='\n'.join(lines) + '\n')


def remove_boot_guard():
    # Only called after the complete allowlist was committed. Partial removal
    # fails closed because any remaining direction still hits DROP.
    for direction in ('-i', '-o'):
        rule = ['FORWARD', direction, 'wg0', '-j', 'AGOGE-WG-BOOT']
        while command(['iptables', '-w', '-C'] + rule, check=False).returncode == 0:
            command(['iptables', '-w', '-D'] + rule)


def configure_forwarding(config):
    lines = ['*filter', ':AGOGE-WG - [0:0]', '-F AGOGE-WG']
    for rule in forwarding_rules(config):
        lines.append('-A AGOGE-WG ' + ' '.join(rule))
    # Remove obsolete hooks only while the boot guard is already denying all
    # tunnel traffic. Reinsert policy hooks before any unrelated permissive rule,
    # then put the guard back above them in the same atomic table transaction.
    for direction in ('-i', '-o'):
        rule = ['FORWARD', direction, 'wg0', '-j', 'AGOGE-WG']
        while command(['iptables', '-w', '-C'] + rule, check=False).returncode == 0:
            command(['iptables', '-w', '-D'] + rule)
        lines.append('-I FORWARD 1 ' + ' '.join(rule[1:]))
        lines.append('-I FORWARD 1 ' + direction + ' wg0 -j AGOGE-WG-BOOT')
    lines.append('COMMIT')
    command(['iptables-restore', '--wait', '10', '--noflush'],
            input_text='\n'.join(lines) + '\n')
    atomic_write('/etc/sysctl.d/90-agoge-wireguard.conf', 'net.ipv4.ip_forward=1\n')
    command(['sysctl', '-w', 'net.ipv4.ip_forward=1'])


def service_ready(config):
    for direction in ('-i', '-o'):
        if command(['iptables', '-w', '-C', 'FORWARD', direction, 'wg0', '-j', 'AGOGE-WG-BOOT'], check=False).returncode == 0:
            return False
    if command(['systemctl', 'is-active', '--quiet', 'wg-quick@wg0'], check=False).returncode:
        return False
    if Path('/proc/sys/net/ipv4/ip_forward').read_text().strip() != '1':
        return False
    if command(['wg', 'show', 'wg0', 'listen-port']).stdout.strip() != str(config['listen_port']):
        return False
    expected_public = command(['wg', 'pubkey'], input_text=config['private_key'] + '\n').stdout.strip()
    if command(['wg', 'show', 'wg0', 'public-key']).stdout.strip() != expected_public:
        return False
    if command(['wg', 'show', 'wg0', 'peers']).stdout.split() != [config['peer_public_key']]:
        return False
    allowed = command(['wg', 'show', 'wg0', 'allowed-ips']).stdout.split()
    if not allowed or allowed[0] != config['peer_public_key']:
        return False
    if set(re.split(r'[\s,]+', ' '.join(allowed[1:]).strip())) != {config['peer_address'], config['equipment_subnet']}:
        return False
    addresses = json.loads(command(['ip', '-j', '-4', 'address', 'show', 'dev', 'wg0']).stdout)
    wanted = ipaddress.ip_interface(config['gateway_address'])
    if not any(item.get('local') == str(wanted.ip) and item.get('prefixlen') == wanted.network.prefixlen
               for interface in addresses for item in interface.get('addr_info', [])):
        return False
    for direction in ('-i', '-o'):
        if command(['iptables', '-w', '-C', 'FORWARD', direction, 'wg0', '-j', 'AGOGE-WG'], check=False).returncode:
            return False
    for rule in forwarding_rules(config):
        if command(['iptables', '-w', '-C', 'AGOGE-WG'] + rule, check=False).returncode:
            return False
    if command(['iptables', '-w', '-C', 'INPUT', '-i', 'wg0', '-j', 'DROP'], check=False).returncode:
        return False
    return True


def report(config, error=None):
    ready = False
    handshake = 0
    if not error:
        try:
            ready = service_ready(config)
            if ready:
                for line in command(['wg', 'show', 'wg0', 'latest-handshakes']).stdout.splitlines():
                    peer, timestamp = line.split()
                    if peer == config['peer_public_key']:
                        handshake = int(timestamp)
        except Exception:
            ready = False
        if not ready:
            error = 'wireguard_service_unready'
    body = {
        'boot_id': (ROOT / 'boot-id').read_text().strip(),
        'service_ready': ready,
        'tunnel_ready': ready and 0 < time.time() - handshake < 180,
        'latest_handshake': handshake,
        'error': error,
    }
    request_json(config['health_url'],
                 {'Authorization': 'Bearer ' + config['callback_token'], 'Content-Type': 'application/json'},
                 json.dumps(body).encode())


def configure(config):
    target = Path('/etc/wireguard/wg0.conf')
    desired = configuration(config)
    changed = not target.exists() or target.read_text() != desired
    install_boot_guard()
    atomic_write(target, desired)
    command(['systemctl', 'enable', 'wg-quick@wg0'])
    if changed:
        command(['systemctl', 'restart', 'wg-quick@wg0'])
    else:
        command(['systemctl', 'start', 'wg-quick@wg0'])
    # A restart invokes ExecStartPre and reinstalls the deny guard. Commit the
    # allowlist afterward and remove the guard only once every step succeeded.
    configure_forwarding(config)
    remove_boot_guard()
    report(config)


def main():
    config = None
    try:
        if sys.argv[1:] == ['guard']:
            install_boot_guard()
            return 0
        if sys.argv[1:] == ['configure']:
            install_boot_guard()
        config = secret_payload()
        if sys.argv[1:] == ['configure']:
            configure(config)
        elif sys.argv[1:] == ['report']:
            report(config)
        else:
            raise ValueError('invalid_operation')
    except Exception:
        # Captured subprocess stderr and HTTP bodies may contain credentials.
        # Emit only a bounded code and make the callback fail closed if possible.
        if config:
            try:
                report(config, error='bootstrap_failed')
            except Exception:
                pass
        print('Agoge WireGuard bootstrap failed; inspect package/service connectivity and lease authorization.', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
'''


def render_wireguard_startup(secret_version_name: str, boot_id: str) -> str:
    """Render executable metadata without embedding any key or bearer token."""
    if not re.fullmatch(
        r"projects/[A-Za-z0-9_-]+/secrets/[A-Za-z0-9_-]+/versions/(?:[1-9][0-9]*|latest)",
        secret_version_name,
    ):
        raise ValueError("Invalid WireGuard secret version reference")
    if not re.fullmatch(r"[A-Za-z0-9_-]{16,128}", boot_id):
        raise ValueError("Invalid WireGuard boot nonce")
    return """#!/bin/bash
set -euo pipefail
umask 077
export DEBIAN_FRONTEND=noninteractive
# No xtrace: runtime secrets must never enter serial-console logs.
install -d -m 0700 /etc/agoge-wireguard /usr/local/lib/agoge-wireguard
printf '%s\\n' {secret} > /etc/agoge-wireguard/secret-version
printf '%s\\n' {boot} > /etc/agoge-wireguard/boot-id
cat > /usr/local/lib/agoge-wireguard/agent.py <<'AGOGE_WIREGUARD_AGENT'
{agent}
AGOGE_WIREGUARD_AGENT
chmod 0700 /usr/local/lib/agoge-wireguard/agent.py
# apt can race Ubuntu's first-boot updates. Bound retries and lock acquisition.
for attempt in 1 2 3 4 5; do
    if apt-get -o DPkg::Lock::Timeout=60 update -qq && apt-get -o DPkg::Lock::Timeout=60 install -y -qq python3 wireguard iptables; then
        break
    fi
    if [ "$attempt" = 5 ]; then
        echo 'Agoge WireGuard package installation failed.' >&2
        exit 1
    fi
    sleep 5
done
install -d -m 0755 /etc/systemd/system/wg-quick@wg0.service.d
cat > /etc/systemd/system/wg-quick@wg0.service.d/agoge-guard.conf <<'AGOGE_BOOT_GUARD'
[Service]
ExecStartPre=/usr/bin/python3 /usr/local/lib/agoge-wireguard/agent.py guard
AGOGE_BOOT_GUARD
cat > /etc/systemd/system/agoge-wireguard-health.service <<'AGOGE_HEALTH_SERVICE'
[Unit]
Description=Report Agoge WireGuard lease health
After=network-online.target wg-quick@wg0.service
Wants=network-online.target
[Service]
Type=oneshot
ExecStart=/usr/bin/python3 /usr/local/lib/agoge-wireguard/agent.py report
User=root
UMask=0077
NoNewPrivileges=true
ProtectHome=true
ProtectSystem=full
AGOGE_HEALTH_SERVICE
cat > /etc/systemd/system/agoge-wireguard-health.timer <<'AGOGE_HEALTH_TIMER'
[Unit]
Description=Refresh Agoge WireGuard lease health
[Timer]
OnBootSec=30
OnUnitActiveSec=30
AccuracySec=5
[Install]
WantedBy=timers.target
AGOGE_HEALTH_TIMER
systemctl daemon-reload
# Enable reports even if configuration fails, so an operator sees unready health.
systemctl enable --now agoge-wireguard-health.timer
for attempt in 1 2 3 4 5; do
    if /usr/bin/python3 /usr/local/lib/agoge-wireguard/agent.py configure; then
        exit 0
    fi
    sleep 5
done
exit 1
""".format(secret=shlex.quote(secret_version_name), boot=shlex.quote(boot_id), agent=GUEST_AGENT)
