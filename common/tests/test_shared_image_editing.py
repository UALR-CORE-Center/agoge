"""Shared templates must be copied to an independent local image before editing."""

from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock

from google.api_core.exceptions import AlreadyExists
from google.cloud.compute_v1 import Image
import pytest

from api.core.compute import image as image_module
from api.core.compute.image import ComputeImage
from common.constants.database import DbCollections
from common.constants.google import ImageSource, OperationType
from common.constants.pub_sub import PubSub
from common.constants.states import ImageStatus, ServerStates
from common.exceptions import BadRequest, Conflict, NotFound, NotReady, OperationTimeout
from common.models.agoge import AgogeImageModel
from common.models.model_validators.model_validator import ModelValidator
from common.utilities.gcp.compute.compute_image import ComputeImageAPI
from common.utilities.gcp.compute.image_ownership import image_source_project, is_shared_image


PROJECT = 'child-project'
SHARED_PROJECT = 'shared-project'
SOURCE_URL = ComputeImageAPI.self_link('image-shared-router', SHARED_PROJECT)
LOCAL_URL = ComputeImageAPI.self_link('image-local-router', PROJECT)
SOURCE_RECORD = {
    'name': 'shared-router',
    'image': 'image-shared-router',
    'self_link': SOURCE_URL,
    'image_exists': True,
    'machine_type': 'e2-medium',
    'description': 'Shared WireGuard gateway',
    'tags': ['wireguard-gateway'],
    'os': 'linux',
    'add_disk': '25',
    'human_interaction': [{'protocol': 'ssh', 'username': 'instructor', 'ssh_key': 'ssh-ed25519 test'}],
    'labels': ['vpn', 'teaching'],
    'startup_script': '#!/bin/bash\nsysctl -w net.ipv4.ip_forward=1',
    'base_family': 'ubuntu-2404-lts-amd64',
    'architecture': 'X86_64',
    # Old runtime fields must not leak into the new editable template.
    'status': ImageStatus.CHECKED_OUT.value,
    'state': ServerStates.RUNNING.value,
    'state_timestamp': '2026-09-10T12:00:00Z',
    'dns_record': 'old-server.example.edu',
    'in_use_by': 'old-instructor@example.edu',
    'disks': [{'boot': True, 'autoDelete': True, 'initializeParams': {
        'sourceImage': SOURCE_URL, 'diskSizeGb': 25, 'type': 'pd-standard',
    }}],
}


@pytest.fixture
def editing(monkeypatch):
    service = object.__new__(ComputeImage)
    service.collection = DbCollections.IMAGE
    service.env = SimpleNamespace(project=PROJECT, region='us-central1', zone='us-central1-a')
    service.log_name = 'api'
    service.class_name = 'ComputeImage'
    service.logger = Mock()
    service.db = Mock()
    service.pubsub_manager = Mock()
    service.pubsub_keys = PubSub.EventAttributes
    service.agoge_model_validator = ModelValidator(AgogeImageModel)
    records = {'shared-router': deepcopy(SOURCE_RECORD)}
    service.db.get.side_effect = lambda collection_name, doc_id: records.get(doc_id)
    service.db.query.side_effect = lambda collection_name: list(records.values())
    document = service.db.db.collection.return_value.document.return_value
    events = []

    def create_record(record):
        events.append('record-created')
        if record['name'] in records:
            raise AlreadyExists('Concurrent template creation')
        records[record['name']] = deepcopy(record)

    document.create.side_effect = create_record
    source = Image(name='image-shared-router', self_link=SOURCE_URL, status='READY', architecture='X86_64')
    local = Image(name='image-local-router', self_link=LOCAL_URL, status='READY', architecture='X86_64')
    cloud_images = {(SHARED_PROJECT, source.name): source}
    image_api = Mock()

    def get_image(resource, project=None, fallback_to_shared=True):
        if (project, resource) not in cloud_images:
            raise NotFound('Image not found')
        return cloud_images[project, resource]

    def copy_image(**kwargs):
        events.append('image-copied')
        cloud_images[PROJECT, kwargs['resource_name']] = local
        return True

    image_api.get.side_effect = get_image
    image_api.create.side_effect = copy_image
    image_factory = Mock(return_value=image_api)
    image_factory.self_link = ComputeImageAPI.self_link
    monkeypatch.setattr(image_module, 'ComputeImageAPI', image_factory)
    instance_api, disk_api = Mock(), Mock()
    instance_api.get.side_effect = NotFound('Instance not found')
    disk_api.get.side_effect = NotFound('Disk not found')
    monkeypatch.setattr(image_module, 'ComputeInstanceAPI', Mock(return_value=instance_api))
    monkeypatch.setattr(image_module, 'ComputeDiskAPI', Mock(return_value=disk_api))
    return SimpleNamespace(
        service=service, records=records, document=document, image_api=image_api,
        instance_api=instance_api, disk_api=disk_api, source=source, local=local,
        cloud_images=cloud_images, events=events,
    )


