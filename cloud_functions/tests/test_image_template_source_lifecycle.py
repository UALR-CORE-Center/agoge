"""Keep template boot sources valid until a custom image has been checked in."""

from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from google.cloud.compute_v1 import Image

from cloud_fn_utilities.course_objects.compute.image_template_manager import ImageTemplateManager
from cloud_fn_utilities.course_objects.compute.snapshot_manager import SnapshotManager
from common.constants.database import DbCollections
from common.constants.google import ImageSource
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
    manager.compute_snapshot.get.return_value = SimpleNamespace(self_link='projects/test-dev-787001/global/snapshots/wireguard-server-auto-0', status='READY')
    manager.server_spec = SimpleNamespace(description='WireGuard template server')
    manager._build_server = Mock()
    manager._start_server = Mock()
    manager._stop_server = Mock()
    manager.env = SimpleNamespace(project='test-dev-787001', region='us-central1', zone='us-central1-a')
    manager.shared_edit_authorized = False
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

    with pytest.raises(BadRequest, match='administrator authorization'):
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


@pytest.mark.parametrize('action', ['create_snapshot', 'restore_from_snapshot', 'delete_snapshot', 'delete_snapshots'])
def test_shared_template_snapshots_cannot_bypass_management_guard(template, action):
    template_manager, record = template
    record.update(self_link=SHARED_SOURCE, image_exists=True)
    manager = object.__new__(SnapshotManager)
    manager.server_name = template_manager.server_name
    manager.env = template_manager.env
    manager.db = template_manager.db
    manager.server_type = PubSub.CourseObjects.TEMPLATE_SERVER

    with pytest.raises(BadRequest, match='administrator authorization'):
        if action == 'delete_snapshot':
            manager.delete_snapshot('wireguard-server-auto-0')
        else:
            getattr(manager, action)()


@pytest.mark.parametrize('name,expected', [
    ('image-wireguard-server', ('image-wireguard-server', 'wireguard-server')),
    ('imageeditor', ('image-imageeditor', 'imageeditor')),
    ('image', ('image-image', 'image')),
])
def test_local_copy_names_only_strip_the_complete_image_prefix(name, expected):
    assert ImageTemplateManager._extract_image_and_server_names(name) == expected


@pytest.mark.parametrize('source_name', ['image-wireguard-server', 'image-shared-catalog-name'])
def test_authorized_shared_check_in_saves_to_original_project_and_name(template, monkeypatch, source_name):
    manager, record = template
    shared_source = ComputeImageAPI.self_link(source_name, 'agoge-shared-resources')
    record.update(self_link=shared_source, image_exists=True)
    manager.shared_edit_authorized = True
    shared_client = Mock(project='agoge-shared-resources')
    shared_client.get.return_value = Image(name=source_name, self_link=shared_source, status='READY')
    shared_client.create.return_value = True
    shared_client.delete.return_value = True
    image_client_factory = Mock(return_value=shared_client)
    monkeypatch.setattr(
        'cloud_fn_utilities.course_objects.compute.image_template_manager.ComputeImageAPI', image_client_factory,
    )

    manager.check_out()
    manager.check_in()

    image_client_factory.assert_called_once_with(
        project='agoge-shared-resources', region='us-central1', zone='us-central1-a', log_name=LoggerNames.CLOUD_FN,
    )
    shared_client.delete.assert_called_once_with(source_name, project='agoge-shared-resources', wait=True)
    shared_client.create.assert_called_once_with(
        resource_name=source_name, project='agoge-shared-resources',
        description='Agoge-shared-resources production image. WireGuard template server',
        source_type=ImageSource.SNAPSHOT,
        source='projects/test-dev-787001/global/snapshots/wireguard-server-auto-0',
    )
    shared_client.get.assert_called_once_with(source_name, project='agoge-shared-resources', fallback_to_shared=False)
    manager.compute_image.create.assert_not_called()
    manager.compute_image.delete.assert_not_called()
    manager.compute_snapshot.get.assert_called_once_with(
        resource_name='wireguard-server-auto-0', project='test-dev-787001',
    )
    manager.compute_instance.delete.assert_called_once_with(manager.server_name, wait=True)
    assert record['self_link'] == shared_source
    assert record['image'] == source_name
    assert record['image_exists'] is True
    assert record['status'] == ImageStatus.CHECKED_IN.value


def test_authorized_shared_cancel_preserves_shared_image(template):
    manager, record = template
    record.update(self_link=SHARED_SOURCE, image_exists=True)
    manager.shared_edit_authorized = True

    manager.cancel()

    assert record['self_link'] == SHARED_SOURCE
    assert record['image_exists'] is True
    assert record['status'] == ImageStatus.CHECKED_IN.value
    manager.compute_image.create.assert_not_called()
    manager.compute_image.delete.assert_not_called()


def test_shared_check_in_propagates_authorization_to_server_cleanup(template):
    manager, record = template
    record.update(self_link=SHARED_SOURCE, image_exists=True)
    manager.shared_edit_authorized = True
    manager.debug = False
    manager.create_production_image = Mock(return_value=True)

    manager.check_in()

    assert manager.pubsub_manager.msg.call_args.kwargs['shared_edit_authorized'] == 'true'
    assert record['self_link'] == SHARED_SOURCE


