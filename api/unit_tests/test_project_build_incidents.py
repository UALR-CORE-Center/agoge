from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from google.cloud import compute_v1

from common.models.users import AgogeUser
from dependencies import get_cloud_env, get_current_user
from routers import project as project_router_module


PROJECT_ID = 'example-training-project'
HOLD_ID = 'a' * 32
QUOTA_STATUS = '/project/build-availability/'
RECHECK = f'{QUOTA_STATUS}recheck/'
INCIDENTS = '/project/build-incidents/'
HOLD = {
    'id': HOLD_ID, 'metric': 'NETWORKS', 'scope': 'global', 'limit': 30,
    'project': PROJECT_ID, 'generation': 'current-hold',
}


@pytest.fixture
def routes(monkeypatch):
    env = {'project': PROJECT_ID, 'admin_email': ' support@example.edu '}
    user = AgogeUser(uid='operator', email='operator@example.edu', permissions={'admin': True})
    compute = Mock()
    active_hold = Mock(return_value=HOLD)
    update_verified = Mock(return_value=None)
    list_recent = Mock(return_value={'incidents': [], 'next_cursor': None})

    def load_project(project, config):
        project.env = SimpleNamespace(project=config['project'])
        project.db = object()

    monkeypatch.setattr(project_router_module.Project, '__init__', load_project)
    monkeypatch.setattr(project_router_module.BuildIncidents, 'active_hold', active_hold)
    monkeypatch.setattr(project_router_module.BuildIncidents, 'update_verified_quota', update_verified)
    monkeypatch.setattr(project_router_module.BuildIncidents, 'list_recent', list_recent)
    monkeypatch.setattr(project_router_module.compute_v1, 'ProjectsClient', lambda: compute)

    app = FastAPI()
    app.include_router(project_router_module.project_router)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_cloud_env] = lambda: env
    return SimpleNamespace(
        client=TestClient(app), user=user, env=env, active_hold=active_hold,
        compute=compute, update_verified=update_verified, list_recent=list_recent,
    )


def test_instructors_see_the_hold_but_cannot_recheck_or_read_incidents(routes):
    routes.user.permissions = {'instructor': True}
    status = routes.client.get(QUOTA_STATUS)
    assert status.status_code == 200
    assert status.headers['Cache-Control'] == 'no-store'
    assert status.json()['data'] == {
        'hold': {field: value for field, value in HOLD.items() if field != 'generation'},
        'support_contact': 'support@example.edu',
    }
    assert routes.client.post(RECHECK).status_code == 403
    assert routes.client.get(INCIDENTS).status_code == 403
    routes.compute.get.assert_not_called()
    routes.list_recent.assert_not_called()


def test_students_cannot_read_or_change_build_quota_state(routes):
    routes.user.permissions = {'student': True}
    assert routes.client.get(QUOTA_STATUS).status_code == 403
    assert routes.client.post(RECHECK).status_code == 403
    assert routes.client.get(INCIDENTS).status_code == 403
    routes.active_hold.assert_not_called()
    routes.compute.get.assert_not_called()
    routes.list_recent.assert_not_called()


def test_status_without_hold_or_configured_support_contact(routes):
    routes.env.pop('admin_email')
    routes.active_hold.return_value = None
    assert routes.client.get(QUOTA_STATUS).json()['data'] == {'hold': None}


def test_recheck_reads_the_deployment_quota_and_returns_capacity_after_clear(routes):
    routes.compute.get.return_value = compute_v1.Project(quotas=[
        compute_v1.Quota(metric='FIREWALLS', usage=30, limit=30),
        compute_v1.Quota(metric='NETWORKS', usage=0, limit=30),
    ])

    response = routes.client.post(RECHECK, json={'project': 'another-project'})

    assert response.status_code == 200
    assert response.json()['data'] == {
        'hold': None, 'support_contact': 'support@example.edu', 'quota': {'usage': 0, 'limit': 30},
    }
    routes.compute.get.assert_called_once_with(project=PROJECT_ID, retry=None, timeout=10)
    routes.update_verified.assert_called_once_with(HOLD, usage=0, limit=30, verified_by='operator')


@pytest.mark.parametrize('quota', [
    compute_v1.Quota(metric='FIREWALLS', usage=3, limit=30),
    compute_v1.Quota(metric='NETWORKS', limit=30),
    compute_v1.Quota(metric='NETWORKS', usage=0),
    compute_v1.Quota(metric='NETWORKS', usage=float('nan'), limit=30),
])
def test_recheck_does_not_change_the_hold_for_an_unusable_quota_snapshot(routes, quota):
    routes.compute.get.return_value = compute_v1.Project(quotas=[quota])

    response = routes.client.post(RECHECK)

    assert response.status_code == 503
    assert response.json() == {'detail': 'Google Cloud quota could not be verified.'}
    routes.update_verified.assert_not_called()


def test_admin_incident_pagination_is_bounded_and_defaults_to_open(routes):
    assert routes.client.get(INCIDENTS).status_code == 200
    routes.list_recent.assert_called_once_with(cursor=None, page_size=50, include_resolved=False)

    response = routes.client.get(
        INCIDENTS, params={'cursor': HOLD_ID, 'page_size': 12, 'include_resolved': 'true'},
    )
    assert response.status_code == 200
    routes.list_recent.assert_called_with(cursor=HOLD_ID, page_size=12, include_resolved=True)
    assert routes.client.get(INCIDENTS, params={'cursor': 'invalid'}).status_code == 422
    assert routes.client.get(INCIDENTS, params={'page_size': 101}).status_code == 422
