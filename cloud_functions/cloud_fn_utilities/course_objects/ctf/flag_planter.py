import base64
import json
import re
import shlex
import time
from typing import Callable, Dict, List, Optional, Union

from common.constants.database import DATABASE_NAME, DatabaseTypes, DbCollections
from common.exceptions import BadRequest, NotFound
from common.models.agoge import CtfBoardModel, CtfEventModel, CtfFlagSpecModel, CtfNestedGuestSpecModel
from common.models.model_validators.model_validator import ModelValidator
from common.utilities.ctf_flags import derive_flag_value
from common.utilities.ctf_plant_contract import (
    GUEST_ATTRIBUTE_ACK_KEY, GUEST_ATTRIBUTE_ACK_PATH, GUEST_ATTRIBUTE_NAMESPACE, GUEST_ATTRIBUTE_PATH,
    GUEST_ATTRIBUTE_RESULT_KEY, GUEST_ATTRIBUTES_ENABLE_KEY, GUEST_ATTRIBUTES_ENABLE_VALUE, LOCATION_PATH_PATTERNS,
    MAX_RESULT_MESSAGE_LENGTH, NESTED_CONFIRM_TIMEOUT_SECONDS, PLANT_METADATA_KEY, PLANT_PAYLOAD_MAX_BYTES,
    PRISTINE_SNAPSHOT_NAME, RELAY_BUDGET_SECONDS, RESULT_ERROR, RESULT_OK, WATCHER_ACK_SECONDS, guest_result_key,
    guest_result_path, parse_plant_result
)
from common.utilities.gcp.cloud_logger import Logger, LoggerNames
from common.utilities.id_generator import IdGenerator

_GUEST_ATTRIBUTES_URL = "http://metadata.google.internal/computeMetadata/v1/instance/guest-attributes/"
_GUEST_ATTRIBUTE_URL = f"{_GUEST_ATTRIBUTES_URL}{GUEST_ATTRIBUTE_PATH}"
_METADATA_SERVER_IP = "169.254.169.254"
# Every string interpolated into a payload is checked against one of these first, so a script never
# receives anything that could break out of its quoting.
_VALUE_PATTERN = r'^[a-z0-9]+\{[a-z0-9-]+_[0-9a-f]{20}\}$'
_NONCE_PATTERN = r'^[A-Za-z0-9-]{1,64}$'
_FILE_MODE_PATTERN = r'^0[0-7]{3}$'
_FILE_OWNER_PATTERN = r'^[a-z_][a-z0-9_-]*:[a-z_][a-z0-9_-]*$'
_DEFAULT_LINUX_FILE_MODE = '0644'
_WINDOWS_USER_PATTERN = r'^[A-Za-z0-9][A-Za-z0-9._-]{0,19}$'
_WINDOWS_ACCESS_LEVELS = ('administrators', 'user', 'everyone')

# Module-level so tests can point the Linux env placement at a scratch file
LINUX_ENVIRONMENT_FILE = '/etc/environment'

# Shared bash prologue. All output is discarded before anything else runs (startup-script output reaches
# the serial console and Cloud Logging), and values are only ever passed to builtins (printf), so they
# never appear in a process argument list either. {save_stdout} is empty for a server payload; a guest
# payload keeps the relay's stdout on fd 3 for its one result line (_LINUX_GUEST_SAVE_STDOUT). {ack} is
# empty except on a nested host, whose payload writes plant-ack as its first action (_LINUX_ACK).
_LINUX_PROLOGUE = """#!/bin/bash
# agoge-ctf plant payload. Never prints a flag value.
{save_stdout}exec >/dev/null 2>&1
{ack}umask 022
agoge_ctf_nonce={nonce}
agoge_ctf_env_file={env_file}
agoge_ctf_errors=''
agoge_ctf_fail() {{
  agoge_ctf_errors="${{agoge_ctf_errors:+$agoge_ctf_errors; }}$1"
}}
# Best effort: keep non-root users off the metadata server until the plant key is removed, and keep
# nested guests NAT'd through this host off it entirely (their traffic is FORWARDed, not OUTPUT).
if command -v iptables >/dev/null 2>&1; then
  iptables -C OUTPUT -d {metadata_ip} -m owner ! --uid-owner 0 -j REJECT \\
    || iptables -I OUTPUT -d {metadata_ip} -m owner ! --uid-owner 0 -j REJECT \\
    || true
  iptables -C FORWARD -d {metadata_ip} -j REJECT \\
    || iptables -I FORWARD -d {metadata_ip} -j REJECT \\
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

_LINUX_RESULT = """if [ -z "$agoge_ctf_errors" ]; then
  agoge_ctf_result="{ok}:$agoge_ctf_nonce"
else
  agoge_ctf_result="{error}:$agoge_ctf_nonce:${{agoge_ctf_errors:0:{max_message}}}"
