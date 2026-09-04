import ipaddress
import copy
import json
from pathlib import Path
import unittest

from pydantic import ValidationError

from common.models.agoge import RouteModel, UnitModel
from api.utilities.infrastructure_as_code.object_validators.unit import UnitValidator


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_SPEC = REPOSITORY_ROOT / "docs" / "examples" / "community-wireguard.json"


class CommunityWireGuardSpecTest(unittest.TestCase):
    """Keep the documented WireGuard topology aligned with the shared schema."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.raw_spec = json.loads(EXAMPLE_SPEC.read_text(encoding="utf-8"))
        cls.unit = UnitModel.model_validate(cls.raw_spec)
        cls.servers = {server.name: server for server in cls.unit.servers or []}

    def test_example_parses_without_dropping_wireguard_fields(self) -> None:
        self.assertEqual(self.unit.unit_type, "community")
        self.assertEqual(len(self.unit.routes or []), 1)

        gateway = self.servers["wireguard"]
        self.assertTrue(gateway.community_server)
        self.assertTrue(gateway.wireguard_gateway)
        self.assertTrue(gateway.can_ip_forward)
        self.assertTrue(gateway.nics[0].external_nat)
        self.assertIsNone(gateway.nics[0].external_ip_name)

        route = self.unit.routes[0]
        self.assertEqual(route.dest_range, "172.30.0.0/24")
        self.assertEqual(route.next_hop_instance, "wireguard")

    def test_example_passes_project_aware_public_listener_validation(self) -> None:
        validated = UnitValidator(wireguard_port=51820).load(copy.deepcopy(self.raw_spec))

        self.assertEqual(validated["version"], "1.1")

    def test_gateway_is_shared_but_kali_is_per_student(self) -> None:
        gateway = self.servers["wireguard"]
        kali = self.servers["kali"]

        self.assertTrue(gateway.community_server)
        self.assertFalse(kali.community_server)
        self.assertEqual(gateway.nics[0].network, kali.nics[0].network)
        self.assertIsNone(kali.nics[0].internal_ip)

    def test_fixed_gateway_address_is_reserved_and_in_the_subnet(self) -> None:
        network = self.unit.networks[0]
        subnet = ipaddress.ip_network(network.subnets[0].ip_subnet)
        gateway_address = ipaddress.ip_address(
            self.servers["wireguard"].nics[0].internal_ip
        )

        self.assertIn(gateway_address, subnet)
        self.assertIn(str(gateway_address), network.reservations)

    def test_remote_route_targets_gateway_and_only_tagged_clients(self) -> None:
        route = self.unit.routes[0]
        gateway = self.servers[route.next_hop_instance]
        kali_tags = set(self.servers["kali"].tags or [])

        self.assertTrue(gateway.wireguard_gateway)
        self.assertTrue(set(route.tags or []).issubset(kali_tags))

        vpc_subnet = ipaddress.ip_network(self.unit.networks[0].subnets[0].ip_subnet)
        remote_subnet = ipaddress.ip_network(route.dest_range)
        self.assertFalse(vpc_subnet.overlaps(remote_subnet))

    def test_route_rejects_a_destination_with_host_bits(self) -> None:
        invalid_route = self.raw_spec["routes"][0] | {"dest_range": "172.30.0.1/24"}

        with self.assertRaisesRegex(ValidationError, "valid CIDR network"):
            RouteModel.model_validate(invalid_route)

    def test_listener_firewall_rule_targets_only_the_gateway(self) -> None:
        rule = next(
            rule
            for rule in self.unit.firewall_rules or []
            if rule.name == "allow-wireguard-ingress"
        )
        gateway_tags = set(self.servers["wireguard"].tags or [])

        self.assertEqual(rule.ports, ["udp/51820"])
        self.assertTrue(set(rule.target_tags or []).issubset(gateway_tags))

    def test_remote_peer_firewall_rule_targets_kali_clients(self) -> None:
        rule = next(
            rule
            for rule in self.unit.firewall_rules or []
            if rule.name == "allow-wireguard-remote-to-kali"
        )
        route = self.unit.routes[0]
        kali_tags = set(self.servers["kali"].tags or [])

        self.assertEqual(rule.ip_ranges, [route.dest_range])
        self.assertEqual(rule.ports, ["tcp/any", "udp/any", "icmp/any"])
        self.assertTrue(set(rule.target_tags or []).issubset(kali_tags))

    def test_runtime_endpoint_is_not_baked_into_catalog_spec(self) -> None:
        self.assertNotIn("wireguard_endpoint", self.raw_spec)
        gateway = next(
            server for server in self.raw_spec["servers"] if server["name"] == "wireguard"
        )
        self.assertNotIn("external_ip_name", gateway["nics"][0])


if __name__ == "__main__":
    unittest.main()
