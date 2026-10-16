import re
import shlex
from typing import List, Union

from common.exceptions import BadRequest
from common.models.agoge import CtfBoardModel, CtfEventModel, CtfFlagSpecModel
from common.models.model_validators.model_validator import ModelValidator
from common.utilities.ctf_flags import derive_flag_value
from common.utilities.ctf_plant_contract import (
    GUEST_ATTRIBUTE_PATH, LOCATION_PATH_PATTERNS, MAX_RESULT_MESSAGE_LENGTH, RESULT_ERROR, RESULT_OK
)
from common.utilities.gcp.cloud_logger import Logger, LoggerNames

_GUEST_ATTRIBUTE_URL = f"http://metadata.google.internal/computeMetadata/v1/instance/guest-attributes/{GUEST_ATTRIBUTE_PATH}"
_METADATA_SERVER_IP = "169.254.169.254"
# Every string interpolated into a payload is checked against one of these first, so a script never
# receives anything that could break out of its quoting.
_VALUE_PATTERN = r'^[a-z0-9]+\{[a-z0-9-]+_[0-9a-f]{20}\}$'
_NONCE_PATTERN = r'^[A-Za-z0-9-]{1,64}$'
_FILE_MODE_PATTERN = r'^0[0-7]{3}$'
_FILE_OWNER_PATTERN = r'^[a-z_][a-z0-9_-]*:[a-z_][a-z0-9_-]*$'
_DEFAULT_LINUX_FILE_MODE = '0644'

# Module-level so tests can point the Linux env placement at a scratch file
LINUX_ENVIRONMENT_FILE = '/etc/environment'

# Shared bash prologue. All output is discarded before anything else runs (startup-script output reaches
# the serial console and Cloud Logging), and values are only ever passed to builtins (printf), so they
# never appear in a process argument list either.
_LINUX_PROLOGUE = """#!/bin/bash
# agoge-ctf plant payload. Never prints a flag value.
exec >/dev/null 2>&1
umask 022
agoge_ctf_nonce={nonce}
agoge_ctf_env_file={env_file}
agoge_ctf_errors=''
agoge_ctf_fail() {{
  agoge_ctf_errors="${{agoge_ctf_errors:+$agoge_ctf_errors; }}$1"
}}
# Best effort: keep non-root users off the metadata server until the plant key is removed.
if command -v iptables >/dev/null 2>&1; then
  iptables -C OUTPUT -d {metadata_ip} -m owner ! --uid-owner 0 -j REJECT \\
    || iptables -I OUTPUT -d {metadata_ip} -m owner ! --uid-owner 0 -j REJECT \\
    || true
fi
# path value mode owner flag_id
agoge_ctf_plant_file() {{
  mkdir -p "$(dirname "$1")" || {{ agoge_ctf_fail "$5: could not create directory"; return; }}
  ( umask 077; printf '%s' "$2" > "$1" ) || {{ agoge_ctf_fail "$5: could not write file"; return; }}
  chmod "$3" "$1" || agoge_ctf_fail "$5: could not set file mode"
  if [ -n "$4" ]; then
    chown "$4" "$1" || agoge_ctf_fail "$5: could not set file owner"
  fi
}}
# name value flag_id. Replaces the NAME= line (or appends it); cat > keeps the file's mode and owner.
agoge_ctf_plant_env() {{
  local agoge_ctf_tmp
  agoge_ctf_tmp="$(mktemp)" || {{ agoge_ctf_fail "$3: could not create temporary file"; return; }}
  {{ grep -v "^$1=" "$agoge_ctf_env_file"; printf '%s=%s\\n' "$1" "$2"; }} > "$agoge_ctf_tmp" \\
    && cat "$agoge_ctf_tmp" > "$agoge_ctf_env_file" \\
    || agoge_ctf_fail "$3: could not write $agoge_ctf_env_file"
  rm -f "$agoge_ctf_tmp"
}}
"""

_LINUX_EPILOGUE = """if [ -z "$agoge_ctf_errors" ]; then
  agoge_ctf_result="{ok}:$agoge_ctf_nonce"
else
  agoge_ctf_result="{error}:$agoge_ctf_nonce:${{agoge_ctf_errors:0:{max_message}}}"
fi
curl -s -X PUT -H "Metadata-Flavor: Google" --data "$agoge_ctf_result" {url}
"""

