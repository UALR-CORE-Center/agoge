"""Nested virtualization reaches the instance insert for nested and ip_aliases servers (V1)."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from cloud_fn_utilities.course_objects.compute import base_compute_manager as base_module
from cloud_fn_utilities.course_objects.compute import lab_server_manager as lab_module
from cloud_fn_utilities.course_objects.compute.image_template_manager import ImageTemplateManager
from cloud_fn_utilities.course_objects.compute.lab_server_manager import LabServerManager
from common.constants.database import DbCollections
from common.exceptions import BadRequest

NESTED = {'enable_nested_virtualization': True}


@pytest.fixture
def instance_resource(monkeypatch):
    resource = Mock()
    monkeypatch.setattr(base_module, 'InstanceResource', resource)
    return resource


def _spec(machine_type, min_cpu_platform=None):
    return SimpleNamespace(
        name='nested-host', machine_type=machine_type, min_cpu_platform=min_cpu_platform,
        service_accounts=None, tags=[], disks=[], metadata={'items': []}, can_ip_forward=False,
        network_interfaces=[], build_type=None, delayed_start=False, wireguard_endpoint_id=None,
    )


def _manager(cls, machine_type, nested_host=False, ip_aliases=False, min_cpu_platform=None):
    manager = object.__new__(cls)
    manager.class_name = cls.__name__
    manager.server_name = 'nested-host'
    manager.project = 'test-dev-787001'
    manager.env = SimpleNamespace(project=manager.project, zone='us-central1-a')
    manager.s = base_module.ServerStates
    manager.logger = Mock()
    manager.state_manager = Mock()
    manager.compute_instance = Mock()
    manager.compute_instance.create.return_value = True
    manager.compute_machine_types = Mock()
    manager.compute_machine_types.get.return_value = SimpleNamespace(name=machine_type)
    manager.server_spec = _spec(machine_type, min_cpu_platform)
    manager.nested_host = nested_host
    manager.ip_aliases = False
    manager._add_disks = Mock()
    manager._add_metadata = Mock()

    def add_nics():
        # LabServerManager._add_nics is the only place ip_aliases is set
        manager.ip_aliases = ip_aliases
    manager._add_nics = Mock(side_effect=add_nics)
    manager._dns_record = Mock(return_value=None)
    return manager


def _insert_kwargs(instance_resource):
    return instance_resource.return_value.new.call_args.kwargs


@pytest.mark.parametrize('cls, nested_host, ip_aliases', [
    (ImageTemplateManager, True, False),
    (LabServerManager, True, False),
    (LabServerManager, False, True),
])
@pytest.mark.parametrize('machine_type, platform', [
    ('n2-standard-4', 'Intel Cascade Lake'),
    ('n1-standard-4', 'Intel Haswell'),
])
def test_nested_servers_get_nested_virtualization_and_platform(
    instance_resource, cls, nested_host, ip_aliases, machine_type, platform,
):
    manager = _manager(cls, machine_type, nested_host=nested_host, ip_aliases=ip_aliases)

    manager._build_server(finalize_state=False)

    kwargs = _insert_kwargs(instance_resource)
    assert kwargs['advanced_machine_features'] == NESTED
    assert kwargs['min_cpu_platform'] == platform
    assert kwargs['machine_type'] == machine_type


def test_explicit_platform_is_kept_for_nested_server(instance_resource):
    manager = _manager(ImageTemplateManager, 'n2-standard-4', nested_host=True, min_cpu_platform='Intel Ice Lake')

    manager._build_server(finalize_state=False)

    assert _insert_kwargs(instance_resource)['min_cpu_platform'] == 'Intel Ice Lake'


@pytest.mark.parametrize('cls', [ImageTemplateManager, LabServerManager])
def test_e2_machine_type_is_rejected_before_any_side_effect(instance_resource, cls):
    manager = _manager(cls, 'e2-standard-4', nested_host=True)

    with pytest.raises(BadRequest):
        manager._build_server(finalize_state=False)

    manager.state_manager.state_transition.assert_not_called()
    manager._add_disks.assert_not_called()
    manager._add_nics.assert_not_called()
    manager.compute_instance.create.assert_not_called()


def test_standard_template_server_gets_neither(instance_resource):
    manager = _manager(ImageTemplateManager, 'e2-standard-2')

    manager._build_server(finalize_state=False)

    kwargs = _insert_kwargs(instance_resource)
    assert kwargs['advanced_machine_features'] is None
    assert kwargs['min_cpu_platform'] is None


@pytest.mark.parametrize('image_doc, expected', [
    ({'name': 'nested-hv', 'nested': {'parent_os': 'debian-12'}}, True),
    ({'name': 'ubuntu', 'nested': None}, False),
    ({'name': 'ubuntu'}, False),
])
def test_template_load_sets_nested_host_from_image_record(image_doc, expected):
    manager = object.__new__(ImageTemplateManager)
    manager.server_name = image_doc['name']
    manager.image_name = f"image-{image_doc['name']}"
    manager.server_spec = SimpleNamespace()
    manager.nested_host = not expected

    manager._load_template_server(server_spec=image_doc)

    assert manager.nested_host is expected


@pytest.mark.parametrize('image, record, expected', [
    ('image-nested-hv', {'nested': {'parent_os': 'debian-12'}}, True),
    ('image-ubuntu', {'name': 'ubuntu'}, False),
    ('image-shared-elsewhere', None, False),
    (None, None, False),
])
def test_lab_load_sets_nested_host_from_image_record(monkeypatch, image, record, expected):
    monkeypatch.setattr(lab_module, 'AssessmentManager', Mock())
    manager = object.__new__(LabServerManager)
    manager.class_name = 'LabServerManager'
    manager.env_dict = {}
    manager.collection = DbCollections.SERVER
    manager.state_manager = Mock()
    manager.server_spec = SimpleNamespace()
    manager.db = Mock()
    manager.db.get.return_value = record

    manager.load('nested-host', server_spec={'image': image, 'parent_id': 'abcdefghij'})

    assert manager.nested_host is expected
    if image:
        manager.db.get.assert_called_once_with(
            collection_name=DbCollections.IMAGE, doc_id=image.removeprefix('image-'),
        )
    else:
        manager.db.get.assert_not_called()


@pytest.mark.parametrize('image, doc_id', [
    ('image-kali-2026', 'kali-2026'),
    ('kali-2026', 'kali-2026'),
    ('projects/test-dev-787001/global/images/image-guac-test-dev-787001', 'guac-test-dev-787001'),
    ('https://www.googleapis.com/compute/v1/projects/test-dev-787001/global/images/image-kali-2026', 'kali-2026'),
    ('projects/ubuntu-os-cloud/global/images/family/ubuntu-2404-lts-amd64', 'ubuntu-2404-lts-amd64'),
])
def test_image_is_nested_looks_up_a_valid_document_id(image, doc_id):
    # A Compute path used as-is is an odd-length Firestore path and raises ValueError.
    manager = object.__new__(LabServerManager)
    manager.db = Mock()
    manager.db.get.return_value = {'nested': True}
    assert manager._image_is_nested(image) is True
    manager.db.get.assert_called_once_with(collection_name=DbCollections.IMAGE, doc_id=doc_id)
