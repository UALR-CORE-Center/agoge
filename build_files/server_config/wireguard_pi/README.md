# Registered remote peer bootstrap for a Pi

Copy this directory from the same Agoge release to an Ubuntu/Debian Pi and run
`sudo bash install.sh`. The installer installs OS packages and local repository
code; it does not download or execute a remote application script. It creates a
root-only persistent key and prints **only the public key**. Re-running it keeps
the same key. The Pi private key never goes to Agoge.

An Agoge administrator registers the remote lab in **Admins → Build Manager → Remote Labs**,
using its remote peer ID, device identity, private LAN CIDR, public key, and authorized
instructor emails. Save the returned one-time enrollment token directly on the
Pi. Avoid putting it in shell arguments, shell history, or a catalog file:

```bash
sudo install -m 0600 /dev/null /etc/agoge-wireguard/token
read -rs -p 'Enrollment token: ' agoge_peer_token; echo
printf '%s' "$agoge_peer_token" | sudo tee /etc/agoge-wireguard/token >/dev/null
unset agoge_peer_token
```

Create `/etc/agoge-wireguard/config.json` owned by root with mode `0600`:

```json
{
  "api_url": "https://api.agoge-labs.com/ualr",
  "kit_id": "remote-lab-01",
  "token_file": "/etc/agoge-wireguard/token",
  "key_file": "/etc/wireguard/agoge.key",
  "equipment_interface": "eth0",
  "nat": false,
  "interval": 15
}
```

`kit_id` is the existing Pi client setting for the **Remote peer ID** entered in
**Admins → Build Manager → Remote Labs**. It retains its original name for
compatibility with deployed Pi clients and the authenticated
`/wireguard/kits/<remote-peer-id>/configuration/` endpoint. The current enrollment
API uses `/wireguard/remote-peers/` and calls the private LAN subnet
`remote_network_cidr`; these names refer to the same registered remote peer.

Use the actual API base URL (including its site prefix) and interface connected
to the remote LAN. The private LAN must match **Remote LAN (IPv4 CIDR)**
(`remote_network_cidr`), such as `192.168.50.0/24`, and must not overlap the lab or
tunnel network. Give the remote devices a return route
to the student network via the Pi, or set `nat` to `true` when those routes cannot
be configured. NAT is limited to authorized student traffic to the registered private LAN. The Pi must already have an address on that LAN.

```bash
sudo chown root:root /etc/agoge-wireguard/config.json
sudo chmod 0600 /etc/agoge-wireguard/config.json
sudo systemctl enable --now agoge-wireguard-pi
sudo journalctl -u agoge-wireguard-pi --no-pager -n 30
```

The poller authenticates to the remote peer configuration API, verifies that the enrolled
public key belongs to this Pi, and applies only the current authorized lease.
It refreshes DNS every poll, so a gateway stop/start with a changed ephemeral IP
is picked up automatically. WireGuard keepalive is 25 seconds. Only the assigned
student subnets and gateway tunnel address become Pi `AllowedIPs`; forwarding
permits student-to-remote-LAN traffic and established return traffic. Other
tunnel forwarding and access to Pi services are denied (the gateway can ping
the tunnel address for diagnostics).

Stopped, expired, unassigned, disabled, stale, or unauthorized leases remove the
Pi interface and its scoped firewall/NAT rules on the next poll. Network/API/DNS
failures also disconnect until a verified response returns. This intentionally
favors revocation over connectivity during an API outage. Service shutdown
removes the managed interface/rules, retains the private key, and does not alter
unrelated interfaces or firewall chains. Do not separately enable `wg-quick@agoge`:
the authenticated poller owns its lifecycle. The poller enables IPv4 forwarding
while active; on shutdown it leaves the machine-wide setting as-is to avoid
disrupting other services, but removes all Agoge forwarding permissions.

Never share an enrollment token between remote peers. The registration token is returned
only once; retain it securely for that Pi. Duplicate remote peer IDs, device identities,
and public keys are rejected. A lab number or hostname is a locator, not an enrollment credential.
An instructor cannot obtain the enrollment token through lab details.

The instructor also sees a non-secret **Connection ID** such as
`test-dev-787001:abcdefghij` and the current gateway hostname/DNS suffix. This ID
identifies the cloud lab and does not replace the Pi's enrollment token. A
shared HMI lookup/polling API is future work; this client uses the authenticated
remote peer configuration flow described above.
