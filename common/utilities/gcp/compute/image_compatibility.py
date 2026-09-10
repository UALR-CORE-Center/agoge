"""Resolve the actual boot image and check its CPU architecture before creation."""

import re

from common.exceptions import BadRequest


def normalize_architecture(value: str | None) -> str | None:
    if not isinstance(value, str):
        return None
    return {
        'X86_64': 'X86_64', 'AMD64': 'X86_64', 'X86-64': 'X86_64',
        'ARM64': 'ARM64', 'AARCH64': 'ARM64',
    }.get(value.strip().upper())


def _machine_architecture(machine) -> str | None:
    """Use explicit metadata first, then known series for an omitted field."""
    value = getattr(machine, 'architecture', None)
    if value is not None:
        if not isinstance(value, str):
            return None
        if value.strip().upper() not in ('', 'ARCHITECTURE_UNSPECIFIED', 'UNDEFINED_ARCHITECTURE'):
            # Do not replace an explicit architecture, including an unknown one.
            return normalize_architecture(value)

    # machineTypes.get can omit architecture. These supported series are x86:
    # https://docs.cloud.google.com/compute/docs/general-purpose-machines
    # Use the fetched resource's name, only after a successful machine lookup.
    name = getattr(machine, 'name', '')
    if isinstance(name, str):
        series, separator, size = name.partition('-')
        if separator and size and series in ('e2', 'n1', 'n2'):
            return 'X86_64'
    return None


def compatible_boot_image(image_api, machine_api, source: str, machine_type: str):
    """Use live metadata, including for legacy catalogs and queued templates.

    Resolve family URLs to a concrete image, so creation uses the version that
    was checked. Never fall back from an explicit source project to another.
    """
    path = source.strip() if isinstance(source, str) else ''
    if '/projects/' in path:
        path = 'projects/' + path.split('/projects/', 1)[1]
    if path.startswith('global/images/'):
        path = f'projects/{image_api.project}/{path}'
    match = re.fullmatch(r'projects/([^/]+)/global/images/(family/)?([^/]+)', path)
    if not match:
        raise BadRequest('Cannot verify the boot image. Select an image with a valid Compute image source URL.')
    project, family_prefix, name = match.groups()
    kwargs = {'family': True} if family_prefix else {}
    response = image_api.get(resource=name, project=project, fallback_to_shared=False, **kwargs)
    image = response.image if family_prefix else response
    image_architecture = normalize_architecture(image.architecture)
    if not image_architecture:
        raise BadRequest(
            f'Cannot determine the CPU architecture of image {name}. '
            'Select an image with ARM64 or X86_64 architecture metadata.'
        )
    if not image.self_link or not image.self_link.strip():
        raise BadRequest(f'Image {name} has no concrete source image URL. Refresh the image catalog.')

    machine = machine_api.get_resource(resource=machine_type)
    machine_architecture = _machine_architecture(machine)
    if not machine_architecture:
        raise BadRequest(f'Cannot determine the CPU architecture of machine type {machine_type}.')
    if image_architecture != machine_architecture:
        label = 'AMD64 (x86-64)' if machine_architecture == 'X86_64' else 'ARM64'
        raise BadRequest(
            f'Image {image.name or name} uses {image_architecture}, but machine type '
            f'{machine_type} uses {machine_architecture}. Select an {label} image for this machine.'
        )
    return image
