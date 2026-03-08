from netaddr import IPSet, IPNetwork

from common.exceptions import AgogeValidationError
from common.constants.build_constants import BuildConstants


class NetworksValidator:
    def __init__(
        self,
        config: dict
    ) -> None:
        self.config = config
        self.firewalls = self.config.get('firewalls', None)
        self.promiscuous_mode = False
        self.networks = None
        self.network_map = {}

    def load(self) -> dict:
        self._validate()

        # Return updated config
        self.config['network_map'] = self.network_map
        self.config['promiscuous_mode'] = self.promiscuous_mode
        return self.config

    def _validate(self) -> None:
        if 'networks' not in self.config:
            self.config['networks'] = [BuildConstants.Networks.WORKOUT_DEFAULT_NETWORK_CONFIG]
        else:
            default_exists = False
            for network in self.config['networks']:
                if network['name'] == BuildConstants.Networks.WORKOUT_DEFAULT_NETWORK_CONFIG['name']:
                    default_exists = True
            if not default_exists and not self.firewalls:
                raise AgogeValidationError(f"An external network is not included in the specification")

        # Create network map
        self.map_network()

        # If the workout uses a firewall server, add the gateway network as the default
        # external network
        if self.firewalls:
            firewall_network = BuildConstants.Networks.GATEWAY_NETWORK_CONFIG
            firewall_network['name'] = BuildConstants.Networks.GATEWAY_NETWORK_NAME
            self.config['networks'].append(firewall_network)

    def map_network(self) -> dict:
        """Creates and validates network map"""
        for network in self.config['networks']:
            subnet = network['subnets'][0]['ip_subnet']
            current_network = IPSet(IPNetwork(subnet))
            for processed_network in self.network_map:
                processed_subnet = self.network_map[processed_network]
                if not current_network.isdisjoint(IPSet(IPNetwork(processed_subnet))):
                    raise AgogeValidationError(f"Specification has overlapping networks {subnet} and "
                                               f"{processed_subnet}. Please correct this in the "
                                               f"specification before building")

            # Check if any subnets have promiscuous_mode enabled
            self.enable_promiscuous_mode(network)

            # Add subnet to network map
            self.network_map[network['name']] = subnet
        return self.network_map

    def enable_promiscuous_mode(
            self,
            network_obj: dict | list[dict]
    ) -> None:
        if isinstance(network_obj, dict) and not self.promiscuous_mode:
            self.promiscuous_mode = any(subnet.get('promiscuous_mode') for subnet in network_obj.get('subnets', []))
        elif isinstance(network_obj, list):
            for network in network_obj:
                if not self.promiscuous_mode:
                    self.promiscuous_mode = any(subnet.get('promiscuous_mode') for subnet in network.get('subnets', []))
