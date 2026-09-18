from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

import pytest

from cloud_fn_utilities.gcp import dns_manager as dns_module
from cloud_fn_utilities.gcp.address_manager import AddressManager
from cloud_fn_utilities.gcp.firewall_rule_manager import FirewallManager
from cloud_fn_utilities.gcp.route_manager import RouteManager
from cloud_fn_utilities.gcp.vpc_manager import VpcManager
from common.constants.google import FirewallRuleAction, OperationType
from common.exceptions import Conflict, NotFound
from common.models.agoge import FirewallRuleModel
from common.utilities.gcp.compute.compute_routes import ComputeRoutesAPI
from common.utilities.gcp.compute.resources.firewall_resource import FirewallResource
from common.utilities.gcp.compute.resources.routes_resource import RoutesResource


def test_route_resource_includes_network_and_selection_tags():
    resource = RoutesResource(project='test-project', zone='us-central1-a').new(
        name='unit-remote-lan',
        network='projects/test-project/global/networks/unit-external',
        dest_range='172.30.0.0/24',
        next_hop_instance=(
            'projects/test-project/zones/us-central1-a/instances/unit-wireguard'
        ),
        priority=900,
        tags=['student-kali'],
    )

    assert resource.network == 'projects/test-project/global/networks/unit-external'
    assert resource.dest_range == '172.30.0.0/24'
    assert resource.priority == 900
    assert list(resource.tags) == ['student-kali']


def test_route_manager_prefixes_resources_and_waits_for_creation():
    manager = RouteManager.__new__(RouteManager)
    manager.build_id = 'unit-123'
    manager.routes_resource = RoutesResource(project='test-project', zone='us-central1-a')
    manager.routes_client = MagicMock()
    manager.logger = MagicMock()
    manager.class_name = 'RouteManager'

    manager.build([{
        'name': 'remote-lan',
        'network': 'external',
        'dest_range': '172.30.0.0/24',
        'next_hop_instance': 'wireguard',
        'priority': 800,
        'tags': ['student-kali'],
    }])

    create_call = manager.routes_client.create.call_args
    assert create_call.kwargs['resource_name'] == 'unit-123-remote-lan'
    assert create_call.kwargs['wait'] is True
    route = create_call.kwargs['route_resource']
    assert route.network.endswith('/unit-123-external')
    assert route.next_hop_instance.endswith('/unit-123-wireguard')


def test_route_manager_rejects_unconfirmed_create_and_delete_operations():
    manager = RouteManager.__new__(RouteManager)
    manager.build_id = 'unit-123'
    manager.routes_resource = RoutesResource(project='test-project', zone='us-central1-a')
    manager.routes_client = MagicMock()
    manager.routes_client.create.return_value = False
    manager.routes_client.delete.return_value = False
    manager.logger = MagicMock()
    manager.class_name = 'RouteManager'
    route = {
        'name': 'remote-lan',
        'network': 'external',
        'dest_range': '172.30.0.0/24',
        'next_hop_instance': 'wireguard',
    }

    with pytest.raises(ConnectionError, match='creating route'):
        manager.build([route])
    with pytest.raises(ConnectionError, match='deleting route'):
        manager.delete([route])


def test_route_manager_accepts_a_matching_existing_route_after_conflict():
    manager = RouteManager.__new__(RouteManager)
    manager.build_id = 'unit-123'
    manager.routes_resource = RoutesResource(project='test-project', zone='us-central1-a')
    manager.routes_client = MagicMock()
    manager.routes_client.create.side_effect = Conflict('already exists')
    manager.routes_client.get.return_value = manager.routes_resource.new(
        name='unit-123-remote-lan',
        network=(
            'https://www.googleapis.com/compute/v1/projects/test-project/global/'
            'networks/unit-123-external'
        ),
        dest_range='172.30.0.0/24',
        next_hop_instance=(
            'https://www.googleapis.com/compute/v1/projects/test-project/zones/'
            'us-central1-a/instances/unit-123-wireguard'
        ),
        priority=1000,
        tags=['student-kali'],
        description=(
            'Agoge projects/test-project/global/networks/unit-123-external network '
            'route, unit-123-remote-lan'
        ),
    )
    manager.logger = MagicMock()
    manager.class_name = 'RouteManager'

    manager.build([{
        'name': 'remote-lan',
        'network': 'external',
        'dest_range': '172.30.0.0/24',
        'next_hop_instance': 'wireguard',
        'tags': ['student-kali'],
    }])

    manager.routes_client.get.assert_called_once_with(resource='unit-123-remote-lan')


