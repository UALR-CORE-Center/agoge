from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

import pytest

from cloud_fn_utilities.course_objects.compute import base_compute_manager as base_compute_module
from cloud_fn_utilities.course_objects.compute import lab_server_manager as lab_server_module
from common.constants.states import ServerStates
from common.exceptions import BadRequest, Conflict


LabServerManager = lab_server_module.LabServerManager


def _wireguard_unit(listener_port='udp/51820'):
    return {
        'servers': [
            {
                'wireguard_gateway': True,
                'tags': ['wireguard-gateway'],
                'nics': [{'network': 'external', 'external_nat': True}],
            }
        ],
        'firewall_rules': [
            {
                'network': 'external',
                'action': 'allow',
                'direction': 'INGRESS',
                'priority': 1000,
                'target_tags': ['wireguard-gateway'],
                'ports': [listener_port],
                'ip_ranges': ['0.0.0.0/0'],
            }
        ],
    }


def test_wireguard_build_orders_dns_and_routes_after_the_vm():
    manager = object.__new__(LabServerManager)
    events = []
    manager._build_server = lambda finalize_state=True: (
        events.append(("vm", finalize_state))
    )
    manager.server_spec = SimpleNamespace(wireguard_endpoint_id='12345')
    manager._require_wireguard_provisionable = lambda: events.append("preflight")
    manager._ensure_dns_record = lambda: events.append("dns")
    manager._build_routes = lambda: events.append("routes")
    manager._stage_wireguard_endpoint = lambda: events.append("stage")
    manager._mark_wireguard_endpoint_error = lambda: events.append("error")
    manager.state_manager = MagicMock()
    manager.state_manager.get_state.return_value = ServerStates.READY.value
    manager.state_manager.state_transition.side_effect = lambda state: events.append(state)
    manager.s = ServerStates

    manager.build()

    assert events == [
        "preflight",
        ("vm", False),
        "stage",
        "dns",
        "routes",
        ServerStates.RUNNING,
    ]


@pytest.mark.parametrize("endpoint_status", ["releasing", "released"])
def test_same_owner_stale_wireguard_build_is_rejected_before_gcp(endpoint_status):
    manager = object.__new__(LabServerManager)
    manager.class_name = "LabServerManager"
    manager.server_name = "unit-123-wireguard"
    manager.parent_build_id = "unit-123"
    manager.server_spec = SimpleNamespace(wireguard_endpoint_id='12345')
    manager.logger = MagicMock()
    manager.s = ServerStates
    manager.state_manager = MagicMock()
    manager.state_manager.get_state.return_value = ServerStates.READY.value
    manager._build_server = MagicMock()
    manager._require_wireguard_provisionable = MagicMock(
        side_effect=BadRequest(
            f"WireGuard endpoint in state {endpoint_status} cannot be provisioned"
        )
    )
    manager._stage_wireguard_endpoint = MagicMock()
    manager._ensure_dns_record = MagicMock()
    manager._build_routes = MagicMock()
    manager._mark_wireguard_endpoint_error = MagicMock()

    with pytest.raises(BadRequest, match=endpoint_status):
        manager.build()

    manager._build_server.assert_not_called()
    manager._stage_wireguard_endpoint.assert_not_called()
    manager._ensure_dns_record.assert_not_called()
    manager._build_routes.assert_not_called()
    manager._mark_wireguard_endpoint_error.assert_not_called()
    manager.state_manager.state_transition.assert_not_called()


def test_duplicate_build_is_noop_for_running_server():
    manager = object.__new__(LabServerManager)
    manager.s = ServerStates
    manager.state_manager = MagicMock()
    manager.state_manager.get_state.return_value = ServerStates.RUNNING.value
    manager._build_server = MagicMock()
    manager._ensure_dns_record = MagicMock()
    manager._build_routes = MagicMock()
    manager._stage_wireguard_endpoint = MagicMock()
    manager._mark_wireguard_endpoint_error = MagicMock()

    manager.build()

    manager._build_server.assert_not_called()
    manager._ensure_dns_record.assert_not_called()
    manager._build_routes.assert_not_called()
    manager._stage_wireguard_endpoint.assert_not_called()
    manager._mark_wireguard_endpoint_error.assert_not_called()
    manager.state_manager.state_transition.assert_not_called()


