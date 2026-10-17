#!/bin/bash
# agoge-nested-builder: builds a nested lab host's guests on its template server (resumable).
#  1. Installs libvirt and its tools.
#  2. Replaces libvirt's default network with the spec's networks (bridge @@BRIDGE_PREFIX@@<index>).
#  3. Installs and starts agoge-nested-runtime, so its firewall is in force before any guest boots.
#  4. Installs the guests in start_order, two at a time: media from the cache or the URL, SHA-256
#     checked, then the catalog entry's install method.
#  5. Runs each agent guest's post_install_script through guest-exec.
#  6. Reports ready (or failed) and leaves the guests running.
# Progress goes to the agoge-nested/* guest attributes; a heartbeat is written every minute.
# Every step leaves a marker in the state directory, so a reboot resumes rather than restarts.
#
# Secrets (admin and VNC passwords, the rendered autounattend.xml) are read only from
# @@RUN_DIR@@/secrets.json, a tmpfs copy of the agoge-nested-secrets metadata. They never appear on
# a command line: virt-customize reads passwords from a root-only file, and the VNC password is put
# into the domain XML by a bash substitution before `virsh define`.
# This script never force-stops a domain: a guest that will not shut down is failed, not killed.
# Must stay bash 3.2-clean: the tests run it on macOS's bash.
set -o pipefail

# The root prefix exists for the tests, which run this without root.
ROOT="${AGOGE_NESTED_ROOT:-}"
METADATA=http://metadata.google.internal/computeMetadata/v1
ATTRIBUTES_URL="$METADATA/instance/guest-attributes/agoge-nested"
STATE_DIR="$ROOT@@STATE_DIR@@"
WORK_DIR="$ROOT@@WORK_DIR@@"
RUN_DIR="$ROOT@@RUN_DIR@@"
SECRETS="$RUN_DIR/secrets.json"
MEDIA_DIR="$ROOT@@MEDIA_DIR@@"
IMAGES_DIR="$ROOT/var/lib/libvirt/images"
MANIFEST="$WORK_DIR/manifest.json"
HOST_JSON="$ROOT@@HOST_JSON@@"
RUNTIME_PATH="$ROOT@@RUNTIME_PATH@@"
RUNTIME_UNIT_PATH="$ROOT@@RUNTIME_UNIT_PATH@@"
RUNTIME_UNIT_NAME=@@RUNTIME_UNIT_NAME@@
LIBVIRT_NETWORK_CONF="$ROOT/etc/libvirt/network.conf"
LOG_FILE="$ROOT/var/log/agoge-nested-builder.log"
BRIDGE_PREFIX=@@BRIDGE_PREFIX@@
MEDIA_BUCKET_SUFFIX=@@MEDIA_BUCKET_SUFFIX@@
VIRTIO_WIN_URL=https://fedorapeople.org/groups/virt/virtio-win/direct-downloads/archive-virtio
HOST_PACKAGES="qemu-system-x86 qemu-utils libvirt-daemon-system virtinst libguestfs-tools genisoimage p7zip-full
  ovmf swtpm jq iptables curl xz-utils"
HEARTBEAT_SECONDS=60
AGENT_WAIT_MINUTES=20
WINDOWS_INSTALL_MINUTES=150
POST_INSTALL_MINUTES=60
AGENTLESS_SETTLE_SECONDS=120
# virt-customize --selinux-relabel and the qemu-ga guest-exec block apply to these osinfo ids.
RHEL_FAMILY='^(rhel|centos|rocky|almalinux|alma|fedora|ol|oraclelinux)'
# Arch ships an uninitialized pacman keyring, names its ssh package openssh, and has no sudo.
ARCH_FAMILY='^archlinux'

HEARTBEAT_PID=

log() {
  echo "agoge-nested-builder: $*"
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) $*" >> "$LOG_FILE" 2>/dev/null
}

put_attribute() {
  local value=${2:0:200}
  curl -sf -X PUT -H 'Metadata-Flavor: Google' --data "$value" "$ATTRIBUTES_URL/$1" >/dev/null \
    || log "could not write guest attribute $1"
}

step() {
  log "$*"
  put_attribute message "$*"
}

metadata_get() {
  curl -sf -H 'Metadata-Flavor: Google' "$METADATA/$1"
}

start_heartbeat() {
  (
    while :; do
      put_attribute heartbeat "$(date +%s)"
      sleep "$HEARTBEAT_SECONDS"
    done
  ) >/dev/null 2>&1 &
  HEARTBEAT_PID=$!
}

stop_heartbeat() {
  if [ -n "$HEARTBEAT_PID" ]; then
    kill "$HEARTBEAT_PID" 2>/dev/null
    wait "$HEARTBEAT_PID" 2>/dev/null
    HEARTBEAT_PID=
  fi
}

# One manifest value for guest $1; null prints as an empty string, booleans as true/false.
guest_value() {
  jq -r --arg g "$1" ".guests[] | select(.name == \$g) | $2 | if . == null then \"\" else tostring end" "$MANIFEST"
}

secret_value() {
  jq -r --arg g "$1" --arg k "$2" '.[$g][$k] // empty' "$SECRETS"
}

uri_encode() {
  jq -rn --arg s "$1" '$s | @uri'
}

# ---------------------------------------------------------------- host

install_packages() {
  local _
  step "installing libvirt"
  for _ in 1 2 3; do
    if apt-get update -q && DEBIAN_FRONTEND=noninteractive apt-get install -y -q $HOST_PACKAGES; then
      return 0
    fi
    sleep 30
  done
  return 1
}

