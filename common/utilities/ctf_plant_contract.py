"""
Every name both sides of the CTF flag-delivery channel depend on.

The Cloud Function (FlagPlanter) writes a payload to PLANT_METADATA_KEY and resets the VM.
At boot, the loader stub (added to every lab server at build by LabServerManager) fetches that
key from the metadata server, runs it, and deletes it. The payload reports back through the
guest attribute at GUEST_ATTRIBUTE_PATH. Neither side hardcodes these strings elsewhere.
"""
import re
import textwrap
from typing import Optional

from common.models.agoge import NESTED_GUEST_NAME_PATTERN

PLANT_METADATA_KEY = "agoge-ctf-plant"

# Guest attributes are off by default; every plant writes this pair so the payload can report.
GUEST_ATTRIBUTES_ENABLE_KEY = "enable-guest-attributes"
GUEST_ATTRIBUTES_ENABLE_VALUE = "TRUE"

GUEST_ATTRIBUTE_NAMESPACE = "agoge-ctf/"
GUEST_ATTRIBUTE_RESULT_KEY = "plant-result"
GUEST_ATTRIBUTE_PATH = f"{GUEST_ATTRIBUTE_NAMESPACE}{GUEST_ATTRIBUTE_RESULT_KEY}"

RESULT_OK = "ok"
RESULT_ERROR = "error"
MAX_RESULT_MESSAGE_LENGTH = 200

# Nested Guest Contract (PRD). A nested host's payload writes the ack key as its first action,
# then one result key per relayed guest (same ok/error grammar as plant-result), and plant-result
# last, so its presence means every guest section has finished.
GUEST_ATTRIBUTE_ACK_KEY = "plant-ack"
GUEST_ATTRIBUTE_ACK_PATH = f"{GUEST_ATTRIBUTE_NAMESPACE}{GUEST_ATTRIBUTE_ACK_KEY}"
GUEST_ATTRIBUTE_GUEST_RESULT_PREFIX = f"{GUEST_ATTRIBUTE_RESULT_KEY}-"

# The watcher long-polls PLANT_METADATA_KEY so a nested host is planted without a reset. It and
# the loader stub share the lock and the dedupe file, so one payload never runs twice per boot.
WATCHER_UNIT_NAME = "agoge-ctf-watcher.service"
WATCHER_SCRIPT_PATH = "/usr/local/sbin/agoge-ctf-watcher"
RUN_DIR = "/run/agoge-ctf"
RUN_DIR_MODE = 0o700
RUN_LOCK_PATH = f"{RUN_DIR}/plant.lock"
LAST_PAYLOAD_PATH = f"{RUN_DIR}/last"

# Made by the instructor on each guest domain; a guest `rebuild` reverts to it.
PRISTINE_SNAPSHOT_NAME = "agoge-pristine"

# The Cloud Function times out at 540 s (agoge_app.py), and FlagPlanter waits for the ack and then
# for confirmation inside one invocation, so WATCHER_ACK_SECONDS + NESTED_CONFIRM_TIMEOUT_SECONDS
# must stay below it with room for API overhead. Do not raise one of these alone.
WATCHER_ACK_SECONDS = 30
NESTED_CONFIRM_TIMEOUT_SECONDS = 420
# Each guest relay section runs in parallel under this bound, inside the confirmation window.
RELAY_BUDGET_SECONDS = 360

# GCE metadata value limit: a plant payload larger than this cannot be written to PLANT_METADATA_KEY.
PLANT_PAYLOAD_MAX_BYTES = 256 * 1024

# (location_type, operating_system) -> path pattern, from the PRD's Flag Location Formats table.
# The spec validator enforces these at save time and FlagPlanter re-checks them before a path
# reaches a script; always match with re.fullmatch ('$' alone accepts a trailing newline).
LOCATION_PATH_PATTERNS = {
    ('file', 'linux'): r'^/[A-Za-z0-9_./-]+$',
    ('file', 'windows'): r'^[A-Za-z]:\\[A-Za-z0-9_.\\ -]+$',
    ('registry', 'windows'): r'^HKLM\\[A-Za-z0-9_\\ ]+:[A-Za-z0-9_]+$',
    ('env', 'linux'): r'^[A-Z_][A-Z0-9_]{0,63}$',
    ('env', 'windows'): r'^[A-Z_][A-Z0-9_]{0,63}$',
    ('ads', 'windows'): r'^[A-Za-z]:\\[A-Za-z0-9_.\\ -]+:[A-Za-z0-9_]+$',
}

LINUX_LOADER_METADATA_KEY = "startup-script"
WINDOWS_LOADER_METADATA_KEY = "windows-startup-script-ps1"

_METADATA_SERVER_IP = "169.254.169.254"
_METADATA_URL = f"http://metadata.google.internal/computeMetadata/v1/instance/attributes/{PLANT_METADATA_KEY}"

