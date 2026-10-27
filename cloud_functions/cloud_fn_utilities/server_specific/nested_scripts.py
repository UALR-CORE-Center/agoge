"""Render the shell scripts and systemd units a nested lab host's parent runs.

The sources live in server_specific/nested/ and carry `@@NAME@@` placeholders (bash's own `${...}`
rules out string.Template). See the Nested Image Builder Contract in PRD.md.
"""
import re
from pathlib import Path
from typing import Dict

from common.constants.nested import NESTED_MEDIA_BUCKET_SUFFIX

NESTED_DIR = Path(__file__).resolve().parent / 'nested'

# Parent filesystem layout shared by the builder, the runtime, and the finalize watcher.
HOST_JSON_PATH = '/etc/agoge-nested/host.json'
RUNTIME_PATH = '/usr/local/sbin/agoge-nested-runtime'
RUNTIME_UNIT_NAME = 'agoge-nested-runtime.service'
RUNTIME_UNIT_PATH = f'/etc/systemd/system/{RUNTIME_UNIT_NAME}'
# libvirt network i gets bridge agb<i>; the runtime matches guest traffic on agb+.
BRIDGE_PREFIX = 'agb'
BUILDER_PATH = '/usr/local/sbin/agoge-nested-builder'
BUILDER_UNIT_NAME = 'agoge-nested-builder.service'
# Media must stay out of /root: qemu runs as libvirt-qemu (Working Note 15).
MEDIA_DIR = '/var/lib/libvirt/boot/agoge-nested'
STATE_DIR = '/var/lib/agoge-nested/state'
WORK_DIR = '/var/lib/agoge-nested/work'
# tmpfs: the builder's copy of agoge-nested-secrets lives here and never reaches the disk.
RUN_DIR = '/run/agoge-nested'
SECRETS_PATH = f'{RUN_DIR}/secrets.json'
FINALIZE_PATH = '/usr/local/sbin/agoge-nested-finalize'
FINALIZE_UNIT_NAME = 'agoge-nested-finalize.service'
# Outside STATE_DIR and WORK_DIR, which the finalize deletes.
FINALIZE_ANSWERED_PATH = '/var/lib/agoge-nested/finalize-answered'
# Contract: guests get 240 s to shut down, inside the function's NESTED_FINALIZE_TIMEOUT_SECONDS.
FINALIZE_SHUTDOWN_SECONDS = 240
# The builder embeds the runtime between these heredoc delimiters.
_HEREDOC_DELIMITERS = ('AGOGE_NESTED_RUNTIME_SCRIPT', 'AGOGE_NESTED_RUNTIME_UNIT')
# The template server's startup-script embeds the builder between this delimiter.
_BUILDER_DELIMITER = 'AGOGE_NESTED_BUILDER_SCRIPT'
_FINALIZE_DELIMITER = 'AGOGE_NESTED_FINALIZE_SCRIPT'

_PLACEHOLDER = re.compile(r'@@([A-Z_]+)@@')


def render_runtime() -> str:
    """Return the agoge-nested-runtime script."""
    return _render('runtime.sh', {'HOST_JSON': HOST_JSON_PATH, 'BRIDGE_PREFIX': BRIDGE_PREFIX})


def render_direct_connect(slot: int) -> str:
    """Return startup-script lines that forward outside SSH on the host's primary address to the slot's guest."""
    return _render('direct_connect.sh', {'HOST_JSON': HOST_JSON_PATH, 'SLOT': str(int(slot))})


def direct_connect_slot(human_interaction: list | None) -> int | None:
    """The jumpbox's alias slot: the first displayed SSH connection to a nested guest, else None."""
    for connection in human_interaction or []:
        if (isinstance(connection, dict) and connection.get('display') and connection.get('protocol') == 'ssh'
                and connection.get('alias_index') is not None):
            return int(connection['alias_index'])
    return None


def render_runtime_unit() -> str:
    """Return the agoge-nested-runtime systemd unit."""
    return _render(RUNTIME_UNIT_NAME, {'RUNTIME_PATH': RUNTIME_PATH})


