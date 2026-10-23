#!/bin/bash
# agoge-nested-direct-connect: SSH from outside the lab to this nested host's primary address reaches the
# jumpbox, the guest exposed on alias slot @@SLOT@@, instead of the host's own sshd. Lab-internal (RFC 1918)
# and IAP sources still reach the host. The lab build merges this into startup-script, so it runs in a
# subshell and exits only itself, and every boot flushes and refills its own chains.
# Must stay bash 3.2-clean: the tests run it on macOS's bash.
(
  set -u
  HOST_JSON="${AGOGE_NESTED_HOST_JSON:-@@HOST_JSON@@}"
  SLOT=@@SLOT@@
  PRE_CHAIN=AGOGE-NESTED-DIRECT
  FWD_CHAIN=AGOGE-NESTED-DIRECT-FWD

  log() {
    echo "agoge-nested-direct-connect: $*"
  }

  # GCP's DHCP default route carries the primary address as its src; failing that, the route device's first address.
  # The FORWARD accept below is a backstop: the runtime already accepts DNAT'd traffic to every exposed guest.
  route="$(ip -o -4 route show default | head -n 1)"
  primary_ip="$(echo "$route" | awk '{for (i = 1; i < NF; i++) if ($i == "src") {print $(i + 1); exit}}')"
  if [ -z "$primary_ip" ]; then
    device="$(echo "$route" | awk '{for (i = 1; i < NF; i++) if ($i == "dev") {print $(i + 1); exit}}')"
    if [ -n "$device" ]; then
      primary_ip="$(ip -o -4 addr show dev "$device" | awk '{split($4, a, "/"); print a[1]; exit}')"
    fi
  fi
  guest_ip="$(jq -r --argjson slot "$SLOT" '.exposures[$slot] as [$g, $n]
                | ([.guests[] | select(.name == $g) | .nics[$n].ip][0] // empty)' "$HOST_JSON" 2>/dev/null)"
  if [ -z "$primary_ip" ]; then
    log "no primary address on the default route; SSH stays on this host"
    exit 0
  fi
  if [ -z "$guest_ip" ]; then
    log "slot $SLOT has no guest with a static IP; SSH stays on this host"
    exit 0
  fi

  iptables -t nat -N "$PRE_CHAIN" 2>/dev/null || iptables -t nat -F "$PRE_CHAIN"
  for source in 10.0.0.0/8 172.16.0.0/12 192.168.0.0/16 35.235.240.0/20; do
    iptables -t nat -A "$PRE_CHAIN" -s "$source" -j RETURN
  done
  iptables -t nat -A "$PRE_CHAIN" -d "$primary_ip" -p tcp --dport 22 -j DNAT --to-destination "$guest_ip:22"
  iptables -t nat -C PREROUTING -j "$PRE_CHAIN" 2>/dev/null || iptables -t nat -I PREROUTING 1 -j "$PRE_CHAIN"

  # Ahead of libvirt's REJECTs, which drop new connections into a NAT network.
  iptables -N "$FWD_CHAIN" 2>/dev/null || iptables -F "$FWD_CHAIN"
  iptables -A "$FWD_CHAIN" -d "$guest_ip" -p tcp --dport 22 -m conntrack --ctstate DNAT -j ACCEPT
  iptables -C FORWARD -j "$FWD_CHAIN" 2>/dev/null || iptables -I FORWARD 1 -j "$FWD_CHAIN"
  sysctl -qw net.ipv4.ip_forward=1
  log "SSH to $primary_ip from outside the lab goes to $guest_ip"
)
