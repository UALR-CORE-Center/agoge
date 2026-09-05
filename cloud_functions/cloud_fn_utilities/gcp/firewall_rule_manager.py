import time
from typing import List

from common.exceptions import Conflict
from common.utilities.gcp.compute.compute_firewall import ComputeFirewallsAPI
from common.constants.google import FirewallDirection, FirewallRuleAction
from common.models.agoge import FirewallRuleModel
from common.utilities.gcp.cloud_env import CloudEnv
from common.utilities.gcp.cloud_logger import Logger, LoggerNames
from common.utilities.gcp.compute.resources.firewall_resource import FirewallResource
from common.utilities.gcp.compute.resources.network_interface_resource import NetworkInterfaceResource


class FirewallManager:
    def __init__(self, env_dict=None):
        self.class_name = self.__class__.__name__
        self.env = CloudEnv(env_dict=env_dict) if env_dict else CloudEnv()
        self.firewalls_client = ComputeFirewallsAPI(
            project=self.env.project,
            region=self.env.region,
            zone=self.env.zone
        )
        self.firewall_resource = FirewallResource()
        self.logger = Logger(log_name=LoggerNames.CLOUD_FN, class_name=self.class_name)

    def build(
        self,
        build_id: str,
        firewall_spec: List[FirewallRuleModel]
    ) -> None:
        for rule in firewall_spec:
            firewall_rule_name = f'{build_id}-{rule.name}'
            target_tags = rule.target_tags
            rule_direction = rule.direction
            if rule_direction is None:
                rule_direction = FirewallDirection.INGRESS

            rule_action = FirewallRuleAction.ALLOW
            if target_tags and target_tags is not None:
                if 'deny-outbound' in target_tags:
                    rule_action = FirewallRuleAction.DENY

            rules = []
            for ports_str in rule.ports:
                protocol, ports = ports_str.split('/')
                new_rule = self.firewall_resource.allowed_or_denied(rule_action, protocol, ports)
                rules.append(new_rule)

            firewall_body = self.firewall_resource.new(
                name=firewall_rule_name,
                network=NetworkInterfaceResource.network_path(f'{build_id}-{rule.network}', self.env.project),
                direction=rule_direction,
                ip_ranges=rule.ip_ranges,
                action=rule_action,
                rules=rules,
                priority=rule.priority,
                target_tags=target_tags,
            )

            try:
                self.firewalls_client.create(
                   resource_name=firewall_rule_name,
                   firewall_resource=firewall_body
                )
            except Conflict:
                # Rebuilds must reconcile rules created by older versions of
                # Agoge. In particular, legacy rules omitted target tags and
                # could expose the wrong VMs or fail to target Guacamole.
                self.firewalls_client.patch(
                    resource_name=firewall_rule_name,
                    firewall_body=firewall_body,
                )

    def delete(
        self,
        build_id: str
    ) -> bool:
        self.logger.info(f"{self.class_name}:{build_id} - Deleting firewall for Workout")
        try:
            list_response = self.firewalls_client.list(filter_='name = {}*'.format(build_id))
            for fw_rule in list_response:
                self.firewalls_client.delete(resource_name=fw_rule.name, wait=False)

            self._wait_for_deletion(build_id)
            return True
        except ():
            self.logger.info(f"{self.class_name}:{build_id} - Error in deleting firewall rules for Workout")
            return False

    def _wait_for_deletion(
        self,
        build_id: str
    ) -> None:
        i = 0
        success = False
        while not success and i < 10:
            list_response = self.firewalls_client.list(filter_='name = {}*'.format(build_id))
            if not list_response:
                success = True
            else:
                i += 1
                time.sleep(10)

        if not success:
            self.logger.error(f'{self.class_name}:{build_id} - Timeout in deleting firewall rules')
            raise ConnectionError