configure_libvirt() {
  # Under libvirt's nftables backend (Debian 13), its own reject rules would still drop the
  # DNAT'd traffic the runtime's iptables rules accept.
  if [ "$(jq -r '.parent_os' "$MANIFEST")" = "debian-13" ]; then
    mkdir -p "$(dirname "$LIBVIRT_NETWORK_CONF")"
    grep -q '^firewall_backend' "$LIBVIRT_NETWORK_CONF" 2>/dev/null \
      || echo 'firewall_backend = "iptables"' >> "$LIBVIRT_NETWORK_CONF"
    systemctl try-restart virtnetworkd.service libvirtd.service
  fi
}

network_xml() {
  jq -r --argjson i "$1" --arg bridge "$BRIDGE_PREFIX$1" '
    .networks[$i] as $n
    | ($n.cidr | split("/")[1]) as $prefix
    | [.guests[] as $g | $g.nics[] | select(.network == $n.name and .ip != null)
       | "      <host mac=\"\(.mac)\" name=\"\($g.name)\" ip=\"\(.ip)\"/>"] as $hosts
    | "<network>",
      "  <name>\($n.name)</name>",
      "  <bridge name=\"\($bridge)\" stp=\"on\" delay=\"0\"/>",
      (if $n.mode == "nat" then "  <forward mode=\"nat\"/>" else empty end),
      (if $n.parent_address then
         "  <ip address=\"\($n.parent_address)\" prefix=\"\($prefix)\">",
         (if $n.dhcp then
            "    <dhcp>",
            "      <range start=\"\($n.dhcp_start)\" end=\"\($n.dhcp_end)\"/>",
            $hosts[],
            "    </dhcp>"
          else empty end),
         "  </ip>"
       else empty end),
      "</network>"' "$MANIFEST"
}

define_networks() {
  local count index name xml
  step "defining networks"
  virsh net-destroy default >/dev/null 2>&1
  virsh net-undefine default >/dev/null 2>&1
  count=$(jq '.networks | length' "$MANIFEST")
  for ((index = 0; index < count; index++)); do
    name=$(jq -r --argjson i "$index" '.networks[$i].name' "$MANIFEST")
    # A reboot mid-step leaves some networks defined; define them afresh.
    if virsh net-info "$name" >/dev/null 2>&1; then
      virsh net-destroy "$name" >/dev/null 2>&1
      virsh net-undefine "$name" >/dev/null 2>&1
    fi
    xml="$WORK_DIR/network-$name.xml"
    network_xml "$index" > "$xml" || return 1
    virsh net-define "$xml" >/dev/null || return 1
    virsh net-autostart "$name" >/dev/null || return 1
    virsh net-start "$name" >/dev/null || return 1
  done
}

# host.json is the runtime's input. While building, every guest is written with autostart off,
# so a reboot's runtime run does not start a half-installed guest.
write_host_json() {
  local autostart_filter='.autostart'
  if [ "$1" = "building" ]; then
    autostart_filter='false'
  fi
  mkdir -p "$(dirname "$HOST_JSON")"
  jq "{version, networks, exposures, console_ports,
       guests: [.guests[] | {name, nics, autostart: $autostart_filter, start_order, start_delay_seconds}]}" \
    "$MANIFEST" > "$HOST_JSON.tmp" && mv "$HOST_JSON.tmp" "$HOST_JSON"
}

install_runtime() {
  step "installing agoge-nested-runtime"
  mkdir -p "$(dirname "$RUNTIME_PATH")" "$(dirname "$RUNTIME_UNIT_PATH")"
  cat > "$RUNTIME_PATH" <<'AGOGE_NESTED_RUNTIME_SCRIPT'
@@RUNTIME_SCRIPT@@
AGOGE_NESTED_RUNTIME_SCRIPT
  chmod 755 "$RUNTIME_PATH"
  cat > "$RUNTIME_UNIT_PATH" <<'AGOGE_NESTED_RUNTIME_UNIT'
@@RUNTIME_UNIT@@
AGOGE_NESTED_RUNTIME_UNIT
  systemctl daemon-reload
  systemctl enable "$RUNTIME_UNIT_NAME" >/dev/null 2>&1 || return 1
}

# ---------------------------------------------------------------- media

gcs_auth_header() {
  metadata_get instance/service-accounts/default/token \
    | jq -r '"Authorization: Bearer " + .access_token' > "$RUN_DIR/gcs-auth"
}

# Downloads gs://bucket/object to a file. The token stays in a header file, off the command line.
gcs_get() {
  gcs_auth_header || return 1
  curl -fsS -H "@$RUN_DIR/gcs-auth" -o "$3" \
    "https://storage.googleapis.com/storage/v1/b/$1/o/$(uri_encode "$2")?alt=media"
}

gcs_put() {
  gcs_auth_header || return 1
  curl -fsS -H "@$RUN_DIR/gcs-auth" -X POST -T "$3" \
    "https://storage.googleapis.com/upload/storage/v1/b/$1/o?uploadType=media&name=$(uri_encode "$2")" >/dev/null
}

lock() {
  until mkdir "$RUN_DIR/lock-$1" 2>/dev/null; do
    sleep 5
  done
}

unlock() {
  rmdir "$RUN_DIR/lock-$1" 2>/dev/null
}