# Runs as SYSTEM under -File from the Windows loader. Every cmdlet that returns an object is piped to
# Out-Null, and error messages are built from flag ids only, never from an exception that could quote a value.
_WINDOWS_PROLOGUE = """# agoge-ctf plant payload. Never prints a flag value.
$ErrorActionPreference = 'Stop'
$agogeCtfNonce = {nonce}
$agogeCtfErrors = New-Object System.Collections.Generic.List[string]
function Set-AgogeCtfFile([string]$Path, [string]$Value, [string]$FlagId) {{
  try {{
    $parent = Split-Path -Parent $Path
    if (-not (Test-Path -LiteralPath $parent)) {{ New-Item -ItemType Directory -Force -Path $parent | Out-Null }}
    [System.IO.File]::WriteAllText($Path, $Value)
  }} catch {{ $agogeCtfErrors.Add("${{FlagId}}: could not write file") }}
}}
function Set-AgogeCtfRegistry([string]$Key, [string]$Name, [string]$Value, [string]$FlagId) {{
  try {{
    # New-Item -Force on an existing key would wipe its values, so only create a missing key
    if (-not (Test-Path -LiteralPath $Key)) {{ New-Item -Path $Key -Force | Out-Null }}
    New-ItemProperty -LiteralPath $Key -Name $Name -Value $Value -PropertyType String -Force | Out-Null
  }} catch {{ $agogeCtfErrors.Add("${{FlagId}}: could not write registry value") }}
}}
function Set-AgogeCtfEnv([string]$Name, [string]$Value, [string]$FlagId) {{
  try {{
    [System.Environment]::SetEnvironmentVariable($Name, $Value, [System.EnvironmentVariableTarget]::Machine)
  }} catch {{ $agogeCtfErrors.Add("${{FlagId}}: could not set environment variable") }}
}}
function Set-AgogeCtfStream([string]$Path, [string]$Stream, [string]$Value, [string]$FlagId) {{
  try {{
    # New-Item -Force on an existing file would truncate it, so only create a missing host file
    if (-not (Test-Path -LiteralPath $Path)) {{ New-Item -ItemType File -Force -Path $Path | Out-Null }}
    Set-Content -LiteralPath $Path -Stream $Stream -Value $Value -NoNewline
  }} catch {{ $agogeCtfErrors.Add("${{FlagId}}: could not write alternate data stream") }}
}}
"""

_WINDOWS_EPILOGUE = """if ($agogeCtfErrors.Count -eq 0) {{
  $agogeCtfResult = "{ok}:$agogeCtfNonce"
}} else {{
  $agogeCtfMessage = $agogeCtfErrors -join '; '
  if ($agogeCtfMessage.Length -gt {max_message}) {{ $agogeCtfMessage = $agogeCtfMessage.Substring(0, {max_message}) }}
  $agogeCtfResult = "{error}:${{agogeCtfNonce}}:$agogeCtfMessage"
}}
try {{
  Invoke-RestMethod -Method Put -Uri {url} -Headers @{{'Metadata-Flavor' = 'Google'}} -Body $agogeCtfResult | Out-Null
}} catch {{ }}
"""


