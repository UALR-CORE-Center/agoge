"""Check interactive student-image metadata without logging credential values."""
from collections.abc import Mapping

from common.constants.states import ImageStatus
from common.utilities.gcp.compute.image_ownership import is_shared_image


def student_image_profile(record: Mapping, project: str | None = None) -> tuple[list[dict], list[str]]:
    """Return normalized display connections and credential-free rejection reasons.

    A legacy shared record may say image_exists=False even though it refers to
    its published shared image. That exception applies only to an authoritative
    source reference, not a new local template still pointing at a base image.
    Callers must verify the actual Compute image is READY/AMD64 before building.
    """
    reasons = []
    if not isinstance(record.get('name'), str) or not record['name'].strip():
        reasons.append('missing name field (Agoge image/template ID)')
    status = record.get('status')
    status = status.value if isinstance(status, ImageStatus) else status
    if isinstance(status, bool) or status not in (0, '0'):
        reasons.append('status is not checked in (expected 0)')
    if record.get('image_exists') is False and not (project and is_shared_image(record, project)):
        reasons.append('image_exists is false and no published shared-image reference was identified')

    raw = record.get('human_interaction') or []
    raw = [raw] if isinstance(raw, Mapping) else raw
    if not isinstance(raw, list) or not raw:
        reasons.append('human_interaction has no saved connection')
        return [], reasons

    connections, connection_errors = [], []
    for index, connection in enumerate(raw, 1):
        if not isinstance(connection, Mapping):
            connection_errors.append(f'connection {index}: invalid connection object')
            continue
        errors = []
        if connection.get('display') is not True:
            errors.append('display is not enabled')
        protocol = connection.get('protocol')
        protocol = protocol.strip().lower() if isinstance(protocol, str) else ''
        if protocol not in ('ssh', 'rdp', 'vnc'):
            errors.append('protocol must be SSH, RDP, or VNC')
        for field in ('username', 'password'):
            value = connection.get(field)
            if not isinstance(value, str) or not value.strip():
                errors.append(f'missing {field}')
        if errors:
            connection_errors.append(f'connection {index}: {"; ".join(errors)}')
        else:
            connections.append({**connection, 'protocol': protocol})
    if not connections:
        reasons.extend(connection_errors)
    return (connections if not reasons else []), reasons
