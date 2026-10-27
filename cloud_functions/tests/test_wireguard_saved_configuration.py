"""Saved remote settings are applied only to an authorized stopped gateway."""
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from cloud_fn_utilities.server_specific import wireguard_configuration as configuration
from common.exceptions import BadRequest
from common.models.wireguard_provisioning import WireGuardLeaseModel
from cloud_functions.tests.test_managed_wireguard_bootstrap import manager, existing, UNIT, SECRET, EMAIL


def saved_lease(**changes):
    return WireGuardLeaseModel(**{
        'unit_id': UNIT, 'kit_id': 'kit-two', 'device_id': 'pi-two', 'endpoint_id': '10000',
        'equipment_subnet': '192.168.50.0/24', 'student_subnets': ['10.20.0.0/24'],
        'gateway_public_key': 'public-gateway', 'peer_public_key': 'public-peer',
        'secret_version_name': f'projects/tenant-project/secrets/agoge-wg-{UNIT}-cfg-revision/versions/1',
        'previous_secret_version_name': SECRET, 'configuration_revision': 'revision',
        'configuration_pending': True, 'expires': 10_000_000_000, **changes,
    })


def test_stopped_gateway_accepts_saved_secret_transition_and_updates_metadata_after_network():
    value = manager()
    value.compute_instance.get.return_value = existing(status='TERMINATED')
    lease = saved_lease()
    service = value._wireguard_provisioning.return_value
    service.get_lease.return_value = lease
    with patch('cloud_fn_utilities.server_specific.wireguard_configuration.apply_saved_wireguard_network') as apply, \
         patch('cloud_fn_utilities.course_objects.compute.lab_server_manager.WireGuardGatewayIdentity') as identity:
        identity.return_value.ensure.return_value = EMAIL
        value._prepare_wireguard_bootstrap(for_start=True)
    apply.assert_called_once_with(value, lease)
    service.configuration_applied.assert_called_once_with(UNIT, 'revision')
    metadata = value.compute_instance.replace_metadata.call_args.args[1]
    assert any(item.get('value') == lease.secret_version_name for item in metadata['items'])


@pytest.mark.parametrize('status,pending', [('RUNNING', True), ('TERMINATED', False)])
def test_secret_mismatch_without_authorized_stopped_transition_still_fails(status, pending):
    value = manager()
    value.compute_instance.get.return_value = existing(status=status)
    value._wireguard_provisioning.return_value.get_lease.return_value = saved_lease(configuration_pending=pending)
    with patch('cloud_fn_utilities.course_objects.compute.lab_server_manager.WireGuardGatewayIdentity') as identity:
        identity.return_value.ensure.return_value = EMAIL
        with pytest.raises(BadRequest, match='differs'):
            value._prepare_wireguard_bootstrap(for_start=True)
    value.compute_instance.replace_metadata.assert_not_called()


def test_failed_saved_network_update_does_not_mark_configuration_applied_or_change_metadata():
    value = manager()
    value.compute_instance.get.return_value = existing(status='TERMINATED')
    service = value._wireguard_provisioning.return_value
    service.get_lease.return_value = saved_lease()
    with patch('cloud_fn_utilities.server_specific.wireguard_configuration.apply_saved_wireguard_network',
               side_effect=ConnectionError('GCP route operation failed')), \
         patch('cloud_fn_utilities.course_objects.compute.lab_server_manager.WireGuardGatewayIdentity') as identity:
        identity.return_value.ensure.return_value = EMAIL
        with pytest.raises(ConnectionError):
            value._prepare_wireguard_bootstrap(for_start=True)
    value.compute_instance.replace_metadata.assert_not_called()
    service.configuration_applied.assert_not_called()


def test_apply_replaces_only_unit_remote_route_and_remote_lan_rule():
    lease = saved_lease()
    unit = {
        'routes': [{'name': 'wireguard-equipment', 'network': 'external', 'next_hop_instance': 'wireguard',
                    'dest_range': '192.168.50.0/24', 'tags': ['wireguard-client']}],
        'firewall_rules': [{'name': 'allow-kit-to-students', 'network': 'external', 'action': 'allow',
                            'target_tags': ['wireguard-client'], 'ports': ['tcp/any'],
                            'ip_ranges': ['192.168.50.0/24'], 'priority': 900}],
    }
    value = SimpleNamespace(parent_build_id=UNIT, env_dict={'project': 'tenant-project'}, db=Mock(),
                            _wireguard_provisioning=Mock())
    value.db.get.return_value = unit
    value._wireguard_provisioning.return_value.get_lease.return_value = lease
    with patch.object(configuration, 'RouteManager') as routing, patch.object(configuration, 'FirewallManager') as firewall:
        configuration.apply_saved_wireguard_network(value, lease)
    assert routing.return_value.delete.call_args.args[0][0].name == 'wireguard-equipment'
    assert routing.return_value.build.call_args.args[0][0].dest_range == '192.168.50.0/24'
    firewall.return_value.firewalls_client.delete.assert_called_once_with(
        resource_name=f'{UNIT}-allow-kit-to-students', wait=True)
    assert firewall.return_value.build.call_args.args[1][0].ip_ranges == ['192.168.50.0/24']


def test_stale_saved_revision_cannot_mutate_gcp_routes():
    value = SimpleNamespace(parent_build_id=UNIT, _wireguard_provisioning=Mock())
    value._wireguard_provisioning.return_value.get_lease.return_value = saved_lease(configuration_revision='newer')
    with patch.object(configuration, 'RouteManager') as routing, pytest.raises(BadRequest, match='changed'):
        configuration.apply_saved_wireguard_network(value, saved_lease())
    routing.assert_not_called()