fi
"""

_LINUX_EPILOGUE = _LINUX_RESULT + """curl -s -X PUT -H "Metadata-Flavor: Google" --data "$agoge_ctf_result" {url}
"""

# Guest payload (Nested Guest Contract): no guest attributes exist inside a nested guest, so the result line
# goes to the stdout saved on fd 3, which the parent's relay reads back as guest-exec out-data.
_LINUX_GUEST_SAVE_STDOUT = "exec 3>&1\n"
_LINUX_GUEST_EPILOGUE = _LINUX_RESULT + """printf '%s\\n' "$agoge_ctf_result" >&3
"""

# Runs as SYSTEM under -File from the Windows loader. Every cmdlet that returns an object is piped to
# Out-Null, and error messages are built from flag ids only, never from an exception that could quote a value.
_WINDOWS_PROLOGUE = """# agoge-ctf plant payload. Never prints a flag value.
{save_stdout}$ErrorActionPreference = 'Stop'
$agogeCtfNonce = {nonce}
$agogeCtfErrors = New-Object System.Collections.Generic.List[string]
function Clear-AgogeCtfAttributes([string]$Path) {{
  # WriteAllText and Set-Content refuse a Hidden or ReadOnly file, which an earlier plant may have hidden
  if (Test-Path -LiteralPath $Path) {{
    $item = Get-Item -LiteralPath $Path -Force
    $cleared = $item.Attributes -band -bnot ([System.IO.FileAttributes]::Hidden -bor [System.IO.FileAttributes]::ReadOnly)
    if ($cleared -eq 0) {{ $cleared = [System.IO.FileAttributes]::Normal }}
    $item.Attributes = $cleared
  }}
}}
function Set-AgogeCtfFile([string]$Path, [string]$Value, [string]$FlagId) {{
  try {{
    $parent = Split-Path -Parent $Path
    if (-not (Test-Path -LiteralPath $parent)) {{ New-Item -ItemType Directory -Force -Path $parent | Out-Null }}
    Clear-AgogeCtfAttributes $Path
    [System.IO.File]::WriteAllText($Path, $Value)
  }} catch {{ $agogeCtfErrors.Add("${{FlagId}}: could not write file") }}
}}
function Set-AgogeCtfAccess([string]$Path, [string]$Access, [string]$User, [string]$FlagId) {{
  try {{
    # Well-known SIDs, so localized group names do not matter: SYSTEM, Administrators, Everyone
    $grants = @('*S-1-5-18:(F)', '*S-1-5-32-544:(F)')
    if ($Access -eq 'everyone') {{ $grants += '*S-1-1-0:(R)' }}
    if ($Access -eq 'user') {{ $grants += ($User + ':(R)') }}
    & icacls.exe $Path /reset | Out-Null
    if ($LASTEXITCODE -ne 0) {{ throw 'reset' }}
    & icacls.exe $Path /inheritance:r /grant:r @grants | Out-Null
    if ($LASTEXITCODE -ne 0) {{ throw 'grant' }}
  }} catch {{ $agogeCtfErrors.Add("${{FlagId}}: could not set file access (does the user exist?)") }}
}}
function Set-AgogeCtfHidden([string]$Path, [string]$FlagId) {{
  try {{
    $item = Get-Item -LiteralPath $Path -Force
    $item.Attributes = $item.Attributes -bor [System.IO.FileAttributes]::Hidden
  }} catch {{ $agogeCtfErrors.Add("${{FlagId}}: could not hide file") }}
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
    Clear-AgogeCtfAttributes $Path
    Set-Content -LiteralPath $Path -Stream $Stream -Value $Value -NoNewline
  }} catch {{ $agogeCtfErrors.Add("${{FlagId}}: could not write alternate data stream") }}
}}
"""

_WINDOWS_RESULT = """if ($agogeCtfErrors.Count -eq 0) {{
  $agogeCtfResult = "{ok}:$agogeCtfNonce"
}} else {{
  $agogeCtfMessage = $agogeCtfErrors -join '; '
  if ($agogeCtfMessage.Length -gt {max_message}) {{ $agogeCtfMessage = $agogeCtfMessage.Substring(0, {max_message}) }}
  $agogeCtfResult = "{error}:${{agogeCtfNonce}}:$agogeCtfMessage"
}}
"""

_WINDOWS_EPILOGUE = _WINDOWS_RESULT + """try {{
  Invoke-RestMethod -Method Put -Uri {url} -Headers @{{'Metadata-Flavor' = 'Google'}} -Body $agogeCtfResult | Out-Null
}} catch {{ }}
"""

# Guest payload: keep the real stdout writer, then point the console and every chatty stream at nothing,
# so the result line written to the saved writer is the only thing the relay reads back.
_WINDOWS_GUEST_SAVE_STDOUT = """$agogeCtfStdout = [Console]::Out
[Console]::SetOut([System.IO.TextWriter]::Null)
[Console]::SetError([System.IO.TextWriter]::Null)
$ProgressPreference = 'SilentlyContinue'
$WarningPreference = 'SilentlyContinue'
$InformationPreference = 'SilentlyContinue'
$VerbosePreference = 'SilentlyContinue'
$DebugPreference = 'SilentlyContinue'
"""
_WINDOWS_GUEST_EPILOGUE = _WINDOWS_RESULT + """$agogeCtfStdout.WriteLine($agogeCtfResult)
$agogeCtfStdout.Flush()
"""

# Nested host (Nested Guest Contract): the ack tells FlagPlanter the watcher picked the payload up.
_LINUX_ACK = """curl -s -X PUT -H "Metadata-Flavor: Google" --data {nonce} {url}
"""

# qemu-agent relay, defined after the parent's own placements. virsh runs in shell mode with its commands
# on stdin, so no agent JSON (and so no guest payload, which travels as guest-exec input-data) is ever in a
# process argument list; printf is a builtin. Replies are matched with patterns that never occur in the
# request, because virsh may echo each command line after its prompt. Every agent JSON is single-quoted on the
# virsh line: unquoted, virsh's own tokenizer would strip its double quotes. Each section has its own deadline;
# a virsh call started just before it may overrun by at most {virsh_timeout} s, still inside the
# confirmation window. A section never starts a guest.
_LINUX_RELAY = """agoge_ctf_ping={ping}
agoge_ctf_status_open={status_open}
agoge_ctf_status_close={status_close}
agoge_ctf_virsh() {{
  timeout {virsh_timeout} virsh -q
}}
# guest result_url result
agoge_ctf_guest_result() {{
  curl -s -X PUT -H "Metadata-Flavor: Google" --data "$3" "$2"
}}
# guest domain result_url exec_command [deadline]
agoge_ctf_relay_qemu() {{
  local guest="$1" domain="$2" url="$3" exec_command="$4"
  local deadline="${{5:-$((SECONDS + {budget}))}}"
  local reply pid out line
  if ! command -v virsh >/dev/null 2>&1; then
    agoge_ctf_guest_result "$guest" "$url" "{error}:$agoge_ctf_nonce:$guest: virsh is not available"
    return
  fi
  if [ "$(timeout {virsh_timeout} virsh -q domstate "$domain" | head -n 1)" != running ]; then
    agoge_ctf_guest_result "$guest" "$url" "{error}:$agoge_ctf_nonce:$guest: guest is not running"
    return
  fi
  until printf '%s\\n' "qemu-agent-command $domain '$agoge_ctf_ping' --timeout {agent_timeout}" \\
      | agoge_ctf_virsh | grep -q '"return"'; do
    if [ "$SECONDS" -ge "$deadline" ]; then
      agoge_ctf_guest_result "$guest" "$url" "{error}:$agoge_ctf_nonce:$guest: guest agent did not respond"
      return
    fi
    sleep {ping_interval}
  done
  reply="$(printf '%s\\n' "$exec_command" | agoge_ctf_virsh)"
  pid="$(printf '%s\\n' "$reply" | grep -o '"pid": *[0-9][0-9]*' | head -n 1 | tr -dc '0-9')"
  if [ -z "$pid" ]; then
    agoge_ctf_guest_result "$guest" "$url" "{error}:$agoge_ctf_nonce:$guest: guest-exec failed"
    return
  fi
  while :; do
    reply="$(printf '%s\\n' "qemu-agent-command $domain '$agoge_ctf_status_open$pid$agoge_ctf_status_close' --timeout {agent_timeout}" \\
      | agoge_ctf_virsh)"
    if printf '%s\\n' "$reply" | grep -q '"exited": *true'; then
      break
    fi
    if [ "$SECONDS" -ge "$deadline" ]; then
      agoge_ctf_guest_result "$guest" "$url" "{error}:$agoge_ctf_nonce:$guest: guest payload did not finish"
      return
    fi
    sleep {status_interval}
  done
  out="$(printf '%s\\n' "$reply" | grep -o '"out-data": *"[A-Za-z0-9+/=]*' | head -n 1 | sed 's/^.*"//')"
  line="$(printf '%s' "$out" | base64 -d 2>/dev/null | head -n 1 | tr -d '\\r')"
  # Only a line in the result grammar for this nonce is passed on, capped at the longest valid one
  case "$line" in
    "{ok}:$agoge_ctf_nonce"|"{error}:$agoge_ctf_nonce:"*) ;;
    *) line="{error}:$agoge_ctf_nonce:$guest: guest payload returned no result" ;;
  esac
  agoge_ctf_guest_result "$guest" "$url" "${{line:0:{max_line}}}"
}}
# Guest host rebuild: revert to the pristine snapshot, then relay as above inside the same budget. Domain and
# snapshot names are the only virsh arguments; neither is secret.
# guest domain result_url exec_command
agoge_ctf_rebuild_qemu() {{
  local guest="$1" domain="$2" url="$3" exec_command="$4"
  local deadline=$((SECONDS + {budget}))
  if ! command -v virsh >/dev/null 2>&1; then
    agoge_ctf_guest_result "$guest" "$url" "{error}:$agoge_ctf_nonce:$guest: virsh is not available"
    return
  fi
  if ! timeout {virsh_timeout} virsh -q snapshot-info "$domain" {snapshot}; then
    agoge_ctf_guest_result "$guest" "$url" "{error}:$agoge_ctf_nonce:$guest: no {snapshot} snapshot"
    return
  fi
  if ! timeout {revert_timeout} virsh -q snapshot-revert "$domain" {snapshot} --running; then
    agoge_ctf_guest_result "$guest" "$url" "{error}:$agoge_ctf_nonce:$guest: snapshot revert failed"
    return
  fi
  agoge_ctf_relay_qemu "$guest" "$domain" "$url" "$exec_command" "$deadline"
}}
"""

# Guest host restart and flagless rebuild (Host reset modes on a guest): one virsh action on the parent, whose
# outcome is reported through the parent's own plant-result. {checks} is one `elif ! <virsh call>` per step.
_LINUX_GUEST_ACTION = """if ! command -v virsh >/dev/null 2>&1; then
  agoge_ctf_fail {not_available}
{checks}fi
"""

# Fixed bootstrap the relay starts in a Windows guest with -EncodedCommand: reads the guest payload from
# stdin, writes it under the same SYSTEM-only directory ACL as WINDOWS_LOADER, runs it with -File (whose
# one result line is the only output), and deletes it.
_WINDOWS_GUEST_BOOTSTRAP = """$ErrorActionPreference = 'SilentlyContinue'
$agogeCtfReader = New-Object System.IO.StreamReader([Console]::OpenStandardInput(), (New-Object System.Text.UTF8Encoding $false))
$agogeCtfPayload = $agogeCtfReader.ReadToEnd()
if (-not $agogeCtfPayload) { exit 1 }
$agogeCtfDir = Join-Path $env:ProgramData 'agoge-ctf'
New-Item -ItemType Directory -Force -Path $agogeCtfDir | Out-Null
icacls.exe $agogeCtfDir /inheritance:r /grant:r '*S-1-5-18:(OI)(CI)F' | Out-Null
$agogeCtfFile = Join-Path $agogeCtfDir ('plant-' + [guid]::NewGuid().ToString() + '.ps1')
try {
  [System.IO.File]::WriteAllText($agogeCtfFile, $agogeCtfPayload, (New-Object System.Text.UTF8Encoding $true))
  & powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $agogeCtfFile
} finally {
  Remove-Item -Force -LiteralPath $agogeCtfFile -ErrorAction SilentlyContinue
}
"""
_RELAY_VIRSH_TIMEOUT_SECONDS = 30
_RELAY_AGENT_TIMEOUT_SECONDS = 10
_RELAY_PING_INTERVAL_SECONDS = 5
_RELAY_STATUS_INTERVAL_SECONDS = 2
# An internal snapshot revert restores the guest's memory, which can take minutes for a large Windows guest
_RELAY_REVERT_TIMEOUT_SECONDS = 180
GUEST_ACTIONS = ('restart', 'revert')


def board_servers(event: CtfEventModel, board: CtfBoardModel) -> List[str]:
    """Spec servers carrying at least one of the board's flags, in spec flag order."""
    board_flag_ids = {flag.flag_id for flag in board.flags}
    return list(dict.fromkeys(f.server for f in event.spec.flags if f.id in board_flag_ids))