def test_route_manager_rejects_a_mismatched_existing_route_after_conflict():
    manager = RouteManager.__new__(RouteManager)
    manager.build_id = 'unit-123'
    manager.routes_resource = RoutesResource(project='test-project', zone='us-central1-a')
    manager.routes_client = MagicMock()
    manager.routes_client.create.side_effect = Conflict('already exists')
    manager.routes_client.get.return_value = manager.routes_resource.new(
        name='unit-123-remote-lan',
        network='projects/test-project/global/networks/unit-123-external',
        dest_range='172.31.0.0/24',
        next_hop_instance=(
            'projects/test-project/zones/us-central1-a/instances/unit-123-wireguard'
        ),
    )
    manager.logger = MagicMock()
    manager.class_name = 'RouteManager'

    with pytest.raises(Conflict, match='does not match'):
        manager.build([{
            'name': 'remote-lan',
            'network': 'external',
            'dest_range': '172.30.0.0/24',
            'next_hop_instance': 'wireguard',
        }])


def test_address_manager_reuses_or_reserves_an_address():
    manager = AddressManager.__new__(AddressManager)
    manager.addresses_client = MagicMock()
    manager.logger = MagicMock()
    manager.class_name = 'AddressManager'
    manager.addresses_client.get.side_effect = [
        NotFound(),
        SimpleNamespace(address='203.0.113.10'),
    ]

    address = manager.reserve('unit-123-wireguard-ip')

    assert address == '203.0.113.10'
    manager.addresses_client.create.assert_called_once()


def test_address_manager_rejects_an_unconfirmed_release():
    manager = AddressManager.__new__(AddressManager)
    manager.addresses_client = MagicMock()
    manager.addresses_client.delete.return_value = False
    manager.logger = MagicMock()
    manager.class_name = 'AddressManager'

    with pytest.raises(ConnectionError, match='external address'):
        manager.release('unit-123-wireguard-ip')


def test_explicit_firewall_action_takes_precedence_over_legacy_tag():
    assert FirewallManager._rule_action(
        'allow', ['deny-outbound']
    ) == FirewallRuleAction.ALLOW
    assert FirewallManager._rule_action('deny', []) == FirewallRuleAction.DENY


def test_firewall_manager_rejects_an_unconfirmed_listener_rule():
    manager = FirewallManager.__new__(FirewallManager)
    manager.env = SimpleNamespace(project='test-project')
    manager.firewalls_client = MagicMock()
    manager.firewalls_client.create.return_value = False
    manager.firewall_resource = FirewallResource()
    manager.logger = MagicMock()
    manager.class_name = 'FirewallManager'
    rule = FirewallRuleModel(
        name='allow-wireguard-ingress',
        network='external',
        action='allow',
        target_tags=['wireguard-gateway'],
        ports=['udp/51820'],
        ip_ranges=['0.0.0.0/0'],
    )

    with pytest.raises(ConnectionError, match='firewall rule'):
        manager.build('unit-123', [rule])


def _wireguard_firewall_rule():
    return FirewallRuleModel(
        name='allow-wireguard-ingress',
        network='external',
        action='allow',
        target_tags=['wireguard-gateway'],
        ports=['udp/51820'],
        ip_ranges=['0.0.0.0/0'],
    )


def _matching_wireguard_firewall():
    resource = FirewallResource()
    return resource.new(
        name='unit-123-allow-wireguard-ingress',
        network=(
            'https://www.googleapis.com/compute/v1/projects/test-project/global/'
            'networks/unit-123-external'
        ),
        direction='INGRESS',
        ip_ranges=['0.0.0.0/0'],
        action=FirewallRuleAction.ALLOW,
        rules=[resource.allowed_or_denied(FirewallRuleAction.ALLOW, 'udp', '51820')],
        priority=1000,
        target_tags=['wireguard-gateway'],
    )


