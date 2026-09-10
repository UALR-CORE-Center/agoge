import pytest

from common.exceptions import AgogeValidationError
from api.utilities.infrastructure_as_code.object_validators.routes import RoutesValidator
from api.utilities.infrastructure_as_code.object_validators.servers import ServersValidator
from api.utilities.infrastructure_as_code.object_validators.firewall_rules import FirewallRulesValidator


def _networks():
    return [
        {
            'name': 'external',
            'subnets': [{'name': 'default', 'ip_subnet': '10.20.0.0/24'}],
        },
        {
            'name': 'management',
            'subnets': [{'name': 'default', 'ip_subnet': '10.21.0.0/24'}],
        },
    ]


def _route_config():
    return {
        'unit_type': 'community',
        'networks': _networks(),
        'servers': [
            {
                'name': 'router',
                'community_server': True,
                'can_ip_forward': True,
                'nics': [
                    {
                        'network': 'external',
                        'subnet_name': 'default',
                        'internal_ip': '10.20.0.2',
                    }
                ],
            }
        ],
        'routes': [
            {
                'name': 'remote-network',
                'network': 'external',
                'dest_range': '172.30.0.0/24',
                'next_hop_instance': 'router',
            }
        ],
    }


def _wireguard_config(listener_port='udp/51820'):
    config = _route_config()
    gateway = config['servers'][0]
    gateway.update({
        'name': 'wireguard',
        'wireguard_gateway': True,
        'external_nat': True,
        'tags': ['wireguard-gateway'],
    })
    gateway['nics'][0]['external_nat'] = True
    config['routes'][0]['next_hop_instance'] = 'wireguard'
    config['firewall_rules'] = [
        {
            'name': 'allow-wireguard-ingress',
            'network': 'external',
            'action': 'allow',
            'direction': 'INGRESS',
            'priority': 1000,
            'target_tags': ['wireguard-gateway'],
            'ports': [listener_port],
            'ip_ranges': ['0.0.0.0/0'],
        }
    ]
    return config


def test_dynamic_community_nic_still_validates_direct_connect():
    config = {
        'unit_type': 'community',
        'network_map': {'external': '10.20.0.0/24'},
        'networks': [_networks()[0]],
        'servers': [
            {
                'name': 'kali',
                'community_server': False,
                'nics': [
                    {
                        'network': 'external',
                        'subnet_name': 'default',
                        'internal_ip': None,
                        'direct_connect': True,
                        'external_nat': False,
                    }
                ],
            }
        ],
    }

    with pytest.raises(AgogeValidationError, match='direct_connect'):
        ServersValidator(config).load()


def test_gcp_reserved_addresses_are_relative_to_the_actual_cidr():
    config = {
        'unit_type': 'community',
        'network_map': {'external': '10.20.0.0/23'},
        'networks': [
            {
                'name': 'external',
                'subnets': [{'name': 'default', 'ip_subnet': '10.20.0.0/23'}],
            }
        ],
        'servers': [
            {
                'name': 'router',
                'community_server': True,
                'nics': [
                    {
                        'network': 'external',
                        'subnet_name': 'default',
                        # This is valid in a /23; it is not the subnet's penultimate address.
                        'internal_ip': '10.20.0.254',
                    }
                ],
            }
        ],
    }

    assert ServersValidator(config).load() is config

    config['servers'][0]['nics'][0]['internal_ip'] = '10.20.0.1'
    with pytest.raises(AgogeValidationError, match='reserved IP address'):
        ServersValidator(config).load()


def test_valid_remote_route_passes_hardened_validation():
    config = _route_config()

    assert RoutesValidator(config).load() is config


@pytest.mark.parametrize(
    ('mutation', 'error'),
    [
        ({'dest_range': '2001:db8::/64'}, 'must be IPv4'),
        ({'dest_range': '10.20.0.0/25'}, 'overlaps local lab subnet'),
    ],
)
def test_route_rejects_invalid_destination_networks(mutation, error):
    config = _route_config()
    config['routes'][0].update(mutation)

    with pytest.raises(AgogeValidationError, match=error):
        RoutesValidator(config).load()


def test_route_next_hop_requires_a_nic_on_the_route_network():
    config = _route_config()
    config['servers'][0]['nics'][0]['network'] = 'management'

    with pytest.raises(AgogeValidationError, match='no NIC on network external'):
        RoutesValidator(config).load()


def test_community_route_next_hop_must_be_shared():
    config = _route_config()
    config['servers'][0]['community_server'] = False

    with pytest.raises(AgogeValidationError, match='must be a community_server'):
        RoutesValidator(config).load()