def test_wireguard_start_retry_reuses_running_vm_and_retries_publication():
    manager = object.__new__(LabServerManager)
    manager.s = ServerStates
    manager.state_manager = MagicMock()
    manager.state_manager.get_state.return_value = ServerStates.RUNNING.value
    manager.server_spec = SimpleNamespace(wireguard_endpoint_id='12345')
    manager._require_wireguard_provisionable = MagicMock()
    manager._start_server = MagicMock()
    manager._reserved_external_ip = MagicMock(return_value='203.0.113.10')
    manager._stage_wireguard_endpoint = MagicMock()
    manager._ensure_dns_record = MagicMock()
    manager._activate_wireguard_endpoint = MagicMock()
    manager._mark_wireguard_endpoint_error = MagicMock()

    manager.start()

    manager._start_server.assert_not_called()
    manager._require_wireguard_provisionable.assert_called_once_with()
    manager._stage_wireguard_endpoint.assert_called_once_with()
    manager._ensure_dns_record.assert_called_once_with()
    manager._activate_wireguard_endpoint.assert_called_once_with()


@pytest.mark.parametrize("endpoint_status", ["releasing", "released"])
def test_same_owner_stale_wireguard_start_is_rejected_before_gcp(endpoint_status):
    manager = object.__new__(LabServerManager)
    manager.class_name = "LabServerManager"
    manager.server_name = "unit-123-wireguard"
    manager.parent_build_id = "unit-123"
    manager.logger = MagicMock()
    manager.s = ServerStates
    manager.state_manager = MagicMock()
    manager.state_manager.get_state.return_value = ServerStates.STOPPED.value
    manager.server_spec = SimpleNamespace(wireguard_endpoint_id='12345')
    manager._require_wireguard_provisionable = MagicMock(
        side_effect=BadRequest(
            f"WireGuard endpoint in state {endpoint_status} cannot be provisioned"
        )
    )
    manager._start_server = MagicMock()
    manager._reserved_external_ip = MagicMock(return_value='203.0.113.10')
    manager._stage_wireguard_endpoint = MagicMock()
    manager._ensure_dns_record = MagicMock()
    manager._activate_wireguard_endpoint = MagicMock()
    manager._mark_wireguard_endpoint_error = MagicMock()

    with pytest.raises(BadRequest, match=endpoint_status):
        manager.start()

    manager._start_server.assert_not_called()
    manager._reserved_external_ip.assert_not_called()
    manager._stage_wireguard_endpoint.assert_not_called()
    manager._ensure_dns_record.assert_not_called()
    manager._activate_wireguard_endpoint.assert_not_called()
    manager._mark_wireguard_endpoint_error.assert_not_called()
    manager.state_manager.state_transition.assert_not_called()


@pytest.mark.parametrize(
    ("action", "server_state"),
    [
        ("build", ServerStates.STOPPED.value),
        ("build", ServerStates.DELETING.value),
        ("build", ServerStates.DELETED.value),
        ("start", ServerStates.STOPPING.value),
        ("start", ServerStates.DELETING.value),
        ("start", ServerStates.DELETED.value),
    ],
)
def test_stale_wireguard_actions_are_noops_in_teardown_states(action, server_state):
    manager = object.__new__(LabServerManager)
    manager.class_name = "LabServerManager"
    manager.server_name = "unit-123-wireguard"
    manager.server_spec = SimpleNamespace(wireguard_endpoint_id='12345')
    manager.logger = MagicMock()
    manager.s = ServerStates
    manager.state_manager = MagicMock()
    manager.state_manager.get_state.return_value = server_state
    manager._require_wireguard_provisionable = MagicMock()
    manager._build_server = MagicMock()
    manager._start_server = MagicMock()

    getattr(manager, action)()

    manager._require_wireguard_provisionable.assert_not_called()
    manager._build_server.assert_not_called()
    manager._start_server.assert_not_called()
    manager.state_manager.state_transition.assert_not_called()


