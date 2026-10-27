"""A server whose instance insert Google refuses is marked BROKEN, not left BUILDING with no VM."""
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

import pytest

from cloud_fn_utilities.course_objects.compute import base_compute_manager as base_compute_module
from cloud_fn_utilities.course_objects.compute.base_compute_manager import BaseComputeManager
from common.exceptions import ResourceExhausted

STOCKOUT = ("Operation failed with errors: ZONE_RESOURCE_POOL_EXHAUSTED_WITH_DETAILS: The zone "
            "'projects/test-dev-787001/zones/us-central1-a' does not have enough resources available to "
            "fulfill the request.  '(resource type:compute)'.")


def _manager():
    manager = object.__new__(BaseComputeManager)
    manager.class_name = 'BaseComputeManager'
    manager.server_name = 'kali-win11-scan-lab3'
    manager.project = 'test-dev-787001'
    manager.env = SimpleNamespace(zone='us-central1-a')
    manager.logger = MagicMock()
    manager.state_manager = MagicMock()
    manager.s = SimpleNamespace(BUILDING='building', RUNNING='running', BROKEN='broken')
    manager._add_disks = MagicMock()
    manager._add_metadata = MagicMock()
    manager._add_nics = MagicMock()
    manager._lookup_machine_type = lambda value: value
    manager._dns_record = MagicMock(return_value=False)
    manager.ip_aliases = False
    manager.nested_host = True
    manager.compute_instance = MagicMock()
    manager.compute_instance.SERVICE_ACCOUNT_CONFIG = []
    manager.server_spec = SimpleNamespace(
        name=manager.server_name, machine_type='n2-standard-8', service_accounts=None, tags=[],
        min_cpu_platform=None, disks=[], metadata={'items': []}, can_ip_forward=False,
        network_interfaces=[], build_type=None, machine_image=None, delayed_start=False,
        wireguard_endpoint_id=None,
    )
    return manager


@pytest.mark.parametrize('error', [RuntimeError(STOCKOUT), ResourceExhausted('QUOTA_EXCEEDED: CPUS')])
def test_a_refused_insert_marks_the_server_broken_and_raises(error):
    manager = _manager()
    manager.compute_instance.create.side_effect = error

    with patch.object(base_compute_module, 'InstanceResource', return_value=MagicMock()):
        with pytest.raises(type(error)):
            manager._build_server()

    assert manager.state_manager.state_transition.call_args_list == [call('building'), call('broken')]
    manager._dns_record.assert_not_called()
