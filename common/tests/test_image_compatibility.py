"""Architecture validation uses source metadata rather than names or UI claims."""

from types import SimpleNamespace
from unittest.mock import Mock

from google.cloud.compute_v1 import GetMachineTypeRequest, Image, MachineType
import pytest

from common.exceptions import BadRequest, NotFound
from common.utilities.gcp.compute.compute_machine_type import ComputeMachineTypesAPI
from common.utilities.gcp.compute.image_compatibility import compatible_boot_image


SOURCE = 'https://www.googleapis.com/compute/v1/projects/ubuntu-os-cloud/global/images/ubuntu-version'


@pytest.fixture
def clients():
    images = Mock(project='test-dev-787001')
    images.get.return_value = Image(name='ubuntu-version', self_link=SOURCE, architecture='X86_64')
    machines = Mock()
    machines.get_resource.return_value = MachineType(name='e2-standard-2', architecture='X86_64')
    return images, machines


@pytest.mark.parametrize('source', [SOURCE, 'projects/ubuntu-os-cloud/global/images/ubuntu-version'])
def test_exact_source_project_is_resolved_without_shared_fallback(clients, source):
    images, machines = clients
    result = compatible_boot_image(images, machines, source, 'e2-standard-2')
    assert result.self_link == SOURCE
    images.get.assert_called_once_with(resource='ubuntu-version', project='ubuntu-os-cloud', fallback_to_shared=False)
    machines.get_resource.assert_called_once_with(resource='e2-standard-2')


def test_relative_custom_source_uses_the_child_project(clients):
    images, machines = clients
    compatible_boot_image(images, machines, 'global/images/router', 'e2-standard-2')
    images.get.assert_called_once_with(resource='router', project='test-dev-787001', fallback_to_shared=False)


def test_family_is_pinned_to_the_concrete_version_that_was_validated(clients):
    images, machines = clients
    images.get.return_value = SimpleNamespace(image=images.get.return_value)
    result = compatible_boot_image(images, machines, 'projects/ubuntu-os-cloud/global/images/family/ubuntu-2404-lts-amd64', 'e2-standard-2')
    assert result.self_link == SOURCE
    images.get.assert_called_once_with(resource='ubuntu-2404-lts-amd64', project='ubuntu-os-cloud', family=True, fallback_to_shared=False)


@pytest.mark.parametrize('image_arch, machine_arch', [('ARM64', 'X86_64'), ('X86_64', 'ARM64')])
def test_architecture_mismatch_is_rejected_in_both_directions(clients, image_arch, machine_arch):
    images, machines = clients
    images.get.return_value.architecture = image_arch
    machines.get_resource.return_value.architecture = machine_arch
    with pytest.raises(BadRequest, match=f'{image_arch}.*{machine_arch}'):
        compatible_boot_image(images, machines, SOURCE, 'test-machine')


@pytest.mark.parametrize('architecture', ['X86_64', 'ARM64'])
def test_matching_architectures_are_preserved(clients, architecture):
    images, machines = clients
    images.get.return_value.architecture = architecture
    machines.get_resource.return_value.architecture = architecture
    assert compatible_boot_image(images, machines, SOURCE, 'test-machine').architecture == architecture


@pytest.mark.parametrize('machine_name', [
    'e2-standard-2', 'e2-medium', 'e2-custom-2-4096', 'n1-standard-1', 'n2-standard-2',
])
@pytest.mark.parametrize('architecture', ['', 'ARCHITECTURE_UNSPECIFIED', 'UNDEFINED_ARCHITECTURE'])
def test_known_x86_machine_series_work_without_architecture_metadata(clients, machine_name, architecture):
    images, machines = clients
    machines.get_resource.return_value = MachineType(name=machine_name, architecture=architecture)
    assert compatible_boot_image(images, machines, SOURCE, machine_name).architecture == 'X86_64'
    machines.get_resource.assert_called_once_with(resource=machine_name)


def test_missing_image_architecture_is_not_assumed_from_e2(clients):
    images, machines = clients
    images.get.return_value.architecture = ''
    machines.get_resource.return_value = MachineType(name='e2-standard-2')
    with pytest.raises(BadRequest, match='Cannot determine the CPU architecture'):
        compatible_boot_image(images, machines, SOURCE, 'e2-standard-2')


@pytest.mark.parametrize('machine_name', ['', 'e2', 'unknown-standard-2', 'e2a-standard-2', 'n2a-standard-2', 't2a-standard-2'])
def test_unrecognized_machine_series_are_not_assumed_x86(clients, machine_name):
    images, machines = clients
    machines.get_resource.return_value = MachineType(name=machine_name)
    # Only the successfully fetched resource can establish a known series.
    with pytest.raises(BadRequest, match='Cannot determine the CPU architecture of machine type'):
        compatible_boot_image(images, machines, SOURCE, 'e2-standard-2')


def test_explicit_machine_architecture_overrides_series_fallback(clients):
    images, machines = clients
    machines.get_resource.return_value = MachineType(name='e2-standard-2', architecture='ARM64')
    with pytest.raises(BadRequest, match='X86_64.*ARM64'):
        compatible_boot_image(images, machines, SOURCE, 'e2-standard-2')


def test_unrecognized_explicit_machine_architecture_does_not_use_fallback(clients):
    images, machines = clients
    machines.get_resource.return_value = MachineType(name='e2-standard-2', architecture='FUTURE_ARCH')
    with pytest.raises(BadRequest, match='Cannot determine the CPU architecture of machine type'):
        compatible_boot_image(images, machines, SOURCE, 'e2-standard-2')


@pytest.mark.parametrize('source', ['', None, 'ubuntu-version', 'projects/child/global/snapshots/test'])
def test_unverifiable_sources_fail_before_cloud_reads(clients, source):
    images, machines = clients
    with pytest.raises(BadRequest, match='valid Compute image source URL'):
        compatible_boot_image(images, machines, source, 'e2-standard-2')
    images.get.assert_not_called()
    machines.get_resource.assert_not_called()


@pytest.mark.parametrize('error', [NotFound('Image absent'), RuntimeError('Access denied')])
def test_source_lookup_failure_does_not_try_another_project(clients, error):
    images, machines = clients
    images.get.side_effect = error
    with pytest.raises(type(error)):
        compatible_boot_image(images, machines, SOURCE, 'e2-standard-2')
    assert images.get.call_count == 1
    machines.get_resource.assert_not_called()


def test_machine_lookup_failure_is_not_assumed_compatible(clients):
    images, machines = clients
    machines.get_resource.side_effect = RuntimeError('Machine metadata unavailable')
    with pytest.raises(RuntimeError, match='Machine metadata unavailable'):
        compatible_boot_image(images, machines, SOURCE, 'e2-standard-2')


@pytest.mark.parametrize('architecture', ['X86_64', ''])
def test_machine_resource_retains_architecture_and_existing_get_contract(architecture):
    api = object.__new__(ComputeMachineTypesAPI)
    api.project = 'test-dev-787001'
    api.zone = 'us-central1-a'
    api.client = Mock()
    machine = MachineType(name='e2-standard-2', architecture=architecture, memory_mb=8192, guest_cpus=2)
    api._make_request = Mock(return_value=machine)
    assert api.get_resource('e2-standard-2').architecture == architecture
    request = api._make_request.call_args.kwargs['request']
    assert isinstance(request, GetMachineTypeRequest)
    assert (request.project, request.zone, request.machine_type) == ('test-dev-787001', 'us-central1-a', 'e2-standard-2')
    assert api.get('e2-standard-2').name == 'e2-standard-2'
