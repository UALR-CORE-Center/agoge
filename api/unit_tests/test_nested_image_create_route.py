"""POST /compute/images/nested/ writes a CHECKED_OUT nested record and publishes CHECK_OUT; GET …/nested/catalog/ lists enabled entries (PRD V12, SC-29)."""
import copy
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from google.api_core.exceptions import AlreadyExists

import dependencies
from common.constants.database import DbCollections
from common.constants.pub_sub import PubSub
from common.constants.states import ImageStatus
from common.models.agoge import AgogeImageModel
from core.compute import image as image_module
from core.compute.nested import nested_image as nested_image_module
from core.compute.nested import validator as validator_module
from core.compute.nested.validator import NestedHostValidator
from routers import compute_image as compute_image_module
# The validator tests own the catalog, media, and machine-type fixtures; the route must accept the same body.
from test_nested_host_validator import CATALOG, MEDIA, PRODUCT_KEY, FakeMachineTypes, _body

TEACHER = SimpleNamespace(uid='teacher', email='teacher@example.edu', is_authorized=True, is_admin=False)
STUDENT = SimpleNamespace(uid='student', email='student@example.edu', is_authorized=False, is_admin=False)
EXISTING = {'name': 'taken', 'machine_type': 'e2-medium'}


def _assert_firestore_storable(value, path='record'):
    # Firestore answers INVALID_ARGUMENT ("invalid nested entity") for an array directly inside an array.
    if isinstance(value, dict):
        for key, item in value.items():
            _assert_firestore_storable(item, f'{path}.{key}')
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            assert not isinstance(item, (list, tuple)), f'{path}[{index}] is an array inside an array'
            _assert_firestore_storable(item, f'{path}[{index}]')


class FakeDb:
    """Reads the catalog and media; images are created through db.db.collection().document().create()."""

    def __init__(self):
        self.images = {'taken': dict(EXISTING)}
        self.db = SimpleNamespace(collection=lambda name: SimpleNamespace(
            document=lambda doc_id: SimpleNamespace(create=lambda data: self._create(name, doc_id, data))))

    def _create(self, collection, doc_id, data):
        assert collection == DbCollections.IMAGE.value
        if doc_id in self.images:
            raise AlreadyExists('exists')
        _assert_firestore_storable(data)
        self.images[doc_id] = copy.deepcopy(data)

    def _source(self, collection_name):
        return {DbCollections.NESTED_OS_CATALOG: CATALOG, DbCollections.NESTED_MEDIA: MEDIA,
                DbCollections.IMAGE: self.images}[collection_name]

    def get(self, collection_name, doc_id):
        return copy.deepcopy(self._source(collection_name).get(doc_id))

    def delete(self, collection_name, doc_id):
        assert collection_name == DbCollections.IMAGE
        self.images.pop(doc_id, None)

    def query(self, collection_name, **kwargs):
        return copy.deepcopy(list(self._source(collection_name).values()))


@pytest.fixture
def world(monkeypatch):
    db = FakeDb()
    pubsub = MagicMock()
    env = SimpleNamespace(project='test-dev-787001', region='us-central1', zone='us-central1-a', get_env=lambda: {})
    monkeypatch.setattr(image_module, 'CloudEnv', lambda **kwargs: env)
    monkeypatch.setattr(validator_module, 'CloudEnv', lambda **kwargs: env)
    monkeypatch.setattr(image_module, 'PubSubManager', lambda **kwargs: pubsub)
    monkeypatch.setattr(image_module.DocumentDatabaseFactory, 'create_db_object', lambda *args, **kwargs: db)
    monkeypatch.setattr(nested_image_module, 'NestedHostValidator', lambda env_dict, db: NestedHostValidator(
        env_dict=env_dict, db=db, machine_type_api=FakeMachineTypes()))
    return SimpleNamespace(db=db, pubsub=pubsub)


def _client(user):
    app = FastAPI()
    app.include_router(compute_image_module.compute_image_router)
    app.dependency_overrides[dependencies.get_cloud_env] = lambda: {}
    # Override the user, not teacher_required, so the real role check runs.
    app.dependency_overrides[dependencies.get_current_user] = lambda: user
    return TestClient(app)