@pytest.mark.parametrize(('record', 'source_project', 'shared'), [
    ({'self_link': SOURCE_URL, 'image_exists': True}, SHARED_PROJECT, True),
    ({'self_link': LOCAL_URL, 'image_exists': True}, PROJECT, False),
    ({'image': SOURCE_URL}, SHARED_PROJECT, True),
    ({'disks': [{'boot': True, 'initializeParams': {'sourceImage': SOURCE_URL}}]}, SHARED_PROJECT, True),
    ({'self_link': SOURCE_URL}, SHARED_PROJECT, True),
    ({'self_link': SOURCE_URL, 'image_exists': False}, SHARED_PROJECT, False),
    ({'name': 'shared-router', 'image': 'image-shared-router', 'self_link': SOURCE_URL,
      'image_exists': False}, SHARED_PROJECT, True),
    ({'name': 'shared-router', 'image': SOURCE_URL, 'self_link': SOURCE_URL,
      'image_exists': False}, SHARED_PROJECT, True),
    ({'name': 'new-local-router', 'image': SOURCE_URL, 'self_link': SOURCE_URL,
      'image_exists': False}, SHARED_PROJECT, False),
    ({'self_link': 'projects/ubuntu-os-cloud/global/images/ubuntu-test', 'image_exists': False}, 'ubuntu-os-cloud', False),
    ({'name': 'unresolved-template'}, None, False),
])
def test_ownership_supports_shared_local_legacy_and_new_drafts(record, source_project, shared):
    assert image_source_project(record) == source_project
    assert is_shared_image(record, PROJECT) is shared


@pytest.mark.parametrize('method', ['get', 'list_images', 'list_project_images'])
def test_response_ownership_comes_from_source_even_when_saved_flags_are_stale(editing, method):
    editing.records['shared-router'].update(is_shared=False, source_project=PROJECT)
    local = {**deepcopy(SOURCE_RECORD), 'name': 'local-router', 'self_link': LOCAL_URL,
             'is_shared': True, 'source_project': SHARED_PROJECT}
    editing.records['local-router'] = local
    if method == 'get':
        results = [editing.service.get(name) for name in editing.records]
    elif method == 'list_project_images':
        editing.service.db.query.side_effect = lambda collection_name: (
            list(editing.records.values()) if collection_name == DbCollections.IMAGE else []
        )
        results = editing.service.list_project_images()['custom']
    else:
        results = editing.service.list_images()
    assert [(item.name, item.is_shared, item.source_project) for item in results] == [
        ('shared-router', True, SHARED_PROJECT), ('local-router', False, PROJECT),
    ]


@pytest.mark.parametrize('action', [PubSub.Actions.CHECK_OUT, PubSub.Actions.CHECK_IN,
                                  PubSub.Actions.START, PubSub.Actions.STOP, PubSub.Actions.CANCEL])
@pytest.mark.parametrize('image_exists', [True, False])
def test_shared_actions_reject_tampered_client_ownership_before_queueing(editing, action, image_exists):
    editing.records['shared-router']['image_exists'] = image_exists
    with pytest.raises(BadRequest, match='Copy this shared image'):
        editing.service.process_action_on_list('instructor@example.edu', {
            'action': str(action.value),
            'images': [{'name': 'shared-router', 'is_shared': False, 'source_project': PROJECT,
                        'image_exists': False, 'self_link': LOCAL_URL}],
        })
    editing.service.pubsub_manager.msg.assert_not_called()
    editing.image_api.get.assert_not_called()


