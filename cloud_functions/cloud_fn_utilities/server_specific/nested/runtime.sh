#!/bin/bash
# agoge-nested-runtime: runs at every boot of every server built from a nested image (idempotent).
#  1. Guests never reach the metadata server (SC-24).
#  2. Guests reach the parent only for DHCP and DNS.
#  3. The server's NIC 0 alias IPs map 1:1 to the exposed guests, in alias-slot order.
#  4. libvirt-guests shuts guests down cleanly when the server stops.
#  5. Autostart guests start in start_order with their delays.
# host.json is written by the builder: the manifest's networks (bridge @@BRIDGE_PREFIX@@<index>),
# guests (name, nics[].ip, autostart, start_order, start_delay_seconds), and exposures
# ([guest, nic index] per alias slot). It holds no secrets.
# Must stay bash 3.2-clean: the tests run it on macOS's bash.
set -u

# The overrides exist for the tests, which run this without root.
HOST_JSON="${AGOGE_NESTED_HOST_JSON:-@@HOST_JSON@@}"
LIBVIRT_GUESTS_CONF="${AGOGE_NESTED_LIBVIRT_GUESTS_CONF:-/etc/default/libvirt-guests}"
BRIDGES="@@BRIDGE_PREFIX@@+"
METADATA_IP=169.254.169.254
ALIASES_URL="http://metadata.google.internal/computeMetadata/v1/instance/network-interfaces/0/ip-aliases/"
IN_CHAIN=AGOGE-NESTED-IN
FWD_CHAIN=AGOGE-NESTED-FWD
PRE_CHAIN=AGOGE-NESTED-PRE
POST_CHAIN=AGOGE-NESTED-POST

log() {
  echo "agoge-nested-runtime: $*"
}

# Our own chains are flushed and refilled, so a second run leaves exactly one copy of each rule.
reset_chain() {
  iptables -t "$1" -N "$2" 2>/dev/null || iptables -t "$1" -F "$2"
}

# Jump at the top of a built-in chain, ahead of libvirt's REJECTs and MASQUERADE.
jump_first() {
  local table=$1 parent=$2
  shift 2
  iptables -t "$table" -C "$parent" "$@" 2>/dev/null || iptables -t "$table" -I "$parent" 1 "$@"
}

block_metadata() {
  iptables -C FORWARD -d "$METADATA_IP" -j REJECT 2>/dev/null || iptables -I FORWARD -d "$METADATA_IP" -j REJECT
}

start_networks() {
  local active network
  active=" $(virsh -q net-list --name 2>/dev/null | tr '\n' ' ') "
  for network in $(jq -r '.networks[].name' "$HOST_JSON"); do
    case "$active" in
      *" $network "*) ;;
      *) virsh net-start "$network" >/dev/null || log "network $network did not start" ;;
    esac
  done
}

isolate_parent() {
  reset_chain filter "$IN_CHAIN"
  # Replies to connections the parent opened (the Connect dialog's SSH tunnels to guests).
  iptables -A "$IN_CHAIN" -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
  iptables -A "$IN_CHAIN" -p udp --dport 67 -j ACCEPT
  iptables -A "$IN_CHAIN" -p udp --dport 53 -j ACCEPT
  iptables -A "$IN_CHAIN" -p tcp --dport 53 -j ACCEPT
  iptables -A "$IN_CHAIN" -j DROP
  jump_first filter INPUT -i "$BRIDGES" -j "$IN_CHAIN"
}

# The directory itself lists entry indices ("0", "1"), not addresses; recursive=true returns the values as JSON.
fetch_aliases() {
  local attempt body
  for attempt in 1 2 3 4 5; do
    if body="$(curl -sf -H "Metadata-Flavor: Google" "${ALIASES_URL}?recursive=true")" \
        && printf '%s' "$body" | jq -r '.[]'; then
      return 0
    fi
    sleep 2
  done
  return 1
}