def test_wireguard_lifecycle_mutations_use_the_parent_unit_as_owner():
    manager = object.__new__(LabServerManager)
    manager.parent_build_id = 'unit-123'
    manager.primary_external_ip = '203.0.113.10'
    manager.server_spec = SimpleNamespace(wireguard_endpoint_id='12345')
    manager.wireguard_registry = MagicMock()
    manager.wireguard_registry.require_provisionable.return_value = SimpleNamespace(
        port=51820
    )
    manager.db = MagicMock()
    manager.db.get.return_value = _wireguard_unit()
    manager.logger = MagicMock()
    manager.class_name = 'LabServerManager'
    manager.s = ServerStates
    manager.state_manager = MagicMock()
    manager.state_manager.get_state.return_value = ServerStates.STOPPED.value
    manager._stop_server = MagicMock()

    manager._require_wireguard_provisionable()
    manager._stage_wireguard_endpoint()
    manager._activate_wireguard_endpoint()
    manager._mark_wireguard_endpoint_error()
    manager._mark_wireguard_endpoint_releasing()
    manager._release_wireguard_endpoint()
    manager.stop()

    manager.wireguard_registry.stage.assert_called_once_with(
        '12345',
        unit_id='unit-123',
        public_ip='203.0.113.10',
    )
    assert manager.wireguard_registry.require_provisionable.call_args_list == [
        call('12345', unit_id='unit-123'),
        call('12345', unit_id='unit-123'),
    ]
    manager.wireguard_registry.activate.assert_called_once_with(
        '12345',
        unit_id='unit-123',
        public_ip='203.0.113.10',
    )
    manager.wireguard_registry.mark_error.assert_called_once_with(
        '12345',
        unit_id='unit-123',
    )
    manager.wireguard_registry.mark_releasing.assert_called_once_with(
        '12345',
        unit_id='unit-123',
    )
    manager.wireguard_registry.release.assert_called_once_with(
        '12345',
        unit_id='unit-123',
    )
    manager.wireguard_registry.mark_reserved.assert_called_once_with(
        '12345',
        unit_id='unit-123',
    )


def test_gateway_restart_cannot_activate_without_its_configured_listener():
    manager = object.__new__(LabServerManager)
    manager.parent_build_id = 'unit-123'
    manager.primary_external_ip = '203.0.113.10'
    manager.server_spec = SimpleNamespace(wireguard_endpoint_id='12345')
    manager.wireguard_registry = MagicMock()
    manager.wireguard_registry.require_provisionable.return_value = SimpleNamespace(
        port=41194
    )
    manager.db = MagicMock()
    manager.db.get.return_value = _wireguard_unit(listener_port='udp/51820')

    with pytest.raises(BadRequest, match='does not allow public UDP/41194'):
        manager._activate_wireguard_endpoint()

    manager.wireguard_registry.activate.assert_not_called()


