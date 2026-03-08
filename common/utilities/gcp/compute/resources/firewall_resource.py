from enum import Enum
from typing import List
from google.cloud.compute_v1 import Firewall, Denied, Allowed

from common.constants.google import FirewallDirection, IpProtocol, FirewallRuleAction
from common.exceptions import BadRequest


class FirewallResource:
    def new(
        self,
        name: str,
        network: str,
        action: FirewallRuleAction = FirewallRuleAction.ALLOW,
        rules: List[Allowed | Denied] = None,
        direction: FirewallDirection = FirewallDirection.INGRESS,
        description: str = None,
        priority: int = 1000,
        ip_ranges: List[str] = None,
        source_tags: List[str] = None,
        target_tags: List[str] = None,
    ) -> Firewall:
        if priority is None:
            priority = 1000
        if isinstance(direction, Enum):
            direction = direction.value
        if not description:
            description = f'{name} network [{network}] {action.name} {direction} firewall rule.'

        firewall_resource = Firewall(
            name=name,
            network=network,
            priority=priority,
            direction=direction,
            description=description
        )

        if direction == FirewallDirection.EGRESS:
            firewall_resource.destination_ranges = ip_ranges
        else:
            firewall_resource.source_ranges = ip_ranges

        if source_tags and source_tags is not None:
            firewall_resource.source_tags = source_tags
        if target_tags and target_tags is not None:
            firewall_resource.target_tags = target_tags

        if action == FirewallRuleAction.ALLOW:
            firewall_resource.allowed = rules
        elif action == FirewallRuleAction.DENY:
            firewall_resource.denied = rules
        else:
            raise BadRequest(message=f'Unsupported rule action {action}. Must be of type FirewallRuleAction!')

        return firewall_resource

    def allowed_or_denied(
        self,
        action: FirewallRuleAction = FirewallRuleAction.ALLOW,
        i_p_protocol: IpProtocol = IpProtocol.TCP,
        ports_str: str = None
    ) -> Allowed | Denied:
        """Generates the Allow or Denied firewall rule for the input
        I_P_protocol and comma delimited ports string.

        Args:
            action  (FirewallRuleAction): Either ALLOW or DENY
            i_p_protocol (IpProtocol): Protocol to use for rule
            ports_str Optional(str): Optional, comma delimited string of
                ports to ALLOW or DENY

        Returns:
            Allowed(...) or Denied(...)
        """
        split_ports = None
        if ports_str != 'any':
            split_ports = ports_str.split(',')

        if action == FirewallRuleAction.ALLOW:
            method = self.allowed
        else:
            method = self.denied

        if split_ports:
            return method(i_p_protocol, split_ports)
        else:
            return method(i_p_protocol)

    @staticmethod
    def allowed(
        i_p_protocol: IpProtocol = IpProtocol.TCP,
        ports: List[str] = None
    ) -> Allowed:
        allowed = Allowed(I_p_protocol=i_p_protocol)
        if ports:
            allowed.ports = ports
        return allowed

    @staticmethod
    def denied(
        i_p_protocol: IpProtocol = IpProtocol.TCP,
        ports: List[str] = None
    ) -> Denied:
        denied = Denied(I_p_protocol=i_p_protocol)
        if ports:
            denied.ports = ports
        return denied