@pytest.mark.parametrize('method', ['update', 'delete'])
def test_direct_shared_settings_or_delete_are_rejected(editing, method):
    original = deepcopy(editing.records)
    with pytest.raises(BadRequest, match='Copy this shared image'):
        if method == 'update':
            editing.service.update_image('shared-router', {
                'description': 'Modified', 'is_shared': False, 'self_link': LOCAL_URL, 'image_exists': False,
            })
        else:
            editing.service.delete('shared-router')
    assert editing.records == original
    editing.service.db.update.assert_not_called()
    editing.service.pubsub_manager.msg.assert_not_called()


def test_mixed_batch_does_not_partially_queue_before_rejecting_shared_image(editing):
    editing.records['local-router'] = {**SOURCE_RECORD, 'name': 'local-router', 'self_link': LOCAL_URL}
    with pytest.raises(BadRequest, match='Copy this shared image'):
        editing.service.process_action_on_list('instructor@example.edu', {
            'action': str(PubSub.Actions.CANCEL.value), 'images': ['local-router', 'shared-router'],
        })
    editing.service.pubsub_manager.msg.assert_not_called()


@pytest.mark.parametrize('legacy', [False, True])
def test_copy_creates_new_ready_child_image_and_independent_template(editing, legacy):
    if legacy:
        editing.records['shared-router'].update(self_link=None, image_exists=False)
    original = deepcopy(editing.records['shared-router'])
    result = editing.service.copy_shared_image('shared-router', 'local-router')

    assert editing.records['shared-router'] == original
    editing.image_api.create.assert_called_once_with(
        resource_name='image-local-router', source=SOURCE_URL, source_type=ImageSource.IMAGE,
        project=PROJECT, wait=True, description=SOURCE_RECORD['description'],
    )
    assert editing.events == ['image-copied', 'record-created']
    assert result.name == 'local-router'
    assert result.image == 'image-local-router'
    assert result.self_link == LOCAL_URL
    assert result.is_shared is False
    assert result.source_project == PROJECT
    assert result.image_exists is True
    assert result.status == ImageStatus.CHECKED_IN.value
    assert result.state == ServerStates.START.value
    for field in ['disks', 'state_timestamp', 'in_use_by', 'dns_record']:
        assert getattr(result, field) is None
    for field in ['machine_type', 'description', 'tags', 'os', 'add_disk', 'labels', 'startup_script', 'base_family']:
        assert getattr(result, field) == original[field]
    assert result.human_interaction[0].username == 'instructor'
    assert result.human_interaction[0].ssh_key == 'ssh-ed25519 test'
    assert result.architecture == 'X86_64'
    result.labels.append('local-only')
    assert editing.records['shared-router'] == original
    assert editing.records['local-router']['labels'] == original['labels']
    editing.service.db.update.assert_not_called()
    editing.service.pubsub_manager.msg.assert_not_called()
    assert all(call.kwargs['fallback_to_shared'] is False for call in editing.image_api.get.call_args_list)


@pytest.mark.parametrize('name', ['', 'WrongCase', 'name_with_underscore', '-name', 'name-',
                                 '1name', 'a' * 55, 'image-local-router', 'agoge', 'google', None])
def test_invalid_copy_names_stop_before_compute_mutation(editing, name):
    with pytest.raises(BadRequest):
        editing.service.copy_shared_image('shared-router', name)
    editing.image_api.create.assert_not_called()
    editing.document.create.assert_not_called()


def test_longest_allowed_name_leaves_room_for_manual_snapshot_suffix(editing):
    server_name = 'a' * 54
    editing.service._validate_new_name(server_name)
    assert len(f'{server_name}-manual-0') == 63


