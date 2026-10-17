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
# Media must stay out of /root: qemu runs as libvirt-qemu (Working Note 15).
MEDIA_DIR = '/var/lib/libvirt/boot/agoge-nested'
STATE_DIR = '/var/lib/agoge-nested/state'
WORK_DIR = '/var/lib/agoge-nested/work'
# tmpfs: the builder's copy of agoge-nested-secrets lives here and never reaches the disk.
RUN_DIR = '/run/agoge-nested'
SECRETS_PATH = f'{RUN_DIR}/secrets.json'
# The builder embeds the runtime between these heredoc delimiters.
_HEREDOC_DELIMITERS = ('AGOGE_NESTED_RUNTIME_SCRIPT', 'AGOGE_NESTED_RUNTIME_UNIT')

_PLACEHOLDER = re.compile(r'@@([A-Z_]+)@@')


def render_runtime() -> str:
    """Return the agoge-nested-runtime script."""
    return _render('runtime.sh', {'HOST_JSON': HOST_JSON_PATH, 'BRIDGE_PREFIX': BRIDGE_PREFIX})


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


def _render(filename: str, values: Dict[str, str]) -> str:
    source = (NESTED_DIR / filename).read_text()
    missing = sorted(set(_PLACEHOLDER.findall(source)) - set(values))
    if missing:
        raise ValueError(f"{filename}: no value for {', '.join(missing)}")
    return _PLACEHOLDER.sub(lambda match: values[match.group(1)], source)
