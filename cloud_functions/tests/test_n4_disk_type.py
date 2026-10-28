"""N4 attaches only Hyperdisk, so its boot, extra, and restored disks use hyperdisk-balanced; other series keep
Compute Engine's default disk type."""

from types import SimpleNamespace
from unittest.mock import Mock

from google.cloud.compute_v1 import Image, InsertInstanceRequest, MachineType
from google.protobuf.json_format import MessageToDict
import pytest

from cloud_fn_utilities.course_objects.compute import image_template_manager as template_module
from cloud_fn_utilities.course_objects.compute.image_template_manager import ImageTemplateManager
from cloud_fn_utilities.course_objects.compute.snapshot_manager import SnapshotManager
from common.constants.pub_sub import PubSub
from common.exceptions import NotFound
from common.utilities.gcp.compute.compute_disk import ComputeDiskAPI
from common.utilities.gcp.compute.compute_instance import ComputeInstanceAPI
from common.utilities.gcp.compute.compute_machine_type import disk_type_for
from common.utilities.gcp.compute.resources.attached_disk_resource import AttachedDiskResource
from common.utilities.gcp.compute.resources.disks_resource import DiskResource
from common.utilities.gcp.compute.resources.instance_resource import InstanceResource

PROJECT = 'test-dev-787001'
ZONE = 'us-central1-a'
UBUNTU = 'https://www.googleapis.com/compute/v1/projects/ubuntu-os-cloud/global/images/ubuntu-2404-noble-amd64-v20260909'


@pytest.mark.parametrize('machine_type, expected', [
    ('n4-standard-8', 'hyperdisk-balanced'),
    (f'https://www.googleapis.com/compute/v1/projects/{PROJECT}/zones/{ZONE}/machineTypes/n4-standard-4',
     'hyperdisk-balanced'),
    ('n2-standard-8', None),
    ('n1-standard-4', None),
    ('e2-medium', None),
    (None, None),
])
def test_disk_type_for(machine_type, expected):
    assert disk_type_for(machine_type) == expected


@pytest.fixture
def manager(monkeypatch):
    monkeypatch.setattr(template_module.time, 'sleep', Mock())
    manager = object.__new__(ImageTemplateManager)
    manager.server_name = 'nested-host'
    manager.project = PROJECT
    manager.env = SimpleNamespace(project=PROJECT, zone=ZONE)
    manager.server_spec = SimpleNamespace(self_link=UBUNTU, add_disk='40', image='image-nested-host',
                                          machine_type='n4-standard-8')
    manager.compute_disk = Mock()
    manager.compute_disk.get.side_effect = NotFound('No disk')
    manager.compute_image = Mock()
    manager.compute_image.get.return_value = Image(name='ubuntu-test', self_link=UBUNTU, architecture='X86_64')
    manager.compute_machine_types = Mock()
    manager.compute_machine_types.get_resource.return_value = MachineType(name='n4-standard-8',
                                                                          architecture='X86_64')
    manager.state_manager = Mock()
    manager.compute_instance = Mock()
    manager.compute_instance.get.side_effect = NotFound('No VM')
    manager.logger = Mock()
    manager.class_name = 'ImageTemplateManager'
    return manager


def _boot_disk_payload(manager, machine_type):
    instance = InstanceResource(zone=ZONE).new(
        name=manager.server_name, machine_type=machine_type,
        disks=manager.server_spec.disks, metadata={'items': []}, service_accounts=[],
    )
    api = object.__new__(ComputeInstanceAPI)
    api.project = PROJECT
    api.zone = ZONE
    api.client = Mock()
    api._make_request = Mock(return_value=True)
    api.create(resource_name=manager.server_name, instance_resource=instance)
    request = api._make_request.call_args.kwargs['request']
    return MessageToDict(InsertInstanceRequest.pb(request))['instanceResource']['disks'][0]['initializeParams']


def test_n4_boot_disk_is_hyperdisk_balanced(manager):
    manager.disk_type = disk_type_for('n4-standard-8')
    manager._add_disks()

    params = _boot_disk_payload(manager, 'n4-standard-8')
    assert params['diskType'] == f'zones/{ZONE}/diskTypes/hyperdisk-balanced'
    assert params['sourceImage'] == UBUNTU


def test_other_boot_disks_keep_the_default_type(manager):
    manager.disk_type = disk_type_for('n2-standard-8')
    manager._add_disks()

    assert 'diskType' not in _boot_disk_payload(manager, 'n2-standard-8')


def test_disk_type_needs_a_zone():
    with pytest.raises(ValueError, match='zone'):
        AttachedDiskResource().initialized_params(source=UBUNTU, disk_type='hyperdisk-balanced')


@pytest.mark.parametrize('disk_type, source, expected', [
    ('hyperdisk-balanced', None, f'projects/{PROJECT}/zones/{ZONE}/diskTypes/hyperdisk-balanced'),
    (None, None, f'projects/{PROJECT}/zones/{ZONE}/diskTypes/pd-standard'),
    ('hyperdisk-balanced', UBUNTU, f'projects/{PROJECT}/zones/{ZONE}/diskTypes/hyperdisk-balanced'),
    (None, UBUNTU, ''),
])
def test_disk_resource_type(disk_type, source, expected):
    disk = DiskResource(project=PROJECT, zone=ZONE).new(name='nested-host-disk-1', size_gb=40, source=source,
                                                        disk_type=disk_type)

    assert disk.type_ == expected


@pytest.mark.parametrize('disk_type, expected', [
    ('hyperdisk-balanced', f'projects/{PROJECT}/zones/{ZONE}/diskTypes/hyperdisk-balanced'),
    (None, ''),
])
def test_compute_disk_create_sets_the_type(disk_type, expected):
    api = object.__new__(ComputeDiskAPI)
    api.project = PROJECT
    api.zone = ZONE
    api.client = Mock()
    api._make_request = Mock(return_value=True)

    api.create(resource_name='restored-disk', source_snapshot='snap', wait=False, disk_type=disk_type)

    assert api._make_request.call_args.kwargs['disk_resource'].type_ == expected


@pytest.mark.parametrize('machine_type, expected', [
    (f'https://www.googleapis.com/compute/v1/projects/{PROJECT}/zones/{ZONE}/machineTypes/n4-standard-8',
     'hyperdisk-balanced'),
    (f'https://www.googleapis.com/compute/v1/projects/{PROJECT}/zones/{ZONE}/machineTypes/n2-standard-8', None),
])
def test_restored_boot_disk_matches_the_instance_machine_type(machine_type, expected):
    manager = object.__new__(SnapshotManager)
    manager.class_name = 'SnapshotManager'
    manager.server_name = 'nested-host'
    manager.server_type = PubSub.CourseObjects.LAB_SERVER
    manager.debug = True
    manager.logger = Mock()
    manager._get_snapshot_record = Mock(return_value=SimpleNamespace(
        snapshots=[SimpleNamespace(name='snap-1', creation_timestamp=1)]
    ))
    manager.compute_snapshot = Mock()
    manager.compute_snapshot.get.return_value = SimpleNamespace(self_link='projects/p/global/snapshots/snap-1')
    manager.compute_instance = Mock()
    manager.compute_instance.get.return_value = SimpleNamespace(machine_type=machine_type)
    manager.compute_instance.detach_boot_disk.return_value = ('old-disk', 'device')
    manager.compute_disk = Mock()
    manager._stop_server = Mock()
    manager._start_server = Mock()
    manager._get_attached_disk = Mock()

    manager.restore_from_snapshot()

    assert manager.compute_disk.create.call_args.kwargs['disk_type'] == expected
