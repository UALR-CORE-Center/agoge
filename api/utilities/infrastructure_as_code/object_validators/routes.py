from ipaddress import IPv4Network, ip_network
import re

from common.constants.build_constants import BuildConstants
from common.exceptions import AgogeValidationError


class RoutesValidator:
    """Validate references and forwarding requirements for custom static routes."""

    def __init__(self, config: dict) -> None:
        self.config = config

    def load(self) -> dict:
        self._validate()
        return self.config

    def _validate(self) -> None:
        networks = {
            network.get('name'): network
            for network in self.config.get('networks', [])
        }
        local_subnets = self._get_local_subnets(networks.values())
        server_list = self.config.get('servers', [])
        servers = {server.get('name'): server for server in server_list}
        route_entries = [
            (route, None) for route in (self.config.get('routes') or [])
        ]
        route_entries.extend(
            (route, server)
            for server in server_list
            for route in (server.get('routes') or [])
        )
        if not route_entries:
            return

        route_names = set()

        for route, owning_server in route_entries:
            route_name = route.get('name')
            if not route_name:
                raise AgogeValidationError('A static route is missing its name')
            if not self._valid_resource_suffix(route_name):
                raise AgogeValidationError(
                    f'Route name {route_name} must use lowercase letters, numbers, or '
                    'hyphens, start with a letter, not end with a hyphen, and be no '
                    "longer than 52 characters so Agoge's build ID prefix fits the "
                    '63-character GCE route-name limit'
                )
            if route_name in route_names:
                raise AgogeValidationError(
                    f'Specification contains duplicate static route name {route_name}'
                )
            route_names.add(route_name)

            for tag in route.get('tags') or []:
                if not self._valid_network_tag(tag):
                    raise AgogeValidationError(
                        f'Route {route_name} has invalid network tag {tag}; tags must be '
                        '1-63 lowercase letters, numbers, or hyphens, start with a '
                        'letter, and not end with a hyphen'
                    )

            network_name = route.get('network')
            if network_name not in networks:
                raise AgogeValidationError(
                    f'Route {route_name} refers to network {network_name}, which is not '
                    'included in the specification'
                )

            destination = route.get('dest_range')
            try:
                destination_network = ip_network(destination, strict=True)
            except (TypeError, ValueError) as error:
                raise AgogeValidationError(
                    f'Route {route_name} has invalid destination CIDR {destination}'
                ) from error
            if not isinstance(destination_network, IPv4Network):
                raise AgogeValidationError(
                    f'Route {route_name} destination {destination} must be IPv4'
                )
            overlapping_subnet = next(
                (
                    local_subnet
                    for local_subnet in local_subnets
                    if destination_network.overlaps(local_subnet)
                ),
                None
            )
            if overlapping_subnet:
                raise AgogeValidationError(
                    f'Route {route_name} destination {destination_network} overlaps local '
                    f'lab subnet {overlapping_subnet}'
                )

            next_hop_name = route.get('next_hop_instance')
            if owning_server and next_hop_name != owning_server.get('name'):
                raise AgogeValidationError(
                    f'Route {route_name} is attached to server '
                    f'{owning_server.get("name")}, so that server must be its next hop'
                )
            next_hop = servers.get(next_hop_name)
            if not next_hop:
                raise AgogeValidationError(
                    f'Route {route_name} refers to next-hop server {next_hop_name}, which '
                    'is not included in the specification'
                )
            if not next_hop.get('can_ip_forward', False):
                raise AgogeValidationError(
                    f'Route {route_name} uses server {next_hop_name} as its next hop, but '
                    'that server does not enable can_ip_forward'
                )
            if not any(
                nic.get('network') == network_name
                for nic in next_hop.get('nics') or []
            ):
                raise AgogeValidationError(
                    f'Route {route_name} uses server {next_hop_name} as its next hop, but '
                    f'that server has no NIC on network {network_name}'
                )
            is_community_build = (
                self.config.get('unit_type', BuildConstants.UnitType.SOLO)
                == BuildConstants.UnitType.COMMUNITY
            )
            if is_community_build and not next_hop.get('community_server', False):
                raise AgogeValidationError(
                    f'Route {route_name} next-hop server {next_hop_name} must be a '
                    'community_server in a community unit'
                )

    @staticmethod
    def _get_local_subnets(networks) -> list[IPv4Network]:
        local_subnets = []
        for network in networks:
            for subnet in network.get('subnets') or []:
                try:
                    parsed_subnet = ip_network(subnet.get('ip_subnet'), strict=True)
                except (TypeError, ValueError) as error:
                    raise AgogeValidationError(
                        f'Network {network.get("name")} has invalid subnet CIDR '
                        f'{subnet.get("ip_subnet")}'
                    ) from error
                if isinstance(parsed_subnet, IPv4Network):
                    local_subnets.append(parsed_subnet)
        return local_subnets

    @staticmethod
    def _valid_resource_suffix(name: str) -> bool:
        return bool(re.fullmatch(r'[a-z](?:[a-z0-9-]{0,50}[a-z0-9])?', str(name)))

    @staticmethod
    def _valid_network_tag(tag: str) -> bool:
        return bool(re.fullmatch(r'[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?', str(tag)))