# The one way a Linux plant payload runs, shared verbatim by the loader and the watcher so both take
# the same lock and dedupe on the same file: a payload is never run twice on one boot (/run is a
# tmpfs). `last` is written before the run, so a payload that dies part-way is not retried either.
# flock is optional only for the loader's sake (util-linux is on every supported image); the
# watcher installer requires it. A missing hash fails closed: nothing runs. The payload does not
# inherit fd 9, so a process it leaves running cannot hold the lock and stall every later plant.
_LOCKED_RUN = f"""(
  mkdir -p {RUN_DIR} && chmod {RUN_DIR_MODE:o} {RUN_DIR} || exit 0
  exec 9>{RUN_LOCK_PATH} || exit 0
  if command -v flock >/dev/null 2>&1; then flock 9 || exit 0; fi
  agoge_ctf_hash="$(sha256sum "$agoge_ctf_plant_file" | cut -d ' ' -f 1)"
  [ -n "$agoge_ctf_hash" ] || exit 0
  [ "$agoge_ctf_hash" = "$(cat {LAST_PAYLOAD_PATH} 2>/dev/null)" ] && exit 0
  printf '%s\\n' "$agoge_ctf_hash" > {LAST_PAYLOAD_PATH} || exit 0
  bash "$agoge_ctf_plant_file" 9>&- >/dev/null 2>&1
)"""

# Appended to whatever startup-script already holds, so it runs in a subshell, never calls a
# top-level `exit`, and silences everything: startup-script output reaches the serial console
# and Cloud Logging. curl -f turns the metadata server's 404 (no plant pending) into a no-op.
# The FORWARD rule goes in before the fetch, on every boot: guests NAT'd through a nested host
# must never reach the metadata server, where a pending plant payload holds every flag.
LINUX_LOADER = f"""#!/bin/bash
# agoge-ctf loader: run a pending flag plant, if any. Never prints the payload.
(
  if command -v iptables >/dev/null 2>&1; then
    iptables -C FORWARD -d {_METADATA_SERVER_IP} -j REJECT \\
      || iptables -I FORWARD -d {_METADATA_SERVER_IP} -j REJECT \\
      || true
  fi
  umask 077
  agoge_ctf_plant_file="$(mktemp "${{TMPDIR:-/tmp}}/agoge-ctf-plant.XXXXXX")" || exit 0
  if curl -sf -H "Metadata-Flavor: Google" -o "$agoge_ctf_plant_file" "{_METADATA_URL}" >/dev/null 2>&1 \\
      && [ -s "$agoge_ctf_plant_file" ]; then
{textwrap.indent(_LOCKED_RUN, '    ')}
  fi
  rm -f "$agoge_ctf_plant_file"
) >/dev/null 2>&1
"""

# Runs as a systemd service on nested hosts so a plant needs no reset (a reset hard-kills every
# guest). It long-polls the plant key: the metadata server holds the request until the value's
# ETag differs from last_etag, or timeout_sec passes. A missing key answers 404 at once, hence the
# sleep. The ETag is filtered to alphanumerics because it is spliced into the next URL.
WATCHER_SCRIPT = f"""#!/bin/bash
# agoge-ctf watcher: run each new flag plant without a reset. Never prints the payload.
exec >/dev/null 2>&1 </dev/null
umask 077
# A stopped watcher must not leave a fetched payload, which holds every flag, behind in {RUN_DIR}.
trap 'rm -f "$agoge_ctf_plant_file" "$agoge_ctf_headers"; exit 0' TERM INT
agoge_ctf_etag=0
while true; do
  mkdir -p {RUN_DIR} && chmod {RUN_DIR_MODE:o} {RUN_DIR} || {{ sleep 5; continue; }}
  agoge_ctf_plant_file="$(mktemp {RUN_DIR}/watch.XXXXXX)" || {{ sleep 5; continue; }}
  agoge_ctf_headers="$(mktemp {RUN_DIR}/headers.XXXXXX)" || {{ rm -f "$agoge_ctf_plant_file"; sleep 5; continue; }}
  agoge_ctf_code="$(curl -s --max-time 330 -H "Metadata-Flavor: Google" -D "$agoge_ctf_headers" \\
    -o "$agoge_ctf_plant_file" -w '%{{http_code}}' \\
    "{_METADATA_URL}?wait_for_change=true&timeout_sec=300&last_etag=$agoge_ctf_etag")"
  if [ "$agoge_ctf_code" = "200" ]; then
    agoge_ctf_etag="$(sed -n 's/^[Ee][Tt][Aa][Gg]:[[:space:]]*//p' "$agoge_ctf_headers" | head -n 1 | tr -cd 'A-Za-z0-9')"
    [ -n "$agoge_ctf_etag" ] || agoge_ctf_etag=0
    if [ -s "$agoge_ctf_plant_file" ]; then
{textwrap.indent(_LOCKED_RUN, '      ')}
    fi
  else
    agoge_ctf_etag=0
    sleep 5
  fi
  rm -f "$agoge_ctf_plant_file" "$agoge_ctf_headers"
done
"""

WATCHER_UNIT_PATH = f"/etc/systemd/system/{WATCHER_UNIT_NAME}"