def test_reserved_address_is_attached_to_the_wireguard_access_config():
    manager = object.__new__(LabServerManager)
    manager.env = SimpleNamespace(region="us-central1", project="test-project")
    manager.server_name = "unit-123-wireguard"
    manager.primary_external_ip = None
    manager.address_manager = MagicMock()
    manager.address_manager.reserve.return_value = "203.0.113.10"
    manager.server_spec = SimpleNamespace(
        network_prefix="unit-123",
        parent_id="unit-123",
        nics=[
            {
                "network": "external",
                "subnet_name": "default",
                "internal_ip": "10.20.0.10",
                "external_nat": True,
                "external_ip_name": "wireguard-ip",
            }
        ],
    )
    network_resource = MagicMock()
    network_resource.access_config.return_value = "wireguard-access-config"
    network_resource.new.return_value = "wireguard-nic"

    with patch.object(
        lab_server_module,
        "NetworkInterfaceResource",
        return_value=network_resource,
    ):
        manager._add_nics()

    manager.address_manager.reserve.assert_called_once_with(
        name="unit-123-wireguard-ip",
        description="Reserved public address for Agoge server unit-123-wireguard",
    )
    network_resource.access_config.assert_called_once_with(
        type_="ONE_TO_ONE_NAT",
        name="External NAT",
        nat_ip="203.0.113.10",
    )
    assert manager.primary_external_ip == "203.0.113.10"
    assert manager.server_spec.nics[0]["external_ip_name"] == "unit-123-wireguard-ip"
    assert manager.server_spec.network_interfaces == ["wireguard-nic"]


def test_wireguard_delete_releases_dependencies_in_safe_order():
    manager = object.__new__(LabServerManager)
    manager.class_name = "LabServerManager"
    events = []
    manager.server_name = "unit-123-wireguard"
    manager.parent_build_id = "unit-123"
    manager.server_spec = SimpleNamespace(wireguard_endpoint_id='12345')
    manager.s = ServerStates
    manager.state_manager = MagicMock()
    manager.state_manager.get_state.return_value = ServerStates.RUNNING.value
    manager.logger = MagicMock()
    manager._mark_wireguard_endpoint_releasing = lambda: (
        events.append("releasing") or SimpleNamespace(public_ip='203.0.113.10')
    )
    manager._delete_routes = lambda: events.append("routes")
    manager._dns_record = lambda: "wg-12345.vpn.example.edu."
    manager.dns_manager = MagicMock()
    manager.dns_manager.delete_dns.side_effect = lambda **_: events.append("dns") or True
    manager.compute_instance = MagicMock()
    manager.compute_instance.delete.side_effect = lambda **_: events.append("vm") or True
    manager._release_reserved_external_addresses = lambda: events.append("address")
    manager._release_wireguard_endpoint = lambda: events.append("released")

    result = manager.delete()

    assert result is True
    assert events == ["releasing", "routes", "dns", "vm", "address", "released"]
    manager.dns_manager.delete_dns.assert_called_once_with(
        record_name="wg-12345.vpn.example.edu.",
        ip_address="203.0.113.10",
    )


def test_delayed_old_owner_delete_never_name_deletes_reused_endpoint_dns():
    manager = object.__new__(LabServerManager)
    manager.class_name = "LabServerManager"
    manager.server_name = "old-unit-wireguard"
    manager.parent_build_id = "old-unit"
    manager.server_spec = SimpleNamespace(wireguard_endpoint_id='12345')
    manager.s = ServerStates
    manager.state_manager = MagicMock()
    manager.state_manager.get_state.return_value = ServerStates.RUNNING.value
    manager.logger = MagicMock()
    # The helper returns None when the registry rejects this delayed delivery
    # because ID 12345 now belongs to a different Unit.
    manager._mark_wireguard_endpoint_releasing = MagicMock(return_value=None)
    manager._delete_routes = MagicMock()
    manager._dns_record = lambda: "wg-12345.vpn.example.edu."
    manager.dns_manager = MagicMock()
    manager.compute_instance = MagicMock()
    manager.compute_instance.delete.return_value = True
    manager._release_reserved_external_addresses = MagicMock()
    manager._release_wireguard_endpoint = MagicMock()

    assert manager.delete() is True

    manager.dns_manager.delete_dns.assert_not_called()
    manager.compute_instance.delete.assert_called_once_with(
        resource_name="old-unit-wireguard",
        wait=True,
    )
    manager._release_reserved_external_addresses.assert_called_once_with()
    manager._release_wireguard_endpoint.assert_called_once_with()