@pytest.mark.parametrize('collision', ['template', 'image', 'instance', 'disk'])
def test_copy_rejects_existing_destination_resources_without_replacing_them(editing, collision):
    if collision == 'template':
        editing.records['local-router'] = {'name': 'local-router', 'description': 'Existing'}
    elif collision == 'image':
        editing.cloud_images[PROJECT, 'image-local-router'] = editing.local
    elif collision == 'instance':
        editing.instance_api.get.side_effect = None
    else:
        editing.disk_api.get.side_effect = None
    original = deepcopy(editing.records)
    with pytest.raises(Conflict):
        editing.service.copy_shared_image('shared-router', 'local-router')
    assert editing.records == original
    editing.image_api.create.assert_not_called()
    editing.document.create.assert_not_called()


@pytest.mark.parametrize('case', ['missing', 'local', 'same-server-name', 'same-image-name', 'family'])
def test_copy_requires_shared_source_and_distinct_concrete_names(editing, case):
    name = 'local-router'
    exception = BadRequest
    if case == 'missing':
        editing.records.clear()
        exception = NotFound
    elif case == 'local':
        editing.records['shared-router']['self_link'] = LOCAL_URL
    elif case == 'same-server-name':
        name = 'shared-router'
    elif case == 'same-image-name':
        editing.records['shared-router']['self_link'] = SOURCE_URL.replace('image-shared-router', 'image-local-router')
    else:
        editing.records['shared-router']['self_link'] = SOURCE_URL.replace('image-shared-router', 'family/my-family')
    with pytest.raises(exception):
        editing.service.copy_shared_image('shared-router', name)
    editing.image_api.create.assert_not_called()
    editing.document.create.assert_not_called()


@pytest.mark.parametrize('failure', ['source-not-ready', 'source-missing', 'source-project-mismatch',
                                    'copy-timeout', 'copy-error', 'local-not-ready', 'local-destination-mismatch'])
def test_failed_copy_never_publishes_an_editable_record(editing, failure):
    exception = NotReady
    if failure == 'source-not-ready':
        editing.source.status = 'PENDING'
    elif failure == 'source-missing':
        editing.cloud_images.clear()
        exception = NotFound
    elif failure == 'source-project-mismatch':
        editing.source.self_link = SOURCE_URL.replace(SHARED_PROJECT, 'wrong-project')
        exception = BadRequest
    elif failure == 'copy-timeout':
        editing.image_api.create.side_effect = None
        editing.image_api.create.return_value = False
        exception = OperationTimeout
    elif failure == 'copy-error':
        editing.image_api.create.side_effect = RuntimeError('Copy denied')
        exception = RuntimeError
    elif failure == 'local-not-ready':
        editing.local.status = 'PENDING'
    else:
        editing.local.self_link = SOURCE_URL
        exception = BadRequest
    with pytest.raises(exception):
        editing.service.copy_shared_image('shared-router', 'local-router')
    assert editing.records == {'shared-router': SOURCE_RECORD}
    editing.document.create.assert_not_called()


def test_atomic_template_creation_collision_preserves_competing_record(editing):
    competing = {'name': 'local-router', 'description': 'Created by another request'}
    def race(record):
        editing.records['local-router'] = deepcopy(competing)
        raise AlreadyExists('Concurrent template creation')
    editing.document.create.side_effect = race
    with pytest.raises(Conflict, match='already exists'):
        editing.service.copy_shared_image('shared-router', 'local-router')
    assert editing.records['local-router'] == competing
    assert editing.records['shared-router'] == SOURCE_RECORD
    editing.service.db.update.assert_not_called()
    editing.image_api.delete.assert_not_called()


def test_local_checkout_cannot_fall_back_to_a_shared_image(editing):
    editing.records['local-router'] = {
        **SOURCE_RECORD, 'name': 'local-router', 'image': 'image-local-router', 'self_link': LOCAL_URL,
    }
    with pytest.raises(NotFound):
        editing.service.process_action_on_list('instructor@example.edu', {
            'action': str(PubSub.Actions.CHECK_OUT.value), 'images': ['local-router'],
        })
    editing.image_api.get.assert_called_once_with(
        resource='image-local-router', project=PROJECT, fallback_to_shared=False,
    )
    editing.service.pubsub_manager.msg.assert_not_called()


