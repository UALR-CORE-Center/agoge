from types import SimpleNamespace
from unittest.mock import MagicMock

from api.core.workout_internet_firewall import WorkoutInternetFirewall
from cloud_fn_utilities.gcp.firewall_rule_manager import FirewallManager
from common.constants.google import AddressTypes
from common.exceptions import Conflict
from common.models.agoge import FirewallRuleModel
from common.utilities.gcp.compute.resources.firewall_resource import FirewallResource


def test_direct_connect_network_uses_workout_id_when_embedded_parent_is_stale():
    firewall = object.__new__(WorkoutInternetFirewall)
    firewall.class_name = "WorkoutInternetFirewall"
    firewall.workout_id = "workout-a"
    firewall.network_prefix = "workout-a"
    firewall.logger = MagicMock()
    firewall.workout = {
        "servers": [
            {
                "parent_id": None,
                "nics": [
                    {"network": "external", "direct_connect": True},
                    {"network": "internal", "direct_connect": False},
                ],
            }
        ]
    }

    assert firewall._find_direct_connect_networks() == ["workout-a-external"]


def test_direct_connect_network_uses_unit_prefix_for_community_workout():
    firewall = object.__new__(WorkoutInternetFirewall)
    firewall.class_name = "WorkoutInternetFirewall"
    firewall.workout_id = "workout-a"
    firewall.network_prefix = "unit-a"
    firewall.logger = MagicMock()
    firewall.workout = {
        "servers": [
            {
                "nics": [
                    {"network": "external", "direct_connect": True},
                ],
            }
        ]
    }

    assert firewall._find_direct_connect_networks() == ["unit-a-external"]


def test_direct_connect_rule_allows_rdp_only_for_the_workout_tag():
    firewall = object.__new__(WorkoutInternetFirewall)
    firewall.workout_id = "workout-a"
    firewall.env = SimpleNamespace(project="test-project")
    firewall.firewall_resource = FirewallResource()

    name, resource = firewall._direct_connect_rule(
        network="workout-a-external",
        address_types=AddressTypes.IPv4,
        ip_ranges=["203.0.113.10/32"],
    )

    assert name == "workout-a-workout-a-external-ipv4-allow-direct-connect"
    assert list(resource.target_tags) == ["workout-a-direct-connect"]
    assert "3389" in resource.allowed[0].ports
    assert list(resource.source_ranges) == ["203.0.113.10/32"]


def test_display_proxy_rule_allows_https_only_for_the_workout_entry_tag():
    firewall = object.__new__(WorkoutInternetFirewall)
    firewall.workout_id = "workout-a"
    firewall.env = SimpleNamespace(project="test-project")
    firewall.firewall_resource = FirewallResource()

    _, resource = firewall._display_proxy_rule(
        network="workout-a-external",
        ip_ranges=["0.0.0.0/0"],
    )

    assert list(resource.target_tags) == ["workout-a-student-entry"]
    assert "443" in resource.allowed[0].ports


def test_firewall_rebuild_targets_guacamole_and_patches_legacy_rule():
    manager = object.__new__(FirewallManager)
    manager.env = SimpleNamespace(project="test-project")
    manager.firewall_resource = FirewallResource()
    manager.firewalls_client = MagicMock()
    manager.firewalls_client.create.side_effect = Conflict()
    rule = FirewallRuleModel(
        name="allow-student-entry",
        network="external",
        target_tags=["student-entry"],
        ports=["tcp/80,443,8443,4822"],
        ip_ranges=["0.0.0.0/0"],
    )

    manager.build("workout-a", [rule])

    create_call = manager.firewalls_client.create.call_args
    resource = create_call.kwargs["firewall_resource"]
    assert list(resource.target_tags) == ["student-entry"]
    assert "443" in resource.allowed[0].ports
    manager.firewalls_client.patch.assert_called_once_with(
        resource_name="workout-a-allow-student-entry",
        firewall_body=resource,
    )