def test_legacy_wireguard_stop_never_uses_name_only_dns_deletion():
    manager = object.__new__(LabServerManager)
    manager.class_name = "LabServerManager"
    manager.server_name = "old-unit-wireguard"
    manager.parent_build_id = "old-unit"
    manager.server_spec = SimpleNamespace(
        wireguard_endpoint_id='12345',
        nics=[{"external_nat": True}],
    )
    manager.s = ServerStates
    manager.state_manager = MagicMock()
    manager.state_manager.get_state.return_value = ServerStates.RUNNING.value
    manager.logger = MagicMock()
    manager.compute_instance = MagicMock()
    manager.compute_instance.stop.return_value = True
    manager._dns_record = lambda: "wg-12345.vpn.example.edu."
    manager.dns_manager = MagicMock()

    manager._stop_server()

    manager.dns_manager.delete_dns.assert_not_called()
    assert manager.state_manager.state_transition.call_args_list == [
        call(ServerStates.STOPPING),
        call(ServerStates.STOPPED),
    ]


def test_duplicate_delete_is_noop_for_deleted_server():
    manager = object.__new__(LabServerManager)
    manager.s = ServerStates
    manager.state_manager = MagicMock()
    manager.state_manager.get_state.return_value = ServerStates.DELETED.value

    assert manager.delete() is True
    manager.state_manager.state_transition.assert_not_called()


def test_wireguard_delete_retains_address_when_vm_deletion_is_not_confirmed():
    manager = object.__new__(LabServerManager)
    manager.class_name = "LabServerManager"
    manager.server_name = "unit-123-wireguard"
    manager.parent_build_id = "unit-123"
    manager.server_spec = SimpleNamespace(wireguard_endpoint_id='12345')
    manager.s = ServerStates
    manager.state_manager = MagicMock()
    manager.state_manager.get_state.return_value = ServerStates.RUNNING.value
    manager.logger = MagicMock()
    manager._mark_wireguard_endpoint_releasing = MagicMock()
    manager._mark_wireguard_endpoint_releasing.return_value = SimpleNamespace(
        public_ip='203.0.113.10'
    )
    manager._delete_routes = MagicMock()
    manager._dns_record = lambda: "wg-12345.vpn.example.edu."
    manager.dns_manager = MagicMock()
    manager.compute_instance = MagicMock()
    manager.compute_instance.delete.return_value = False
    manager._release_reserved_external_addresses = MagicMock()
    manager._release_wireguard_endpoint = MagicMock()
    manager._mark_wireguard_endpoint_error = MagicMock()

    result = manager.delete()

    assert result is False
    manager.state_manager.state_transition.assert_any_call(ServerStates.BROKEN)
    manager._mark_wireguard_endpoint_error.assert_called_once_with()
    manager._release_reserved_external_addresses.assert_not_called()
    manager._release_wireguard_endpoint.assert_not_called()


def test_wireguard_delete_retains_address_when_dns_deletion_fails():
    manager = object.__new__(LabServerManager)
    manager.class_name = "LabServerManager"
    manager.server_name = "unit-123-wireguard"
    manager.parent_build_id = "unit-123"
    manager.server_spec = SimpleNamespace(wireguard_endpoint_id='12345')
    manager.s = ServerStates
    manager.state_manager = MagicMock()
    manager.state_manager.get_state.return_value = ServerStates.RUNNING.value
    manager.logger = MagicMock()
    manager._mark_wireguard_endpoint_releasing = MagicMock()
    manager._mark_wireguard_endpoint_releasing.return_value = SimpleNamespace(
        public_ip='203.0.113.10'
    )
    manager._delete_routes = MagicMock()
    manager._dns_record = lambda: "wg-12345.vpn.example.edu."
    manager.dns_manager = MagicMock()
    manager.dns_manager.delete_dns.return_value = False
    manager.compute_instance = MagicMock()
    manager.compute_instance.delete.return_value = True
    manager._release_reserved_external_addresses = MagicMock()
    manager._release_wireguard_endpoint = MagicMock()
    manager._mark_wireguard_endpoint_error = MagicMock()

    result = manager.delete()

    assert result is False
    manager.compute_instance.delete.assert_called_once_with(
        resource_name="unit-123-wireguard",
        wait=True,
    )
    manager.state_manager.state_transition.assert_any_call(ServerStates.BROKEN)
    manager._mark_wireguard_endpoint_error.assert_called_once_with()
    manager._release_reserved_external_addresses.assert_not_called()
    manager._release_wireguard_endpoint.assert_not_called()


