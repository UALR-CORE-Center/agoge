"""POST /compute/images/ with CHECK_IN publishes NESTED_FINALIZE for a nested host (PRD V14)."""
import copy
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import dependencies
from common.constants.pub_sub import PubSub
from common.constants.states import ImageStatus
from core.compute import image as image_module
from routers import compute_image as compute_image_module

TEACHER = SimpleNamespace(uid='teacher', email='teacher@example.edu', is_authorized=True, is_admin=False)
CHECK_IN = str(PubSub.Actions.CHECK_IN.value)
NESTED_FINALIZE = str(PubSub.Actions.NESTED_FINALIZE.value)


def _nested(name, phase, **build):
    return {'name': name, 'status': ImageStatus.CHECKED_OUT.value, 'nested': {'parent_os': 'debian-12'},
            'nested_build': {'phase': phase, **build}}


class FakeDb:
    def __init__(self, images):
        self.images = {image['name']: image for image in images}

    def get(self, collection_name, doc_id):
        return copy.deepcopy(self.images.get(doc_id))


@pytest.fixture
def world(monkeypatch):
    def make(*images):
        pubsub = MagicMock()
        env = SimpleNamespace(project='test-dev-787001', region='us-central1', zone='us-central1-a',
                              get_env=lambda: {})
        monkeypatch.setattr(image_module, 'CloudEnv', lambda **kwargs: env)
        monkeypatch.setattr(image_module, 'PubSubManager', lambda **kwargs: pubsub)
        monkeypatch.setattr(image_module.DocumentDatabaseFactory, 'create_db_object',
                            lambda *args, **kwargs: FakeDb(images))
        app = FastAPI()
        app.include_router(compute_image_module.compute_image_router)
        app.dependency_overrides[dependencies.get_cloud_env] = lambda: {}
        app.dependency_overrides[dependencies.get_current_user] = lambda: TEACHER
        return TestClient(app), pubsub
    return make


def _check_in(client, *names):
    return client.post('/compute/images/', json={'action': CHECK_IN, 'images': [{'name': n} for n in names]})


def _actions(pubsub):
    return [(call.kwargs['image_name'], call.kwargs['action']) for call in pubsub.msg.call_args_list]


@pytest.mark.parametrize('phase', ['ready', 'finalized'])
def test_check_in_of_a_ready_or_finalized_nested_host_publishes_nested_finalize(world, phase):
    client, pubsub = world(_nested('nestlab', phase))

    response = _check_in(client, 'nestlab')

    assert response.status_code == 200
    assert _actions(pubsub) == [('nestlab', NESTED_FINALIZE)]
    assert pubsub.msg.call_args.kwargs['course_object'] == str(PubSub.CourseObjects.TEMPLATE_SERVER.value)


@pytest.mark.parametrize('phase', ['provisioning', 'building', 'finalizing'])
def test_check_in_mid_build_or_mid_finalize_is_refused_with_409(world, phase):
    client, pubsub = world(_nested('nestlab', phase))

    response = _check_in(client, 'nestlab')

    assert response.status_code == 409
    assert phase in response.json()['detail']
    pubsub.msg.assert_not_called()


def test_a_refused_nested_host_publishes_nothing_for_the_rest_of_the_list(world):
    # Messages are published only after every image passed, as for the other checks.
    client, pubsub = world({'name': 'plain'}, _nested('nestlab', 'building'))

    assert _check_in(client, 'plain', 'nestlab').status_code == 409
    pubsub.msg.assert_not_called()


def test_a_failed_finalize_is_retried_by_check_in(world):
    client, pubsub = world(_nested('nestlab', 'failed', finalize_nonce='abc', message='web: guest did not shut down'))

    assert _check_in(client, 'nestlab').status_code == 200
    assert _actions(pubsub) == [('nestlab', NESTED_FINALIZE)]


def test_standard_images_and_a_failed_build_keep_plain_check_in(world):
    client, pubsub = world({'name': 'plain'}, _nested('broken', 'failed', message='no guest was built'))

    assert _check_in(client, 'plain', 'broken').status_code == 200
    assert _actions(pubsub) == [('plain', CHECK_IN), ('broken', CHECK_IN)]


def test_other_actions_on_a_nested_host_are_unchanged(world):
    client, pubsub = world(_nested('nestlab', 'building'))

    response = client.post('/compute/images/', json={'action': str(PubSub.Actions.STOP.value),
                                                     'images': [{'name': 'nestlab'}]})

    assert response.status_code == 200
    assert _actions(pubsub) == [('nestlab', str(PubSub.Actions.STOP.value))]