expose_guests() {
  local primary aliases slot guest guest_ip alias_ip exposed=0
  local alias_list=()
  primary="$(ip -o route show default | awk '{print $5; exit}')"
  if aliases="$(fetch_aliases)"; then
    for alias_ip in $aliases; do
      # Agoge assigns single addresses (/32); anything else is not a slot this script can map.
      case "$alias_ip" in
        */32) alias_list+=("${alias_ip%/32}") ;;
        */*) log "ignoring alias range $alias_ip" ;;
        *) alias_list+=("$alias_ip") ;;
      esac
    done
  else
    log "could not read NIC 0 alias IPs; no guest is exposed"
  fi

  reset_chain nat "$PRE_CHAIN"
  reset_chain nat "$POST_CHAIN"
  reset_chain filter "$FWD_CHAIN"
  # Repeated here because this chain sits ahead of the FORWARD rule above.
  iptables -A "$FWD_CHAIN" -d "$METADATA_IP" -j REJECT

  slot=0
  while read -r guest guest_ip; do
    alias_ip="${alias_list[$slot]:-}"
    if [ -z "$alias_ip" ]; then
      log "slot $slot: no alias IP on NIC 0; $guest is not exposed"
    elif [ "$guest_ip" = "-" ]; then
      log "slot $slot: $guest has no static IP on the exposed NIC; not exposed"
    else
      iptables -t nat -A "$PRE_CHAIN" -d "$alias_ip" -j DNAT --to-destination "$guest_ip"
      iptables -t nat -A "$POST_CHAIN" -s "$guest_ip" -o "$primary" -j SNAT --to-source "$alias_ip"
      # Only DNAT'd connections in and their replies out: an isolated guest gains no other route.
      iptables -A "$FWD_CHAIN" -d "$guest_ip" -m conntrack --ctstate DNAT -j ACCEPT
      iptables -A "$FWD_CHAIN" -s "$guest_ip" -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
      log "slot $slot: $alias_ip -> $guest ($guest_ip)"
      exposed=$((exposed + 1))
    fi
    slot=$((slot + 1))
  done < <(jq -r '.exposures[] as [$g, $n]
                  | ([.guests[] | select(.name == $g) | .nics[$n].ip][0] // "-") as $ip
                  | "\($g) \($ip)"' "$HOST_JSON")
  if [ "${#alias_list[@]}" -gt "$slot" ]; then
    log "ignoring $((${#alias_list[@]} - slot)) extra alias IP(s)"
  fi

  jump_first nat PREROUTING -j "$PRE_CHAIN"
  jump_first nat POSTROUTING -j "$POST_CHAIN"
  jump_first filter FORWARD -j "$FWD_CHAIN"
  # libvirt turns forwarding on only for NAT networks; an exposed guest may sit on an isolated one.
  if [ "$exposed" -gt 0 ]; then
    sysctl -qw net.ipv4.ip_forward=1
  fi
}

configure_libvirt_guests() {
  # ON_BOOT=ignore: libvirt-guests would otherwise resume guests out of start_order.
  cat > "$LIBVIRT_GUESTS_CONF" <<'AGOGE_LIBVIRT_GUESTS'
# Written by agoge-nested-runtime at every boot; edits are overwritten.
ON_BOOT=ignore
ON_SHUTDOWN=shutdown
PARALLEL_SHUTDOWN=8
SHUTDOWN_TIMEOUT=80
AGOGE_LIBVIRT_GUESTS
  # Started (a no-op with ON_BOOT=ignore) so that its stop action runs when the server stops.
  systemctl enable --now libvirt-guests.service >/dev/null 2>&1 || log "could not enable libvirt-guests"
}

start_guests() {
  local guest delay
  # libvirt's own autostart would race the ordered start below.
  for guest in $(jq -r '.guests[].name' "$HOST_JSON"); do
    virsh autostart --disable "$guest" >/dev/null 2>&1 || true
  done
  while read -r guest delay; do
    if [ "$(virsh domstate "$guest" 2>/dev/null)" = "running" ]; then
      continue
    fi
    if [ "$delay" -gt 0 ]; then
      sleep "$delay"
    fi
    virsh start "$guest" >/dev/null || log "guest $guest did not start"
  done < <(jq -r '[.guests | to_entries[] | select(.value.autostart)]
                  | sort_by(.value.start_order, .key)[]
                  | "\(.value.name) \(.value.start_delay_seconds // 0)"' "$HOST_JSON")
}

block_metadata
if [ ! -r "$HOST_JSON" ]; then
  log "$HOST_JSON not found; nothing else to do"
  exit 0
fi
command -v jq >/dev/null 2>&1 || { log "jq is not installed"; exit 1; }
start_networks
isolate_parent
expose_guests
configure_libvirt_guests
start_guests
