import re
from netaddr import IPNetwork, IPAddress

from common.constants.build_constants import BuildConstants
from common.exceptions import AgogeValidationError
from .networks import NetworksValidator


class ServersValidator:
    def __init__(
        self,
        config: dict
    ) -> None:
        self.config = config
        self.network_map = self._network_map
        self.direct_connect = False

    @property
    def _network_map(self) -> dict:
        if network_map := self.config.get('network_map'):
            return network_map
        else:
            network_map = NetworksValidator(self.config).map_network()
            self.config['network_map'] = network_map
            return network_map

    def load(self) -> dict:
        self._validate()

        # Return updated config
        return self.config

    def _validate(self) -> None:
        is_community_build = (
                self.config.get('unit_type', BuildConstants.UnitType.SOLO) == BuildConstants.UnitType.COMMUNITY
        )
        for server in self.config['servers']:
            # For community builds that are not shared servers, the internal_IP is dynamic
            if is_community_build and 'community_server' not in server:
                continue
            if not self._validate_server_name(server['name']):
                raise AgogeValidationError(f"Invalid server name \"{server['name']}\". "
                                           f"Server names must meet the following requirements:"
                                           f"\n\t- Starts with a lowercase letter"
                                           f"\n\t- Followed by up to 62 lowercase letters, numbers or hyphens"
                                           f"\n\t- Cannot end with a hyphen")
            for nic in server['nics']:
                network_name = nic['network']
                ip = nic['internal_ip']
                last_quad = ip.split(".")[-1]

                # Validate network name
                if network_name not in self.network_map:
                    raise AgogeValidationError(f"{server['name']} is attempting to build in a network "
                                               f"named {network_name} which is not included in the specification")

                # Validate internal ip
                if not IPAddress(ip) in IPNetwork(self.network_map[network_name]):
                    raise AgogeValidationError(f"{server['name']} uses an IP address {ip} that does not match its "
                                               f"build network subnet {self.network_map[network_name]}")
                if last_quad in ['0', '1', '254', '255']:
                    raise AgogeValidationError(f"{server['name']} uses a reserved IP address {ip} for the cloud.")

                # Validate direct_connect
                if nic.get('direct_connect', False):
                    if not nic['external_nat']:
                        raise AgogeValidationError(f'For network {nic["name"]} in server, {server["name"]}, '
                                                   f'direct_connect was enabled, but external_nat is set to False!')
                    tags = server.setdefault('tags', [])

    @staticmethod
    def _validate_server_name(
            server_name: str
    ) -> bool:
        pattern = r'^[a-z][a-z0-9-]{0,61}[a-z0-9]$'
        return bool(re.match(pattern, str(server_name)))
