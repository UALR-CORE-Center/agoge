import re
from ipaddress import IPv4Address, IPv4Network, ip_address, ip_network

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
        wireguard_gateways = []
        for server in self.config['servers']:
            if not self._validate_server_name(server['name']):
                raise AgogeValidationError(f"Invalid server name \"{server['name']}\". "
                                           f"Server names must meet the following requirements:"
                                           f"\n\t- Starts with a lowercase letter"
                                           f"\n\t- Contains at most 52 lowercase letters, numbers or hyphens"
                                           f"\n\t- Cannot end with a hyphen"
                                           f"\nThe 52-character limit leaves room for Agoge's 10-character "
                                           f"build ID prefix in the final GCE instance name.")
            for tag in server.get('tags') or []:
                if not self._validate_network_tag(tag):
                    raise AgogeValidationError(
                        f'Invalid network tag {tag} on server {server["name"]}; tags must '
                        'be 1-63 lowercase letters, numbers, or hyphens, start with a '
                        'letter, and not end with a hyphen'
                    )
            is_shared_server = server.get('community_server', False)
            dynamic_internal_ip = is_community_build and not is_shared_server

            if server.get('wireguard_gateway', False):
                wireguard_gateways.append(server['name'])
                if not is_community_build or not is_shared_server:
                    raise AgogeValidationError(
                        f'WireGuard gateway {server["name"]} must be a community_server '
                        'in a community unit'
                    )
                if not server.get('can_ip_forward', False):
                    raise AgogeValidationError(
                        f'WireGuard gateway {server["name"]} must enable can_ip_forward'
                    )
                if not any(nic.get('external_nat', False) for nic in server.get('nics', [])):
                    raise AgogeValidationError(
                        f'WireGuard gateway {server["name"]} must have an external NAT interface'
                    )

            for nic in server.get('nics', []):
                network_name = nic['network']

                external_ip_name = nic.get('external_ip_name')
                if external_ip_name and not self._validate_gce_resource_name(external_ip_name):
                    raise AgogeValidationError(
                        f'Invalid external_ip_name {external_ip_name} on server '
                        f'{server["name"]}; it must be a 1-63 character lowercase '
                        'Google Compute Engine resource name'
                    )

                # Validate network name
                if network_name not in self.network_map:
                    raise AgogeValidationError(f"{server['name']} is attempting to build in a network "
                                               f"named {network_name} which is not included in the specification")

                subnet_name = nic.get('subnet_name', 'default')
                subnet = self._get_subnet(network_name, subnet_name)

                # Direct-connect validation cannot be skipped just because a
                # community workout receives its internal address dynamically.
                if nic.get('direct_connect', False) and not nic.get('external_nat', False):
                    raise AgogeValidationError(
                        f'For network {network_name} in server, {server["name"]}, '
                        'direct_connect was enabled, but external_nat is set to False!'
                    )

                # Per-student servers in community builds receive their addresses from
                # the unit allocator. Shared servers still require a fixed address.
                ip = nic.get('internal_ip')
                if not ip and dynamic_internal_ip:
                    continue
                if not ip:
                    raise AgogeValidationError(
                        f'{server["name"]} is missing an internal IP address for network '
                        f'{network_name}'
                    )

                try:
                    address = ip_address(ip)
                except ValueError as error:
                    raise AgogeValidationError(
                        f'{server["name"]} uses invalid internal IP address {ip}'
                    ) from error
                if not isinstance(address, IPv4Address):
                    raise AgogeValidationError(
                        f'{server["name"]} uses non-IPv4 internal IP address {ip}'
                    )
                if address not in subnet:
                    raise AgogeValidationError(f"{server['name']} uses an IP address {ip} that does not match its "
                                               f"build network subnet {subnet}")
                if self._is_gcp_reserved_address(address, subnet):
                    raise AgogeValidationError(f"{server['name']} uses a reserved IP address {ip} for the cloud.")

        if len(wireguard_gateways) > 1:
            raise AgogeValidationError(
                'A community unit can define only one WireGuard gateway; found '
                + ', '.join(wireguard_gateways)
            )

    def _get_subnet(self, network_name: str, subnet_name: str) -> IPv4Network:
        network = next(
            network
            for network in self.config.get('networks', [])
            if network.get('name') == network_name
        )
        subnet_config = next(
            (
                subnet
                for subnet in network.get('subnets') or []
                if subnet.get('name', 'default') == subnet_name
            ),
            None
        )
        if not subnet_config or not subnet_config.get('ip_subnet'):
            raise AgogeValidationError(
                f'Network {network_name} does not define subnet {subnet_name}'
            )
        try:
            subnet = ip_network(subnet_config['ip_subnet'], strict=True)
        except ValueError as error:
            raise AgogeValidationError(
                f'Network {network_name}, subnet {subnet_name} has invalid CIDR '
                f'{subnet_config["ip_subnet"]}'
            ) from error
        if not isinstance(subnet, IPv4Network):
            raise AgogeValidationError(
                f'Network {network_name}, subnet {subnet_name} must be IPv4'
            )
        return subnet

    @staticmethod
    def _is_gcp_reserved_address(address: IPv4Address, subnet: IPv4Network) -> bool:
        """GCP reserves the first two and last two addresses of each subnet."""
        first = subnet.network_address
        last = subnet.broadcast_address
        return address in {first, first + 1, last - 1, last}

    @staticmethod
    def _validate_server_name(
            server_name: str
    ) -> bool:
        pattern = r'^[a-z](?:[a-z0-9-]{0,50}[a-z0-9])?$'
        return bool(re.match(pattern, str(server_name)))

    @staticmethod
    def _validate_network_tag(tag: str) -> bool:
        return bool(re.fullmatch(r'[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?', str(tag)))

    @staticmethod
    def _validate_gce_resource_name(name: str) -> bool:
        return bool(re.fullmatch(r'[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?', str(name)))