# Sets MEDIA_PATH to a verified copy of guest $1's medium, or FAIL_MESSAGE and returns 1.
fetch_media() {
  local guest=$1 source sha256 format key dest part actual cache_bucket from=source
  source=$(guest_value "$guest" .media.source)
  sha256=$(guest_value "$guest" .media.sha256)
  format=$(guest_value "$guest" .media.format)
  if [ -n "$sha256" ]; then
    key=$sha256
  else
    key="upload-$(guest_value "$guest" .media.media_id)"
  fi
  dest="$MEDIA_DIR/$key.$format"
  part="$dest.part"
  cache_bucket="${PROJECT_ID}_$MEDIA_BUCKET_SUFFIX"
  # Two guests can share a medium; only one downloads it.
  lock "$key"
  if [ -f "$dest" ]; then
    unlock "$key"
    MEDIA_PATH=$dest
    return 0
  fi
  rm -f "$part"
  if [ -n "$sha256" ] && gcs_get "$cache_bucket" "cache/$sha256" "$part" 2>/dev/null; then
    from=cache
  elif [ "$source" = "url" ]; then
    if [ -z "$sha256" ]; then
      unlock "$key"
      FAIL_MESSAGE="the catalog entry has no media_sha256, so its download cannot be verified"
      return 1
    fi
    curl -fsSL --retry 3 -o "$part" "$(guest_value "$guest" .media.url)" || {
      rm -f "$part"; unlock "$key"; FAIL_MESSAGE="could not download the media"; return 1; }
  else
    # Uploads run to 20 GiB; gcloud storage downloads them in parallel slices with retries,
    # authenticated as the instance service account (preinstalled on Debian GCE images).
    gcloud storage cp --no-user-output-enabled "$(guest_value "$guest" .media.gcs_path)" "$part" || {
      rm -f "$part"; unlock "$key"; FAIL_MESSAGE="could not download the uploaded media"; return 1; }
  fi
  actual=$(sha256sum "$part" | cut -d' ' -f1)
  # An instructor upload has no hash until its first use, so there is nothing to compare it with.
  if [ -n "$sha256" ] && [ "$actual" != "$sha256" ]; then
    rm -f "$part"
    unlock "$key"
    FAIL_MESSAGE="media sha256 mismatch: expected $sha256, got $actual"
    return 1
  fi
  mv "$part" "$dest"
  unlock "$key"
  if [ -n "$sha256" ] && [ "$from" != "cache" ]; then
    gcs_put "$cache_bucket" "cache/$sha256" "$dest" 2>/dev/null || log "could not cache $key in gs://$cache_bucket"
  fi
  log "$guest: media $dest (sha256 $actual, from $from)"
  MEDIA_PATH=$dest
}

# Sets VIRTIO_PATH to the pinned virtio-win ISO. The catalog pins a release, not a hash.
fetch_virtio() {
  local version=$1 dest
  dest="$MEDIA_DIR/virtio-win-$version.iso"
  lock "virtio-$version"
  if [ ! -f "$dest" ]; then
    if ! curl -fsSL --retry 3 -o "$dest.part" "$VIRTIO_WIN_URL/virtio-win-$version/virtio-win.iso"; then
      rm -f "$dest.part"
      unlock "virtio-$version"
      FAIL_MESSAGE="could not download virtio-win $version"
      return 1
    fi
    mv "$dest.part" "$dest"
  fi
  unlock "virtio-$version"
  VIRTIO_PATH=$dest
}

largest_disk_file() {
  local files
  files=$(find "$1" -type f \( -iname '*.vmdk' -o -iname '*.vhd' -o -iname '*.vhdx' -o -iname '*.qcow2' \
    -o -iname '*.raw' -o -iname '*.img' \))
  [ -n "$files" ] || return 1
  # shellcheck disable=SC2086 # names come from our own extraction directory
  ls -S $files | head -n 1
}

input_format() {
  case "$1" in
    *.vhd|*.VHD) echo vpc ;;
    *.raw|*.img|*.RAW|*.IMG) echo raw ;;
    *) echo "" ;;
  esac
}

# Converts guest $1's medium $2 (format $3) to the qcow2 disk $4, grown to disk_gb when larger.
prepare_disk() {
  local guest=$1 media=$2 format=$3 disk=$4 work input in_format disk_gb size wanted
  work="$MEDIA_DIR/work-$guest"
  rm -rf "$work"
  mkdir -p "$work"
  case "$format" in
    qcow2|raw|vmdk|vhd|vhdx) input=$media; in_format=$format; [ "$format" = "vhd" ] && in_format=vpc ;;
    img.xz) input="$work/disk.img"; in_format=raw; xz -dc "$media" > "$input" ;;
    tar.xz) tar -xJf "$media" -C "$work" && input=$(largest_disk_file "$work") ;;
    ova) tar -xf "$media" -C "$work" && input=$(largest_disk_file "$work") ;;
    zip|7z) 7z x -y -o"$work" "$media" >/dev/null && input=$(largest_disk_file "$work") ;;
    *) FAIL_MESSAGE="media format $format is not a disk image"; return 1 ;;
  esac
  if [ -z "$input" ] || [ ! -f "$input" ]; then
    rm -rf "$work"
    FAIL_MESSAGE="no disk image found in the $format media"
    return 1
  fi
  [ -n "$in_format" ] || in_format=$(input_format "$input")
  mkdir -p "$IMAGES_DIR"
  if [ -n "$in_format" ]; then
    qemu-img convert -f "$in_format" -O qcow2 "$input" "$disk"
  else
    qemu-img convert -O qcow2 "$input" "$disk"
  fi || { rm -rf "$work"; FAIL_MESSAGE="qemu-img could not convert the media"; return 1; }
  rm -rf "$work"
  disk_gb=$(guest_value "$guest" .disk_gb)
  size=$(qemu-img info --output=json "$disk" | jq '."virtual-size"')
  wanted=$((disk_gb * 1073741824))
  if [ "$wanted" -gt "${size:-0}" ]; then
    qemu-img resize "$disk" "${disk_gb}G" >/dev/null || { FAIL_MESSAGE="could not grow the disk"; return 1; }
  fi
}

# ---------------------------------------------------------------- linux customization