def test_valid_request_stores_a_queued_checked_out_record_and_publishes_one_check_out(world):
    response = _client(TEACHER).post('/compute/images/nested/', json=_body())

    assert response.status_code == 200
    assert response.json()['data']['build_id'] == 'ad-lab'
    record = world.db.images['ad-lab']
    assert record['status'] == ImageStatus.CHECKED_OUT.value
    assert record['self_link'] == 'projects/debian-cloud/global/images/family/debian-12'
    assert record['base_family'] == 'debian-12'
    assert record['machine_type'] == 'n2-standard-8'
    assert record['nested_build']['phase'] == 'queued'
    # Derived: router corp NIC and dc01 corp NIC are exposed; every guest has a console by default.
    assert record['nested']['exposures'] == [{'guest': 'router', 'nic': 0}, {'guest': 'dc01', 'nic': 0}]
    assert AgogeImageModel(**record).nested.exposures == [('router', 0), ('dc01', 0)]
    assert record['nested']['console_ports'] == {'router': 5901, 'dc01': 5902, 'ws01': 5903}
    assert all(len(p) == 8 for p in record['nested']['vnc_passwords'].values())
    # disk_size is omitted, so the parent disk is the computed minimum for the three guests and their media.
    assert record['add_disk'] == '134'
    [access] = record['human_interaction']
    assert (access['username'], access['ssh_key'], access['protocol']) == ('agoge', 'ssh-ed25519 AAAA', 'ssh')

    world.pubsub.msg.assert_called_once()
    attributes = world.pubsub.msg.call_args.kwargs
    assert attributes[PubSub.EventAttributes.HANDLER] == str(PubSub.Handlers.CONTROL.value)
    assert attributes[PubSub.EventAttributes.ACTION] == str(PubSub.Actions.CHECK_OUT.value)
    assert attributes[PubSub.EventAttributes.COURSE_OBJECT] == str(PubSub.CourseObjects.TEMPLATE_SERVER.value)
    assert attributes[PubSub.EventAttributes.IMAGE_NAME] == 'ad-lab'
    assert json.loads(attributes[PubSub.EventAttributes.PRODUCT_KEYS]) == {'ws01': PRODUCT_KEY}


def test_stored_record_holds_no_product_key(world):
    _client(TEACHER).post('/compute/images/nested/', json=_body())

    assert PRODUCT_KEY not in json.dumps(world.db.images['ad-lab'])
    assert 'product_key' not in json.dumps(world.db.images['ad-lab'])


def test_request_without_product_keys_publishes_no_product_keys_attribute(world):
    body = _body()
    body['nested']['guests'] = body['nested']['guests'][:2]
    body['product_keys'] = {}

    assert _client(TEACHER).post('/compute/images/nested/', json=body).status_code == 200

    assert PubSub.EventAttributes.PRODUCT_KEYS not in world.pubsub.msg.call_args.kwargs


def test_explicit_disk_size_is_kept(world):
    body = _body()
    body['disk_size'] = 400

    assert _client(TEACHER).post('/compute/images/nested/', json=body).status_code == 200

    assert world.db.images['ad-lab']['add_disk'] == '400'


def test_validator_rejection_is_400_with_its_message_and_writes_nothing(world):
    body = _body()
    body['product_keys'] = {}

    response = _client(TEACHER).post('/compute/images/nested/', json=body)

    assert response.status_code == 400
    assert 'Guest ws01' in response.json()['detail'] and 'product key' in response.json()['detail']
    assert 'ad-lab' not in world.db.images
    world.pubsub.msg.assert_not_called()


def test_invalid_parent_username_is_400(world):
    body = _body()
    body['username'] = 'bad name!'

    response = _client(TEACHER).post('/compute/images/nested/', json=body)

    assert response.status_code == 400
    world.pubsub.msg.assert_not_called()


def test_existing_name_is_409_and_keeps_the_existing_record(world):
    body = _body()
    body['server_name'] = 'taken'

    response = _client(TEACHER).post('/compute/images/nested/', json=body)

    assert response.status_code == 409
    assert world.db.images['taken'] == EXISTING
    world.pubsub.msg.assert_not_called()