def test_local_checkin_can_retry_when_previous_image_creation_failed(editing):
    editing.records['local-router'] = {
        **SOURCE_RECORD, 'name': 'local-router', 'image': 'image-local-router', 'self_link': LOCAL_URL,
    }
    editing.service.process_action_on_list('instructor@example.edu', {
        'action': str(PubSub.Actions.CHECK_IN.value), 'images': ['local-router'],
    })
    editing.image_api.get.assert_not_called()
    editing.service.pubsub_manager.msg.assert_called_once()
    assert editing.service.pubsub_manager.msg.call_args.kwargs[PubSub.EventAttributes.IMAGE_NAME] == 'local-router'


def test_compute_image_get_disabled_fallback_never_queries_shared_project():
    image_api = object.__new__(ComputeImageAPI)
    image_api.project = PROJECT
    image_api.zone = 'us-central1-a'
    image_api.client_type = Mock()
    image_api.client = Mock()
    image_api.logger = Mock()
    image_api._make_request = Mock(side_effect=NotFound('Missing local image'))
    with pytest.raises(NotFound):
        image_api.get('image-local-router', project=PROJECT, fallback_to_shared=False)
    image_api._make_request.assert_called_once()
    assert image_api._make_request.call_args.kwargs['request'].project == PROJECT


def test_compute_copy_insert_uses_source_image_and_waits_for_global_operation():
    image_api = object.__new__(ComputeImageAPI)
    image_api.project = PROJECT
    image_api.client = Mock()
    image_api._make_request = Mock(return_value=True)
    assert image_api.create(
        'image-local-router', source=SOURCE_URL, source_type=ImageSource.IMAGE, project=PROJECT, wait=True,
    ) is True
    image_api._make_request.assert_called_once()
    args = image_api._make_request.call_args.kwargs
    assert args['operation_type'] == OperationType.GLOBAL
    assert args['wait'] is True
    assert args['request'].project == PROJECT
    assert args['request'].image_resource.name == 'image-local-router'
    assert args['request'].image_resource.source_image == SOURCE_URL
    assert not args['request'].image_resource.source_snapshot


@pytest.fixture
def copy_route(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from api.routers import compute_image as router_module

    app = FastAPI()
    app.include_router(router_module.compute_image_router)
    app.dependency_overrides[router_module.get_cloud_env] = lambda: {'project': PROJECT}
    backend = Mock()
    backend.copy_shared_image.return_value = AgogeImageModel(**{
        **SOURCE_RECORD, 'name': 'local-router', 'image': 'image-local-router', 'self_link': LOCAL_URL,
        'is_shared': False, 'source_project': PROJECT,
    })
    factory = Mock(return_value=backend)
    monkeypatch.setattr(router_module, 'ComputeImage', factory)
    with TestClient(app) as client:
        yield SimpleNamespace(app=app, client=client, backend=backend, factory=factory, module=router_module)


def test_copy_route_requires_authentication_and_returns_new_local_template(copy_route):
    response = copy_route.client.post('/compute/images/shared-router/copy/', json={'server_name': 'local-router'})
    assert response.status_code in (401, 403)
    copy_route.factory.assert_not_called()

    copy_route.app.dependency_overrides[copy_route.module.teacher_required] = lambda: SimpleNamespace(
        email='instructor@example.edu', uid='instructor',
    )
    response = copy_route.client.post('/compute/images/shared-router/copy/', json={'server_name': 'local-router'})
    assert response.status_code == 201
    copy_route.backend.copy_shared_image.assert_called_once_with('shared-router', 'local-router')
    assert response.json()['data']['name'] == 'local-router'
    assert response.json()['data']['is_shared'] is False
    assert response.json()['data']['source_project'] == PROJECT


@pytest.mark.parametrize('extra', [{'project': 'another-project'}, {'is_shared': False}, {'self_link': LOCAL_URL}])
def test_copy_route_rejects_client_destination_and_ownership_fields(copy_route, extra):
    copy_route.app.dependency_overrides[copy_route.module.teacher_required] = lambda: SimpleNamespace(
        email='instructor@example.edu', uid='instructor',
    )
    response = copy_route.client.post('/compute/images/shared-router/copy/', json={
        'server_name': 'local-router', **extra,
    })
    assert response.status_code == 422
    copy_route.factory.assert_not_called()