# Writes guest $1's per-NIC network files under $2 and prints "local:remote" upload pairs.
write_network_config() {
  local guest=$1 out=$2 net_config index mac ip prefix gateway dns dhcp file
  net_config=$(guest_value "$guest" .catalog.net_config)
  mkdir -p "$out"
  [ "$net_config" = "netplan" ] && printf 'network:\n  version: 2\n  ethernets:\n' > "$out/90-agoge.yaml"
  # .cfg because Ubuntu 16.04 sources only interfaces.d/*.cfg; Debian sources interfaces.d/*.
  [ "$net_config" = "ifupdown" ] && : > "$out/agoge.cfg"
  while IFS=$'\t' read -r index mac ip prefix gateway dns dhcp; do
    # A NIC with neither a static address nor DHCP is a pure L2 port; leave it unconfigured.
    if [ "$ip" = "-" ] && [ "$dhcp" != "dhcp" ]; then
      continue
    fi
    case "$net_config" in
      networkd)
        file="$out/10-agoge-$index.network"
        {
          printf '[Match]\nMACAddress=%s\n\n[Network]\n' "$mac"
          if [ "$ip" = "-" ]; then
            printf 'DHCP=ipv4\n'
          else
            printf 'Address=%s/%s\n' "$ip" "$prefix"
            [ "$gateway" != "-" ] && printf 'Gateway=%s\n' "$gateway"
            [ "$dns" != "-" ] && printf 'DNS=%s\n' "$dns"
          fi
        } > "$file"
        echo "$file:/etc/systemd/network/10-agoge-$index.network"
        ;;
      netplan)
        {
          printf '    agoge%s:\n      match:\n        macaddress: "%s"\n' "$index" "$mac"
          if [ "$ip" = "-" ]; then
            printf '      dhcp4: true\n'
          else
            printf '      dhcp4: false\n      addresses: ["%s/%s"]\n' "$ip" "$prefix"
            # 0.0.0.0/0, not "default": netplan before 0.103 (Ubuntu 18.04 ships 0.99) rejects the keyword.
            [ "$gateway" != "-" ] && printf '      routes: [{to: 0.0.0.0/0, via: "%s"}]\n' "$gateway"
            [ "$dns" != "-" ] && printf '      nameservers: {addresses: ["%s"]}\n' "$dns"
          fi
        } >> "$out/90-agoge.yaml"
        ;;
      nm-keyfile)
        file="$out/agoge-$index.nmconnection"
        {
          printf '[connection]\nid=agoge-%s\ntype=ethernet\n\n[ethernet]\nmac-address=%s\n\n[ipv4]\n' \
            "$index" "$mac"
          if [ "$ip" = "-" ]; then
            printf 'method=auto\n'
          else
            printf 'method=manual\n'
            if [ "$gateway" != "-" ]; then
              printf 'address1=%s/%s,%s\n' "$ip" "$prefix" "$gateway"
            else
              printf 'address1=%s/%s\n' "$ip" "$prefix"
            fi
            [ "$dns" != "-" ] && printf 'dns=%s;\n' "$dns"
          fi
        } > "$file"
        echo "$file:/etc/NetworkManager/system-connections/agoge-$index.nmconnection"
        ;;
      ifupdown)
        # ifupdown cannot match a MAC, so a udev .link file names the NIC first.
        file="$out/10-agoge-$index.link"
        printf '[Match]\nMACAddress=%s\n\n[Link]\nName=agoge%s\n' "$mac" "$index" > "$file"
        echo "$file:/etc/systemd/network/10-agoge-$index.link"
        {
          printf 'allow-hotplug agoge%s\n' "$index"
          if [ "$ip" = "-" ]; then
            printf 'iface agoge%s inet dhcp\n' "$index"
          else
            printf 'iface agoge%s inet static\n  address %s/%s\n' "$index" "$ip" "$prefix"
            [ "$gateway" != "-" ] && printf '  gateway %s\n' "$gateway"
            [ "$dns" != "-" ] && printf '  dns-nameservers %s\n' "$dns"
          fi
        } >> "$out/agoge.cfg"
        ;;
    esac
  done < <(jq -r --arg g "$guest" '
    (.networks | map({key: .name, value: .}) | from_entries) as $nets
    | .guests[] | select(.name == $g) | .nics | to_entries[]
    | $nets[.value.network] as $n
    | [.key, .value.mac, (.value.ip // "-"), ($n.cidr | split("/")[1]),
       (if $n.mode == "nat" and $n.parent_address then $n.parent_address else "-" end),
       ($n.parent_address // "-"), (if $n.dhcp then "dhcp" else "static" end)] | @tsv' "$MANIFEST")
  [ "$net_config" = "netplan" ] && echo "$out/90-agoge.yaml:/etc/netplan/90-agoge.yaml"
  [ "$net_config" = "ifupdown" ] && echo "$out/agoge.cfg:/etc/network/interfaces.d/agoge.cfg"
  return 0
}

# virt-customize for a Linux guest: hostname, admin user, agent, network, cloud-init off.
# Guest names, usernames, and packages are validated by the API (slugs), so they are safe in
# --run-command strings. The password is read from a root-only file, never passed as an argument.
customize_linux() {
  local guest=$1 disk=$2 method user osinfo net_config packages install upload password_file ssh_package
  local args=()
  method=$(guest_value "$guest" .catalog.install_method)
  user=$(guest_value "$guest" .admin_username)
  osinfo=$(guest_value "$guest" .catalog.osinfo)
  net_config=$(guest_value "$guest" .catalog.net_config)
  password_file="$RUN_DIR/password-$guest"
  (umask 077 && secret_value "$guest" admin_password > "$password_file")
  if [ ! -s "$password_file" ]; then
    rm -f "$password_file"
    FAIL_MESSAGE="agoge-nested-secrets has no admin password for this guest"
    return 1
  fi
  install=qemu-guest-agent
  ssh_package=openssh-server
  args=(-a "$disk" --hostname "$guest")
  if echo "$osinfo" | grep -Eq "$ARCH_FAMILY"; then
    ssh_package=openssh
    install="$install,sudo"
    # pacman-init.service fills the keyring only on first boot, and virt-customize's pacman -S does not
    # sync. A full -Syu, not -Sy: Arch does not support partial upgrades.
    args+=(--run-command 'pacman-key --init && pacman-key --populate archlinux && pacman -Syu --noconfirm'
      --write '/etc/sudoers.d/10-agoge-wheel:%wheel ALL=(ALL:ALL) ALL'
      --chmod '0440:/etc/sudoers.d/10-agoge-wheel')
  fi
  if [ "$method" = "cloud_image" ]; then
    packages=$(jq -r --arg g "$guest" '.guests[] | select(.name == $g) | .packages | join(",")' "$MANIFEST")
    install="$install,$ssh_package${packages:+,$packages}"
  fi
  args+=(--install "$install"
    --run-command "id -u $user >/dev/null 2>&1 || useradd -m -s /bin/bash $user"
    --run-command "for group in sudo wheel; do getent group \$group >/dev/null && usermod -aG \$group $user; done; true"
    --password "$user:file:$password_file"
    --run-command 'systemctl enable qemu-guest-agent >/dev/null 2>&1 || true')
  if [ "$method" = "cloud_image" ]; then
    # Disabled, not purged: a purge also removes the network config the image boots with (Working Note 16).
    args+=(--touch /etc/cloud/cloud-init.disabled
      --run-command 'rm -f /etc/ssh/ssh_host_*'
      --firstboot-command 'ssh-keygen -A && (systemctl restart ssh || systemctl restart sshd)'
      # cloud-init's growpart no longer runs, so the root filesystem is grown here. --nofsroot drops a
      # btrfs subvolume suffix (Fedora's root is /dev/vda4[/root]), and the resize tool follows the fstype.
      --firstboot-command 'command -v growpart >/dev/null || exit 0; root=$(findmnt -nvo SOURCE /); disk=/dev/$(lsblk -no PKNAME "$root"); growpart "$disk" "${root##*[!0-9]}" && case $(findmnt -no FSTYPE /) in xfs) xfs_growfs / ;; btrfs) btrfs filesystem resize max / ;; *) resize2fs "$root" ;; esac')
  fi
  while IFS= read -r upload; do
    [ -n "$upload" ] && args+=(--upload "$upload")
  done < <(write_network_config "$guest" "$WORK_DIR/net-$guest")
  case "$net_config" in
    networkd) args+=(--run-command 'systemctl enable systemd-networkd') ;;
    netplan) args+=(--run-command 'chmod 600 /etc/netplan/90-agoge.yaml') ;;
    nm-keyfile) args+=(--run-command 'chmod 600 /etc/NetworkManager/system-connections/agoge-*.nmconnection') ;;
  esac
  if echo "$osinfo" | grep -Eq "$RHEL_FAMILY"; then
    # RHEL's qemu-ga ships with guest-exec blocked; post-install needs it.
    args+=(--run-command "if [ -f /etc/sysconfig/qemu-ga ]; then sed -i -e '/^BLACKLIST_RPC=/s/^/#/' -e '/^FILTER_RPC_ARGS=/s/^/#/' /etc/sysconfig/qemu-ga; fi"
      --selinux-relabel)
  fi
  if ! virt-customize "${args[@]}" >> "$WORK_DIR/virt-customize-$guest.log" 2>&1; then
    rm -f "$password_file"
    FAIL_MESSAGE="virt-customize failed: $(tail -n 1 "$WORK_DIR/virt-customize-$guest.log")"
    return 1
  fi
  rm -f "$password_file"
}

