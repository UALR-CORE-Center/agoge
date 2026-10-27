"""Gateway publication relies on cloud lifecycle, never guest health reports."""
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from cloud_fn_utilities.course_objects.compute import lab_server_manager as server_module
from cloud_fn_utilities.course_objects.unit import community_unit as unit_module
from common.models.wireguard_provisioning import WireGuardLeaseModel


def lease(**changes):
    return WireGuardLeaseModel(**{
        'unit_id': 'abcdefghij', 'kit_id': 'remote-lab-01', 'device_id': 'device-01',
        'endpoint_id': '10000', 'equipment_subnet': '192.168.50.0/24',
        'student_subnets': ['10.20.0.0/24'], 'gateway_public_key': 'public-gateway-key',
        'peer_public_key': 'public-peer-key', 'secret_version_name': 'private-secret-reference',
        'boot_id': 'private-boot-nonce', 'expires': 2000.0,
        **changes,
    })


@pytest.fixture
def publication(monkeypatch):
    monkeypatch.setattr(server_module.time, 'time', lambda: 1000)
    unit = SimpleNamespace(
        wireguard_endpoint=SimpleNamespace(id='10000', port=51820),
        servers=[SimpleNamespace(
            wireguard_gateway=True, wireguard_managed=True, tags=['wireguard-gateway'],
            nics=[SimpleNamespace(network='external', external_nat=True)])],
        firewall_rules=[SimpleNamespace(
            network='external', action='allow', direction='INGRESS', priority=1000,
            target_tags=['wireguard-gateway'], ports=['udp/51820'], ip_ranges=['0.0.0.0/0'])])
    server = object.__new__(server_module.LabServerManager)
    server.parent_build_id = 'abcdefghij'
    server.server_spec = SimpleNamespace(wireguard_managed=True, wireguard_endpoint_id='10000')
    server.primary_external_ip = '203.0.113.10'
    server.wireguard_registry = Mock()
    server.wireguard_registry.require_provisionable.return_value = unit.wireguard_endpoint
    server.db = Mock()
    server.db.get.return_value = unit
    service = Mock()
    server._wireguard_provisioning = Mock(return_value=service)
    community = object.__new__(unit_module.CommunityUnit)
    community.unit_id, community.unit_model = 'abcdefghij', unit
    community.env_dict, community.db = {'project': 'tenant-project'}, server.db
    return server, community, service


@pytest.mark.parametrize('telemetry', [
    {},
    {'health_timestamp': 500, 'service_ready': True},
    {'health_timestamp': 999, 'health_error': 'bootstrap_failed'},
])
def test_publication_accepts_absent_stale_or_unhealthy_telemetry(publication, telemetry):
    server, community, service = publication
    current = lease(**telemetry)
    assert not current.is_ready(1000)
    assert current.tunnel_ready is False and current.latest_handshake == 0
    service.get_lease.return_value = current

    server._activate_wireguard_endpoint()
    with patch('common.services.wireguard_provisioning.WireGuardProvisioningService', return_value=service), \
         patch.object(unit_module, 'WireGuardEndpointRegistry') as registry:
        community._activate_wireguard_endpoint()

    server.wireguard_registry.activate.assert_called_once_with(
        '10000', unit_id='abcdefghij', public_ip='203.0.113.10')
    registry.return_value.activate.assert_called_once_with('10000', unit_id='abcdefghij')
    service.report_health.assert_not_called()


@pytest.mark.parametrize('change', [
    {'status': 'released'}, {'expires': 999}, {'expires': float('nan')}, {'expires': float('inf')},
    {'unit_id': 'other-unit'}, {'endpoint_id': '10001'},
])
def test_publication_retains_current_lease_and_owner_guards(publication, change):
    server, community, service = publication
    service.get_lease.return_value = lease(**change)

    with pytest.raises(server_module.BadRequest, match='lease is expired, released, or no longer owns'):
        server._activate_wireguard_endpoint()
    with patch('common.services.wireguard_provisioning.WireGuardProvisioningService', return_value=service), \
         patch.object(unit_module, 'WireGuardEndpointRegistry') as registry:
        with pytest.raises(ValueError, match='lease is expired, released, or no longer owns'):
            community._activate_wireguard_endpoint()

    server.wireguard_registry.activate.assert_not_called()
    registry.assert_not_called()


def test_bootstrap_rejects_wrong_lease_owner_before_identity_or_vm_mutation(publication):
    server, _, service = publication
    service.get_lease.return_value = lease(unit_id='other-unit')

    with patch.object(server_module, 'WireGuardGatewayIdentity') as identity:
        with pytest.raises(server_module.BadRequest):
            server._prepare_wireguard_bootstrap()

    identity.assert_not_called()
    service.grant_gateway_access.assert_not_called()