def test_retried_server_build_conflict_transitions_to_running():
    manager = object.__new__(LabServerManager)
    manager.class_name = "LabServerManager"
    manager.state_manager = MagicMock()
    manager.s = SimpleNamespace(BUILDING="building", RUNNING="running", BROKEN="broken")
    manager._add_disks = MagicMock()
    manager._add_metadata = MagicMock()
    manager._add_nics = MagicMock()
    manager.ip_aliases = False
    manager.server_name = "unit-123-wireguard"
    manager.project = "test-project"
    manager.env = SimpleNamespace(zone="us-central1-a")
    manager.logger = MagicMock()
    manager._lookup_machine_type = lambda value: value
    manager._dns_record = lambda: False
    manager.compute_instance = MagicMock()
    manager.compute_instance.SERVICE_ACCOUNT_CONFIG = []
    manager.compute_instance.create.side_effect = Conflict("already exists")
    desired_instance = SimpleNamespace(
        machine_type='zones/us-central1-a/machineTypes/e2-medium',
        can_ip_forward=True,
        tags=SimpleNamespace(items=['wireguard']),
        network_interfaces=[SimpleNamespace(
            network='global/networks/unit-123-external',
            subnetwork='regions/us-central1/subnetworks/unit-123-external-default',
            network_i_p='10.20.0.2',
            access_configs=[SimpleNamespace(nat_i_p='203.0.113.10')],
        )],
    )
    manager.compute_instance.get.return_value = SimpleNamespace(
        status='RUNNING',
        machine_type='projects/test/zones/us-central1-a/machineTypes/e2-medium',
        can_ip_forward=True,
        tags=SimpleNamespace(items=['wireguard']),
        network_interfaces=[SimpleNamespace(
            network='projects/test/global/networks/unit-123-external',
            subnetwork='projects/test/regions/us-central1/subnetworks/unit-123-external-default',
            network_i_p='10.20.0.2',
            access_configs=[SimpleNamespace(nat_i_p='203.0.113.10')],
        )],
    )
    manager.server_spec = SimpleNamespace(
        name=manager.server_name,
        machine_type="e2-medium",
        service_accounts=None,
        tags=['wireguard'],
        min_cpu_platform=None,
        disks=[],
        metadata={"items": []},
        can_ip_forward=True,
        network_interfaces=desired_instance.network_interfaces,
        build_type=None,
        machine_image=None,
        delayed_start=False,
        wireguard_endpoint_id=None,
    )
    instance_builder = MagicMock()
    instance_builder.new.return_value = desired_instance

    with patch.object(base_compute_module, "InstanceResource", return_value=instance_builder):
        manager._build_server()

    assert manager.state_manager.state_transition.call_args_list == [
        call("building"),
        call("running"),
    ]
    manager.compute_instance.get.assert_called_once_with(resource_name=manager.server_name)


