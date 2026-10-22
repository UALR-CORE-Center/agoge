#!/bin/bash
# Install local repository code; no remote application script is fetched.
set -euo pipefail
if [[ "$EUID" -ne 0 ]]; then
  echo 'Run this installer with sudo.' >&2
  exit 1
fi
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y wireguard-tools python3 iptables
install -d -m 0755 /usr/local/lib/agoge-wireguard
install -d -m 0700 /etc/agoge-wireguard /etc/wireguard
install -m 0755 "$script_dir/agoge_wireguard_pi.py" /usr/local/lib/agoge-wireguard/pi.py
install -m 0644 "$script_dir/agoge-wireguard-pi.service" /etc/systemd/system/agoge-wireguard-pi.service
systemctl daemon-reload
python3 /usr/local/lib/agoge-wireguard/pi.py keygen
echo 'Enroll this PUBLIC key, create config.json and token as documented, then enable agoge-wireguard-pi.'
