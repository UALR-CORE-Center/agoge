from common.exceptions import AgogeValidationError
from common.constants.build_constants import BuildConstants

from .networks import NetworksValidator


class FirewallRulesValidator:
    def __init__(
        self,
        config: dict
    ) -> None:
        self.config = config
        self.firewalls = self.config.get('firewalls')
        self.network_map = {}
        self.external_network = None

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
                if rule['network'] == self.external_network:
                    continue
                elif not self.network_map.get(rule['network'], False):
                    raise AgogeValidationError(f'Invalid network given for firewall rule with name: {rule["name"]}. '
                                               f'Network {rule["network"]} does not exist!')
