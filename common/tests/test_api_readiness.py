"""Probe and host-validation regressions without GCP credentials or resources."""
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from health import HealthCheckTrustedHostMiddleware, health_router


@pytest.fixture
def app():
    value = FastAPI()
    value.add_middleware(HealthCheckTrustedHostMiddleware, allowed_hosts=['api.example.edu'])
    value.include_router(health_router)

    @value.get('/')
    async def root():
        return {'application': True}

    return value


@pytest.mark.parametrize('host', ['10.0.0.42', 'localhost:8080', 'internal-probe.run.app'])
@pytest.mark.parametrize('method', ['GET', 'HEAD'])
def test_ready_probe_accepts_internal_host_only_for_read_only_endpoint(app, host, method):
    app.state.api_ready = True
    client = TestClient(app)
    response = client.request(method, '/health/ready', headers={'Host': host})
    assert response.status_code == 200
    assert response.headers['Cache-Control'] == 'no-store'
    if method == 'GET':
        assert response.json() == {'status': 'ready'}
    else:
        assert response.content == b''


@pytest.mark.parametrize('ready', [None, False])
def test_probe_is_unavailable_without_completed_startup(app, ready):
    if ready is not None:
        app.state.api_ready = ready
    response = TestClient(app).get('/health/ready', headers={'Host': 'internal-probe'})
    assert response.status_code == 503
    assert response.json() == {'status': 'not_ready'}


@pytest.mark.parametrize('path', ['/', '/auth/', '/health/ready/child', '/health/ready/',
                                 '/health/ready-application', '/health/not-a-probe'])
def test_untrusted_hosts_are_still_rejected_on_every_other_path(app, path):
    app.state.api_ready = True
    response = TestClient(app).get(path, headers={'Host': 'untrusted.example'}, follow_redirects=False)
    assert response.status_code == 400
    assert response.text == 'Invalid host header'


@pytest.mark.parametrize('method', ['POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'])
def test_probe_exemption_does_not_accept_write_methods(app, method):
    response = TestClient(app).request(method, '/health/ready', headers={'Host': 'internal-probe'})
    assert response.status_code == 400


def test_normal_domain_routes_and_method_checks_are_preserved(app):
    client = TestClient(app, base_url='https://api.example.edu')
    assert client.get('/').json() == {'application': True}
    assert client.post('/health/ready').status_code == 405
    assert '/health/ready' not in app.openapi()['paths']


def test_real_api_probe_uses_lifespan_readiness_without_repeated_cloud_reads(monkeypatch):
    from api import main

    calls = []
    environment = SimpleNamespace(project='offline-project')

    def initialize(**kwargs):
        calls.append(kwargs)
        return environment

    monkeypatch.setattr(main, 'CloudEnv', initialize)
    with TestClient(main.app, base_url='http://internal-probe') as client:
        for _ in range(3):
            response = client.get('/health/ready')
            assert response.status_code == 200
            assert response.json() == {'status': 'ready'}
        assert main.app.state.cloud_env is environment
        assert client.get('/').status_code == 400
        assert len(calls) == 1
    assert main.app.state.api_ready is False


@pytest.mark.asyncio
async def test_failed_environment_initialization_never_marks_api_ready(monkeypatch):
    from api import main

    def fail(**_):
        raise RuntimeError('offline environment failure')

    monkeypatch.setattr(main, 'CloudEnv', fail)
    main.app.state.api_ready = True  # A previous process/lifespan cannot leave it ready.
    with pytest.raises(RuntimeError, match='offline environment failure'):
        async with main.lifespan(main.app):
            pytest.fail('A failed startup must not serve requests')
    assert main.app.state.api_ready is False
