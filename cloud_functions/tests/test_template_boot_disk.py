"""Verify template boot sources with real Compute protos and no cloud writes."""

from types import SimpleNamespace
from unittest.mock import Mock

from google.cloud.compute_v1 import AttachedDisk, Disk, Image, Instance, InsertInstanceRequest
from google.protobuf.json_format import MessageToDict
import pytest

from cloud_fn_utilities.course_objects.compute import image_template_manager as template_module
from cloud_fn_utilities.course_objects.compute.image_template_manager import ImageTemplateManager
from common.constants.google import ImageSource
from common.exceptions import Conflict, NotFound
from common.utilities.gcp.compute.compute_instance import ComputeInstanceAPI
from common.utilities.gcp.compute.resources.attached_disk_resource import AttachedDiskResource
from common.utilities.gcp.compute.resources.instance_resource import InstanceResource


UBUNTU = 'https://www.googleapis.com/compute/v1/projects/ubuntu-os-cloud/global/images/ubuntu-2404-noble-amd64-v20260909'
DISK = 'projects/test-dev-787001/zones/us-central1-a/disks/wireguard-server-disk'


@pytest.fixture
def manager(monkeypatch):
    monkeypatch.setattr(template_module.time, 'sleep', Mock())
    manager = object.__new__(ImageTemplateManager)
    manager.server_name = 'wireguard-server'
    manager.project = 'test-dev-787001'
    manager.env = SimpleNamespace(project=manager.project, zone='us-central1-a')
    manager.server_spec = SimpleNamespace(self_link=UBUNTU, add_disk='20', image='image-wireguard-server')
    manager.compute_disk = Mock()
    manager.compute_disk.get.side_effect = NotFound('No disk')
    manager.compute_image = Mock()
    manager.compute_instance = Mock()
    manager.compute_instance.get.side_effect = NotFound('No VM')
    manager.logger = Mock()
    manager.class_name = 'ImageTemplateManager'
    return manager


def retained_disk(manager, image=UBUNTU, attached=True, disk_path=DISK):
    manager.compute_disk.get.side_effect = None
    manager.compute_disk.get.return_value = Disk(
        name='wireguard-server-disk', source_image=image, status='READY',
    )
    if attached:
        manager.compute_instance.get.side_effect = None
        manager.compute_instance.get.return_value = Instance(
            name='wireguard-server', status='RUNNING',
            disks=[AttachedDisk(boot=True, source=disk_path)],
        )


def test_selected_ubuntu_image_reaches_actual_instance_insert_request(manager):
    manager._add_disks()
    instance = InstanceResource(zone=manager.env.zone).new(
        name=manager.server_name, machine_type='e2-standard-2',
        disks=manager.server_spec.disks, metadata={'items': []}, service_accounts=[],
    )
    api = object.__new__(ComputeInstanceAPI)
    api.project = manager.env.project
    api.zone = manager.env.zone
    api.client = Mock()
    api._make_request = Mock(return_value=True)

    api.create(resource_name=manager.server_name, instance_resource=instance)

    request = api._make_request.call_args.kwargs['request']
    payload = MessageToDict(InsertInstanceRequest.pb(request))
    disk = payload['instanceResource']['disks'][0]
    assert disk['initializeParams']['sourceImage'] == UBUNTU
    assert disk['initializeParams']['diskSizeGb'] == '20'
    assert disk['initializeParams']['diskName'] == 'wireguard-server-disk'
    assert disk['boot'] is True
    assert disk['autoDelete'] is True
    assert payload['project'] == manager.env.project
    assert payload['zone'] == manager.env.zone


@pytest.mark.parametrize('source', [None, '', '  \n '])
@pytest.mark.parametrize('source_type', [ImageSource.IMAGE, ImageSource.SNAPSHOT])
def test_source_free_disk_initialization_is_rejected(source, source_type):
    with pytest.raises(ValueError, match='non-empty image or snapshot source'):
        AttachedDiskResource().initialized_params(source=source, source_type=source_type, disk_size_gb=20)


