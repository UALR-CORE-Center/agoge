from common.utilities.wireguard_firewall import DEFAULT_WIREGUARD_PORT

from .networks import NetworksValidator
from .routes import RoutesValidator
from .servers import ServersValidator
from .firewall_rules import FirewallRulesValidator
from .assessment import AssessmentValidator


class UnitValidator:
    """
    Object validators perform higher-level validation than serializers. They look for common errors in configuration
    files and automatically fix them if possible. Otherwise, the validator throws an error with a message to let the
    user know the configuration needs to be fixed.
    """
    def __init__(self, wireguard_port: int = DEFAULT_WIREGUARD_PORT):
        self.config = None
        self.firewalls = None
        self.wireguard_port = wireguard_port

    def load(
        self,
        config: dict
    ) -> dict:
        self.config = config
        self.firewalls = self.config.get('firewalls', False)
        if config.get('servers'):
            self._validate_network()
            self._validate_servers()
            self._validate_routes()
            self._validate_firewall_rules()
        if config.get('assessment'):
            self._validate_assessment()
        return self.config

    def _validate_network(self) -> None:
        networks = NetworksValidator(self.config).load()
        self.config.update(networks)

    def _validate_servers(self) -> None:
        servers = ServersValidator(self.config).load()
        self.config.update(servers)

    def _validate_routes(self) -> None:
        routes = RoutesValidator(self.config).load()
        self.config.update(routes)

    def _validate_firewall_rules(self) -> None:
        firewall_rules = FirewallRulesValidator(
            self.config,
            wireguard_port=self.wireguard_port,
        ).load()
        self.config.update(firewall_rules)

    def _validate_assessment(self) -> None:
        assessment = AssessmentValidator(self.config).load()
        self.config.update(assessment)
