"""Keep template boot sources valid until a custom image has been checked in."""

from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from google.cloud.compute_v1 import Image

from cloud_fn_utilities.course_objects.compute.image_template_manager import ImageTemplateManager
from cloud_fn_utilities.course_objects.compute.snapshot_manager import SnapshotManager
from common.constants.database import DbCollections
from common.constants.pub_sub import PubSub
from common.constants.states import ImageStatus, ServerStates
from common.exceptions import BadRequest, NotFound, OperationTimeout
from common.utilities.gcp.cloud_logger import LoggerNames
from common.utilities.gcp.compute.compute_image import ComputeImageAPI


PUBLIC_SOURCE = (
    'https://www.googleapis.com/compute/v1/projects/ubuntu-os-cloud/global/images/'
    'ubuntu-2404-noble-amd64-v20260901'
)
CUSTOM_SOURCE = ComputeImageAPI.self_link('image-wireguard-server', 'test-dev-787001')
SHARED_SOURCE = ComputeImageAPI.self_link('image-wireguard-server', 'agoge-shared-resources')


@pytest.fixture
def template():
    manager = object.__new__(ImageTemplateManager)
    manager.server_name = 'wireguard-server'
    manager.image_name = 'image-wireguard-server'
    manager.user = 'instructor@example.edu'
    manager.collection = DbCollections.IMAGE
    manager.log_name = LoggerNames.CLOUD_FN
    manager.logger = Mock()
    manager.class_name = 'ImageTemplateManager'
    manager.parent_build_id = None
    manager.debug = True
    manager.s = ServerStates
    manager.state_manager = Mock()
    manager.dns_manager = Mock()
    manager.pubsub_manager = Mock()
    manager.compute_instance = Mock()
    manager.compute_instance.delete.return_value = True
    manager.snapshot_manager = Mock()
    manager.snapshot_manager.create_snapshot.return_value = 'wireguard-server-auto-0'
    manager.compute_snapshot = Mock()
    manager.compute_snapshot.get.return_value = SimpleNamespace(self_link='projects/test-dev-787001/global/snapshots/wireguard-server-auto-0')
    manager.server_spec = SimpleNamespace(description='WireGuard template server')
    manager._build_server = Mock()
    manager._start_server = Mock()
    manager._stop_server = Mock()
    manager.env = SimpleNamespace(project='test-dev-787001')
    manager.compute_image = Mock()
    manager.compute_image.self_link.side_effect = ComputeImageAPI.self_link
    manager.compute_image.create.return_value = True
    manager.compute_image.delete.return_value = True
    manager.compute_image.get.return_value = Image(name=manager.image_name, self_link=CUSTOM_SOURCE, status='READY')
    manager._dns_record = Mock(return_value='wireguard-server.agoge-labs.com.')
    record = {
        'name': manager.server_name,
        'machine_type': 'e2-standard-2',
        'description': 'WireGuard template server',
        'tags': [],
        'image': PUBLIC_SOURCE,
        'os': 'linux',
        'add_disk': '20',
        'human_interaction': [],
        'status': ImageStatus.CHECKED_OUT.value,
        'state': ServerStates.RUNNING.value,
        'self_link': PUBLIC_SOURCE,
        'image_exists': False,
        'base_family': 'ubuntu-2404-lts-amd64',
    }
    manager.db = Mock()
    manager.db.get.side_effect = lambda **kwargs: deepcopy(record)

    def update(collection_name, doc_id, data):
        assert collection_name == DbCollections.IMAGE
        assert doc_id == manager.server_name
        record.update(deepcopy(data))

    manager.db.update.side_effect = update
    return manager, record


@pytest.mark.parametrize('checkouts', [1, 2], ids=['first-checkout', 'repeated-checkout'])
def test_checkout_preserves_public_source_until_first_check_in(template, checkouts):
    manager, record = template

    for _ in range(checkouts):
        manager._update_record_status(ImageStatus.CHECKED_OUT)

    assert record['self_link'] == PUBLIC_SOURCE
    assert record['image_exists'] is False
    assert record['image'] == manager.image_name
    assert record['status'] == ImageStatus.CHECKED_OUT.value
    assert record['in_use_by'] == manager.user
    manager.compute_image.self_link.assert_not_called()


def test_checkout_preserves_existing_custom_source(template):
    manager, record = template
    shared_source = ComputeImageAPI.self_link('image-wireguard-server', 'agoge-shared-resources')
    record.update(self_link=shared_source, image_exists=True, status=ImageStatus.CHECKED_IN.value)

    manager._update_record_status(ImageStatus.CHECKED_OUT)

    assert record['self_link'] == shared_source
    assert record['image_exists'] is True
    assert record['status'] == ImageStatus.CHECKED_OUT.value


def test_check_in_switches_to_the_created_custom_image(template):
    manager, record = template
    manager._update_record_status(ImageStatus.CHECKED_OUT)

    manager.check_in()

    assert record['self_link'] == CUSTOM_SOURCE
    assert record['image_exists'] is True
    assert record['status'] == ImageStatus.CHECKED_IN.value
    assert record['state'] == ServerStates.START.value
    assert record['in_use_by'] is None
    assert record['dns_record'] is None

    manager.compute_image.get.assert_called_once_with(
        manager.image_name, project=manager.env.project, fallback_to_shared=False,
    )

    manager.check_out()

    assert record['self_link'] == CUSTOM_SOURCE
    assert record['image_exists'] is True