def test_missing_link_from_compute_image_cannot_produce_a_blank_boot_disk(manager):
    manager.compute_image.get.return_value = Image(name='image-wireguard-server')
    with pytest.raises(ValueError, match='non-empty image or snapshot source'):
        manager._get_boot_disk(disk_size_gb=20)


def test_missing_image_lookup_propagates_without_creating_a_disk(manager):
    manager.compute_image.get.side_effect = NotFound('Image absent')
    with pytest.raises(NotFound, match='Image absent'):
        manager._get_boot_disk(disk_size_gb=20)


def test_snapshot_initialization_keeps_its_snapshot_source():
    source = 'projects/test-dev-787001/global/snapshots/wireguard-backup'
    params = AttachedDiskResource().initialized_params(source=source, source_type=ImageSource.SNAPSHOT)
    assert params.source_snapshot == source
    assert not params.source_image


@pytest.mark.parametrize('image', ['', UBUNTU, 'projects/other/global/images/wrong-image'])
def test_orphan_disk_is_never_silently_reused(manager, image):
    retained_disk(manager, image=image, attached=False)
    with pytest.raises(Conflict, match='disk was retained'):
        manager._add_disks()
    manager.compute_disk.delete.assert_not_called()
    manager.compute_instance.create.assert_not_called()


@pytest.mark.parametrize('image', ['', 'projects/other/global/images/wrong-image'])
def test_running_vm_with_wrong_or_unverifiable_boot_source_is_rejected(manager, image):
    retained_disk(manager, image=image)
    with pytest.raises(Conflict, match='cannot be verified'):
        manager._add_disks()


@pytest.mark.parametrize('path', [DISK, 'https://www.googleapis.com/compute/v1/' + DISK])
def test_existing_matching_vm_allows_duplicate_build_reconciliation(manager, path):
    retained_disk(manager, image=UBUNTU.split('/compute/v1/')[1], disk_path=path)
    manager._add_disks()
    assert manager.server_spec.disks[0].initialize_params.source_image == UBUNTU


@pytest.mark.parametrize('path', [DISK.replace('test-dev-787001', 'other-child'), DISK.replace('us-central1-a', 'us-central1-b')])
def test_same_named_boot_disk_in_other_project_or_zone_is_rejected(manager, path):
    retained_disk(manager, disk_path=path)
    with pytest.raises(Conflict, match='cannot be verified'):
        manager._add_disks()


@pytest.mark.parametrize('status', ['CREATING', 'READY'])
def test_duplicate_delivery_waits_for_a_creating_disk_and_vm(manager, monkeypatch, status):
    retained_disk(manager)
    manager.compute_disk.get.side_effect = [
        Disk(name='wireguard-server-disk', status=status),
        manager.compute_disk.get.return_value,
    ]
    manager.compute_instance.get.side_effect = [NotFound('VM not visible yet'), manager.compute_instance.get.return_value]
    sleep = Mock()
    monkeypatch.setattr(template_module.time, 'sleep', sleep)
    manager._add_disks()
    sleep.assert_called_once_with(1)


def test_disk_read_permission_failure_stops_build(manager):
    manager.compute_disk.get.side_effect = RuntimeError('Access denied')
    with pytest.raises(RuntimeError, match='Access denied'):
        manager._add_disks()
    manager.compute_instance.create.assert_not_called()


def test_in_progress_disk_retries_are_bounded(manager, monkeypatch):
    manager.compute_disk.get.side_effect = None
    manager.compute_disk.get.return_value = Disk(name='wireguard-server-disk', status='CREATING')
    sleep = Mock()
    monkeypatch.setattr(template_module.time, 'sleep', sleep)
    with pytest.raises(Conflict, match='still being created'):
        manager._add_disks()
    assert sleep.call_count == 3
    manager.compute_disk.delete.assert_not_called()