def test_retried_server_build_rejects_stopped_conflicting_instance():
    existing = SimpleNamespace(
        status='TERMINATED',
        machine_type='zones/us-central1-a/machineTypes/e2-medium',
        can_ip_forward=True,
        tags=SimpleNamespace(items=['wireguard']),
        network_interfaces=[],
    )
    desired = SimpleNamespace(
        machine_type='zones/us-central1-a/machineTypes/e2-medium',
        can_ip_forward=True,
        tags=SimpleNamespace(items=['wireguard']),
        network_interfaces=[],
    )

    assert not LabServerManager._existing_instance_matches(existing, desired)


def test_retried_server_build_rejects_wrong_static_address():
    nic = lambda address: SimpleNamespace(
        network='global/networks/unit-123-external',
        subnetwork='regions/us-central1/subnetworks/unit-123-external-default',
        network_i_p='10.20.0.2',
        access_configs=[SimpleNamespace(nat_i_p=address)],
    )
    existing = SimpleNamespace(
        status='RUNNING',
        machine_type='zones/us-central1-a/machineTypes/e2-medium',
        can_ip_forward=True,
        tags=SimpleNamespace(items=['wireguard']),
        network_interfaces=[nic('203.0.113.99')],
    )
    desired = SimpleNamespace(
        machine_type='zones/us-central1-a/machineTypes/e2-medium',
        can_ip_forward=True,
        tags=SimpleNamespace(items=['wireguard']),
        network_interfaces=[nic('203.0.113.10')],
    )

    assert not LabServerManager._existing_instance_matches(existing, desired)


def test_concurrent_duplicate_build_waits_for_matching_in_progress_vm():
    nic = SimpleNamespace(
        network='global/networks/unit-123-external',
        subnetwork='regions/us-central1/subnetworks/unit-123-external-default',
        network_i_p='10.20.0.2',
        access_configs=[SimpleNamespace(nat_i_p='203.0.113.10')],
    )
    desired = SimpleNamespace(
        machine_type='zones/us-central1-a/machineTypes/e2-medium',
        can_ip_forward=True,
        tags=SimpleNamespace(items=['wireguard']),
        network_interfaces=[nic],
    )
    provisioning = SimpleNamespace(
        status='PROVISIONING',
        machine_type='zones/us-central1-a/machineTypes/e2-medium',
        can_ip_forward=True,
        tags=SimpleNamespace(items=['wireguard']),
        network_interfaces=[nic],
    )
    running = SimpleNamespace(**{**vars(provisioning), 'status': 'RUNNING'})
    manager = object.__new__(LabServerManager)
    manager.server_name = 'unit-123-wireguard'
    manager.server_spec = SimpleNamespace(name=manager.server_name)
    manager.compute_instance = MagicMock()
    manager.compute_instance.get.return_value = running

    with patch.object(base_compute_module.time, 'sleep') as sleep:
        assert manager._reconcile_existing_build(provisioning, desired)

    sleep.assert_called_once_with(manager._INSERT_CONFLICT_WAIT_SECONDS)
    manager.compute_instance.get.assert_called_once_with(
        resource_name=manager.server_name,
    )


def test_concurrent_duplicate_build_waits_the_full_insert_operation_window():
    desired = SimpleNamespace(
        machine_type='zones/us-central1-a/machineTypes/e2-medium',
        can_ip_forward=True,
        tags=SimpleNamespace(items=['wireguard']),
        network_interfaces=[],
    )
    provisioning = SimpleNamespace(
        status='PROVISIONING',
        machine_type=desired.machine_type,
        can_ip_forward=desired.can_ip_forward,
        tags=desired.tags,
        network_interfaces=[],
    )
    running = SimpleNamespace(**{**vars(provisioning), 'status': 'RUNNING'})
    manager = object.__new__(LabServerManager)
    manager.server_name = 'unit-123-wireguard'
    manager.server_spec = SimpleNamespace(name=manager.server_name)
    manager.compute_instance = MagicMock()
    # The VM becomes RUNNING only on the last poll at 150 seconds.
    manager.compute_instance.get.side_effect = [
        *([provisioning] * 29),
        running,
    ]

    with patch.object(base_compute_module.time, 'sleep') as sleep:
        assert manager._reconcile_existing_build(provisioning, desired)

    assert sleep.call_count == 30
    assert manager.compute_instance.get.call_count == 30
    assert sum(call_.args[0] for call_ in sleep.call_args_list) == 150


