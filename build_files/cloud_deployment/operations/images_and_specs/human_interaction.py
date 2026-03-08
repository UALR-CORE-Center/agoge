import re
from typing import List, Union

from common.models.agoge import HumanInteractionModel
from common.constants.build_constants import BuildConstants

from .message import Message


class HumanInteraction:
    class Protocol:
        RDP = 'rdp'
        SSH = 'ssh'

    def __init__(self) -> None:
        self.human_interaction = []
        self.msg = Message()

    def create(self) -> List[HumanInteractionModel]:
        self.msg.info("Creating human interaction fields ...")
        while True:
            # Populate model
            username = self._get_username()
            password = self._get_password(username)
            display = self._get_display()
            protocol = self._get_connection_protocol()

            conn = HumanInteractionModel(
                username=username,
                password=password,
                display=display,
                protocol=protocol,
            )

            if protocol == self.Protocol.SSH:
                conn.ssh_key = self._get_ssh_key(username=username)

            if security_mode := self._get_security_mode(conn.display):
                conn.security_mode = security_mode

            if domain := self._get_domain():
                conn.domain = domain

            self.human_interaction.append(conn)

            if not self.msg.confirm("Add another connection"):
                break

        return self.human_interaction

    def _get_username(self) -> str:
        pattern = r"^[a-zA-Z0-9_.-]{3,32}$"
        while True:
            username = str(input("Enter username of user on image: "))
            if username[0].isdigit():
                self.msg.error("Usernames cannot start with a number or special character!")
                continue
            if re.match(pattern, username):
                if self.msg.confirm(f"Set username to", username):
                    return username
            self.msg.error(f"Invalid input for username, {username}. Usernames must follow the pattern ({pattern})")

    def _get_password(self, username: str) -> str:
        while True:
            password = str(input(f"Enter a password for {username}: "))
            if password and not password.isspace():
                if self.msg.confirm(f"Set password to", password):
                    return password
            else:
                self.msg.error("Password cannot be empty or only spaces.")

    def _get_domain(self) -> Union[str, None]:
        pattern = r"^[a-z][a-z0-9-]*[a-z0-9]$"
        confirm = input("Attach existing cloud local domain for active directory? (Y/n) ")

        if confirm.lower() == 'y':
            while True:
                domain = str(input("Enter local domain ([a-z][a-z0-9-][a-z0-9]): "))
                domain = "".join(domain.split())
                if re.match(pattern, domain):
                    if self.msg.confirm(f"Set domain to", domain):
                        return domain
                else:
                    self.msg.error("Domains must follow the following pattern: ([a-z][a-z0-9-][a-z0-9])")

    def _get_security_mode(
        self,
        display_enabled: bool
    ) -> Union[str, None]:
        if display_enabled:
            opts = ["[0] RDP", "[1] NLA", "[2] ANY", "[3] TLS"]
            options = BuildConstants.Guacamole.SecurityModes
            mode_name = options.NLA.value
            while True:
                print("Enter a proxy security mode (default is NLA)")
                for opt in opts:
                    self.msg.default(opt, indent=True)

                mode = input("Security Mode: ")
                if mode:
                    try:
                        mode = int(mode)
                        if mode == 0:
                            mode_name = options.RDP.value
                        elif mode == 2:
                            mode_name = options.ANY.value
                        elif mode == 3:
                            mode_name = options.TLS.value
                    except ValueError:
                        self.msg.error(f"Invalid input for security mode: {mode}")
                        continue

                if self.msg.confirm(f'Set proxy security mode to',  mode_name.upper()):
                    return mode_name

    def _get_connection_protocol(self) -> str:
        opts = ["[1] RDP", "[2] SSH"]
        while True:
            print("Select a protocol:")
            for opt in opts:
                self.msg.default(opt, indent=True)

            choice = input("Enter your choice (1/2): ")
            if choice == "1":
                return self.Protocol.RDP
            elif choice == "2":
                return self.Protocol.SSH
            else:
                self.msg.error("Invalid choice. Please try again.")

    def _get_display(self) -> bool:
        return self.msg.confirm("Enable display for proxy machine")

    @staticmethod
    def _get_ssh_key(username: str) -> str:
        ssh_key = str(input(f"Enter SSH key to authenticate user {username}: "))
        return ssh_key