def test_name_created_concurrently_is_409(world, monkeypatch):
    # Passes the get() check, then loses the atomic create() to a competing request.
    original_get = world.db.get
    monkeypatch.setattr(world.db, 'get', lambda collection_name, doc_id: None
                        if collection_name == DbCollections.IMAGE else original_get(collection_name, doc_id))
    body = _body()
    body['server_name'] = 'taken'

    assert _client(TEACHER).post('/compute/images/nested/', json=body).status_code == 409
    world.pubsub.msg.assert_not_called()


def test_student_is_403_and_nothing_is_written(world):
    response = _client(STUDENT).post('/compute/images/nested/', json=_body())

    assert response.status_code == 403
    assert 'ad-lab' not in world.db.images
    world.pubsub.msg.assert_not_called()


def test_client_supplied_derived_fields_are_rejected(world):
    body = _body()
    body['nested']['vnc_passwords'] = {'router': 'aaaaaaaa'}

    assert _client(TEACHER).post('/compute/images/nested/', json=body).status_code == 422
    world.pubsub.msg.assert_not_called()


def test_publish_raising_is_503_and_removes_the_new_record(world):
    world.pubsub.msg.side_effect = RuntimeError('pubsub down')

    response = _client(TEACHER).post('/compute/images/nested/', json=_body())

    assert response.status_code == 503
    assert 'No template was created' in response.json()['detail']
    assert 'ad-lab' not in world.db.images


def test_publish_future_failing_is_503_and_a_retry_with_the_same_name_succeeds(world):
    # publish() returns at once; a delivery failure surfaces only on the future.
    world.pubsub.msg.return_value.result.side_effect = TimeoutError()

    assert _client(TEACHER).post('/compute/images/nested/', json=_body()).status_code == 503
    assert 'ad-lab' not in world.db.images
    world.pubsub.msg.return_value.result.assert_called_once_with(
        timeout=nested_image_module.NestedImage.CHECK_OUT_PUBLISH_TIMEOUT_SECONDS)

    world.pubsub.msg.return_value.result.side_effect = None
    assert _client(TEACHER).post('/compute/images/nested/', json=_body()).status_code == 200
    assert world.db.images['ad-lab']['nested_build']['phase'] == 'queued'


def test_publish_failure_never_puts_product_keys_in_the_response(world):
    world.pubsub.msg.side_effect = RuntimeError('pubsub down')

    response = _client(TEACHER).post('/compute/images/nested/', json=_body())

    assert PRODUCT_KEY not in response.text


def test_publish_failure_with_a_failed_cleanup_says_the_record_must_be_deleted(world, monkeypatch):
    world.pubsub.msg.side_effect = RuntimeError('pubsub down')
    monkeypatch.setattr(world.db, 'delete', MagicMock(side_effect=RuntimeError('firestore down')))

    response = _client(TEACHER).post('/compute/images/nested/', json=_body())

    assert response.status_code == 503
    assert 'Delete the template' in response.json()['detail']


def test_catalog_lists_enabled_entries_and_is_not_captured_by_get_image(world, monkeypatch):
    get_image = MagicMock(side_effect=AssertionError('/{image_name}/ captured the catalog route'))
    monkeypatch.setattr(image_module.ComputeImage, 'get', get_image)

    response = _client(TEACHER).get('/compute/images/nested/catalog/')

    assert response.status_code == 200
    ids = [entry['id'] for entry in response.json()['data']['items']]
    assert sorted(ids) == ['debian-12', 'win10-licensed', 'win2022-eval']
    get_image.assert_not_called()


def test_catalog_skips_malformed_entries(world, monkeypatch):
    monkeypatch.setitem(CATALOG, 'broken', {'id': 'broken'})

    response = _client(TEACHER).get('/compute/images/nested/catalog/')

    assert response.status_code == 200
    assert 'broken' not in [entry['id'] for entry in response.json()['data']['items']]


def test_catalog_is_403_for_students(world):
    assert _client(STUDENT).get('/compute/images/nested/catalog/').status_code == 403
