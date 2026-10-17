import re

from common.exceptions import AgogeValidationError
from common.utilities.ctf_plant_contract import LOCATION_PATH_PATTERNS


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
        config: dict
    ) -> None:
        self.config = config

    def load(self) -> dict:
        self._validate()
        return self.config

    def _validate(self) -> None:
        flags = (self.config.get('ctf') or {}).get('flags') or []
        server_names = {server.get('name') for server in self.config.get('servers') or []}
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

            slot = flag.get('slot')
            if (server, slot) in slots:
                raise AgogeValidationError(
                    f"Invalid CTF flag {flag_id}: slot {slot} on server '{server}' is already used by "
                    f"flag {slots[(server, slot)]}"
                )
            slots[(server, slot)] = flag_id

            first_os = server_os.setdefault(server, (operating_system, flag_id))
            if first_os[0] != operating_system:
                raise AgogeValidationError(
                    f"Invalid CTF flag {flag_id}: operating_system '{operating_system}' conflicts with "
                    f"'{first_os[0]}' on flag {first_os[1]} for server '{server}'"
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