def test_shared_snapshot_create_accepts_internal_authorization(template):
    template_manager, record = template
    record.update(self_link=SHARED_SOURCE, image_exists=True)
    manager = object.__new__(SnapshotManager)
    manager.server_name = template_manager.server_name
    manager.env = template_manager.env
    manager.db = template_manager.db
    manager.server_type = PubSub.CourseObjects.TEMPLATE_SERVER
    manager.shared_edit_authorized = True
    manager.compute_instance = Mock()
    manager.compute_instance.get_boot_disk_name.return_value = ('wireguard-server', 'wireguard-server-disk')
    manager.compute_disk = Mock()
    manager.get_next_snapshot_name = Mock(return_value=('wireguard-server-auto-0', False))
    manager._update_snapshots_record = Mock()

    assert manager.create_snapshot() == 'wireguard-server-auto-0'

    manager.compute_disk.create_snapshot.assert_called_once_with(
        disk_name='wireguard-server-disk', snapshot_name='wireguard-server-auto-0',
    )


def test_daily_maintenance_can_stop_local_shared_edit_vms(template):
    manager, record = template
    record.update(self_link=SHARED_SOURCE, image_exists=True)
    manager.db_query = Mock()
    manager.db_query.get_running.return_value = [record]
    manager.debug = False

    manager.stop_all_running()

    manager.pubsub_manager.msg.assert_called_once_with(
        handler=str(PubSub.Handlers.CONTROL.value), action=str(PubSub.Actions.STOP.value),
        course_object=str(PubSub.CourseObjects.TEMPLATE_SERVER.value), image_name=manager.server_name,
        shared_edit_authorized='true',
    )
    assert manager.shared_edit_authorized is False


def test_shared_image_verification_failure_keeps_reservation_and_original_source(template):
    manager, record = template
    record.update(self_link=SHARED_SOURCE, image_exists=True)
    original = deepcopy(record)
    manager.shared_edit_authorized = True
    shared_client = Mock(project='agoge-shared-resources')
    shared_client.delete.return_value = True
    shared_client.create.return_value = True
    # A same-named local image cannot stand in for the shared image being saved.
    shared_client.get.return_value = Image(name=manager.image_name, self_link=CUSTOM_SOURCE, status='READY')
    manager._shared_image_api = shared_client

    with pytest.raises(OperationTimeout, match='not ready in project agoge-shared-resources'):
        manager.check_in()

    assert record == original
    manager.compute_instance.delete.assert_not_called()
    manager.pubsub_manager.msg.assert_not_called()


@pytest.mark.parametrize('source_field', ['image', 'disks'])
def test_legacy_shared_checkout_preserves_source_for_later_check_in(template, source_field):
    manager, record = template
    record.update(self_link=None, image='image-wireguard-server', image_exists=True)
    if source_field == 'image':
        record['image'] = SHARED_SOURCE
    else:
        record['disks'] = [{'boot': True, 'autoDelete': True, 'initializeParams': {'sourceImage': SHARED_SOURCE, 'diskSizeGb': 20, 'type': 'pd-standard'}}]
    manager.shared_edit_authorized = True

    manager.check_out()

    assert record['self_link'] == SHARED_SOURCE
    assert manager._production_image_target() == ('agoge-shared-resources', 'image-wireguard-server')


@pytest.mark.parametrize('failure', ['missing', 'pending', 'wrong-project'])
def test_shared_check_in_requires_ready_snapshot_before_deleting_image(template, failure):
    manager, record = template
    record.update(self_link=SHARED_SOURCE, image_exists=True)
    manager.shared_edit_authorized = True
    original = deepcopy(record)
    manager._shared_image_api = Mock(project='agoge-shared-resources')
    if failure == 'missing':
        manager.compute_snapshot.get.side_effect = NotFound('Snapshot absent')
    elif failure == 'pending':
        manager.compute_snapshot.get.return_value.status = 'CREATING'
    else:
        manager.compute_snapshot.get.return_value.self_link = 'projects/other/global/snapshots/wireguard-server-auto-0'

    with pytest.raises((NotFound, OperationTimeout)):
        manager.check_in()

    manager._shared_image_api.delete.assert_not_called()
    manager._shared_image_api.create.assert_not_called()
    manager.compute_image.delete.assert_not_called()
    manager.compute_instance.delete.assert_not_called()
    assert record == original


def test_shared_snapshot_timeout_cannot_delete_production_image(template):
    manager, record = template
    record.update(self_link=SHARED_SOURCE, image_exists=True)
    manager.shared_edit_authorized = True
    original = deepcopy(record)
    snapshot_manager = object.__new__(SnapshotManager)
    snapshot_manager.server_name = manager.server_name
    snapshot_manager.env = manager.env
    snapshot_manager.db = manager.db
    snapshot_manager.server_type = PubSub.CourseObjects.TEMPLATE_SERVER
    snapshot_manager.shared_edit_authorized = True
    snapshot_manager.logger = Mock()
    snapshot_manager.class_name = 'SnapshotManager'
    snapshot_manager.compute_instance = Mock()
    snapshot_manager.compute_instance.get_boot_disk_name.return_value = ('wireguard-server', 'wireguard-server-disk')
    snapshot_manager.compute_disk = Mock()
    snapshot_manager.compute_disk.create_snapshot.return_value = False
    snapshot_manager.get_next_snapshot_name = Mock(return_value=('wireguard-server-auto-0', False))
    snapshot_manager._update_snapshots_record = Mock()
    manager.snapshot_manager = snapshot_manager
    manager._shared_image_api = Mock(project='agoge-shared-resources')

    with pytest.raises(OperationTimeout, match='did not finish'):
        manager.check_in()

    snapshot_manager._update_snapshots_record.assert_not_called()
    manager._shared_image_api.delete.assert_not_called()
    manager._shared_image_api.create.assert_not_called()
    manager.compute_image.delete.assert_not_called()
    manager.compute_instance.delete.assert_not_called()
    assert record == original