@pytest.mark.parametrize('source,exists', [(PUBLIC_SOURCE, False), (CUSTOM_SOURCE, True)])
def test_cancel_preserves_source_and_allows_checkout_again(template, source, exists):
    manager, record = template
    record.update(self_link=source, image_exists=exists)

    manager.cancel()

    assert record['self_link'] == source
    assert record['image_exists'] is exists
    assert record['status'] == ImageStatus.CHECKED_IN.value
    assert record['in_use_by'] is None
    manager.compute_image.create.assert_not_called()
    manager.compute_image.delete.assert_not_called()

    manager.check_out()

    assert record['self_link'] == source
    assert record['image_exists'] is exists
    assert record['status'] == ImageStatus.CHECKED_OUT.value
    assert record['in_use_by'] == manager.user
    manager._build_server.assert_called_once()


def test_cancel_keeps_reservation_and_dns_when_server_deletion_fails(template):
    manager, record = template
    manager._update_record_status(ImageStatus.CHECKED_OUT)
    original = deepcopy(record)
    manager.compute_instance.delete.return_value = False

    with pytest.raises(OperationTimeout, match='Retry canceling'):
        manager.cancel()

    assert record == original
    manager.compute_instance.delete.assert_called_once_with(manager.server_name, wait=True)
    manager.dns_manager.delete_dns.assert_not_called()
    manager.state_manager.state_transition.assert_not_called()


def test_failed_server_deletion_marks_broken_when_state_transition_requested(template):
    manager, _ = template
    manager.compute_instance.delete.return_value = False

    assert manager.delete_server() is False

    assert [call.args[0] for call in manager.state_manager.state_transition.call_args_list] == [
        ServerStates.DELETING, ServerStates.BROKEN,
    ]
    manager.dns_manager.delete_dns.assert_not_called()


@pytest.mark.parametrize('action', [
    'build', 'check_out', 'check_in', 'create_production_image', 'cancel',
    'delete', 'delete_image', 'delete_server', 'start_server', 'stop_server',
])
@pytest.mark.parametrize('legacy', [False, True])
def test_shared_image_management_is_rejected_before_side_effects(template, action, legacy):
    manager, record = template
    record.update(self_link=SHARED_SOURCE, image_exists=True)
    if legacy:
        record.pop('image_exists')
    original = deepcopy(record)

    with pytest.raises(BadRequest, match='copied.*new name'):
        getattr(manager, action)()

    assert record == original
    manager.compute_image.create.assert_not_called()
    manager.compute_image.delete.assert_not_called()
    manager.compute_instance.delete.assert_not_called()
    manager.snapshot_manager.create_snapshot.assert_not_called()
    manager.snapshot_manager.delete_snapshots.assert_not_called()
    manager._build_server.assert_not_called()
    manager._start_server.assert_not_called()
    manager._stop_server.assert_not_called()
    manager.db.update.assert_not_called()
    manager.db.delete.assert_not_called()


def test_shared_project_can_manage_its_own_image(template):
    manager, record = template
    record.update(self_link=SHARED_SOURCE, image_exists=True)
    manager.env.project = 'agoge-shared-resources'

    manager.check_out()

    manager._build_server.assert_called_once()
    assert record['self_link'] == SHARED_SOURCE


@pytest.mark.parametrize('failure', ['delete', 'create', 'lookup', 'not-ready', 'wrong-project'])
def test_failed_check_in_keeps_server_reserved_and_source_unchanged(template, failure):
    manager, record = template
    manager._update_record_status(ImageStatus.CHECKED_OUT)
    original = deepcopy(record)
    if failure == 'delete':
        manager.compute_image.delete.return_value = False
    elif failure == 'create':
        manager.compute_image.create.return_value = False
    elif failure == 'lookup':
        manager.compute_image.get.side_effect = NotFound('No local image')
    elif failure == 'not-ready':
        manager.compute_image.get.return_value.status = 'PENDING'
    else:
        manager.compute_image.get.return_value.self_link = SHARED_SOURCE

    with pytest.raises((OperationTimeout, NotFound)):
        manager.check_in()

    assert record == original
    manager.compute_instance.delete.assert_not_called()
    manager.pubsub_manager.msg.assert_not_called()
    if failure == 'delete':
        manager.compute_image.create.assert_not_called()


@pytest.mark.parametrize('action', ['create_snapshot', 'restore_from_snapshot'])
def test_shared_template_snapshots_cannot_bypass_management_guard(template, action):
    template_manager, record = template
    record.update(self_link=SHARED_SOURCE, image_exists=True)
    manager = object.__new__(SnapshotManager)
    manager.server_name = template_manager.server_name
    manager.env = template_manager.env
    manager.db = template_manager.db
    manager.server_type = PubSub.CourseObjects.TEMPLATE_SERVER

    with pytest.raises(BadRequest, match='copied.*new name'):
        getattr(manager, action)()


@pytest.mark.parametrize('name,expected', [
    ('image-wireguard-server', ('image-wireguard-server', 'wireguard-server')),
    ('imageeditor', ('image-imageeditor', 'imageeditor')),
    ('image', ('image-image', 'image')),
])
def test_local_copy_names_only_strip_the_complete_image_prefix(name, expected):
    assert ImageTemplateManager._extract_image_and_server_names(name) == expected
