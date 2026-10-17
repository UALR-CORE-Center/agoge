"""GET /compute/images/{name}/nested-build/ refreshes the build from guest attributes, then returns it (PRD V13)."""
import copy
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import dependencies
from common.constants.states import ImageStatus
from common.utilities import nested_build_monitor as monitor_module
from core.compute import image as image_module
from routers import compute_image as compute_image_module

TEACHER = SimpleNamespace(uid='teacher', email='teacher@example.edu', is_authorized=True, is_admin=False)
STUDENT = SimpleNamespace(uid='student', email='student@example.edu', is_authorized=False, is_admin=False)
NESTED = {
    'name': 'nestlab',
    'status': ImageStatus.CHECKED_OUT.value,
    'nested': {'parent_os': 'debian-12'},
    'nested_build': {'phase': 'building', 'started_at': '2026-10-17T11:50:00+00:00'},
}


class FakeDb:
    def __init__(self):
        self.images = {'nestlab': copy.deepcopy(NESTED), 'plain': {'name': 'plain'}}

    def get(self, collection_name, doc_id):
        return copy.deepcopy(self.images.get(doc_id))

    def update(self, collection_name, doc_id, data):
        self.images[doc_id].update(copy.deepcopy(data))


@pytest.fixture
def world(monkeypatch):
    db = FakeDb()
    compute = MagicMock()
    env = SimpleNamespace(project='test-dev-787001', region='us-central1', zone='us-central1-a', get_env=lambda: {})
    monkeypatch.setattr(image_module, 'CloudEnv', lambda **kwargs: env)
    monkeypatch.setattr(image_module, 'PubSubManager', lambda **kwargs: MagicMock())
    monkeypatch.setattr(image_module.DocumentDatabaseFactory, 'create_db_object', lambda *args, **kwargs: db)
    monkeypatch.setattr(monitor_module, 'CloudEnv', lambda **kwargs: env)
    monkeypatch.setattr(monitor_module, 'ComputeInstanceAPI', lambda **kwargs: compute)
    return SimpleNamespace(db=db, compute=compute)


def _client(user):
    app = FastAPI()
    app.include_router(compute_image_module.compute_image_router)
    app.dependency_overrides[dependencies.get_cloud_env] = lambda: {}
    # Override the user, not teacher_required, so the real role check runs.
    app.dependency_overrides[dependencies.get_current_user] = lambda: user
    return TestClient(app)


def test_returns_the_refreshed_build_and_stores_it(world):
    world.compute.get_guest_attributes.return_value = {'phase': 'ready', 'guest-kali': 'ready', 'message': 'done'}

    response = _client(TEACHER).get('/compute/images/nestlab/nested-build/')

    assert response.status_code == 200
    data = response.json()['data']
    assert data['phase'] == 'ready' and data['guests'] == {'kali': 'ready'} and data['message'] == 'done'
    assert world.db.images['nestlab']['nested_build']['phase'] == 'ready'
    world.compute.set_metadata.assert_called_once_with('nestlab', remove=['agoge-nested-secrets'], wait=False)


def test_unknown_image_is_404(world):
    assert _client(TEACHER).get('/compute/images/missing/nested-build/').status_code == 404


def test_standard_image_is_400(world):
    response = _client(TEACHER).get('/compute/images/plain/nested-build/')
    assert response.status_code == 400
    world.compute.get_guest_attributes.assert_not_called()


def test_student_is_403(world):
    assert _client(STUDENT).get('/compute/images/nestlab/nested-build/').status_code == 403
    world.compute.get_guest_attributes.assert_not_called()