# ---------------------------------------------------------------- domains

# Defines guest $1 with disk $2 and the CD-ROM images that follow.
define_domain() {
  local guest=$1 disk=$2 xml err osinfo firmware disk_bus cdrom_bus boot console port password text from to
  local index mac network
  shift 2
  osinfo=$(guest_value "$guest" .catalog.osinfo)
  firmware=$(guest_value "$guest" .catalog.firmware)
  disk_bus=$(guest_value "$guest" .catalog.disk_bus)
  cdrom_bus=sata
  [ "$disk_bus" = "ide" ] && cdrom_bus=ide
  boot=hd,cdrom
  [ "$firmware" = "uefi" ] && boot=uefi,hd,cdrom
  # shellcheck disable=SC2054 # the commas are virt-install sub-options
  local args=(--print-xml --import --noautoconsole --name "$guest"
    --memory "$(guest_value "$guest" .memory_mb)" --vcpus "$(guest_value "$guest" .vcpus)"
    --cpu host-passthrough --boot "$boot" --video "$(guest_value "$guest" .catalog.video)"
    --disk "path=$disk,format=qcow2,bus=$disk_bus"
    --channel unix,target.type=virtio,target.name=org.qemu.guest_agent.0)
  for cdrom in "$@"; do
    args+=(--disk "path=$cdrom,device=cdrom,bus=$cdrom_bus")
  done
  while IFS=$'\t' read -r index mac network; do
    args+=(--network "network=$network,model=$(guest_value "$guest" .catalog.nic_model),mac=$mac")
  done < <(jq -r --arg g "$guest" '.guests[] | select(.name == $g) | .nics | to_entries[]
                                    | [.key, .value.mac, .value.network] | @tsv' "$MANIFEST")
  console=$(guest_value "$guest" .console)
  if [ "$console" = "true" ]; then
    port=$(jq -r --arg g "$guest" '.console_ports[$g] // empty' "$MANIFEST")
    password=$(secret_value "$guest" vnc_password)
    if [ -z "$port" ] || [ -z "$password" ]; then
      FAIL_MESSAGE="the console has no port or VNC password"
      return 1
    fi
    args+=(--graphics "vnc,listen=0.0.0.0,port=$port")
  else
    args+=(--graphics none)
  fi
  xml="$RUN_DIR/domain-$guest.xml"
  err="$WORK_DIR/virt-install-$guest.log"
  (umask 077 && : > "$xml")
  if ! virt-install "${args[@]}" --osinfo "$osinfo" > "$xml" 2> "$err"; then
    log "$guest: virt-install rejected osinfo $osinfo ($(tail -n 1 "$err")); using generic"
    if ! virt-install "${args[@]}" --osinfo generic > "$xml" 2>> "$err"; then
      rm -f "$xml"
      FAIL_MESSAGE="virt-install failed: $(tail -n 1 "$err")"
      return 1
    fi
  fi
  if [ "$console" = "true" ]; then
    # VNC passwords are alphanumeric (derive), but escape anyway. A bash substitution and the
    # printf builtin keep the password out of every process's arguments.
    password=${password//&/&amp;}
    password=${password//\"/&quot;}
    password=${password//</&lt;}
    text=$(<"$xml")
    from='<graphics type="vnc"'
    to="<graphics type=\"vnc\" passwd=\"$password\""
    case "$text" in
      *"$from"*) ;;
      *) rm -f "$xml"; FAIL_MESSAGE="virt-install produced no VNC console"; return 1 ;;
    esac
    # Split rather than ${text/from/to}: replacement quoting and `&` differ between bash 3.2 and 5.2.
    printf '%s%s%s\n' "${text%%"$from"*}" "$to" "${text#*"$from"}" > "$xml"
  fi
  if ! virsh define "$xml" >/dev/null 2>> "$err"; then
    rm -f "$xml"
    FAIL_MESSAGE="virsh define failed: $(tail -n 1 "$err")"
    return 1
  fi
  rm -f "$xml"
}

domain_state() {
  virsh domstate "$1" 2>/dev/null
}

# Waits up to $3 minutes for guest $1 to reach state $2.
wait_for_state() {
  local tries
  for ((tries = 0; tries < $3 * 2; tries++)); do
    [ "$(domain_state "$1")" = "$2" ] && return 0
    sleep 30
  done
  [ "$(domain_state "$1")" = "$2" ]
}

wait_for_agent() {
  local tries
  for ((tries = 0; tries < AGENT_WAIT_MINUTES * 6; tries++)); do
    virsh qemu-agent-command "$1" '{"execute":"guest-ping"}' >/dev/null 2>&1 && return 0
    sleep 10
  done
  return 1
}

# The guest is up when its agent answers, or for an agentless entry when it has kept running.
wait_until_up() {
  local guest=$1
  if [ "$(guest_value "$guest" .catalog.agent)" = "true" ]; then
    wait_for_agent "$guest" || { FAIL_MESSAGE="the guest agent did not answer"; return 1; }
  else
    sleep "$AGENTLESS_SETTLE_SECONDS"
    [ "$(domain_state "$guest")" = "running" ] || { FAIL_MESSAGE="the guest stopped running"; return 1; }
  fi
}

start_domain() {
  virsh start "$1" >/dev/null 2>&1 || { FAIL_MESSAGE="virsh start failed"; return 1; }
}

# A guest whose install a reboot interrupted is shut down (never destroyed) and removed.
reset_guest() {
  local guest=$1 state
  state=$(domain_state "$guest") || state=
  if [ -n "$state" ]; then
    if [ "$state" != "shut off" ]; then
      virsh shutdown "$guest" >/dev/null 2>&1
      wait_for_state "$guest" "shut off" 3 || {
        FAIL_MESSAGE="an interrupted install did not shut down"; return 1; }
    fi
    virsh undefine "$guest" --nvram >/dev/null 2>&1 || virsh undefine "$guest" >/dev/null 2>&1
  fi
  rm -f "$IMAGES_DIR/$guest.qcow2"
}

eject_media() {
  local target
  for target in $(virsh domblklist "$1" --details | awk '$2 == "cdrom" {print $3}'); do
    virsh change-media "$1" "$target" --eject --config >/dev/null 2>&1 || log "$1: could not eject $target"
  done
}

# Builds guest $1's unattend ISO from the autounattend.xml the Cloud Function rendered into the
# secrets. It holds the admin password, so it lives on tmpfs and is deleted once the install ends.
unattend_iso() {
  local guest=$1
  local dir="$RUN_DIR/unattend-$guest"
  rm -rf "$dir"
  (umask 077 && mkdir -p "$dir/files" && secret_value "$guest" autounattend > "$dir/files/autounattend.xml")
  if [ ! -s "$dir/files/autounattend.xml" ]; then
    rm -rf "$dir"
    FAIL_MESSAGE="agoge-nested-secrets has no autounattend for this guest"
    return 1
  fi
  genisoimage -quiet -J -r -V AGOGE -o "$dir/unattend.iso" "$dir/files" || {
    rm -rf "$dir"; FAIL_MESSAGE="could not build the unattend ISO"; return 1; }
  rm -rf "$dir/files"
  # qemu runs as libvirt-qemu and must reach the ISO through the otherwise private run directory.
  chmod 711 "$dir"
  chgrp libvirt-qemu "$dir/unattend.iso" 2>/dev/null
  chmod 640 "$dir/unattend.iso"
  UNATTEND_PATH="$dir/unattend.iso"
}

# ---------------------------------------------------------------- install methods

install_cloud_image() {
  local guest=$1 disk="$IMAGES_DIR/$1.qcow2"
  set_guest_status "$guest" downloading
  fetch_media "$guest" || return 1
  set_guest_status "$guest" installing
  prepare_disk "$guest" "$MEDIA_PATH" "$(guest_value "$guest" .media.format)" "$disk" || return 1
  customize_linux "$guest" "$disk" || return 1
  define_domain "$guest" "$disk" || return 1
  start_domain "$guest" || return 1
  wait_until_up "$guest"
}

install_disk_image() {
  local guest=$1 disk="$IMAGES_DIR/$1.qcow2"
  set_guest_status "$guest" downloading
  fetch_media "$guest" || return 1
  set_guest_status "$guest" installing
  prepare_disk "$guest" "$MEDIA_PATH" "$(guest_value "$guest" .media.format)" "$disk" || return 1
  if [ "$(guest_value "$guest" .catalog.family)" = "linux" ] && [ "$(guest_value "$guest" .catalog.agent)" = "true" ]; then
    customize_linux "$guest" "$disk" || return 1
  fi
  define_domain "$guest" "$disk" || return 1
  start_domain "$guest" || return 1
  wait_until_up "$guest"
}

install_unattended_iso() {
  local guest=$1 disk="$IMAGES_DIR/$1.qcow2" virtio_version cdroms=()
  set_guest_status "$guest" downloading
  fetch_media "$guest" || return 1
  cdroms=("$MEDIA_PATH")
  virtio_version=$(guest_value "$guest" .catalog.virtio_win_version)
  if [ -n "$virtio_version" ]; then
    fetch_virtio "$virtio_version" || return 1
    cdroms+=("$VIRTIO_PATH")
  fi
  set_guest_status "$guest" installing
  unattend_iso "$guest" || return 1
  cdroms+=("$UNATTEND_PATH")
  mkdir -p "$IMAGES_DIR"
  qemu-img create -q -f qcow2 "$disk" "$(guest_value "$guest" .disk_gb)G" || {
    FAIL_MESSAGE="could not create the disk"; return 1; }
  define_domain "$guest" "$disk" "${cdroms[@]}" || return 1
  start_domain "$guest" || return 1
  # virt-install --wait returns at Setup's first reboot (Working Note 17); FirstLogonCommands
  # power the guest off when the install is really done.
  if ! wait_for_state "$guest" "shut off" "$WINDOWS_INSTALL_MINUTES"; then
    rm -rf "$RUN_DIR/unattend-$guest"
    FAIL_MESSAGE="Windows Setup did not finish within $WINDOWS_INSTALL_MINUTES minutes"
    return 1
  fi
  eject_media "$guest"
  rm -rf "$RUN_DIR/unattend-$guest"
  start_domain "$guest" || return 1
  wait_until_up "$guest"
}

install_manual_iso() {
  local guest=$1 disk="$IMAGES_DIR/$1.qcow2"
  set_guest_status "$guest" downloading
  fetch_media "$guest" || return 1
  set_guest_status "$guest" installing
  mkdir -p "$IMAGES_DIR"
  qemu-img create -q -f qcow2 "$disk" "$(guest_value "$guest" .disk_gb)G" || {
    FAIL_MESSAGE="could not create the disk"; return 1; }
  define_domain "$guest" "$disk" "$MEDIA_PATH" || return 1
  start_domain "$guest"
}

# Runs guest $1's post_install_script through guest-exec, with the script as input-data.
post_install() {
  local guest=$1 request pid status tries exited code stderr
  request=$(jq -c --arg g "$guest" '
    .guests[] | select(.name == $g)
    | (if .catalog.family == "windows"
       then {path: "powershell.exe", arg: ["-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", "-"]}
       else {path: "/bin/bash", arg: ["-s"]} end) as $shell
    | {execute: "guest-exec",
       arguments: ($shell + {"input-data": (.post_install_script | @base64), "capture-output": true})}' "$MANIFEST")
  pid=$(virsh qemu-agent-command "$guest" --timeout 60 "$request" 2>/dev/null | jq -r '.return.pid // empty')
  if [ -z "$pid" ]; then
    FAIL_MESSAGE="guest-exec did not start the post-install script"
    return 1
  fi
  for ((tries = 0; tries < POST_INSTALL_MINUTES * 12; tries++)); do
    status=$(virsh qemu-agent-command "$guest" --timeout 30 \
      "{\"execute\":\"guest-exec-status\",\"arguments\":{\"pid\":$pid}}" 2>/dev/null)
    exited=$(echo "$status" | jq -r '.return.exited // false')
    if [ "$exited" = "true" ]; then
      code=$(echo "$status" | jq -r '.return.exitcode // 0')
      [ "$code" = "0" ] && return 0
      stderr=$(echo "$status" | jq -r '.return["err-data"] // "" | @base64d' | tr '\r\n' '  ')
      FAIL_MESSAGE="post-install exited $code: ${stderr:0:150}"
      return 1
    fi
    sleep 5
  done
  FAIL_MESSAGE="post-install did not finish within $POST_INSTALL_MINUTES minutes"
  return 1
}

# ---------------------------------------------------------------- guests

set_guest_status() {
  put_attribute "guest-$1" "$2"
}

finish_guest() {
  echo "$2" > "$STATE_DIR/guest-$1.done"
  set_guest_status "$1" "$2"
  log "$1: $2"
}

build_guest() {
  local guest=$1 method
  [ -f "$STATE_DIR/guest-$guest.done" ] && return 0
  FAIL_MESSAGE=
  method=$(guest_value "$guest" .catalog.install_method)
  if [ -f "$STATE_DIR/installed-$guest" ]; then
    # A reboot interrupted the post-install: the guest is installed, so only start it again.
    if [ "$(domain_state "$guest")" != "running" ]; then
      start_domain "$guest" || { finish_guest "$guest" "failed:$FAIL_MESSAGE"; return; }
    fi
    wait_until_up "$guest" || { finish_guest "$guest" "failed:$FAIL_MESSAGE"; return; }
  else
    reset_guest "$guest" || { finish_guest "$guest" "failed:$FAIL_MESSAGE"; return; }
    step "installing $guest ($method)"
    case "$method" in
      cloud_image) install_cloud_image "$guest" ;;
      unattended_iso) install_unattended_iso "$guest" ;;
      disk_image) install_disk_image "$guest" ;;
      manual_iso) install_manual_iso "$guest" ;;
      *) FAIL_MESSAGE="unknown install method $method"; false ;;
    esac || { finish_guest "$guest" "failed:$FAIL_MESSAGE"; return; }
    : > "$STATE_DIR/installed-$guest"
  fi
  if [ "$method" = "manual_iso" ]; then
    finish_guest "$guest" manual
    return
  fi
  if [ -n "$(guest_value "$guest" .post_install_script)" ] && [ "$(guest_value "$guest" .catalog.agent)" = "true" ]; then
    set_guest_status "$guest" post_install
    step "running $guest's post-install script"
    post_install "$guest" || { finish_guest "$guest" "failed:$FAIL_MESSAGE"; return; }
  fi
  finish_guest "$guest" ready
}

