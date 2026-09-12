"""Determine image ownership from stored Compute references, not client flags."""

import re
from collections.abc import Mapping


def image_source(record: Mapping) -> str:
    """Support current image records and legacy imported boot-disk records."""
    for value in (record.get('self_link'), record.get('image')):
        if isinstance(value, str) and 'projects/' in value:
            return value.strip()
    for disk in record.get('disks') or []:
        if disk.get('boot'):
            return disk.get('initializeParams', {}).get('sourceImage', '')
    return ''


def image_source_project(record: Mapping) -> str | None:
    match = re.search(r'(?:^|/)projects/([^/]+)/global/images/', image_source(record))
    return match.group(1) if match else None


def is_shared_image(record: Mapping, project: str) -> bool:
    source_project = image_source_project(record)
    if not source_project or source_project == project:
        return False
    # New local templates reference a differently named base until check-in.
    # Legacy imported templates can incorrectly set image_exists=False, so
    # that flag alone must not make a shared template editable in place.
    if record.get('image_exists') is False:
        source_name = image_source(record).rstrip('/').rsplit('/', 1)[-1]
        target_names = {f'image-{record.get("name", "")}', record.get('image')}
        if source_name not in target_names:
            return False
    return True
