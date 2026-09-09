"""Public image catalog synchronization without cloud credentials or writes."""

from copy import deepcopy
from types import MethodType, SimpleNamespace
from unittest.mock import Mock

from google.cloud.compute_v1 import Image
from google.cloud.firestore_v1._helpers import encode_value
import pytest

from cloud_fn_utilities.course_objects.compute.google_image_sync_manager import GoogleImageSyncManager
from cloud_fn_utilities.course_objects.compute import google_image_sync_manager as sync_module
from common.constants.build_constants import BuildConstants
from common.constants.database import DbCollections, DbOperationTypes
from common.constants.google import ImageProjects
from common.document_database.document_database import DocumentDatabase
from common.exceptions import NotFound, ServiceUnavailable
from common.models.google import ComputeImageModel
from common.utilities.gcp.compute.compute_image import ComputeImageAPI


class ImageDatabase:
    def __init__(self, records=()):
        self.records = {record['uuid']: deepcopy(record) for record in records}
        self.batches = []
        self.updates = []
        self.fail_writes = False

    def query(self, collection_name):
        assert collection_name == DbCollections.GOOGLE_IMAGES
        return deepcopy(list(self.records.values()))

    def operation(self, **operation):
        return operation

    def batch_write(self, operations):
        self.batches.append(deepcopy(operations))
        staged = deepcopy(self.records)
        for operation in operations:
            identity = operation['doc_id']
            if operation['operation_type'] == DbOperationTypes.DELETE:
                staged.pop(identity, None)
            else:
                if self.fail_writes:
                    raise RuntimeError('Database unavailable')
                encode_value(operation['data'])
                if operation['operation_type'] == DbOperationTypes.UPDATE and identity not in staged:
                    raise RuntimeError('Cannot update a missing document')
                staged[identity] = deepcopy(operation['data'])
        self.records = staged

    def update(self, **record):
        self.updates.append(record)


def cloud_image(project=ImageProjects.UBUNTU, family='ubuntu-2404-lts-amd64', image_id=123):
    return Image(
        id=image_id, family=family, name=f'{family}-v{image_id}',
        self_link=f'https://www.googleapis.com/compute/v1/projects/{project}/global/images/{family}-v{image_id}',
        creation_timestamp='2026-09-09T00:00:00Z', disk_size_gb=10,
        description=f'Public image for {family}',
    )


@pytest.fixture
def manager(monkeypatch):
    monkeypatch.setattr(ImageProjects, 'ALL', [ImageProjects.UBUNTU])
    service = object.__new__(GoogleImageSyncManager)
    service.class_name = 'GoogleImageSyncManager'
    service.env = SimpleNamespace(project='tenant-project', zone='us-central1-a')
    service.logger = Mock()
    service.db = ImageDatabase()
    service.collection = DbCollections.GOOGLE_IMAGES
    service.compute_images = Mock()
    service.image_data = {}
    service.images = []
    service.image_keys = set()
    service.failed_projects = {}
    service.successful_projects = set()
    image = cloud_image()
    service.compute_images.list.return_value = [image]
    service.compute_images.get.return_value = SimpleNamespace(image=image)
    return service


def saved_record(manager, image=None, enabled=False, identity='saved-uuid', numeric=False):
    image = image or cloud_image()
    record = manager._create_image_object(image, image.family, ImageProjects.UBUNTU, enabled).model_dump()
    record['uuid'] = identity
    record['global_id'] = image.id if numeric else str(image.id)
    return record


def test_initial_sync_can_store_unsigned_compute_image_ids(manager):
    image = cloud_image(image_id=2**63 + 123)
    manager.compute_images.list.return_value = [image]
    manager.compute_images.get.return_value = SimpleNamespace(image=image)

    manager.sync()

    record = next(iter(manager.db.records.values()))
    assert record['global_id'] == str(image.id)
    assert record['is_enabled'] is True
    assert record['family'] == image.family
    encode_value(record)