run_queue() {
  local guest
  for guest in "$@"; do
    build_guest "$guest"
  done
}

# At most two installs at a time: start_order is dealt round-robin to two workers.
build_guests() {
  local guest queue0=() queue1=() count=0 pid0 pid1
  for guest in $(jq -r '[.guests | to_entries[]] | sort_by(.value.start_order, .key)[] | .value.name' "$MANIFEST"); do
    if [ $((count % 2)) -eq 0 ]; then
      queue0+=("$guest")
    else
      queue1+=("$guest")
    fi
    count=$((count + 1))
  done
  run_queue "${queue0[@]}" &
  pid0=$!
  if [ "${#queue1[@]}" -gt 0 ]; then
    run_queue "${queue1[@]}" &
    pid1=$!
    wait "$pid1"
  fi
  wait "$pid0"
}

# ---------------------------------------------------------------- phases

finish_build() {
  local phase=$1 message=$2
  echo "$phase" > "$STATE_DIR/done"
  echo "$message" > "$STATE_DIR/message"
  step "$message"
  put_attribute phase "$phase"
  stop_heartbeat
}

# One failed guest does not fail the host; the phase is failed only when no guest is usable.
conclude() {
  local guest result usable=0 failed=""
  for guest in $(jq -r '.guests[].name' "$MANIFEST"); do
    result=$(cat "$STATE_DIR/guest-$guest.done" 2>/dev/null)
    case "$result" in
      ready|manual) usable=$((usable + 1)) ;;
      *) failed="$failed $guest" ;;
    esac
  done
  write_host_json final
  if [ "$usable" -eq 0 ]; then
    finish_build failed "no guest was built; failed:$failed"
  elif [ -n "$failed" ]; then
    finish_build ready "ready; failed:$failed"
  else
    finish_build ready "ready; every guest was built"
  fi
}