class FlagPlanter:
    """
    Plants one CTF event's flags on a board's servers through the agoge-ctf-plant metadata key
    (see common/utilities/ctf_plant_contract.py). Flag values are derived here, written only into the
    payload, and never logged or persisted.
    """
    def __init__(
        self,
        event: Union[CtfEventModel, dict],
        env_dict: dict = None
    ) -> None:
        self.class_name = self.__class__.__name__
        self.logger = Logger(LoggerNames.CLOUD_FN, class_name=self.class_name)
        self.env_dict = env_dict
        if not isinstance(event, CtfEventModel):
            event = ModelValidator(model=CtfEventModel, log_location=LoggerNames.CLOUD_FN).load(data=event)
        self.event = event

    def build_payload(
        self,
        board: Union[CtfBoardModel, dict],
        server: str,
        nonce: str,
        seed: str
    ) -> str:
        """
        Returns the bash (Linux) or PowerShell (Windows) script that writes this board's flags for one
        server, idempotently, and reports ok:<nonce> or error:<nonce>:<message> to the guest attribute.
        Raises BadRequest if the server has no flags on the board or any interpolated string fails its
        Flag Location Formats pattern.
        """
        if not isinstance(board, CtfBoardModel):
            board = ModelValidator(model=CtfBoardModel, log_location=LoggerNames.CLOUD_FN).load(data=board)
        if not seed:
            raise ValueError(f"{self.class_name}:{self.event.id} - CTF flag seed is not configured")
        if not re.fullmatch(_NONCE_PATTERN, str(nonce)):
            raise BadRequest(f"{self.class_name}:{self.event.id} - Invalid plant nonce")

        flags = self._server_flags(board, server)
        operating_systems = {flag.operating_system for flag in flags}
        if len(operating_systems) != 1:
            raise BadRequest(
                f"{self.class_name}:{self.event.id} - Flags on server '{server}' mix operating systems"
            )
        prefix = self.event.spec.scoring.flag_prefix
        planted = []
        for flag in flags:
            self._check_path(flag)
            value = derive_flag_value(seed, board.workout_id, flag.id, self.event.seed_version, prefix)
            if not re.fullmatch(_VALUE_PATTERN, value):
                raise BadRequest(f"{self.class_name}:{self.event.id} - Flag {flag.id} derived an unsafe value")
            planted.append((flag, value))

        if operating_systems == {'windows'}:
            return self._windows_payload(planted, nonce)
        return self._linux_payload(planted, nonce)

    def _server_flags(self, board: CtfBoardModel, server: str) -> List[CtfFlagSpecModel]:
        board_flag_ids = {flag.flag_id for flag in board.flags}
        flags = [flag for flag in self.event.spec.flags if flag.server == server and flag.id in board_flag_ids]
        if not flags:
            raise BadRequest(
                f"{self.class_name}:{self.event.id} - Board {board.id} has no flags on server '{server}'"
            )
        return flags

    def _check_path(self, flag: CtfFlagSpecModel) -> None:
        pattern = LOCATION_PATH_PATTERNS.get((flag.location_type, flag.operating_system))
        if pattern is None or not re.fullmatch(pattern, flag.path):
            raise BadRequest(
                f"{self.class_name}:{self.event.id} - Flag {flag.id} path does not match the "
                f"{flag.location_type} format for {flag.operating_system}"
            )
        if flag.location_type == 'file' and flag.operating_system == 'linux':
            if flag.file_mode is not None and not re.fullmatch(_FILE_MODE_PATTERN, flag.file_mode):
                raise BadRequest(f"{self.class_name}:{self.event.id} - Flag {flag.id} has an invalid file_mode")
            if flag.file_owner is not None and not re.fullmatch(_FILE_OWNER_PATTERN, flag.file_owner):
                raise BadRequest(f"{self.class_name}:{self.event.id} - Flag {flag.id} has an invalid file_owner")

    @staticmethod
    def _linux_payload(planted: list, nonce: str) -> str:
        q = shlex.quote
        lines = [_LINUX_PROLOGUE.format(
            nonce=q(nonce), env_file=q(LINUX_ENVIRONMENT_FILE), metadata_ip=_METADATA_SERVER_IP
        )]
        for flag, value in planted:
            if flag.location_type == 'file':
                # file_mode/file_owner apply to Linux file placements only
                mode = flag.file_mode or _DEFAULT_LINUX_FILE_MODE
                lines.append(
                    f"agoge_ctf_plant_file {q(flag.path)} {q(value)} {q(mode)} {q(flag.file_owner or '')} {q(flag.id)}"
                )
            else:
                lines.append(f"agoge_ctf_plant_env {q(flag.path)} {q(value)} {q(flag.id)}")
        lines.append(_LINUX_EPILOGUE.format(
            ok=RESULT_OK, error=RESULT_ERROR, max_message=MAX_RESULT_MESSAGE_LENGTH, url=q(_GUEST_ATTRIBUTE_URL)
        ))
        return "\n".join(lines)

    @staticmethod
    def _windows_payload(planted: list, nonce: str) -> str:
        q = FlagPlanter._ps_quote
        lines = [_WINDOWS_PROLOGUE.format(nonce=q(nonce))]
        for flag, value in planted:
            if flag.location_type == 'file':
                lines.append(f"Set-AgogeCtfFile {q(flag.path)} {q(value)} {q(flag.id)}")
            elif flag.location_type == 'registry':
                # HKLM\<key>:<value name> -> the HKLM: PowerShell drive
                key, name = flag.path.rsplit(':', 1)
                registry_key = 'HKLM:' + key[len('HKLM'):]
                lines.append(f"Set-AgogeCtfRegistry {q(registry_key)} {q(name)} {q(value)} {q(flag.id)}")
            elif flag.location_type == 'env':
                lines.append(f"Set-AgogeCtfEnv {q(flag.path)} {q(value)} {q(flag.id)}")
            else:
                # <drive>:\<file>:<stream>; the last colon separates the stream, the first is the drive
                path, stream = flag.path.rsplit(':', 1)
                lines.append(f"Set-AgogeCtfStream {q(path)} {q(stream)} {q(value)} {q(flag.id)}")
        lines.append(_WINDOWS_EPILOGUE.format(
            ok=RESULT_OK, error=RESULT_ERROR, max_message=MAX_RESULT_MESSAGE_LENGTH, url=q(_GUEST_ATTRIBUTE_URL)
        ))
        return "\n".join(lines)

    @staticmethod
    def _ps_quote(value: str) -> str:
        # PowerShell single-quoted literal: no expansion; a quote is escaped by doubling it
        return "'" + value.replace("'", "''") + "'"
