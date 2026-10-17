"""A template record created by a request is removed when its CHECK_OUT publish fails (V12b).

Only that CHECK_OUT ever builds the new record, so a lost message would strand it, and a retry
with the same name would get 409.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import dependencies
from common.constants.database import DbCollections
from common.constants.pub_sub import PubSub
from common.exceptions import ServiceUnavailable
from core.compute import image as image_module
from core.compute.image import ComputeImage
from routers import compute_image as compute_image_module

TEACHER = SimpleNamespace(uid='teacher', email='teacher@example.edu', is_authorized=True, is_admin=False)
BUILD_FORM = {'server_name': 'kali-lab', 'action': str(PubSub.Actions.BUILD.value)}


@pytest.fixture
def world(monkeypatch):
    db = MagicMock()
    pubsub = MagicMock()
    env = SimpleNamespace(project='test-dev-787001', region='us-central1', zone='us-central1-a', get_env=lambda: {})
    monkeypatch.setattr(image_module, 'CloudEnv', lambda **kwargs: env)
    monkeypatch.setattr(image_module, 'PubSubManager', lambda **kwargs: pubsub)
    monkeypatch.setattr(image_module.DocumentDatabaseFactory, 'create_db_object', lambda *args, **kwargs: db)
    # Record creation has its own tests; these only need it to have "written" kali-lab.
    monkeypatch.setattr(ComputeImage, '_create_database_object', lambda self, data: data['server_name'])
    return SimpleNamespace(db=db, pubsub=pubsub)


def _client():
    app = FastAPI()
    app.include_router(compute_image_module.compute_image_router)
    app.dependency_overrides[dependencies.get_cloud_env] = lambda: {}
    app.dependency_overrides[dependencies.get_current_user] = lambda: TEACHER
    return TestClient(app)


def test_successful_publish_waits_for_the_future_and_keeps_the_record(world):
    ComputeImage(env_dict={}).create_image_server(TEACHER, dict(BUILD_FORM))

    attributes = world.pubsub.msg.call_args.kwargs
    assert attributes[PubSub.EventAttributes.ACTION] == str(PubSub.Actions.CHECK_OUT.value)
    assert attributes[PubSub.EventAttributes.IMAGE_NAME] == 'kali-lab'
    world.pubsub.msg.return_value.result.assert_called_once_with(
        timeout=ComputeImage.CHECK_OUT_PUBLISH_TIMEOUT_SECONDS)
    world.db.delete.assert_not_called()


@pytest.mark.parametrize('fail', ['publish', 'future'])
def test_failed_publish_removes_the_record_and_raises_service_unavailable(world, fail):
    if fail == 'publish':
        world.pubsub.msg.side_effect = RuntimeError('pubsub down')
    else:
        world.pubsub.msg.return_value.result.side_effect = TimeoutError()

    with pytest.raises(ServiceUnavailable, match='No template was created'):
        ComputeImage(env_dict={}).create_image_server(TEACHER, dict(BUILD_FORM))

    world.db.delete.assert_called_once_with(collection_name=DbCollections.IMAGE, doc_id='kali-lab')


def test_failed_cleanup_tells_the_user_to_delete_the_template(world):
    world.pubsub.msg.side_effect = RuntimeError('pubsub down')
    world.db.delete.side_effect = RuntimeError('firestore down')

    with pytest.raises(ServiceUnavailable, match='Delete the template'):
        ComputeImage(env_dict={}).create_image_server(TEACHER, dict(BUILD_FORM))


def test_create_route_maps_a_failed_publish_to_503(world):
    world.pubsub.msg.side_effect = RuntimeError('pubsub down')

    response = _client().post('/compute/images/create/', json=BUILD_FORM)

    assert response.status_code == 503
    assert 'No template was created' in response.json()['detail']


def test_image_action_route_build_maps_a_failed_publish_to_503_and_removes_the_record(world):
    world.pubsub.msg.return_value.result.side_effect = TimeoutError()

    response = _client().put('/compute/images/kali-lab/', json=BUILD_FORM)

    assert response.status_code == 503
    world.db.delete.assert_called_once_with(collection_name=DbCollections.IMAGE, doc_id='kali-lab')
