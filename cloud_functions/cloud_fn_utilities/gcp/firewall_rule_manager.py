import time
from typing import List

from common.exceptions import Conflict, NotFound
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

            rule_action = self._rule_action(rule.action, target_tags)

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
                created = self.firewalls_client.create(
                   resource_name=firewall_rule_name,
                   firewall_resource=firewall_body
                )
                if not created:
                    raise ConnectionError(
                        f'Timed out creating firewall rule {firewall_rule_name}'
                    )
            except Conflict as error:
                existing_rule = self.firewalls_client.get(
                    resource_name=firewall_rule_name
                )
                if not self._firewalls_match(existing_rule, firewall_body):
                    raise Conflict(
                        f'Existing firewall rule {firewall_rule_name} does not match '
                        f'the requested configuration'
                    ) from error
                self.logger.info(
                    f"{self.class_name}:{firewall_rule_name} - Matching firewall rule already exists"
                )

    @staticmethod
    def _rule_action(action, target_tags: List[str]) -> FirewallRuleAction:
        """Resolve an explicit allow/deny action with legacy compatibility."""
        if isinstance(action, FirewallRuleAction):
            return action
        if action:
            try:
                return FirewallRuleAction[str(action).upper()]
            except KeyError as exc:
                raise ValueError(f"Unsupported firewall action '{action}'") from exc
        if target_tags and 'deny-outbound' in target_tags:
            return FirewallRuleAction.DENY
        return FirewallRuleAction.ALLOW

    def delete(
        self,
        build_id: str
    ) -> bool:
        self.logger.info(f"{self.class_name}:{build_id} - Deleting firewall for Workout")
        try:
            for fw_rule in self._list_build_firewalls(build_id):
                try:
                    deleted = self.firewalls_client.delete(resource_name=fw_rule.name, wait=True)
                    if not deleted:
                        raise ConnectionError(
                            f'Timed out deleting firewall rule {fw_rule.name}'
                        )
                except NotFound:
                    self.logger.info(
                        f"{self.class_name}:{fw_rule.name} - Firewall rule already deleted"
                    )

            self._wait_for_deletion(build_id)
            return True
        except Exception as error:
            self.logger.info(f"{self.class_name}:{build_id} - Error in deleting firewall rules for Workout")
            self.logger.error(str(error))
            return False

    def _wait_for_deletion(
        self,
        build_id: str
    ) -> None:
        i = 0
        success = False
        while not success and i < 10:
            list_response = self._list_build_firewalls(build_id)
            if not list_response:
                success = True
            else:
                i += 1
                time.sleep(10)

        if not success:
            self.logger.error(f'{self.class_name}:{build_id} - Timeout in deleting firewall rules')
            raise ConnectionError

    def _list_build_firewalls(self, build_id: str) -> list:
        """List rules owned by a build without relying on GCE wildcard filters."""
        prefix = f'{build_id}-'
        return [
            rule
            for rule in self.firewalls_client.list()
            if getattr(rule, 'name', '').startswith(prefix)
        ]

    @classmethod
    def _firewalls_match(cls, existing, desired) -> bool:
        """Compare the functional fields controlled by an Agoge firewall rule."""
        scalar_fields = ('direction', 'priority', 'disabled')
        list_fields = (
            'source_ranges',
            'destination_ranges',
            'source_tags',
            'target_tags',
            'source_service_accounts',
            'target_service_accounts',
        )
        return (
            cls._resource_path(cls._field(existing, 'network'))
            == cls._resource_path(cls._field(desired, 'network'))
            and all(
                cls._field(existing, field) == cls._field(desired, field)
                for field in scalar_fields
            )
            and all(
                sorted(cls._field(existing, field, []) or [])
                == sorted(cls._field(desired, field, []) or [])
                for field in list_fields
            )
            and cls._normalized_rules(cls._field(existing, 'allowed', []) or [])
            == cls._normalized_rules(cls._field(desired, 'allowed', []) or [])
            and cls._normalized_rules(cls._field(existing, 'denied', []) or [])
            == cls._normalized_rules(cls._field(desired, 'denied', []) or [])
        )

    @classmethod
    def _normalized_rules(cls, rules) -> list[tuple[str, tuple[str, ...]]]:
        return sorted(
            (
                str(cls._field(rule, 'I_p_protocol', '')),
                tuple(sorted(cls._field(rule, 'ports', []) or [])),
            )
            for rule in rules
        )

    @staticmethod
    def _field(resource, name: str, default=None):
        if isinstance(resource, dict):
            return resource.get(name, default)
        return getattr(resource, name, default)

    @staticmethod
    def _resource_path(resource_url: str | None) -> str:
        value = str(resource_url or '')
        marker = '/compute/v1/'
        return value.split(marker, 1)[-1].lstrip('/')