WATCHER_UNIT = f"""[Unit]
Description=agoge CTF plant watcher
Wants=network-online.target
After=network-online.target

[Service]
Type=simple
ExecStart={WATCHER_SCRIPT_PATH}
Restart=always
RestartSec=5
StandardOutput=null
StandardError=null

[Install]
WantedBy=multi-user.target
"""

# Merged into startup-script on Linux servers with ip_aliases (nested hosts), before the loader.
# It reinstalls at every boot, so it is idempotent: the script is replaced by rename (a running
# watcher keeps reading its old inode) and `enable --now` leaves a running service alone. Quoted
# heredoc delimiters keep both files literal. Without systemd or flock it installs nothing, and
# plants on that server fall back to a reset and the loader.
WATCHER_INSTALLER = f"""#!/bin/bash
# agoge-ctf watcher installer: run flag plants without a reset on this nested host.
(
  command -v systemctl >/dev/null 2>&1 || exit 0
  command -v flock >/dev/null 2>&1 || exit 0
  umask 022
  mkdir -p "$(dirname {WATCHER_SCRIPT_PATH})" "$(dirname {WATCHER_UNIT_PATH})" || exit 0
  cat > {WATCHER_SCRIPT_PATH}.new <<'AGOGE_CTF_WATCHER_SCRIPT' || exit 0
{WATCHER_SCRIPT}AGOGE_CTF_WATCHER_SCRIPT
  chmod 0700 {WATCHER_SCRIPT_PATH}.new && mv -f {WATCHER_SCRIPT_PATH}.new {WATCHER_SCRIPT_PATH} || exit 0
  cat > {WATCHER_UNIT_PATH} <<'AGOGE_CTF_WATCHER_UNIT' || exit 0
{WATCHER_UNIT}AGOGE_CTF_WATCHER_UNIT
  chmod 0644 {WATCHER_UNIT_PATH}
  systemctl daemon-reload
  systemctl enable --now {WATCHER_UNIT_NAME}
) >/dev/null 2>&1
"""

# Concatenated with other windows-startup-script-ps1 content, so it is scoped in a script block
# and only returns from that block. The file sits in a directory whose ACL grants SYSTEM (the
# boot account, by SID so it is locale-independent) and nobody else.
WINDOWS_LOADER = f"""# agoge-ctf loader: run a pending flag plant, if any. Never prints the payload.
& {{
  $ErrorActionPreference = 'SilentlyContinue'
  try {{
    $agogeCtfClient = New-Object System.Net.WebClient
    $agogeCtfClient.Headers.Add('Metadata-Flavor', 'Google')
    $agogeCtfClient.Encoding = [System.Text.Encoding]::UTF8
    $agogeCtfPayload = $agogeCtfClient.DownloadString('{_METADATA_URL}')
  }} catch {{
    return
  }}
  if (-not $agogeCtfPayload) {{ return }}
  $agogeCtfDir = Join-Path $env:ProgramData 'agoge-ctf'
  New-Item -ItemType Directory -Force -Path $agogeCtfDir | Out-Null
  icacls.exe $agogeCtfDir /inheritance:r /grant:r '*S-1-5-18:(OI)(CI)F' | Out-Null
  $agogeCtfFile = Join-Path $agogeCtfDir ('plant-' + [guid]::NewGuid().ToString() + '.ps1')
  try {{
    Set-Content -Path $agogeCtfFile -Value $agogeCtfPayload -Encoding UTF8
    & powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $agogeCtfFile *> $null
  }} finally {{
    Remove-Item -Force -Path $agogeCtfFile -ErrorAction SilentlyContinue
  }}
}} *> $null
"""


def guest_result_key(guest: str) -> str:
    """The per-guest result key under GUEST_ATTRIBUTE_NAMESPACE, e.g. plant-result-win-dc."""
    # The name ends up in shell and in a guest attribute path, so only a valid guest slug passes.
    if not isinstance(guest, str) or not re.fullmatch(NESTED_GUEST_NAME_PATTERN, guest):
        raise ValueError(f"Invalid nested guest name: {guest!r}")
    return f"{GUEST_ATTRIBUTE_GUEST_RESULT_PREFIX}{guest}"


def guest_result_path(guest: str) -> str:
    """The full guest attribute path FlagPlanter reads for one guest's flags."""
    return f"{GUEST_ATTRIBUTE_NAMESPACE}{guest_result_key(guest)}"


def parse_plant_result(value: Optional[str], nonce: str) -> Optional[tuple[str, Optional[str]]]:
    """
    Reads the plant-result guest attribute. Returns (RESULT_OK, None) or (RESULT_ERROR, message)
    when it carries this nonce, and None when it is absent, malformed, or from an earlier plant.
    """
    if not value or not nonce:
        return None
    if value == f"{RESULT_OK}:{nonce}":
        return RESULT_OK, None
    error_prefix = f"{RESULT_ERROR}:{nonce}:"
    if value.startswith(error_prefix):
        return RESULT_ERROR, value[len(error_prefix):][:MAX_RESULT_MESSAGE_LENGTH]
    return None
