"""
Every name both sides of the CTF flag-delivery channel depend on.

The Cloud Function (FlagPlanter) writes a payload to PLANT_METADATA_KEY and resets the VM.
At boot, the loader stub (added to every lab server at build by LabServerManager) fetches that
key from the metadata server, runs it, and deletes it. The payload reports back through the
guest attribute at GUEST_ATTRIBUTE_PATH. Neither side hardcodes these strings elsewhere.
"""
from typing import Optional

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

LINUX_LOADER_METADATA_KEY = "startup-script"
WINDOWS_LOADER_METADATA_KEY = "windows-startup-script-ps1"

_METADATA_URL = f"http://metadata.google.internal/computeMetadata/v1/instance/attributes/{PLANT_METADATA_KEY}"

# Appended to whatever startup-script already holds, so it runs in a subshell, never calls a
# top-level `exit`, and silences everything: startup-script output reaches the serial console
# and Cloud Logging. curl -f turns the metadata server's 404 (no plant pending) into a no-op.
LINUX_LOADER = f"""#!/bin/bash
# agoge-ctf loader: run a pending flag plant, if any. Never prints the payload.
(
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
