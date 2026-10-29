"""A template-server insert refused for zone capacity is retried in the region's other zones; lab servers never are."""
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

import pytest

from cloud_fn_utilities.course_objects.compute import base_compute_manager as base_module
from cloud_fn_utilities.course_objects.compute.base_compute_manager import BaseComputeManager, is_zone_stockout
from cloud_fn_utilities.course_objects.compute.image_template_manager import ImageTemplateManager
from common.constants.database import DbCollections
from common.exceptions import ResourceExhausted
from common.models.agoge import NestedBuildStatusModel
from common.models.model_validators.model_validator import ModelValidator
from common.utilities.gcp.compute.base_compute_api import BaseComputeAPI
from common.utilities.gcp.compute.compute_machine_type import ComputeMachineTypesAPI
from common.utilities.nested_build_monitor import NestedBuildMonitor

ZONE_A, ZONE_B, ZONE_C = 'us-central1-a', 'us-central1-b', 'us-central1-c'
MACHINE = 'n2-standard-8'
STOCKOUT = ("Operation failed with errors: ZONE_RESOURCE_POOL_EXHAUSTED_WITH_DETAILS: The zone "
            "'projects/test-dev-787001/zones/us-central1-a' does not have enough resources available.")


def _zone_clients():
    return {name: MagicMock() for name in ('compute_disk', 'compute_instance', 'compute_machine_types')}


def _manager(cls=BaseComputeManager, offered=(ZONE_A, ZONE_B, ZONE_C), existing=()):
    manager = object.__new__(cls)
    manager.class_name = cls.__name__
    manager.server_name = 'kali-lab'
    manager.project = 'test-dev-787001'
    manager.env = SimpleNamespace(zone=ZONE_A, region='us-central1', project=manager.project)
    manager.logger = MagicMock()
    manager.state_manager = MagicMock()
    manager.s = SimpleNamespace(BUILDING='building', RUNNING='running', BROKEN='broken')
    manager._add_disks = MagicMock()
    manager._add_metadata = MagicMock()
    manager._add_nics = MagicMock()
    manager._lookup_machine_type = lambda value: value
    manager._dns_record = MagicMock(return_value=False)
    manager.ip_aliases = False
    manager.nested_host = False
    manager._server_zone = None
    for name, client in _zone_clients().items():
        setattr(manager, name, client)
    manager.dns_manager = MagicMock()
    manager.compute_instance.SERVICE_ACCOUNT_CONFIG = []
    manager.compute_instance.zones_with_instance.return_value = list(existing)
    manager.compute_machine_types.zones_offering.return_value = list(offered)
    manager.server_spec = SimpleNamespace(
        name=manager.server_name, machine_type=MACHINE, service_accounts=None, tags=[],
        min_cpu_platform=None, disks=[], metadata={'items': []}, can_ip_forward=False,
        network_interfaces=[], build_type=None, machine_image=None, delayed_start=False,
        wireguard_endpoint_id=None,
    )
    return manager


@pytest.fixture
def instance_resource():
    """Records the zone each InstanceResource was built for."""
    with patch.object(base_module, 'InstanceResource') as resource:
        def build(zone):
            instance = MagicMock(zone=zone)
            builder = MagicMock()
            builder.new.return_value = instance
            return builder

        resource.side_effect = build
        yield resource


def _all_zone_clients(manager):
    return [manager.compute_disk, manager.compute_instance, manager.compute_machine_types,
            manager.dns_manager.compute_instance]


def test_is_zone_stockout_matches_the_stockout_code_but_not_a_quota():
    assert is_zone_stockout(RuntimeError(STOCKOUT))
    assert not is_zone_stockout(ResourceExhausted('QUOTA_EXCEEDED: CPUS'))


# --- 1. fallback to the second zone ---