@pytest.mark.parametrize('numeric', [False, True], ids=['string-id', 'legacy-numeric-id'])
def test_resync_preserves_document_id_and_disabled_choice(manager, numeric):
    manager.db = ImageDatabase([saved_record(manager, numeric=numeric)])

    manager.sync()

    assert set(manager.db.records) == {'saved-uuid'}
    assert manager.db.records['saved-uuid']['is_enabled'] is False
    assert manager.db.records['saved-uuid']['global_id'] == '123'


def test_new_family_version_keeps_existing_selection_and_enablement(manager):
    manager.db = ImageDatabase([saved_record(manager)])
    replacement = cloud_image(image_id=456)
    manager.compute_images.list.return_value = [replacement]
    manager.compute_images.get.return_value = SimpleNamespace(image=replacement)

    manager.sync()

    assert set(manager.db.records) == {'saved-uuid'}
    record = manager.db.records['saved-uuid']
    assert record['global_id'] == '456'
    assert record['self_link'] == replacement.self_link
    assert record['is_enabled'] is False


def test_new_family_after_existing_family_can_be_inserted(manager):
    manager.db = ImageDatabase([saved_record(manager)])
    other = cloud_image(family='ubuntu-2204-lts', image_id=456)
    images = {image.family: image for image in [cloud_image(), other]}
    manager.compute_images.list.return_value = list(images.values())
    manager.compute_images.get.side_effect = lambda resource, **kwargs: SimpleNamespace(image=images[resource])

    manager.sync()

    assert {record['family'] for record in manager.db.records.values()} == set(images)
    assert manager.db.records['saved-uuid']['is_enabled'] is False


def test_failed_provider_does_not_hide_ubuntu_or_delete_its_cached_images(manager, monkeypatch):
    monkeypatch.setattr(ImageProjects, 'ALL', [ImageProjects.COS, ImageProjects.UBUNTU])
    cached = saved_record(manager, identity='cached-cos')
    cached.update(project=ImageProjects.COS, family='cos-stable', global_id='999')
    manager.db = ImageDatabase([cached])
    def list_images(project, **kwargs):
        if project == ImageProjects.UBUNTU:
            return [cloud_image()]
        raise ServiceUnavailable('Unavailable')

    manager.compute_images.list.side_effect = list_images

    report = manager.sync()

    assert manager.db.records['cached-cos'] == cached
    assert any(record['project'] == ImageProjects.UBUNTU for record in manager.db.records.values())
    assert ImageProjects.COS in report['failed_projects']


def test_failed_family_fetch_discards_partial_publisher_refresh(manager, monkeypatch):
    monkeypatch.setattr(ImageProjects, 'ALL', [ImageProjects.COS, ImageProjects.UBUNTU])
    cached = saved_record(manager, identity='cached-cos')
    cached.update(project=ImageProjects.COS, family='cos-stable', global_id='999')
    manager.db = ImageDatabase([cached])
    cos_images = [cloud_image(ImageProjects.COS, family) for family in ['cos-beta', 'cos-stable']]
    manager.compute_images.list.side_effect = lambda project, **kwargs: (
        cos_images if project == ImageProjects.COS else [cloud_image()]
    )

    def get_family(resource, project, **kwargs):
        if resource == 'cos-stable':
            raise ServiceUnavailable('Family lookup unavailable')
        return SimpleNamespace(image=cloud_image(project, resource))

    manager.compute_images.get.side_effect = get_family

    report = manager.sync()

    assert report['image_count'] == 1
    assert ImageProjects.COS in report['failed_projects']
    assert manager.db.records['cached-cos'] == cached
    assert {record['family'] for record in manager.db.records.values()} == {'cos-stable', 'ubuntu-2404-lts-amd64'}


