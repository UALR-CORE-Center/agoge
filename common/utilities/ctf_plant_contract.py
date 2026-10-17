"""
Every name both sides of the CTF flag-delivery channel depend on.

The Cloud Function (FlagPlanter) writes a payload to PLANT_METADATA_KEY and resets the VM.
At boot, the loader stub (added to every lab server at build by LabServerManager) fetches that
key from the metadata server, runs it, and deletes it. The payload reports back through the
guest attribute at GUEST_ATTRIBUTE_PATH. Neither side hardcodes these strings elsewhere.
"""
import re
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
    bash "$agoge_ctf_plant_file" >/dev/null 2>&1
  fi
  rm -f "$agoge_ctf_plant_file"
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