def test_concurrent_duplicate_build_never_waits_for_mismatched_in_progress_vm():
    desired = SimpleNamespace(
        machine_type='zones/us-central1-a/machineTypes/e2-medium',
        can_ip_forward=True,
        tags=SimpleNamespace(items=['wireguard']),
        network_interfaces=[],
    )
    provisioning = SimpleNamespace(
        status='PROVISIONING',
        machine_type='zones/us-central1-a/machineTypes/e2-small',
        can_ip_forward=True,
        tags=SimpleNamespace(items=['wireguard']),
        network_interfaces=[],
    )
    manager = object.__new__(LabServerManager)
    manager.server_name = 'unit-123-wireguard'
    manager.server_spec = SimpleNamespace(name=manager.server_name)
    manager.compute_instance = MagicMock()

    with patch.object(base_compute_module.time, 'sleep') as sleep:
        assert not manager._reconcile_existing_build(provisioning, desired)

    sleep.assert_not_called()
    manager.compute_instance.get.assert_not_called()


def _start_manager(existing_state):
    manager = object.__new__(LabServerManager)
    manager.class_name = 'LabServerManager'
    manager.s = ServerStates
    manager.server_name = 'unit-123-wireguard'
    manager.parent_build_id = 'unit-123'
    manager.server_spec = SimpleNamespace(
        delayed_start=False,
        wireguard_endpoint_id='12345',
    )
    manager.state_manager = MagicMock()
    manager.state_manager.get_state.return_value = existing_state
    manager.state_manager.SLEEP_TIME = 0
    manager.compute_instance = MagicMock()
    manager.logger = MagicMock()
    manager._dns_record = MagicMock(return_value=False)
    return manager


def test_duplicate_start_reconciles_running_vm_without_second_start_request():
    manager = _start_manager(ServerStates.STARTING.value)
    manager.compute_instance.get.return_value = SimpleNamespace(status='RUNNING')

    manager._start_server()

    manager.compute_instance.start.assert_not_called()
    assert manager.state_manager.state_transition.call_args_list == [
        call(ServerStates.STARTING),
        call(ServerStates.RUNNING),
    ]
    assert call(ServerStates.BROKEN) not in manager.state_manager.state_transition.call_args_list


def test_duplicate_start_bad_request_reconciles_running_vm_without_broken_state():
    manager = _start_manager(ServerStates.STOPPED.value)
    manager.compute_instance.start.side_effect = BadRequest('already starting')
    manager.compute_instance.get.return_value = SimpleNamespace(status='RUNNING')

    manager._start_server()

    manager.compute_instance.start.assert_called_once_with(
        resource_name=manager.server_name,
        wait=True,
    )
    assert manager.state_manager.state_transition.call_args_list == [
        call(ServerStates.STARTING),
        call(ServerStates.RUNNING),
    ]
    assert call(ServerStates.BROKEN) not in manager.state_manager.state_transition.call_args_list


def test_in_progress_duplicate_start_times_out_retryably_without_broken_state():
    manager = _start_manager(ServerStates.STARTING.value)
    manager.compute_instance.get.return_value = SimpleNamespace(status='STAGING')

    with patch.object(base_compute_module.time, 'sleep'), pytest.raises(
        TimeoutError,
        match='in-progress start',
    ):
        manager._start_server()

    manager.compute_instance.start.assert_not_called()
    assert manager.state_manager.state_transition.call_args_list == [
        call(ServerStates.STARTING),
    ]
    assert call(ServerStates.BROKEN) not in manager.state_manager.state_transition.call_args_list