def render_builder() -> str:
    """Return the agoge-nested-builder script, with the runtime and its unit embedded."""
    runtime, unit = render_runtime().rstrip('\n'), render_runtime_unit().rstrip('\n')
    for delimiter in _HEREDOC_DELIMITERS:
        if any(line == delimiter for line in (runtime + '\n' + unit).splitlines()):
            raise ValueError(f"the runtime contains the heredoc delimiter {delimiter}")
    return _render('builder.sh', {
        'STATE_DIR': STATE_DIR, 'WORK_DIR': WORK_DIR, 'RUN_DIR': RUN_DIR, 'MEDIA_DIR': MEDIA_DIR,
        'HOST_JSON': HOST_JSON_PATH, 'RUNTIME_PATH': RUNTIME_PATH, 'RUNTIME_UNIT_PATH': RUNTIME_UNIT_PATH,
        'RUNTIME_UNIT_NAME': RUNTIME_UNIT_NAME, 'BRIDGE_PREFIX': BRIDGE_PREFIX,
        'MEDIA_BUCKET_SUFFIX': NESTED_MEDIA_BUCKET_SUFFIX, 'RUNTIME_SCRIPT': runtime, 'RUNTIME_UNIT': unit,
    })


def render_builder_bootstrap() -> str:
    """Return startup-script lines that install the builder and start it as a transient unit.

    No `exit`: the lines are merged into the template's startup-script after the user-creation
    script, where the shebang is only a comment. The build takes hours, so it runs under systemd-run rather than blocking
    the startup-script, and every boot re-installs the script and restarts the unit only when it
    is not already running (the builder's markers make a rerun resume, and it is a no-op without a
    manifest).
    """
    builder = render_builder().rstrip('\n')
    if any(line == _BUILDER_DELIMITER for line in builder.splitlines()):
        raise ValueError(f"the builder contains the heredoc delimiter {_BUILDER_DELIMITER}")
    unit = BUILDER_UNIT_NAME.removesuffix('.service')
    return '\n'.join([
        '#!/bin/bash',
        '# agoge-nested-builder bootstrap',
        f"cat > '{BUILDER_PATH}.tmp' <<'{_BUILDER_DELIMITER}'",
        builder,
        _BUILDER_DELIMITER,
        f"chmod 700 '{BUILDER_PATH}.tmp' && mv -f '{BUILDER_PATH}.tmp' '{BUILDER_PATH}'",
        f"if ! systemctl is-active --quiet {BUILDER_UNIT_NAME}; then",
        f"  systemctl reset-failed {BUILDER_UNIT_NAME} 2>/dev/null || true",
        f"  systemd-run --unit={unit} --description='Agoge nested host builder' '{BUILDER_PATH}'",
        'fi',
    ]) + '\n'


def render_finalize_watcher() -> str:
    """Return the agoge-nested-finalize script."""
    return _render('finalize.sh', {
        'HOST_JSON': HOST_JSON_PATH, 'MEDIA_DIR': MEDIA_DIR, 'RUN_DIR': RUN_DIR, 'STATE_DIR': STATE_DIR,
        'WORK_DIR': WORK_DIR, 'ANSWERED_PATH': FINALIZE_ANSWERED_PATH,
        'SHUTDOWN_SECONDS': str(FINALIZE_SHUTDOWN_SECONDS),
    })


def render_finalize_bootstrap() -> str:
    """Return startup-script lines that install the finalize watcher and start it as a transient unit.

    Transient (systemd-run), never enabled: the contract installs the watcher only on template
    servers, and an enabled unit would be baked into the image and run on every lab server.
    No `exit`, for the same reason as render_builder_bootstrap.
    """
    watcher = render_finalize_watcher().rstrip('\n')
    if any(line == _FINALIZE_DELIMITER for line in watcher.splitlines()):
        raise ValueError(f"the finalize watcher contains the heredoc delimiter {_FINALIZE_DELIMITER}")
    unit = FINALIZE_UNIT_NAME.removesuffix('.service')
    return '\n'.join([
        '#!/bin/bash',
        '# agoge-nested-finalize bootstrap',
        f"cat > '{FINALIZE_PATH}.tmp' <<'{_FINALIZE_DELIMITER}'",
        watcher,
        _FINALIZE_DELIMITER,
        f"chmod 700 '{FINALIZE_PATH}.tmp' && mv -f '{FINALIZE_PATH}.tmp' '{FINALIZE_PATH}'",
        f"if ! systemctl is-active --quiet {FINALIZE_UNIT_NAME}; then",
        f"  systemctl reset-failed {FINALIZE_UNIT_NAME} 2>/dev/null || true",
        f"  systemd-run --unit={unit} --property=Restart=always --description='Agoge nested host finalize watcher' "
        f"'{FINALIZE_PATH}'",
        'fi',
    ]) + '\n'


def _render(filename: str, values: Dict[str, str]) -> str:
    source = (NESTED_DIR / filename).read_text()
    missing = sorted(set(_PLACEHOLDER.findall(source)) - set(values))
    if missing:
        raise ValueError(f"{filename}: no value for {', '.join(missing)}")
    return _PLACEHOLDER.sub(lambda match: values[match.group(1)], source)