def test_a_stocked_out_first_zone_falls_back_to_the_second_and_records_it(instance_resource):
    manager = _manager()
    manager._on_instance_created = MagicMock()
    manager.compute_instance.create.side_effect = [RuntimeError(STOCKOUT), True]

    manager._build_server(zone_fallback=True)

    assert [c.kwargs['zone'] for c in instance_resource.call_args_list] == [ZONE_A, ZONE_B]
    assert manager.compute_instance.create.call_count == 2
    sent = [c.kwargs['instance_resource'].zone for c in manager.compute_instance.create.call_args_list]
    assert sent == [ZONE_A, ZONE_B]
    # The boot disk path names the zone, so it is rebuilt for the second zone.
    assert manager._add_disks.call_count == 2
    manager._on_instance_created.assert_called_once_with(ZONE_B)
    assert manager.server_zone == ZONE_B
    for client in _all_zone_clients(manager):
        assert client.set_zone.call_args_list[-1] == call(ZONE_B)
    assert manager.state_manager.state_transition.call_args_list == [call('building'), call('running')]


def test_a_first_zone_success_never_falls_back(instance_resource):
    manager = _manager()
    manager._on_instance_created = MagicMock()
    manager.compute_instance.create.return_value = True

    manager._build_server(zone_fallback=True)

    assert manager.compute_instance.create.call_count == 1
    assert manager._add_disks.call_count == 1
    manager._on_instance_created.assert_called_once_with(ZONE_A)


def test_the_build_can_fall_through_two_stocked_out_zones(instance_resource):
    manager = _manager()
    manager._on_instance_created = MagicMock()
    manager.compute_instance.create.side_effect = [RuntimeError(STOCKOUT), RuntimeError(STOCKOUT), True]

    manager._build_server(zone_fallback=True)

    manager._on_instance_created.assert_called_once_with(ZONE_C)


# --- 2. every zone stocked out ---

def test_when_every_zone_is_stocked_out_the_server_breaks_once_and_the_error_is_raised(instance_resource):
    manager = _manager()
    manager._on_instance_created = MagicMock()
    manager.compute_instance.create.side_effect = RuntimeError(STOCKOUT)

    with pytest.raises(RuntimeError, match='ZONE_RESOURCE_POOL_EXHAUSTED'):
        manager._build_server(zone_fallback=True)

    assert manager.compute_instance.create.call_count == 3
    assert manager.state_manager.state_transition.call_args_list == [call('building'), call('broken')]
    manager._on_instance_created.assert_not_called()


# --- 3. other errors are not retried ---

def test_a_quota_error_in_the_first_zone_is_not_retried(instance_resource):
    manager = _manager()
    manager._on_instance_created = MagicMock()
    manager.compute_instance.create.side_effect = ResourceExhausted('QUOTA_EXCEEDED: CPUS')

    with pytest.raises(ResourceExhausted):
        manager._build_server(zone_fallback=True)

    assert manager.compute_instance.create.call_count == 1
    assert manager._add_disks.call_count == 1
    assert manager.state_manager.state_transition.call_args_list == [call('building'), call('broken')]
    manager._on_instance_created.assert_not_called()


# --- 4. lab servers ---

def test_without_zone_fallback_the_zone_lookups_are_never_made_and_a_stockout_is_not_retried(instance_resource):
    manager = _manager()
    manager.compute_instance.create.side_effect = RuntimeError(STOCKOUT)

    with pytest.raises(RuntimeError, match='ZONE_RESOURCE_POOL_EXHAUSTED'):
        manager._build_server()

    manager.compute_machine_types.zones_offering.assert_not_called()
    manager.compute_instance.zones_with_instance.assert_not_called()
    assert manager.compute_instance.create.call_count == 1
    assert [c.kwargs['zone'] for c in instance_resource.call_args_list] == [ZONE_A]
    assert manager.state_manager.state_transition.call_args_list == [call('building'), call('broken')]


# --- 5. _build_zones ---

def test_an_existing_vm_pins_the_build_to_its_zone():
    manager = _manager(existing=[ZONE_C, ZONE_B])

    assert manager._build_zones(MACHINE) == [ZONE_C]
    manager.compute_instance.zones_with_instance.assert_called_once_with('kali-lab')
    manager.compute_machine_types.zones_offering.assert_not_called()


def test_a_zone_left_by_an_earlier_check_out_does_not_lead_a_fresh_build():
    manager = _manager(offered=[ZONE_B, ZONE_C])
    manager._server_zone = ZONE_B

    assert manager._build_zones(MACHINE) == [ZONE_A, ZONE_B, ZONE_C]
    manager.compute_machine_types.zones_offering.assert_called_once_with(MACHINE)


