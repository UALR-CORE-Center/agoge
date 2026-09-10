import re

from common.exceptions import AgogeValidationError
from common.constants.build_constants import BuildConstants
from common.utilities.wireguard_firewall import (
    DEFAULT_WIREGUARD_PORT,
    has_public_wireguard_ingress,
)

from .networks import NetworksValidator


class FirewallRulesValidator:
    def __init__(
        self,
        config: dict,
        wireguard_port: int = DEFAULT_WIREGUARD_PORT,
        require_wireguard_listener: bool = True,
    ) -> None:
        self.config = config
        self.firewalls = self.config.get('firewalls')
        self.network_map = {}
        self.external_network = None
        self.wireguard_port = wireguard_port
        self.require_wireguard_listener = require_wireguard_listener

    def load(self) -> dict:
        networks_validator = NetworksValidator(self.config)
        if not (network_map := self.config.get('network_map')):
            self.network_map = networks_validator.map_network()
            self.config['network_map'] = self.network_map
        else:
            self.network_map = network_map

        if not (promiscuous_mode := self.config.get('promiscuous_mode')) and promiscuous_mode is None:
            self.config['promiscuous_mode'] = (
                networks_validator.enable_promiscuous_mode(self.config['networks'])
            )
        else:
            self.config['promiscuous_mode'] = promiscuous_mode

        # Update config with validated firewall rules
        self._add_firewall_rules()
        self._validate_firewall_rules()
        self._validate_wireguard_listener()

        return self.config

    def _add_firewall_rules(self) -> None:
        if not self.firewalls:
            self.external_network = BuildConstants.Networks.WORKOUT_EXTERNAL_NAME
        else:
            self.external_network = self.firewalls[0]['gateway']

        firewall_rules = self.config.get('firewall_rules', [])

        for network in self.network_map:
            firewall_rule = {
                'name': 'allow-all-local',
                'network': network,
                'target_tags': [],
                'protocol': None,
                'ports': ['tcp/any', 'udp/any', 'icmp/any'],
                'ip_ranges': [self.network_map[network]],
                'priority': 999
            }
            self._add_or_update_rule(firewall_rules, firewall_rule)

            # If any builds require a connection without allowing any internet access, we need this rule
            # to ensure that all local traffic is still allowed
            internal_egress_all = {
                'name': 'allow-internal-egress',
                'network': network,
                'target_tags': [],
                'protocol': None,
                'ports': ['tcp/any', 'udp/any', 'icmp/any'],
                'ip_ranges': [self.network_map[network]],
                'direction': BuildConstants.Firewalls.TrafficDirection.EGRESS.value,
                'priority': 999
            }
            self._add_or_update_rule(firewall_rules, internal_egress_all)
        display_proxy_rule = {
            'name': 'allow-student-entry',
            'network': self.external_network,
            'target_tags': ['student-entry'],
            'protocol': None,
            'ports': ['tcp/80,443,8443,4822'],
            'ip_ranges': ['0.0.0.0/0']
        }
        self._add_or_update_rule(firewall_rules, display_proxy_rule)

        if self.config.get('promiscuous_mode'):
            collector_lb_rule = {
                'name': 'allow-health-check',
                'network': self.external_network,
                'target_tags': ['lb-health-check'],
                'direction': BuildConstants.Firewalls.TrafficDirection.INGRESS.value,
                'protocol': BuildConstants.Firewalls.TransportProtocols.TCP.value,
                'ports': ['tcp/80,8080,443'],
                'ip_ranges': [
                    "35.191.0.0/16",
                    "130.211.0.0/22",
                ],
                'priority': 1000,
            }
            self._add_or_update_rule(firewall_rules, collector_lb_rule)

            collector_lb_ssh_rule = {
                'name': 'allow-ssh',
                'network': self.external_network,
                'target_tags': ['lb-health-check'],
                'direction': BuildConstants.Firewalls.TrafficDirection.INGRESS.value,
                'protocol': BuildConstants.Firewalls.TransportProtocols.TCP.value,
                'ports': ['tcp/22'],
                'ip_ranges': [
                    '0.0.0.0/0'
                ],
                'priority': 1000,
            }
            self._add_or_update_rule(firewall_rules, collector_lb_ssh_rule)

        # Update config firewall rules
        self.config['firewall_rules'] = firewall_rules

    @staticmethod
    def _add_or_update_rule(
        firewall_rules: list,
        new_rule: dict
    ) -> None:
        """Check if a rule already exists, update it or add if it doesn't."""
        for existing_rule in firewall_rules:
            if existing_rule['name'] == new_rule['name'] and existing_rule['network'] == new_rule['network']:
                existing_rule.update(new_rule)  # Update the existing rule
                return

        # If no matching rule is found, append the new rule
        firewall_rules.append(new_rule)

    def _validate_firewall_rules(self) -> None:
        """Validates that all networks declared in firewall rules exist"""
        rules = self.config.get('firewall_rules', [])
        if rules:
            for rule in rules:
                name = rule.get('name')
                if not self._valid_resource_suffix(name):
                    raise AgogeValidationError(
                        f'Firewall rule name {name} must use lowercase letters, numbers, '
                        'or hyphens, start with a letter, not end with a hyphen, and be '
                        "no longer than 52 characters so Agoge's build ID prefix fits "
                        'the 63-character GCE firewall-rule limit'
                    )
                for tag in rule.get('target_tags') or []:
                    if not self._valid_network_tag(tag):
                        raise AgogeValidationError(
                            f'Firewall rule {name} has invalid target tag {tag}; tags must '
                            'be 1-63 lowercase letters, numbers, or hyphens, start with a '
                            'letter, and not end with a hyphen'
                        )
                if rule['network'] == self.external_network:
                    continue
                elif not self.network_map.get(rule['network'], False):
                    raise AgogeValidationError(f'Invalid network given for firewall rule with name: {rule["name"]}. '
                                               f'Network {rule["network"]} does not exist!')

    def _validate_wireguard_listener(self) -> None:
        """Require an explicit, project-port-aware rule before publication."""
        if not self.require_wireguard_listener:
            return
        if self.config.get('unit_type', BuildConstants.UnitType.SOLO) != BuildConstants.UnitType.COMMUNITY:
            return

        gateways = [
            server
            for server in self.config.get('servers', [])
            if server.get('wireguard_gateway', False)
        ]
        if not gateways:
            return
        try:
            port = int(self.wireguard_port)
        except (TypeError, ValueError) as error:
            raise AgogeValidationError(
                'The project wireguard_port must be an integer from 1 through 65535'
            ) from error
        if isinstance(self.wireguard_port, bool) or not 1 <= port <= 65535:
            raise AgogeValidationError(
                'The project wireguard_port must be an integer from 1 through 65535'
            )
        if has_public_wireguard_ingress(self.config, port):
            return

        gateway = gateways[0]
        public_nic = next(
            (nic for nic in gateway.get('nics', []) if nic.get('external_nat', False)),
            {},
        )
        network = public_nic.get('network', '<gateway-network>')
        raise AgogeValidationError(
            f'Community WireGuard gateway {gateway.get("name")} requires an explicit '
            f'allow INGRESS firewall rule on network {network} for public UDP port '
            f'{port}. The rule must apply to the gateway tag (or all targets), allow '
            'a public source range, and use priority 0-65534.'
        )

    @staticmethod
    def _valid_resource_suffix(name: str) -> bool:
        return bool(re.fullmatch(r'[a-z](?:[a-z0-9-]{0,50}[a-z0-9])?', str(name)))

    @staticmethod
    def _valid_network_tag(tag: str) -> bool:
        return bool(re.fullmatch(r'[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?', str(tag)))