class FlagPlanter:
    """
    Plants one CTF event's flags on a board's servers through the agoge-ctf-plant metadata key
    (see common/utilities/ctf_plant_contract.py). Flag values are derived here, written only into the
    payload, and never logged or persisted.
    """
    POLL_INTERVAL_SECONDS = 10
    ACK_POLL_INTERVAL_SECONDS = 5
    CONFIRM_TIMEOUT_SECONDS = 240
    MSG_NOT_RUNNING = "Server is not running"
    MSG_NOT_FOUND = "Server instance not found"
    MSG_TIMEOUT = f"No plant confirmation within {CONFIRM_TIMEOUT_SECONDS} s"
    MSG_NESTED_TIMEOUT = f"No plant confirmation within {NESTED_CONFIRM_TIMEOUT_SECONDS} s"
    MSG_NO_WATCHER = "Plant watcher did not respond"
    MSG_NO_GUEST_RESULT = "Guest relay reported no result"
    MSG_NO_SEED = "CTF flag seed is not configured"
    MSG_BAD_PAYLOAD = "Could not build the plant payload"
    MSG_DELIVERY = "Could not deliver the plant payload"
    MSG_ABORTED = "Plant aborted by an internal error"
    MSG_ACTION_ERROR = "Guest action reported an error"

    def __init__(
        self,
        event: Union[CtfEventModel, dict],
        env_dict: dict = None,
        compute_api=None,
        db=None
    ) -> None:
        self.class_name = self.__class__.__name__
        self.logger = Logger(LoggerNames.CLOUD_FN, class_name=self.class_name)
        self.env_dict = env_dict
        if not isinstance(event, CtfEventModel):
            event = ModelValidator(model=CtfEventModel, log_location=LoggerNames.CLOUD_FN).load(data=event)
        self.event = event
        # Built lazily so build_payload needs no GCP clients
        self._env = None
        self._compute_api = compute_api
        self._db = db

    @property
    def env(self):
        if self._env is None:
            from common.utilities.gcp.cloud_env import CloudEnv
            self._env = CloudEnv(env_dict=self.env_dict) if self.env_dict else CloudEnv()
        return self._env

    @property
    def compute_api(self):
        if self._compute_api is None:
            from common.utilities.gcp.compute.compute_instance import ComputeInstanceAPI
            self._compute_api = ComputeInstanceAPI(
                project=self.env.project, region=self.env.region, zone=self.env.zone, log_name=LoggerNames.CLOUD_FN
            )
        return self._compute_api

    @property
    def db(self):
        if self._db is None:
            from common.document_database.factory import DocumentDatabaseFactory
            self._db = DocumentDatabaseFactory.create_db_object(
                db_type=DatabaseTypes.firestore, database_name=DATABASE_NAME, log_name=LoggerNames.CLOUD_FN
            )
        return self._db

    def plant(
        self,
        board: Union[CtfBoardModel, dict],
        servers: List[str],
        guest: Optional[str] = None,
        revert: bool = False
    ) -> CtfBoardModel:
        """
        Plants the board's flags on each named spec server (Plant procedure, PRD): payload on every server
        first, then one shared poll for each server's nonce. Every targeted flag ends `planted` or `failed`;
        the result is written to the board document and returned. The plant key is removed in a `finally`
        from every server it was written to, whatever the outcome. Stopped servers are never started.

        A plain server is reset right after its payload is written. A nested host (one with nested_guests)
        is not: its plant watcher runs the payload, so its guests keep running (Nested plant procedure).
        With no plant-ack within WATCHER_ACK_SECONDS a whole-server plant falls back to a reset; a `guest`
        plant never resets and fails its flags instead. With `guest` set, only that guest's flags are
        targeted, and servers that do not declare it are skipped. Each flag takes its status from its own
        result key: plant-result-<guest> for a guest flag, plant-result for a parent or plain-server flag.
        `revert` (guest host rebuild) reverts that guest to its pristine snapshot before relaying its flags.
        """
        if revert and guest is None:
            raise ValueError("A snapshot revert needs a guest.")
        if not isinstance(board, CtfBoardModel):
            board = ModelValidator(model=CtfBoardModel, log_location=LoggerNames.CLOUD_FN).load(data=board)
        # server -> {result key: board flag ids reported by that key}; servers with none are skipped
        targets: Dict[str, Dict[str, List[str]]] = {}
        for server in dict.fromkeys(servers):
            groups = self._result_groups(board, server, guest)
            if groups:
                targets[server] = groups
            else:
                scope = f"guest '{guest}' of server '{server}'" if guest else f"server '{server}'"
                self.logger.warning(f"{self.class_name}:{board.id} - no board flags on {scope}; skipped")
        if not targets:
            return board

        seed = self.env.ctf_flag_seed
        if not seed:
            self.logger.error(f"{self.class_name}:{board.id} - {self.MSG_NO_SEED}")
            return self._record(board, {fid: self._failed(self.MSG_NO_SEED) for fid in self._target_ids(targets)})

        nonces = {}       # server -> nonce, for servers whose payload was (or may have been) written
        written = []      # instance names that may hold the plant key; cleaned in the finally
        try:
            for server, groups in targets.items():
                flag_ids = [fid for ids in groups.values() for fid in ids]
                nonce = IdGenerator.uuid()
                board = self._record(board, {fid: {'plant_status': 'planting'} for fid in flag_ids})
                instance_name = self._instance_name(board, server)
                failure = self._deliver(
                    board, server, instance_name, nonce, seed, written,
                    guest=guest, reset=not self._is_nested_host(server), revert=revert
                )
                if failure:
                    board = self._record(board, {fid: self._failed(failure) for fid in flag_ids})
                else:
                    nonces[server] = nonce
            board, nonces = self._await_acks(board, targets, nonces, guest)
            board = self._await_results(board, targets, nonces)
        except Exception:
            self._fail_unfinished(board, targets)
            raise
        finally:
            for instance_name in written:
                try:
                    self.compute_api.set_metadata(instance_name, remove=[PLANT_METADATA_KEY])
                except Exception as e:
                    # Logged, not raised: the plant outcome is already recorded. The key stays until a later attempt.
                    self.logger.error(
                        f"{self.class_name}:{board.id} - could not remove {PLANT_METADATA_KEY} from {instance_name}",
                        error=type(e).__name__
                    )
        return board

    def mark_stale(self, board: CtfBoardModel, server: str) -> CtfBoardModel:
        """
        Marks the board's flags on one server `stale` (host rebuild: the instance was recreated from its
        image, so the planted values are gone until a replant). Returns the board unchanged when it has none.
        """
        flag_ids = [f.id for f in self._board_flags_on(board, server)]
        if not flag_ids:
            return board
        stale = {'plant_status': 'stale', 'planted_at': None, 'plant_error': None}
        return self._record(board, {fid: dict(stale) for fid in flag_ids})

    def run_guest_action(self, board: Union[CtfBoardModel, dict], server: str, guest: str, action: str) -> Optional[str]:
        """
        Runs one GUEST_ACTIONS action on a declared guest of a nested host through its plant watcher (Host reset
        modes on a guest: `restart`, and `revert` for a rebuild of a guest the board has no flags on). The payload
        holds no flag value and no flag status changes. The instance is never reset, stopped or started, so an
        un-acked payload fails instead. Returns None once plant-result reports ok, otherwise the failure message.
        The plant key is removed in a `finally`. Raises BadRequest for an undeclared guest.
        """
        if not isinstance(board, CtfBoardModel):
            board = ModelValidator(model=CtfBoardModel, log_location=LoggerNames.CLOUD_FN).load(data=board)
        nonce = IdGenerator.uuid()
        payload = self.build_guest_action_payload(server, guest, action, nonce)
        instance_name = self._instance_name(board, server)
        try:
            instance = self.compute_api.get(instance_name)
        except NotFound:
            return self.MSG_NOT_FOUND
        if str(getattr(instance, 'status', '')).upper() != 'RUNNING':
            return self.MSG_NOT_RUNNING
        # The finally covers the write itself: a failed or timed-out write may still have landed
        try:
            try:
                self.compute_api.set_metadata(
                    instance_name,
                    items={PLANT_METADATA_KEY: payload, GUEST_ATTRIBUTES_ENABLE_KEY: GUEST_ATTRIBUTES_ENABLE_VALUE}
                )
            except Exception as e:
                self.logger.error(
                    f"{self.class_name}:{board.id} - {self.MSG_DELIVERY} to {instance_name}", error=type(e).__name__
                )
                return self.MSG_DELIVERY
            return self._await_action(board, instance_name, nonce)
        finally:
            try:
                self.compute_api.set_metadata(instance_name, remove=[PLANT_METADATA_KEY])
            except Exception as e:
                self.logger.error(
                    f"{self.class_name}:{board.id} - could not remove {PLANT_METADATA_KEY} from {instance_name}",
                    error=type(e).__name__
                )

    def _await_action(self, board: CtfBoardModel, instance_name: str, nonce: str) -> Optional[str]:
        """Polls for plant-ack within WATCHER_ACK_SECONDS, then for plant-result within the nested window."""
        ack_deadline = time.monotonic() + WATCHER_ACK_SECONDS
        deadline = ack_deadline + NESTED_CONFIRM_TIMEOUT_SECONDS
        acked = False
        while True:
            now = time.monotonic()
            if not acked and now >= ack_deadline:
                self.logger.warning(f"{self.class_name}:{board.id} - no plant ack from {instance_name}")
                return self.MSG_NO_WATCHER
            if now >= deadline:
                return self.MSG_NESTED_TIMEOUT
            time.sleep(self.ACK_POLL_INTERVAL_SECONDS)
            try:
                attributes = self.compute_api.get_guest_attributes(instance_name, query_path=GUEST_ATTRIBUTE_NAMESPACE)
            except NotFound:
                return self.MSG_NOT_FOUND
            except Exception as e:
                # Transient API errors keep polling until the deadline
                self.logger.warning(f"{self.class_name}:{board.id} - guest attribute poll failed", error=type(e).__name__)
                continue
            acked = acked or attributes.get(GUEST_ATTRIBUTE_ACK_KEY) == nonce
            result = parse_plant_result(attributes.get(GUEST_ATTRIBUTE_RESULT_KEY), nonce)
            if result is not None:
                status, message = result
                return None if status == RESULT_OK else (message or self.MSG_ACTION_ERROR)

    def build_guest_action_payload(self, server: str, guest: str, action: str, nonce: str) -> str:
        """
        The nested host payload for one guest action: ack first, the virsh action on the parent, then plant-result
        reporting its outcome. Raises ValueError for an unknown action and BadRequest for an undeclared guest.
        """
        if action not in GUEST_ACTIONS:
            raise ValueError(f"Unsupported guest action: {action}")
        if not re.fullmatch(_NONCE_PATTERN, str(nonce)):
            raise BadRequest(f"{self.class_name}:{self.event.id} - Invalid plant nonce")
        declared = next((g for g in self.event.spec.nested_guests if g.server == server and g.name == guest), None)
        if declared is None:
            raise BadRequest(
                f"{self.class_name}:{self.event.id} - Guest '{guest}' is not declared on server '{server}'"
            )
        payload = self._linux_payload([], nonce, actions=[self._linux_guest_action(declared, action)])
        self._check_size(payload)
        return payload

    def _board_flags_on(self, board: CtfBoardModel, server: str) -> List[CtfFlagSpecModel]:
        board_flag_ids = {flag.flag_id for flag in board.flags}
        return [flag for flag in self.event.spec.flags if flag.server == server and flag.id in board_flag_ids]

    def _is_nested_host(self, server: str) -> bool:
        return any(guest.server == server for guest in self.event.spec.nested_guests)

    def _result_groups(self, board: CtfBoardModel, server: str, guest: Optional[str]) -> Dict[str, List[str]]:
        """{result key: board flag ids} for one server, limited to one declared guest when `guest` is set."""
        flags = self._board_flags_on(board, server)
        if guest is not None:
            if not any(g.server == server and g.name == guest for g in self.event.spec.nested_guests):
                return {}
            flags = [flag for flag in flags if flag.guest == guest]
        groups: Dict[str, List[str]] = {}
        for flag in flags:
            key = GUEST_ATTRIBUTE_RESULT_KEY if flag.guest is None else guest_result_key(flag.guest)
            groups.setdefault(key, []).append(flag.id)
        return groups

    @staticmethod
    def _target_ids(targets: Dict[str, Dict[str, List[str]]]) -> List[str]:
        return [fid for groups in targets.values() for ids in groups.values() for fid in ids]

    def _fail_unfinished(self, board: CtfBoardModel, targets: Dict[str, Dict[str, List[str]]]) -> None:
        """
        Best effort on an unexpected error: no flag is left `planting` with nothing to finish it. Statuses are
        read from the stored board inside the transaction, not from `board`: the await helpers rebind their own
        board, so flags they already recorded planted/failed would still read `planting` here (BUG5).
        """
        target_ids = set(self._target_ids(targets))
        failed = self._failed(self.MSG_ABORTED)

        def apply(flags: list) -> list:
            for flag in flags:
                if flag.get('flag_id') in target_ids and flag.get('plant_status') == 'planting':
                    flag.update(failed)
            return flags

        try:
            self._write_flags(board, apply)
        except Exception as e:
            self.logger.error(f"{self.class_name}:{board.id} - could not mark aborted flags failed", error=type(e).__name__)

    def _deliver(
        self, board, server, instance_name, nonce, seed, written, guest=None, reset=True, revert=False
    ) -> Optional[str]:
        """
        Steps 3-4: payload into metadata, then reset unless `reset` is False (a nested host's watcher runs
        it instead). Returns a failure message, or None on success.
        """
        try:
            instance = self.compute_api.get(instance_name)
        except NotFound:
            return self.MSG_NOT_FOUND
        if str(getattr(instance, 'status', '')).upper() != 'RUNNING':
            return self.MSG_NOT_RUNNING
        try:
            payload = self.build_payload(board, server, nonce, seed, guest=guest, revert=revert)
        except (BadRequest, ValueError) as e:
            # BadRequest messages carry flag ids only, never a value
            self.logger.error(f"{self.class_name}:{board.id} - {self.MSG_BAD_PAYLOAD} for '{server}'", error=str(e))
            return self.MSG_BAD_PAYLOAD
        try:
            # Recorded before the call: a failed or timed-out write may still have landed
            written.append(instance_name)
            self.compute_api.set_metadata(
                instance_name,
                items={PLANT_METADATA_KEY: payload, GUEST_ATTRIBUTES_ENABLE_KEY: GUEST_ATTRIBUTES_ENABLE_VALUE}
            )
            if reset:
                self.compute_api.reset(instance_name)
        except Exception as e:
            # Type only: a set_metadata error could echo the request body, which holds flag values
            self.logger.error(
                f"{self.class_name}:{board.id} - {self.MSG_DELIVERY} to {instance_name}", error=type(e).__name__
            )
            return self.MSG_DELIVERY
        return None

    def _await_acks(self, board, targets, nonces, guest):
        """
        Nested plant procedure: waits up to WATCHER_ACK_SECONDS for each delivered nested host to write
        plant-ack = its nonce. An un-acked whole-server plant resets the host so its loader runs the payload
        at boot; an un-acked guest plant fails its flags and never resets. Returns the board and the nonces
        still awaiting results.
        """
        nonces = dict(nonces)
        waiting = {server: nonce for server, nonce in nonces.items() if self._is_nested_host(server)}
        deadline = time.monotonic() + WATCHER_ACK_SECONDS
        while waiting and time.monotonic() < deadline:
            time.sleep(self.ACK_POLL_INTERVAL_SECONDS)
            for server, nonce in list(waiting.items()):
                try:
                    attributes = self.compute_api.get_guest_attributes(
                        self._instance_name(board, server), query_path=GUEST_ATTRIBUTE_NAMESPACE
                    )
                except NotFound:
                    board = self._fail_server(board, targets, server, self.MSG_NOT_FOUND)
                    del waiting[server], nonces[server]
                    continue
                except Exception as e:
                    self.logger.warning(f"{self.class_name}:{board.id} - plant ack poll failed", error=type(e).__name__)
                    continue
                if attributes.get(GUEST_ATTRIBUTE_ACK_KEY) == nonce:
                    del waiting[server]
        for server in waiting:
            instance_name = self._instance_name(board, server)
            if guest is not None:
                # A guest reset must leave the parent and its other guests running
                self.logger.warning(f"{self.class_name}:{board.id} - no plant ack from {instance_name}")
                board = self._fail_server(board, targets, server, self.MSG_NO_WATCHER)
                del nonces[server]
                continue
            self.logger.warning(f"{self.class_name}:{board.id} - no plant ack from {instance_name}; resetting")
            try:
                self.compute_api.reset(instance_name)
            except Exception as e:
                self.logger.error(
                    f"{self.class_name}:{board.id} - {self.MSG_DELIVERY} to {instance_name}", error=type(e).__name__
                )
                board = self._fail_server(board, targets, server, self.MSG_DELIVERY)
                del nonces[server]
        return board, nonces

    def _await_results(self, board, targets, nonces) -> CtfBoardModel:
        """
        Steps 5-6: poll every delivered server until each of its result keys answers with its nonce or the
        server's deadline passes (CONFIRM_TIMEOUT_SECONDS, or NESTED_CONFIRM_TIMEOUT_SECONDS for a nested host).
        """
        # (server, result key) -> nonce
        pending = {(server, key): nonce for server, nonce in nonces.items() for key in targets[server]}
        start = time.monotonic()
        deadlines = {
            server: start + (NESTED_CONFIRM_TIMEOUT_SECONDS if self._is_nested_host(server)
                             else self.CONFIRM_TIMEOUT_SECONDS)
            for server in nonces
        }
        while pending:
            now = time.monotonic()
            for server, key in [k for k in pending if deadlines[k[0]] <= now]:
                message = self.MSG_NESTED_TIMEOUT if self._is_nested_host(server) else self.MSG_TIMEOUT
                board = self._record(board, {fid: self._failed(message) for fid in targets[server][key]})
                del pending[(server, key)]
            if not pending:
                break
            time.sleep(self.POLL_INTERVAL_SECONDS)
            for server in dict.fromkeys(server for server, _ in pending):
                nonce = nonces[server]
                keys = [key for s, key in pending if s == server]
                try:
                    attributes = self.compute_api.get_guest_attributes(
                        self._instance_name(board, server), query_path=GUEST_ATTRIBUTE_NAMESPACE
                    )
                except NotFound:
                    flag_ids = [fid for key in keys for fid in targets[server][key]]
                    board = self._record(board, {fid: self._failed(self.MSG_NOT_FOUND) for fid in flag_ids})
                    for key in keys:
                        del pending[(server, key)]
                    continue
                except Exception as e:
                    # Transient API errors keep polling until the deadline
                    self.logger.warning(
                        f"{self.class_name}:{board.id} - guest attribute poll failed", error=type(e).__name__
                    )
                    continue
                for key in keys:
                    result = parse_plant_result(attributes.get(key), nonce)
                    if result is None:
                        continue
                    status, message = result
                    if status == RESULT_OK:
                        update = {'plant_status': 'planted', 'planted_at': time.time(), 'plant_error': None}
                    else:
                        update = self._failed(message or "Plant reported an error")
                    board = self._record(board, {fid: dict(update) for fid in targets[server][key]})
                    del pending[(server, key)]
                # plant-result is written after every relay section has finished, so a guest key still
                # missing once it is present will never arrive
                if parse_plant_result(attributes.get(GUEST_ATTRIBUTE_RESULT_KEY), nonce) is not None:
                    missing = [key for s, key in pending if s == server]
                    flag_ids = [fid for key in missing for fid in targets[server][key]]
                    if flag_ids:
                        board = self._record(board, {fid: self._failed(self.MSG_NO_GUEST_RESULT) for fid in flag_ids})
                    for key in missing:
                        del pending[(server, key)]
        return board

    def _fail_server(self, board, targets, server, message) -> CtfBoardModel:
        flag_ids = [fid for ids in targets[server].values() for fid in ids]
        return self._record(board, {fid: self._failed(message) for fid in flag_ids})

    @staticmethod
    def _instance_name(board: CtfBoardModel, server: str) -> str:
        # Same naming as SoloWorkout: f"{workout_id}-{server.name}"
        return f"{board.workout_id}-{server}"

    @staticmethod
    def _failed(message: str) -> dict:
        return {'plant_status': 'failed', 'plant_error': message[:MAX_RESULT_MESSAGE_LENGTH]}

    def _record(self, board: CtfBoardModel, updates: Dict[str, dict]) -> CtfBoardModel:
        """
        Writes plant fields for the given flag ids onto the board document in a transaction, touching only
        those flags' plant_* fields, so a concurrent solve or hint on the same board is never overwritten.
        """
        def apply(flags: list) -> list:
            for flag in flags:
                if flag.get('flag_id') in updates:
                    flag.update(updates[flag['flag_id']])
            return flags

        flags = self._write_flags(board, apply)
        stored = board.model_dump()
        stored['flags'] = flags
        return ModelValidator(model=CtfBoardModel, log_location=LoggerNames.CLOUD_FN).load(data=stored)

    def _write_flags(self, board: CtfBoardModel, apply: Callable[[list], list]) -> list:
        """Rewrites the stored board's flags list through `apply` in one transaction; returns the written list."""
        doc_ref = self.db.db.collection(DbCollections.CTF_BOARD.value).document(board.id)

        def operation(transaction):
            snapshot = doc_ref.get(transaction=transaction)
            if not snapshot.exists:
                raise NotFound(f"CTF board {board.id} not found")
            flags = apply(snapshot.to_dict().get('flags', []))
            transaction.update(doc_ref, {'flags': flags})
            return flags

        return self.db.transaction(operation)

    def build_payload(
        self,
        board: Union[CtfBoardModel, dict],
        server: str,
        nonce: str,
        seed: str,
        guest: Optional[str] = None,
        revert: bool = False
    ) -> str:
        """
        Returns the bash (Linux) or PowerShell (Windows) script that writes this board's flags for one
        server, idempotently, and reports ok:<nonce> or error:<nonce>:<message> to the guest attribute.
        A server with nested_guests gets the nested host payload instead (_nested_host_payload); `guest`
        limits that payload to one guest's relay section, and is rejected for any other server; `revert`
        (guest only) reverts that guest to its pristine snapshot first.
        Raises BadRequest if the server has no flags on the board, any interpolated string fails its
        Flag Location Formats pattern, or the payload exceeds the metadata size limit.
        """
        if not isinstance(board, CtfBoardModel):
            board = ModelValidator(model=CtfBoardModel, log_location=LoggerNames.CLOUD_FN).load(data=board)
        if not seed:
            raise ValueError(f"{self.class_name}:{self.event.id} - CTF flag seed is not configured")
        if not re.fullmatch(_NONCE_PATTERN, str(nonce)):
            raise BadRequest(f"{self.class_name}:{self.event.id} - Invalid plant nonce")

        if revert and guest is None:
            raise BadRequest(f"{self.class_name}:{self.event.id} - A snapshot revert needs a guest")
        if self._is_nested_host(server):
            payload = self._nested_host_payload(board, server, nonce, seed, guest=guest, revert=revert)
        elif guest is not None:
            raise BadRequest(f"{self.class_name}:{self.event.id} - Server '{server}' has no nested guests")
        else:
            payload = self._server_payload(board, server, nonce, seed)
        self._check_size(payload)
        return payload

    def _check_size(self, payload: str) -> None:
        if len(payload.encode('utf-8')) > PLANT_PAYLOAD_MAX_BYTES:
            raise BadRequest(f"{self.class_name}:{self.event.id} - Plant payload exceeds the metadata size limit")

    def _server_payload(self, board: CtfBoardModel, server: str, nonce: str, seed: str) -> str:
        flags = self._server_flags(board, server)
        operating_systems = {flag.operating_system for flag in flags}
        if len(operating_systems) != 1:
            raise BadRequest(
                f"{self.class_name}:{self.event.id} - Flags on server '{server}' mix operating systems"
            )
        planted = self._planted(board, flags, seed)
        if operating_systems == {'windows'}:
            return self._windows_payload(planted, nonce)
        return self._linux_payload(planted, nonce)

    def build_guest_payload(
        self,
        board: Union[CtfBoardModel, dict],
        server: str,
        guest: str,
        nonce: str,
        seed: str
    ) -> str:
        """
        Returns the bash or PowerShell body (per the guest's operating_system) that writes this board's flags
        for one nested guest of `server` (Nested Guest Contract). It writes no guest attribute: its epilogue
        prints exactly one line, ok:<nonce> or error:<nonce>:<message>, to the stdout saved before the
        prologue silences everything else, and the parent's relay reads that line back.
        Raises BadRequest if the guest is not declared on the server, has no flags on the board, a flag's
        operating system differs from the guest's, or any interpolated string fails its pattern.
        """
        if not isinstance(board, CtfBoardModel):
            board = ModelValidator(model=CtfBoardModel, log_location=LoggerNames.CLOUD_FN).load(data=board)
        if not seed:
            raise ValueError(f"{self.class_name}:{self.event.id} - CTF flag seed is not configured")
        if not re.fullmatch(_NONCE_PATTERN, str(nonce)):
            raise BadRequest(f"{self.class_name}:{self.event.id} - Invalid plant nonce")

        declared = next(
            (g for g in self.event.spec.nested_guests if g.server == server and g.name == guest), None
        )
        if declared is None:
            raise BadRequest(
                f"{self.class_name}:{self.event.id} - Guest '{guest}' is not declared on server '{server}'"
            )
        flags = [flag for flag in self._board_flags_on(board, server) if flag.guest == guest]
        if not flags:
            raise BadRequest(
                f"{self.class_name}:{self.event.id} - Board {board.id} has no flags on guest '{guest}' of '{server}'"
            )
        for flag in flags:
            if flag.operating_system != declared.operating_system:
                raise BadRequest(
                    f"{self.class_name}:{self.event.id} - Flag {flag.id} operating system differs from guest '{guest}'"
                )
        planted = self._planted(board, flags, seed)
        if declared.operating_system == 'windows':
            return self._windows_payload(planted, nonce, guest=True)
        return self._linux_payload(planted, nonce, guest=True)

    def _nested_host_payload(
        self, board: CtfBoardModel, server: str, nonce: str, seed: str, guest: Optional[str] = None,
        revert: bool = False
    ) -> str:
        """
        Parent payload for a nested host (Nested Guest Contract): ack first, then the parent's own flags,
        then one relay section per qemu-agent guest with board flags, run in parallel, then plant-result
        last, reporting the parent's flags only. Guests with the offline driver are not relayed here.
        With `guest` set (a guest host reset) the parent's flags and every other guest are left out.
        """
        board_flags = self._board_flags_on(board, server)
        parent_flags = [flag for flag in board_flags if flag.guest is None] if guest is None else []
        guests = [
            g for g in self.event.spec.nested_guests
            if g.server == server and g.driver == 'qemu-agent' and (guest is None or g.name == guest)
            and any(flag.guest == g.name for flag in board_flags)
        ]
        if not parent_flags and not guests:
            raise BadRequest(
                f"{self.class_name}:{self.event.id} - Board {board.id} has no flags on server '{server}'"
            )
        if any(flag.operating_system != 'linux' for flag in parent_flags):
            raise BadRequest(
                f"{self.class_name}:{self.event.id} - Flags on nested host '{server}' must be linux"
            )
        relays = [(g, self.build_guest_payload(board, server, g.name, nonce, seed)) for g in guests]
        return self._linux_payload(self._planted(board, parent_flags, seed), nonce, relays=relays, revert=revert)

    def _planted(self, board: CtfBoardModel, flags: List[CtfFlagSpecModel], seed: str) -> list:
        """(flag, value) pairs, each path and derived value checked against its pattern before interpolation."""
        prefix = self.event.spec.scoring.flag_prefix
        planted = []
        for flag in flags:
            self._check_path(flag)
            value = derive_flag_value(seed, board.workout_id, flag.id, self.event.seed_version, prefix)
            if not re.fullmatch(_VALUE_PATTERN, value):
                raise BadRequest(f"{self.class_name}:{self.event.id} - Flag {flag.id} derived an unsafe value")
            planted.append((flag, value))
        return planted

    def _server_flags(self, board: CtfBoardModel, server: str) -> List[CtfFlagSpecModel]:
        flags = self._board_flags_on(board, server)
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
        if flag.operating_system == 'windows' and flag.location_type in ('file', 'ads'):
            if flag.windows_access is not None and flag.windows_access not in _WINDOWS_ACCESS_LEVELS:
                raise BadRequest(f"{self.class_name}:{self.event.id} - Flag {flag.id} has an invalid windows_access")
            if flag.windows_access == 'user' and not re.fullmatch(_WINDOWS_USER_PATTERN, flag.windows_user or ''):
                raise BadRequest(f"{self.class_name}:{self.event.id} - Flag {flag.id} has an invalid windows_user")

    @staticmethod
    def _linux_payload(
        planted: list, nonce: str, guest: bool = False, relays: Optional[list] = None, revert: bool = False,
        actions: Optional[List[str]] = None
    ) -> str:
        """
        `relays` (nested host only) is a list of (guest spec, guest payload) to relay after the placements, each
        reverted to its pristine snapshot first when `revert` is set. `actions` (nested host only) are guest
        action sections (_linux_guest_action) whose failures are reported through plant-result.
        """
        q = shlex.quote
        ack = _LINUX_ACK.format(nonce=q(nonce), url=q(_GUEST_ATTRIBUTES_URL + GUEST_ATTRIBUTE_ACK_PATH))
        lines = [_LINUX_PROLOGUE.format(
            nonce=q(nonce), env_file=q(LINUX_ENVIRONMENT_FILE), metadata_ip=_METADATA_SERVER_IP,
            save_stdout=_LINUX_GUEST_SAVE_STDOUT if guest else '',
            ack=ack if relays is not None or actions is not None else ''
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
        if relays:
            lines.append(FlagPlanter._linux_relays(relays, revert=revert))
        lines.extend(actions or [])
        epilogue = _LINUX_GUEST_EPILOGUE if guest else _LINUX_EPILOGUE
        lines.append(epilogue.format(
            ok=RESULT_OK, error=RESULT_ERROR, max_message=MAX_RESULT_MESSAGE_LENGTH, url=q(_GUEST_ATTRIBUTE_URL)
        ))
        return "\n".join(lines)

    @staticmethod
    def _linux_relays(relays: list, revert: bool = False) -> str:
        """The relay functions, one background section per guest, and the wait that precedes plant-result."""
        q = shlex.quote
        compact = {'separators': (',', ':')}
        lines = [_LINUX_RELAY.format(
            ping=q(json.dumps({'execute': 'guest-ping'}, **compact)),
            status_open=q('{"execute":"guest-exec-status","arguments":{"pid":'), status_close=q('}}'),
            virsh_timeout=_RELAY_VIRSH_TIMEOUT_SECONDS, agent_timeout=_RELAY_AGENT_TIMEOUT_SECONDS,
            budget=RELAY_BUDGET_SECONDS, ping_interval=_RELAY_PING_INTERVAL_SECONDS,
            status_interval=_RELAY_STATUS_INTERVAL_SECONDS, ok=RESULT_OK, error=RESULT_ERROR,
            revert_timeout=_RELAY_REVERT_TIMEOUT_SECONDS, snapshot=q(PRISTINE_SNAPSHOT_NAME),
            # error:<nonce>:<message>, with the longest nonce _NONCE_PATTERN allows
            max_line=len(RESULT_ERROR) + 64 + MAX_RESULT_MESSAGE_LENGTH + 2
        )]
        for guest, payload in relays:
            arguments = {'input-data': base64.b64encode(payload.encode('utf-8')).decode('ascii'), 'capture-output': True}
            if guest.operating_system == 'windows':
                bootstrap = base64.b64encode(_WINDOWS_GUEST_BOOTSTRAP.encode('utf-16-le')).decode('ascii')
                arguments.update(path='powershell.exe', arg=[
                    '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-EncodedCommand', bootstrap
                ])
            else:
                arguments.update(path='/bin/bash', arg=['-s'])
            request = json.dumps({'execute': 'guest-exec', 'arguments': arguments}, **compact)
            # Single-quoted for virsh's own tokenizer; base64 and the fixed arguments hold no quote
            if "'" in request:
                raise BadRequest(f"Relay request for guest '{guest.name}' cannot be quoted")
            exec_command = f"qemu-agent-command {guest.domain} '{request}' --timeout {_RELAY_AGENT_TIMEOUT_SECONDS}"
            url = _GUEST_ATTRIBUTES_URL + guest_result_path(guest.name)
            relay = 'agoge_ctf_rebuild_qemu' if revert else 'agoge_ctf_relay_qemu'
            lines.append(f"{relay} {q(guest.name)} {q(guest.domain)} {q(url)} {q(exec_command)} &")
        # plant-result (the epilogue) is written only once every guest section has written its own key
        lines.append("wait\n")
        return "\n".join(lines)

    @staticmethod
    def _linux_guest_action(guest: CtfNestedGuestSpecModel, action: str) -> str:
        """One guest action section: `restart` is `virsh reboot`, `revert` a pristine snapshot revert."""
        q = shlex.quote
        domain, snapshot = q(guest.domain), q(PRISTINE_SNAPSHOT_NAME)
        if action == 'restart':
            steps = [(f"timeout {_RELAY_VIRSH_TIMEOUT_SECONDS} virsh -q reboot {domain}",
                      f"{guest.name}: guest reboot failed")]
        elif action == 'revert':
            steps = [
                (f"timeout {_RELAY_VIRSH_TIMEOUT_SECONDS} virsh -q snapshot-info {domain} {snapshot}",
                 f"{guest.name}: no {PRISTINE_SNAPSHOT_NAME} snapshot"),
                (f"timeout {_RELAY_REVERT_TIMEOUT_SECONDS} virsh -q snapshot-revert {domain} {snapshot} --running",
                 f"{guest.name}: snapshot revert failed"),
            ]
        else:
            raise ValueError(f"Unsupported guest action: {action}")
        checks = ''.join(f"elif ! {command}; then\n  agoge_ctf_fail {q(message)}\n" for command, message in steps)
        return _LINUX_GUEST_ACTION.format(not_available=q(f"{guest.name}: virsh is not available"), checks=checks)

    @staticmethod
    def _windows_payload(planted: list, nonce: str, guest: bool = False) -> str:
        q = FlagPlanter._ps_quote
        lines = [_WINDOWS_PROLOGUE.format(nonce=q(nonce), save_stdout=_WINDOWS_GUEST_SAVE_STDOUT if guest else '')]
        for flag, value in planted:
            if flag.location_type == 'file':
                lines.append(f"Set-AgogeCtfFile {q(flag.path)} {q(value)} {q(flag.id)}")
                lines.extend(FlagPlanter._windows_file_options(flag, flag.path))
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
                # A stream shares its host file's permissions and attributes
                lines.extend(FlagPlanter._windows_file_options(flag, path))
        epilogue = _WINDOWS_GUEST_EPILOGUE if guest else _WINDOWS_EPILOGUE
        lines.append(epilogue.format(
            ok=RESULT_OK, error=RESULT_ERROR, max_message=MAX_RESULT_MESSAGE_LENGTH, url=q(_GUEST_ATTRIBUTE_URL)
        ))
        return "\n".join(lines)

    @staticmethod
    def _windows_file_options(flag: CtfFlagSpecModel, path: str) -> List[str]:
        # Access before Hidden: changing attributes needs the write-attributes right SYSTEM keeps either way
        q = FlagPlanter._ps_quote
        lines = []
        if flag.windows_access:
            user = flag.windows_user if flag.windows_access == 'user' else ''
            lines.append(f"Set-AgogeCtfAccess {q(path)} {q(flag.windows_access)} {q(user or '')} {q(flag.id)}")
        if flag.hidden:
            lines.append(f"Set-AgogeCtfHidden {q(path)} {q(flag.id)}")
        return lines

    @staticmethod
    def _ps_quote(value: str) -> str:
        # PowerShell single-quoted literal: no expansion; a quote is escaped by doubling it
        return "'" + value.replace("'", "''") + "'"