def test_empty_discovery_does_not_erase_existing_catalog(manager):
    original = saved_record(manager)
    manager.db = ImageDatabase([original])
    manager.compute_images.list.return_value = []

    with pytest.raises(ServiceUnavailable):
        manager.sync()

    assert manager.db.records == {'saved-uuid': original}


def test_write_failure_does_not_delete_old_records_first(manager):
    old = saved_record(manager)
    old['family'] = 'retired-family'
    old['global_id'] = '999'
    manager.db = ImageDatabase([old])
    manager.db.fail_writes = True

    with pytest.raises(RuntimeError, match='Database unavailable'):
        manager.sync()

    assert manager.db.records == {'saved-uuid': old}


def test_large_catalog_write_failure_is_not_reported_as_success(manager):
    images = {f'ubuntu-family-{number}': cloud_image(family=f'ubuntu-family-{number}') for number in range(501)}
    manager.compute_images.list.return_value = list(images.values())
    manager.compute_images.get.side_effect = lambda resource, **kwargs: SimpleNamespace(image=images[resource])
    # Exercise the real database batching wrapper, which suppresses errors when
    # asked to split more than 500 operations into separate requests.
    database = manager.db
    database.fail_writes = True
    database.logger = Mock()
    database._batch_write = database.batch_write
    database._handle_batch_splitting = MethodType(DocumentDatabase._handle_batch_splitting, database)
    database.batch_write = MethodType(DocumentDatabase.batch_write, database)

    with pytest.raises(RuntimeError, match='Database unavailable'):
        manager.sync()

    assert database.records == {}
    assert database.updates[-1]['data']['action'] == GoogleImageSyncManager.SyncActions.FAILED


def test_reusing_sync_manager_does_not_accumulate_duplicate_rows(manager):
    manager.sync()
    first_ids = set(manager.db.records)

    manager.sync()

    assert len(manager.images) == 1
    assert set(manager.db.records) == first_ids


def test_legacy_integer_metadata_normalizes_to_safe_string(manager):
    record = saved_record(manager, numeric=True)
    normalized = ComputeImageModel(**record)
    assert normalized.global_id == '123'


def test_sync_database_is_scoped_to_environment_project(monkeypatch):
    env_dict = {'project': 'selected-child', 'region': 'us-central1', 'zone': 'us-central1-a'}
    env = SimpleNamespace(**env_dict, get_env=lambda: env_dict)
    monkeypatch.setattr(sync_module, 'CloudEnv', Mock(return_value=env))
    monkeypatch.setattr(sync_module, 'Logger', Mock())
    compute = Mock()
    database = Mock()
    monkeypatch.setattr(sync_module, 'ComputeImageAPI', compute)
    monkeypatch.setattr(sync_module.DocumentDatabaseFactory, 'create_db_object', database)

    GoogleImageSyncManager(env=env_dict)

    assert database.call_args.kwargs['project_id'] == 'selected-child'
    compute.assert_called_once_with('selected-child', 'us-central1', 'us-central1-a')


@pytest.mark.parametrize('fallback_to_shared', [False, True])
def test_missing_family_only_retries_shared_project_when_allowed(fallback_to_shared):
    api = object.__new__(ComputeImageAPI)
    api.logger = Mock()
    api.client = Mock()
    api._make_request = Mock(side_effect=[NotFound('No such family'), 'shared-family'])

    kwargs = dict(resource='ubuntu-2404-lts-amd64', project=ImageProjects.UBUNTU,
                  zone='us-central1-a', family=True)
    if fallback_to_shared:
        assert api.get(**kwargs) == 'shared-family'
    else:
        with pytest.raises(NotFound, match='No such family'):
            api.get(**kwargs, fallback_to_shared=False)

    projects = [call.kwargs['request'].project for call in api._make_request.call_args_list]
    expected = [ImageProjects.UBUNTU]
    if fallback_to_shared:
        expected.append(BuildConstants.SharedResourceProjects.MAIN_SHARED_RESOURCE_PROJECT)
    assert projects == expected