def test_firewall_manager_accepts_a_matching_existing_rule_after_conflict():
    manager = FirewallManager.__new__(FirewallManager)
    manager.env = SimpleNamespace(project='test-project')
    manager.firewalls_client = MagicMock()
    manager.firewalls_client.create.side_effect = Conflict('already exists')
    manager.firewalls_client.get.return_value = _matching_wireguard_firewall()
    manager.firewall_resource = FirewallResource()
    manager.logger = MagicMock()
    manager.class_name = 'FirewallManager'

    manager.build('unit-123', [_wireguard_firewall_rule()])

    manager.firewalls_client.get.assert_called_once_with(
        resource_name='unit-123-allow-wireguard-ingress'
    )


def test_firewall_manager_rejects_a_mismatched_existing_rule_after_conflict():
    manager = FirewallManager.__new__(FirewallManager)
    manager.env = SimpleNamespace(project='test-project')
    manager.firewalls_client = MagicMock()
    manager.firewalls_client.create.side_effect = Conflict('already exists')
    existing = _matching_wireguard_firewall()
    existing.target_tags = ['wrong-target']
    manager.firewalls_client.get.return_value = existing
    manager.firewall_resource = FirewallResource()
    manager.logger = MagicMock()
    manager.class_name = 'FirewallManager'

    with pytest.raises(Conflict, match='does not match'):
        manager.build('unit-123', [_wireguard_firewall_rule()])


def test_firewall_delete_selects_build_rules_in_python_and_confirms_each_delete():
    manager = FirewallManager.__new__(FirewallManager)
    manager.firewalls_client = MagicMock()
    manager.firewalls_client.list.side_effect = [
        [
            SimpleNamespace(name='unit-123-allow-wireguard'),
            SimpleNamespace(name='unit-1234-unrelated'),
        ],
        [],
    ]
    manager.firewalls_client.delete.return_value = True
    manager.logger = MagicMock()
    manager.class_name = 'FirewallManager'

    assert manager.delete('unit-123') is True

    assert manager.firewalls_client.list.call_args_list == [call(), call()]
    manager.firewalls_client.delete.assert_called_once_with(
        resource_name='unit-123-allow-wireguard',
        wait=True,
    )


def test_firewall_delete_returns_false_when_a_rule_delete_is_unconfirmed():
    manager = FirewallManager.__new__(FirewallManager)
    manager.firewalls_client = MagicMock()
    manager.firewalls_client.list.return_value = [
        SimpleNamespace(name='unit-123-allow-wireguard'),
    ]
    manager.firewalls_client.delete.return_value = False
    manager.logger = MagicMock()
    manager.class_name = 'FirewallManager'

    assert manager.delete('unit-123') is False


def test_route_bulk_delete_selects_build_routes_in_python_and_confirms_each_delete():
    manager = RouteManager.__new__(RouteManager)
    manager.build_id = 'unit-123'
    manager.routes_client = MagicMock()
    manager.routes_client.list.side_effect = [
        [
            SimpleNamespace(name='unit-123-remote-lan'),
            SimpleNamespace(name='unit-1234-unrelated'),
        ],
        [],
    ]
    manager.routes_client.delete.return_value = True
    manager.logger = MagicMock()
    manager.class_name = 'RouteManager'

    assert manager.delete() is True

    assert manager.routes_client.list.call_args_list == [call(), call()]
    manager.routes_client.delete.assert_called_once_with(
        resource_name='unit-123-remote-lan'
    )


def test_route_bulk_delete_propagates_an_unconfirmed_delete():
    manager = RouteManager.__new__(RouteManager)
    manager.build_id = 'unit-123'
    manager.routes_client = MagicMock()
    manager.routes_client.list.return_value = [
        SimpleNamespace(name='unit-123-remote-lan'),
    ]
    manager.routes_client.delete.return_value = False
    manager.logger = MagicMock()
    manager.class_name = 'RouteManager'

    with pytest.raises(ConnectionError, match='deleting route'):
        manager.delete()


def test_route_delete_with_an_explicit_empty_spec_does_not_bulk_delete():
    manager = RouteManager.__new__(RouteManager)
    manager.build_id = 'unit-123'
    manager.routes_client = MagicMock()
    manager.logger = MagicMock()
    manager.class_name = 'RouteManager'

    assert manager.delete([]) is True
    manager.routes_client.list.assert_not_called()
    manager.routes_client.delete.assert_not_called()


