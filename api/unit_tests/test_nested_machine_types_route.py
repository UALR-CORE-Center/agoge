"""GET /compute/images/machine-types/?nested=true lists N1/N2 types up to the nested cap (PRD V2)."""
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import dependencies
from routers import compute_image as compute_image_module
from utilities.gcp.compute.compute_resources import ComputeResources

MACHINE_TYPES = {
    'e2-standard-4': 16384,
    'e2-standard-8': 32768,
    'n1-standard-16': 61440,
    'n2-standard-4': 16384,
    'n2-standard-8': 32768,
    'n2-standard-32': 131072,
}


def _resources():
    resources = object.__new__(ComputeResources)
    resources.env = SimpleNamespace(project='test-dev-787001', zone='us-central1-a')
    resources.machine_client = MagicMock()
    resources.machine_client.list.return_value = [
        SimpleNamespace(name=name, memory_mb=memory, description=name, is_shared_cpu=False, guest_cpus=4)
        for name, memory in MACHINE_TYPES.items()
    ]
    return resources


@pytest.fixture
def client(monkeypatch):
    resources = _resources()
    monkeypatch.setattr(compute_image_module, 'ComputeImage', lambda env_dict: SimpleNamespace(
        machine_types=lambda nested=False: resources.get_machine_types(nested=nested),
    ))
    app = FastAPI()
    app.include_router(compute_image_module.compute_image_router)
    app.dependency_overrides[dependencies.get_cloud_env] = lambda: {}
    app.dependency_overrides[dependencies.teacher_required] = lambda: SimpleNamespace(uid='teacher')
    return TestClient(app)


def _names(response):
    assert response.status_code == 200
    return sorted(item['name'] for item in response.json()['data']['items'])


def test_default_list_is_unchanged(client):
    assert _names(client.get('/compute/images/machine-types/')) == ['e2-standard-4', 'n2-standard-4']


def test_nested_list_holds_n1_and_n2_up_to_the_nested_cap_and_no_e2(client):
    names = _names(client.get('/compute/images/machine-types/?nested=true'))

    assert names == ['n1-standard-16', 'n2-standard-4', 'n2-standard-8']
