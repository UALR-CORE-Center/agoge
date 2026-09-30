"""Nested virtualization on a lab server.

A lab that ships its own targets (Metasploitable, a vulnerable AD forest, anything driven by
libvirt) needs /dev/kvm inside the guest, and Google only provides that when the instance is
created with advanced_machine_features.enable_nested_virtualization. The flag has no effect after
creation, so getting it wrong means a VM that boots, looks healthy, and cannot run the lab.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from cloud_fn_utilities.course_objects.compute.base_compute_manager import BaseComputeManager
from common.constants.build_constants import BuildConstants
from common.constants.states import ServerStates
from common.exceptions.agoge import BadRequest


def _manager(machine_type, nested_virtualization=False, ip_aliases=False, min_cpu_platform=""):
    """A BaseComputeManager wired up just far enough to run _build_server."""
    manager = object.__new__(BaseComputeManager)
    manager.class_name = "BaseComputeManager"
    manager.server_name = "metasploitable"
    manager.project = "test-project"
    manager.env = SimpleNamespace(zone="us-central1-a")
    manager.logger = MagicMock()
    manager.state_manager = MagicMock()
    manager.dns_manager = MagicMock()
    manager.s = ServerStates
    manager.ip_aliases = ip_aliases

    manager.compute_instance = MagicMock()
    manager.compute_instance.SERVICE_ACCOUNT_CONFIG = []
    manager.compute_instance.create.return_value = True

    manager._add_disks = MagicMock()
    manager._add_metadata = MagicMock()
    manager._add_nics = MagicMock()
    manager._dns_record = MagicMock(return_value=None)
    # The real lookup calls the Compute API; it returns the resolved machine type name.
    manager._lookup_machine_type = MagicMock(return_value=machine_type)

    manager.server_spec = SimpleNamespace(
        name="metasploitable",
        machine_type=machine_type,
        nested_virtualization=nested_virtualization,
        min_cpu_platform=min_cpu_platform,
        service_accounts=None,
        tags=[],
        disks=[],
        metadata={"items": []},
        can_ip_forward=False,
        network_interfaces=[],
        build_type=None,
        machine_image=None,
        delayed_start=False,
    )
    return manager


def _built_instance(manager):
    manager._build_server()
    return manager.compute_instance.create.call_args.kwargs["instance_resource"]


def test_nested_virtualization_flag_reaches_the_instance():
    manager = _manager("n2-standard-8", nested_virtualization=True)

    instance = _built_instance(manager)

    assert instance.advanced_machine_features.enable_nested_virtualization is True


def test_nested_virtualization_is_off_by_default():
    manager = _manager("e2-medium")

    instance = _built_instance(manager)

    assert instance.advanced_machine_features.enable_nested_virtualization is False


def test_ip_aliases_still_imply_nested_virtualization():
    """The original trigger. Specs in the field rely on it, so it has to keep working."""
    manager = _manager("n2-standard-4", ip_aliases=True)

    instance = _built_instance(manager)

    assert instance.advanced_machine_features.enable_nested_virtualization is True


def test_min_cpu_platform_floor_is_applied_when_the_spec_leaves_it_blank():
    """The spec editor writes "" rather than None, and the floor used to be assigned back onto
    server_spec after it had already been read, so it never reached the instance either way."""
    manager = _manager("n1-standard-4", nested_virtualization=True, min_cpu_platform="")

    instance = _built_instance(manager)

    assert instance.min_cpu_platform == "Intel Haswell"


def test_explicit_min_cpu_platform_is_not_overridden():
    manager = _manager("n2-standard-4", nested_virtualization=True, min_cpu_platform="Intel Ice Lake")

    instance = _built_instance(manager)

    assert instance.min_cpu_platform == "Intel Ice Lake"


def test_nested_virtualization_on_e2_fails_the_build_instead_of_building_a_useless_server():
    manager = _manager("e2-standard-8", nested_virtualization=True)

    with pytest.raises(BadRequest):
        manager._build_server()

    manager.compute_instance.create.assert_not_called()
    manager.state_manager.state_transition.assert_called_with(ServerStates.BROKEN)


def test_unresolvable_machine_type_falling_back_to_e2_does_not_silently_drop_the_flag():
    """_lookup_machine_type falls back to e2-medium when it cannot resolve the request. Checking
    the requested value rather than the resolved one would build an E2 with no KVM and no error."""
    manager = _manager("n2-standard-8", nested_virtualization=True)
    manager._lookup_machine_type = MagicMock(return_value="e2-medium")

    with pytest.raises(BadRequest):
        manager._build_server()


@pytest.mark.parametrize(
    "machine_type,supported",
    [
        ("n1-standard-1", True),
        ("n2-standard-8", True),
        ("e2-medium", False),
        ("e2-standard-8", False),
        ("", False),
        (None, False),
    ],
)
def test_supported_families(machine_type, supported):
    assert BuildConstants.NestedVirtualization.is_supported(machine_type) is supported