def test_server_attached_routes_are_validated_and_require_the_owner_as_next_hop():
    config = _route_config()
    route = config.pop('routes')[0]
    config['servers'][0]['routes'] = [route]

    assert RoutesValidator(config).load() is config

    config['servers'].append({
        'name': 'other-router',
        'community_server': True,
        'can_ip_forward': True,
        'nics': [{'network': 'external', 'subnet_name': 'default'}],
    })
    config['servers'][0]['routes'][0]['next_hop_instance'] = 'other-router'
    with pytest.raises(AgogeValidationError, match='must be its next hop'):
        RoutesValidator(config).load()


def test_duplicate_route_names_across_unit_and_server_are_rejected():
    config = _route_config()
    config['servers'][0]['routes'] = [dict(config['routes'][0])]

    with pytest.raises(AgogeValidationError, match='duplicate static route name'):
        RoutesValidator(config).load()


def test_logical_names_leave_room_for_build_id_prefix():
    route_config = _route_config()
    route_config['routes'][0]['name'] = 'r' * 53
    with pytest.raises(AgogeValidationError, match='no longer than 52 characters'):
        RoutesValidator(route_config).load()

    server_config = {
        'unit_type': 'community',
        'network_map': {'external': '10.20.0.0/24'},
        'networks': [_networks()[0]],
        'servers': [
            {
                'name': 's' * 53,
                'community_server': True,
                'nics': [
                    {
                        'network': 'external',
                        'subnet_name': 'default',
                        'internal_ip': '10.20.0.2',
                    }
                ],
            }
        ],
    }
    with pytest.raises(AgogeValidationError, match='52-character limit'):
        ServersValidator(server_config).load()


@pytest.mark.parametrize('invalid_name', ['UPPER', 'bad_name', 'ends-', 'a' * 64])
def test_server_rejects_invalid_external_address_names(invalid_name):
    config = _route_config()
    config['servers'][0]['nics'][0]['external_ip_name'] = invalid_name

    with pytest.raises(AgogeValidationError, match='external_ip_name'):
        ServersValidator(config).load()


@pytest.mark.parametrize('invalid_tag', ['UPPER', 'bad_tag', 'ends-', 'a' * 64])
def test_gce_network_tags_are_validated_across_resources(invalid_tag):
    server_config = _route_config()
    server_config['servers'][0]['tags'] = [invalid_tag]
    with pytest.raises(AgogeValidationError, match='network tag'):
        ServersValidator(server_config).load()

    route_config = _route_config()
    route_config['routes'][0]['tags'] = [invalid_tag]
    with pytest.raises(AgogeValidationError, match='network tag'):
        RoutesValidator(route_config).load()


def test_firewall_rule_names_leave_room_for_unit_prefix_and_tags_are_validated():
    config = _route_config()
    config['firewall_rules'] = [{
        'name': 'f' * 53,
        'network': 'external',
        'target_tags': [],
    }]
    with pytest.raises(AgogeValidationError, match='no longer than 52 characters'):
        FirewallRulesValidator(config).load()

    config['firewall_rules'][0] = {
        'name': 'allow-wireguard',
        'network': 'external',
        'target_tags': ['bad_tag'],
    }
    with pytest.raises(AgogeValidationError, match='invalid target tag'):
        FirewallRulesValidator(config).load()


def test_wireguard_listener_must_be_explicit_and_public():
    config = _wireguard_config()
    config['firewall_rules'] = []

    # The generated allow-all-local rule includes udp/any, but its RFC1918
    # source range cannot make a public endpoint reachable.
    with pytest.raises(AgogeValidationError, match='public UDP port 51820'):
        FirewallRulesValidator(config).load()


@pytest.mark.parametrize(
    ('mutation', 'wireguard_port'),
    [
        ({'ports': ['udp/51820']}, 41194),
        ({'target_tags': ['student-only']}, 51820),
        ({'ip_ranges': ['10.20.0.0/24']}, 51820),
        ({'direction': 'EGRESS'}, 51820),
        ({'action': 'deny'}, 51820),
        ({'priority': 65535}, 51820),
    ],
)
def test_wireguard_listener_rejects_rules_that_do_not_reach_the_gateway(
    mutation,
    wireguard_port,
):
    config = _wireguard_config()
    config['firewall_rules'][0].update(mutation)

    with pytest.raises(AgogeValidationError, match=f'public UDP port {wireguard_port}'):
        FirewallRulesValidator(config, wireguard_port=wireguard_port).load()


def test_wireguard_listener_accepts_the_project_port_in_a_udp_range():
    config = _wireguard_config(listener_port='udp/41000-42000')

    assert FirewallRulesValidator(config, wireguard_port=41194).load() is config


def test_partial_editor_validation_can_defer_wireguard_listener_requirement():
    config = _wireguard_config()
    config['firewall_rules'] = []

    assert FirewallRulesValidator(
        config,
        require_wireguard_listener=False,
    ).load() is config
