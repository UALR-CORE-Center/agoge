from typing import Callable, Optional

from common.constants.nested import NESTED_MACHINE_FAMILIES
from common.exceptions import AgogeValidationError


class NestedServersValidator:
    """
    Checks spec servers built from a nested lab host image, and every Guacamole `alias_index`.

    A nested image exposes guest *i* through alias IP *i* on NIC 0 (the runtime DNATs slot by slot), so a
    server using one needs an N1/N2 machine type and at least `len(nested.exposures)` aliases on NIC 0. A
    connection's `alias_index` names one of those aliases, so it must be in range on any server.
    """
    def __init__(
        self,
        config: dict,
        image_loader: Callable[[str], Optional[dict]]
    ) -> None:
        """
        @param config: The specification
        @param image_loader: Returns the image document for an image doc id, or None when there is none
        """
        self.config = config
        self.image_loader = image_loader

    def load(self) -> dict:
        images = {}
        for server in self.config.get('servers') or []:
            name = server.get('name')
            aliases = self._nic0_aliases(server)
            image_id = self._image_doc_id(server.get('image'))
            if image_id and image_id not in images:
                images[image_id] = self.image_loader(image_id)
            image = images.get(image_id) if image_id else None
            nested = image.get('nested') if isinstance(image, dict) else None
            if isinstance(nested, dict):
                self._validate_nested_host(name, server, nested, aliases)
            self._validate_alias_indexes(name, server, aliases)
        return self.config

    @staticmethod
    def _validate_nested_host(name: str, server: dict, nested: dict, aliases: list) -> None:
        machine_type = server.get('machine_type')
        family = machine_type.split('-')[0].lower() if isinstance(machine_type, str) else None
        if family not in NESTED_MACHINE_FAMILIES:
            raise AgogeValidationError(
                f'Server {name} uses a nested lab host image and needs an N1 or N2 machine type, '
                f'not {machine_type}'
            )
        exposures = len(nested.get('exposures') or [])
        if len(aliases) < exposures:
            raise AgogeValidationError(
                f'Server {name} uses a nested lab host image that exposes {exposures} guest(s), so NIC 0 '
                f'needs at least {exposures} ip_aliases; it has {len(aliases)}'
            )

    @staticmethod
    def _validate_alias_indexes(name: str, server: dict, aliases: list) -> None:
        for connection in server.get('human_interaction') or []:
            if not isinstance(connection, dict) or connection.get('alias_index') is None:
                continue
            alias_index = connection['alias_index']
            if not isinstance(alias_index, int) or not 0 <= alias_index < len(aliases):
                raise AgogeValidationError(
                    f'Server {name} has a connection with alias_index {alias_index}, but NIC 0 has '
                    f'{len(aliases)} ip_aliases'
                )

    @staticmethod
    def _nic0_aliases(server: dict) -> list:
        nics = server.get('nics') or []
        if not nics or not isinstance(nics[0], dict):
            return []
        aliases = nics[0].get('ip_aliases') or []
        return aliases if isinstance(aliases, list) else []

    @staticmethod
    def _image_doc_id(image) -> Optional[str]:
        """Image doc ids drop the `image-` prefix; anything with a path (a public image) is not an Agoge image."""
        if isinstance(image, dict):
            image = image.get('value')
        if not isinstance(image, str) or not image or '/' in image:
            return None
        return image.removeprefix('image-')