def test_the_deployment_zone_leads_when_no_server_zone_is_set():
    manager = _manager(offered=[ZONE_B, ZONE_C])

    assert manager._build_zones(MACHINE) == [ZONE_A, ZONE_B, ZONE_C]


def test_a_failed_offered_zones_lookup_narrows_the_build_to_the_deployment_zone():
    manager = _manager()
    manager.compute_machine_types.zones_offering.side_effect = RuntimeError('aggregatedList unavailable')

    assert manager._build_zones(MACHINE) == [ZONE_A]
    manager.logger.warning.assert_called_once()


def test_a_failed_existing_vm_lookup_still_offers_every_zone():
    manager = _manager()
    manager.compute_instance.zones_with_instance.side_effect = RuntimeError('aggregatedList unavailable')

    assert manager._build_zones(MACHINE) == [ZONE_A, ZONE_B, ZONE_C]
    manager.logger.warning.assert_called_once()


def test_a_vm_created_by_a_concurrent_delivery_pins_the_retry_to_its_zone():
    manager = _manager()
    stockout = RuntimeError('Operation failed with errors: ZONE_RESOURCE_POOL_EXHAUSTED')
    # Before the first insert nothing exists; by the retry the other delivery's VM is in zone C.
    manager.compute_instance.zones_with_instance.side_effect = [[], [ZONE_C]]
    manager.compute_instance.create.side_effect = [stockout, True]

    manager._build_server(zone_fallback=True)

    zones = [c.kwargs['instance_resource'].zone for c in manager.compute_instance.create.call_args_list]
    assert zones == [ZONE_A, ZONE_C]
    assert manager.server_zone == ZONE_C


def test_an_insert_that_times_out_still_records_its_zone():
    manager = _manager()
    stockout = RuntimeError('Operation failed with errors: ZONE_RESOURCE_POOL_EXHAUSTED')
    manager.compute_instance.create.side_effect = [stockout, False]
    manager._on_instance_created = MagicMock()

    with pytest.raises(TimeoutError):
        manager._build_server(zone_fallback=True)

    manager._on_instance_created.assert_called_once_with(ZONE_B)
    manager.state_manager.state_transition.assert_called_with('broken')


# --- 6. ImageTemplateManager ---

def test_the_template_manager_records_the_zone_that_took_the_vm():
    manager = _manager(ImageTemplateManager)
    manager.db = MagicMock()
    manager.collection = DbCollections.IMAGE

    manager._on_instance_created(ZONE_B)

    manager.db.update.assert_called_once_with(
        collection_name=DbCollections.IMAGE, doc_id='kali-lab', data={'zone': ZONE_B},
    )


def test_the_base_manager_hook_writes_nothing():
    manager = _manager()
    manager.db = MagicMock()

    manager._on_instance_created(ZONE_B)

    manager.db.update.assert_not_called()


def test_template_build_requests_zone_fallback():
    manager = _manager(ImageTemplateManager)
    manager._require_image_management = MagicMock()
    manager._build_server = MagicMock()

    manager.build()

    manager._build_server.assert_called_once_with(zone_fallback=True)


def test_a_template_build_that_falls_back_persists_the_successful_zone(instance_resource):
    manager = _manager(ImageTemplateManager)
    manager.db = MagicMock()
    manager.collection = DbCollections.IMAGE
    manager.compute_instance.create.side_effect = [RuntimeError(STOCKOUT), True]

    manager._build_server(zone_fallback=True)

    manager.db.update.assert_called_once_with(
        collection_name=DbCollections.IMAGE, doc_id='kali-lab', data={'zone': ZONE_B},
    )


# --- 7. _load_template_server ---

def _template_manager():
    manager = _manager(ImageTemplateManager)
    manager.image_name = 'image-kali-lab'
    manager.server_spec = SimpleNamespace()
    return manager


def test_loading_a_record_with_a_zone_rebinds_every_zonal_client():
    manager = _template_manager()

    manager._load_template_server(server_spec={'name': 'kali-lab', 'zone': ZONE_C})

    assert manager.server_zone == ZONE_C
    for client in _all_zone_clients(manager):
        client.set_zone.assert_called_once_with(ZONE_C)