run_step() {
  local name=$1
  shift
  [ -f "$STATE_DIR/$name" ] && return 0
  "$@" || return 1
  : > "$STATE_DIR/$name"
}

main() {
  local guest
  mkdir -p "$STATE_DIR" "$WORK_DIR" "$MEDIA_DIR" "$(dirname "$LOG_FILE")"
  # tmpfs; 711 so qemu can open the unattend ISOs inside, while secrets.json stays 600.
  mkdir -p "$RUN_DIR"
  chmod 711 "$RUN_DIR"
  rm -rf "$RUN_DIR"/lock-*

  if [ -f "$STATE_DIR/done" ]; then
    log "the build already finished ($(cat "$STATE_DIR/done"))"
    put_attribute phase "$(cat "$STATE_DIR/done")"
    exit 0
  fi
  if ! metadata_get instance/attributes/agoge-nested-manifest > "$MANIFEST.tmp" || [ ! -s "$MANIFEST.tmp" ]; then
    rm -f "$MANIFEST.tmp"
    log "no agoge-nested-manifest; nothing to build"
    exit 0
  fi
  mv "$MANIFEST.tmp" "$MANIFEST"
  trap stop_heartbeat EXIT
  start_heartbeat
  put_attribute phase building

  if [ ! -s "$SECRETS" ]; then
    (umask 077 && metadata_get instance/attributes/agoge-nested-secrets > "$SECRETS")
  fi
  if [ ! -s "$SECRETS" ]; then
    rm -f "$SECRETS"
    finish_build failed "agoge-nested-secrets is missing; the build cannot continue"
    exit 1
  fi
  chmod 600 "$SECRETS"
  PROJECT_ID=$(metadata_get project/project-id)

  for guest in $(jq -r '.guests[].name' "$MANIFEST"); do
    if [ -f "$STATE_DIR/guest-$guest.done" ]; then
      set_guest_status "$guest" "$(cat "$STATE_DIR/guest-$guest.done")"
    else
      set_guest_status "$guest" pending
    fi
  done

  run_step packages install_packages || { finish_build failed "could not install libvirt"; exit 1; }
  configure_libvirt
  run_step networks define_networks || { finish_build failed "could not define the networks"; exit 1; }
  # Written on every run: autostart stays off until the build finishes.
  write_host_json building
  run_step runtime install_runtime || { finish_build failed "could not install agoge-nested-runtime"; exit 1; }
  systemctl restart "$RUNTIME_UNIT_NAME" || { finish_build failed "agoge-nested-runtime failed"; exit 1; }

  build_guests
  conclude
}

main "$@"
