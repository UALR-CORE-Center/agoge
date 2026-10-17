import re
from typing import Callable, Optional

from common.exceptions import AgogeValidationError
from common.utilities.ctf_plant_contract import LOCATION_PATH_PATTERNS
from .nested_servers import NestedServersValidator


class CtfValidator:
    """
    Spec-time validation of the `ctf` block. The payload builder interpolates `path` into bash/PowerShell,
    so these patterns are the only thing keeping spec-authored strings from reaching a script unescaped.
    """
    WINDOWS_ONLY_LOCATIONS = ('registry', 'ads')
    # Shared with FlagPlanter, which re-checks every path before it reaches a script
    PATH_PATTERNS = LOCATION_PATH_PATTERNS

    def __init__(
        self,
        config: dict,
        image_loader: Optional[Callable[[str], Optional[dict]]] = None
    ) -> None:
        """
        @param config: The specification
        @param image_loader: Returns the image document for an image doc id; lets a nested-guest parent
            built from a nested lab host image pass without ip_aliases. Without it only ip_aliases count.
        """
        self.config = config
        self.image_loader = image_loader

    def load(self) -> dict:
        self._validate()
        return self.config

    def _validate(self) -> None:
        flags = (self.config.get('ctf') or {}).get('flags') or []
        server_names = {server.get('name') for server in self.config.get('servers') or []}
        guests = self._validate_nested_guests()
        flag_ids = set()
        slots = {}
        server_os = {}

        for flag in flags:
            flag_id = flag.get('id')
            server = flag.get('server')
            operating_system = flag.get('operating_system')
            location_type = flag.get('location_type')

            if flag_id in flag_ids:
                raise AgogeValidationError(f"Invalid CTF flag {flag_id}: flag ids must be unique")
            flag_ids.add(flag_id)

            if server not in server_names:
                raise AgogeValidationError(
                    f"Invalid CTF flag {flag_id}: server '{server}' does not exist in the specification"
                )

            guest_name = flag.get('guest')
            target = f"server '{server}'" if guest_name is None else f"guest '{guest_name}' on server '{server}'"
            guest = None
            if guest_name is not None:
                guest = guests.get((server, guest_name))
                if guest is None:
                    raise AgogeValidationError(
                        f"Invalid CTF flag {flag_id}: guest '{guest_name}' is not declared in nested_guests "
                        f"on server '{server}'"
                    )
                if operating_system != guest.get('operating_system'):
                    raise AgogeValidationError(
                        f"Invalid CTF flag {flag_id}: operating_system '{operating_system}' does not match "
                        f"'{guest.get('operating_system')}' on guest '{guest_name}'"
                    )

            # A guest is its own machine, so slots and the single-OS rule are per (server, guest);
            # guest None is the parent itself
            slot = flag.get('slot')
            if (server, guest_name, slot) in slots:
                raise AgogeValidationError(
                    f"Invalid CTF flag {flag_id}: slot {slot} on {target} is already used by "
                    f"flag {slots[(server, guest_name, slot)]}"
                )
            slots[(server, guest_name, slot)] = flag_id

            first_os = server_os.setdefault((server, guest_name), (operating_system, flag_id))
            if first_os[0] != operating_system:
                raise AgogeValidationError(
                    f"Invalid CTF flag {flag_id}: operating_system '{operating_system}' conflicts with "
                    f"'{first_os[0]}' on flag {first_os[1]} for {target}"
                )

            if location_type in self.WINDOWS_ONLY_LOCATIONS and operating_system != 'windows':
                raise AgogeValidationError(
                    f"Invalid CTF flag {flag_id}: location_type '{location_type}' requires operating_system 'windows'"
                )

            pattern = self.PATH_PATTERNS.get((location_type, operating_system))
            # fullmatch, not match: '$' alone accepts a trailing newline, which would reach the plant script
            if pattern is None or not re.fullmatch(pattern, str(flag.get('path'))):
                raise AgogeValidationError(
                    f"Invalid CTF flag {flag_id}: path {flag.get('path')!r} does not match the "
                    f"{location_type} format for {operating_system} ({pattern})"
                )

            self._validate_windows_file_options(flag)
            if guest is not None and guest.get('driver') == 'offline' and operating_system == 'windows':
                self._validate_offline_windows(flag)

            if not flag.get('decoy', False) and not (isinstance(flag.get('points'), int) and flag['points'] > 0):
                raise AgogeValidationError(
                    f"Invalid CTF flag {flag_id}: points must be greater than 0 unless the flag is a decoy"
                )

        unlocks = {flag.get('id'): flag.get('unlocks_after') or [] for flag in flags}
        for flag_id, prerequisites in unlocks.items():
            for prerequisite in prerequisites:
                if prerequisite not in unlocks:
                    raise AgogeValidationError(
                        f"Invalid CTF flag {flag_id}: unlocks_after names unknown flag '{prerequisite}'"
                    )
        self._validate_no_cycles(unlocks)

    MAX_GUESTS_PER_SERVER = 8

    def _validate_nested_guests(self) -> dict:
        """Check `ctf.nested_guests` against the spec servers; returns {(server, name): guest}."""
        servers = {server.get('name'): server for server in self.config.get('servers') or []}
        guests = {}
        per_server = {}
        for guest in (self.config.get('ctf') or {}).get('nested_guests') or []:
            name = guest.get('name')
            server_name = guest.get('server')
            server = servers.get(server_name)
            if server is None:
                raise AgogeValidationError(
                    f"Invalid CTF nested guest {name}: server '{server_name}' does not exist in the specification"
                )
            # Spec servers carry their OS under details (ServerModel); the top-level key is the compute form
            server_os = (server.get('details') or {}).get('os') or server.get('os')
            if server_os != 'linux':
                raise AgogeValidationError(
                    f"Invalid CTF nested guest {name}: server '{server_name}' must be a Linux server, not "
                    f"{server_os!r}"
                )
            # ip_aliases, or an image with `nested`, is what turns on nested virtualization at build
            # (base_compute_manager)
            if not any(nic.get('ip_aliases') for nic in server.get('nics') or []) \
                    and not self._has_nested_image(server):
                raise AgogeValidationError(
                    f"Invalid CTF nested guest {name}: server '{server_name}' needs a NIC with ip_aliases or "
                    f"a nested lab host image to run nested guests"
                )
            if (server_name, name) in guests:
                raise AgogeValidationError(
                    f"Invalid CTF nested guest {name}: guest names must be unique on server '{server_name}'"
                )
            guests[(server_name, name)] = guest
            per_server[server_name] = per_server.get(server_name, 0) + 1
            if per_server[server_name] > self.MAX_GUESTS_PER_SERVER:
                raise AgogeValidationError(
                    f"Invalid CTF nested guest {name}: server '{server_name}' has more than "
                    f"{self.MAX_GUESTS_PER_SERVER} nested guests"
                )
        return guests

    def _has_nested_image(self, server: dict) -> bool:
        image_id = NestedServersValidator.image_doc_id(server.get('image'))
        if self.image_loader is None or not image_id:
            return False
        image = self.image_loader(image_id)
        # Only a dict counts: callers' mocked dbs return MagicMocks whose .get('nested') is truthy
        return isinstance(image, dict) and isinstance(image.get('nested'), dict)

    OFFLINE_WINDOWS_LOCATIONS = ('file', 'registry', 'env')
    # The offline driver edits the guest's registry hives on its disk; only SOFTWARE and SYSTEM are supported
    OFFLINE_REGISTRY_PREFIXES = ('HKLM\\SOFTWARE\\', 'HKLM\\SYSTEM\\')

    @classmethod
    def _validate_offline_windows(cls, flag: dict) -> None:
        flag_id = flag.get('id')
        location_type = flag.get('location_type')
        if location_type not in cls.OFFLINE_WINDOWS_LOCATIONS:
            raise AgogeValidationError(
                f"Invalid CTF flag {flag_id}: location_type '{location_type}' is not supported on an offline "
                f"Windows guest (use {', '.join(cls.OFFLINE_WINDOWS_LOCATIONS)})"
            )
        if flag.get('windows_access') or flag.get('hidden'):
            raise AgogeValidationError(
                f"Invalid CTF flag {flag_id}: windows_access and hidden are not supported on an offline Windows guest"
            )
        if location_type == 'registry' and not str(flag.get('path')).startswith(cls.OFFLINE_REGISTRY_PREFIXES):
            raise AgogeValidationError(
                f"Invalid CTF flag {flag_id}: an offline Windows guest's registry path must start with "
                f"{' or '.join(cls.OFFLINE_REGISTRY_PREFIXES)}"
            )

    WINDOWS_FILE_LOCATIONS = ('file', 'ads')

    @classmethod
    def _validate_windows_file_options(cls, flag: dict) -> None:
        flag_id = flag.get('id')
        access = flag.get('windows_access')
        user = flag.get('windows_user')
        windows_file = flag.get('operating_system') == 'windows' and flag.get('location_type') in cls.WINDOWS_FILE_LOCATIONS
        if (access or user or flag.get('hidden')) and not windows_file:
            raise AgogeValidationError(
                f"Invalid CTF flag {flag_id}: windows_access, windows_user and hidden apply only to Windows "
                f"file and ads flags"
            )
        if access == 'user' and not user:
            raise AgogeValidationError(f"Invalid CTF flag {flag_id}: windows_access 'user' requires windows_user")
        if user and access != 'user':
            raise AgogeValidationError(f"Invalid CTF flag {flag_id}: windows_user is used only with windows_access 'user'")

    @staticmethod
    def _validate_no_cycles(unlocks: dict) -> None:
        # Iterative three-colour DFS; a back edge to a 'visiting' node is a cycle
        visiting, done = 1, 2
        colour = {}
        for root in unlocks:
            if root in colour:
                continue
            colour[root] = visiting
            path = [root]
            stack = [iter(unlocks[root])]
            while stack:
                child = next(stack[-1], None)
                if child is None:
                    colour[path.pop()] = done
                    stack.pop()
                elif colour.get(child) == visiting:
                    cycle = path[path.index(child):] + [child]
                    raise AgogeValidationError(
                        f"Invalid CTF flag {child}: unlocks_after forms a cycle ({' -> '.join(cycle)})"
                    )
                elif child not in colour:
                    colour[child] = visiting
                    path.append(child)
                    stack.append(iter(unlocks[child]))