def _vpc_manager_for_delete():
    manager = VpcManager.__new__(VpcManager)
    manager.build_id = 'unit-123'
    manager.subnetworks_client = MagicMock()
    manager.networks_client = MagicMock()
    manager.logger = MagicMock()
    manager.class_name = 'VpcManager'
    network = SimpleNamespace(
        name='external',
        subnets=[SimpleNamespace(name='default')],
    )
    return manager, network


def test_vpc_delete_propagates_an_unconfirmed_subnet_delete():
    manager, network = _vpc_manager_for_delete()
    manager.subnetworks_client.delete.return_value = False

    with pytest.raises(ConnectionError, match='subnetwork'):
        manager.delete(network)

    manager.networks_client.delete.assert_not_called()


def test_vpc_delete_propagates_an_unconfirmed_network_delete():
    manager, network = _vpc_manager_for_delete()
    manager.subnetworks_client.delete.return_value = True
    manager.networks_client.delete.return_value = False

    with pytest.raises(ConnectionError, match='network unit-123-external'):
        manager.delete(network)


def test_compute_route_delete_passes_resource_only_to_request_wrapper():
    api = ComputeRoutesAPI.__new__(ComputeRoutesAPI)
    api.project = 'test-project'
    api.default_operation = OperationType.GLOBAL
    api.routes_client = MagicMock()
    api._make_request = MagicMock(return_value=True)

    assert api.delete('unit-123-remote-lan') is True

    request_call = api._make_request.call_args.kwargs
    assert request_call['resource'] == 'unit-123-remote-lan'
    assert 'resource_name' not in request_call
    assert request_call['request'].route == 'unit-123-remote-lan'


class _FakeHttpError(Exception):
    def __init__(self, status: int):
        super().__init__(f'HTTP {status}')
        self.resp = SimpleNamespace(status=status)
        self.error_details = f'HTTP {status}'


def _dns_manager():
    manager = dns_module.DnsManager.__new__(dns_module.DnsManager)
    manager.class_name = 'DnsManager'
    manager.env = SimpleNamespace(parent_project='dns-project', parent_zone='public-zone')
    manager.dns = MagicMock()
    manager.logger = MagicMock()
    manager.MAX_CHANGE_RETRIES = 3
    manager.CHANGE_RETRY_DELAY = 0
    return manager


def test_dns_upsert_treats_concurrent_same_record_as_success():
    manager = _dns_manager()
    first_list = MagicMock()
    first_list.execute.return_value = {'rrsets': []}
    second_list = MagicMock()
    second_list.execute.return_value = {
        'rrsets': [{
            'name': 'wg-12345.example.edu.',
            'type': 'A',
            'ttl': 30,
            'rrdatas': ['203.0.113.10'],
        }]
    }
    manager.dns.resourceRecordSets.return_value.list.side_effect = [first_list, second_list]
    change_request = MagicMock()
    change_request.execute.side_effect = _FakeHttpError(409)
    manager.dns.changes.return_value.create.return_value = change_request

    with patch.object(dns_module, 'HttpError', _FakeHttpError):
        result = manager.add_dns_record(
            'wg-12345.example.edu.',
            ip_address='203.0.113.10',
        )

    assert result is True
    assert manager.dns.resourceRecordSets.return_value.list.call_count == 2
    manager.dns.changes.return_value.create.assert_called_once()


def test_dns_upsert_returns_false_when_record_listing_fails():
    manager = _dns_manager()
    list_request = MagicMock()
    list_request.execute.side_effect = _FakeHttpError(500)
    manager.dns.resourceRecordSets.return_value.list.return_value = list_request

    with patch.object(dns_module, 'HttpError', _FakeHttpError):
        result = manager.add_dns_record(
            'wg-12345.example.edu.',
            ip_address='203.0.113.10',
        )

    assert result is False
    manager.dns.changes.return_value.create.assert_not_called()


def test_dns_delete_is_idempotent_when_record_is_already_absent():
    manager = _dns_manager()
    delete_request = MagicMock()
    delete_request.execute.side_effect = _FakeHttpError(404)
    manager.dns.resourceRecordSets.return_value.delete.return_value = delete_request

    with patch.object(dns_module, 'HttpError', _FakeHttpError):
        result = manager.delete_dns(record_name='wg-12345.example.edu.')

    assert result is True
