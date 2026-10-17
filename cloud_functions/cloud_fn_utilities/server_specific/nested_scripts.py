"""Render the shell scripts and systemd units a nested lab host's parent runs.

The sources live in server_specific/nested/ and carry `@@NAME@@` placeholders (bash's own `${...}`
rules out string.Template). See the Nested Image Builder Contract in PRD.md.
"""
import re
from pathlib import Path
from typing import Dict

NESTED_DIR = Path(__file__).resolve().parent / 'nested'

# Parent filesystem layout shared by the builder, the runtime, and the finalize watcher.
HOST_JSON_PATH = '/etc/agoge-nested/host.json'
RUNTIME_PATH = '/usr/local/sbin/agoge-nested-runtime'
RUNTIME_UNIT_NAME = 'agoge-nested-runtime.service'
RUNTIME_UNIT_PATH = f'/etc/systemd/system/{RUNTIME_UNIT_NAME}'
# libvirt network i gets bridge agb<i>; the runtime matches guest traffic on agb+.
BRIDGE_PREFIX = 'agb'

_PLACEHOLDER = re.compile(r'@@([A-Z_]+)@@')


def render_runtime() -> str:
    """Return the agoge-nested-runtime script."""
    return _render('runtime.sh', {'HOST_JSON': HOST_JSON_PATH, 'BRIDGE_PREFIX': BRIDGE_PREFIX})


def render_runtime_unit() -> str:
    """Return the agoge-nested-runtime systemd unit."""
    return _render(RUNTIME_UNIT_NAME, {'RUNTIME_PATH': RUNTIME_PATH})


def _render(filename: str, values: Dict[str, str]) -> str:
    source = (NESTED_DIR / filename).read_text()
    missing = sorted(set(_PLACEHOLDER.findall(source)) - set(values))
    if missing:
        raise ValueError(f"{filename}: no value for {', '.join(missing)}")
    return _PLACEHOLDER.sub(lambda match: values[match.group(1)], source)