def test_loading_a_record_without_a_zone_resets_to_the_deployment_zone_for_warm_reuse():
    manager = _template_manager()

    manager._load_template_server(server_spec={'name': 'one', 'zone': ZONE_C})
    manager._load_template_server(server_spec={'name': 'two'})

    assert manager.server_zone == ZONE_A
    for client in _all_zone_clients(manager):
        assert client.set_zone.call_args_list == [call(ZONE_C), call(ZONE_A)]


# --- 8. BaseComputeAPI ---

def test_set_zone_moves_the_client_and_its_operation_poller():
    api = object.__new__(BaseComputeAPI)
    api.zone = ZONE_A
    api.cloud_ops_mgr = SimpleNamespace(zone=ZONE_A)

    api.set_zone(ZONE_C)

    assert api.zone == ZONE_C
    assert api.cloud_ops_mgr.zone == ZONE_C


def _machine_types_api(scopes):
    api = object.__new__(ComputeMachineTypesAPI)
    api.region = 'us-central1'
    api.project = 'test-dev-787001'
    api.class_name = 'ComputeMachineTypesAPI'
    client = MagicMock()
    client.aggregated_list.return_value = scopes
    api.client = lambda: client
    api._make_request = MagicMock(side_effect=lambda **kwargs: kwargs['client_request'](kwargs['request']))
    return api, client


def _scope(name, machine_types):
    return (name, SimpleNamespace(machine_types=machine_types))


def test_zones_offering_keeps_only_this_regions_nonempty_zone_scopes_sorted():
    api, client = _machine_types_api([
        _scope('zones/us-central1-f', ['n2']),
        _scope('zones/us-central1-a', ['n2']),
        _scope('zones/us-central1-b', []),               # empty scope: no such machine type there
        _scope('zones/us-east1-b', ['n2']),               # another region
        _scope('zones/us-central10-a', ['n2']),           # region prefix needs the dash
        _scope('regions/us-central1', ['n2']),            # not a zone scope
        _scope('global', ['n2']),
        _scope('zones/us-central1-c', ['n2']),
    ])

    assert api.zones_offering('n2-standard-8') == ['us-central1-a', 'us-central1-c', 'us-central1-f']
    request = client.aggregated_list.call_args.args[0]
    assert request.project == 'test-dev-787001'
    assert request.filter == 'name = "n2-standard-8"'


def test_zones_offering_is_empty_when_no_zone_offers_the_machine_type():
    api, _ = _machine_types_api([_scope('zones/us-central1-a', [])])

    assert api.zones_offering('n2-standard-8') == []


# --- 9. NestedBuildMonitor.refresh ---

def _monitor(compute):
    monitor = object.__new__(NestedBuildMonitor)
    monitor.class_name = 'NestedBuildMonitor'
    monitor.env = SimpleNamespace(zone=ZONE_A)
    monitor.logger = MagicMock()
    monitor.db = MagicMock()
    monitor.pubsub_manager = MagicMock()
    monitor.compute_instance = compute
    monitor.validator = ModelValidator(model=NestedBuildStatusModel, log_location='test')
    return monitor


def _refresh(image):
    compute = MagicMock()
    compute.get_guest_attributes.return_value = {}
    monitor = _monitor(compute)
    now = datetime(2026, 10, 17, 12, 0, tzinfo=timezone.utc)
    image = {'name': 'nestlab', 'nested': {'parent_os': 'debian-12'},
             'nested_build': {'phase': 'provisioning', 'guests': {}, 'started_at': now.isoformat()}, **image}
    monitor.refresh(image, now=now)
    return compute


def test_refresh_reads_the_zone_the_build_landed_in():
    compute = _refresh({'zone': ZONE_C})

    compute.set_zone.assert_called_once_with(ZONE_C)
    assert compute.method_calls[0] == call.set_zone(ZONE_C)  # before any guest-attribute read


def test_refresh_falls_back_to_the_deployment_zone_for_a_record_without_a_zone():
    compute = _refresh({})

    compute.set_zone.assert_called_once_with(ZONE_A)


def test_refresh_does_not_touch_the_zone_of_an_inactive_build():
    compute = MagicMock()
    monitor = _monitor(compute)
    monitor.refresh({'name': 'x', 'nested': {'parent_os': 'debian-12'}, 'nested_build': {'phase': 'ready'}})

    compute.set_zone.assert_not_called()

