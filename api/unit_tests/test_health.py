from fastapi import FastAPI
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.testclient import TestClient

from health import HEALTH_PATH, HealthCheckMiddleware


def _client():
    # Same order as main.py: TrustedHostMiddleware, then HealthCheckMiddleware outermost.
    app = FastAPI()

    @app.get('/')
    async def root():
        return 'Server is running!'

    app.add_middleware(TrustedHostMiddleware, allowed_hosts=['agoge-labs.com', '*.agoge-labs.com'])
    app.add_middleware(HealthCheckMiddleware)
    return TestClient(app)


def test_probe_from_an_untrusted_host_is_answered():
    response = _client().get(HEALTH_PATH, headers={'host': '169.254.8.1:8080'})

    assert response.status_code == 200
    assert response.text == 'ok'


def test_other_paths_still_require_a_trusted_host():
    client = _client()

    assert client.get('/', headers={'host': '169.254.8.1:8080'}).status_code == 400
    assert client.get('/', headers={'host': 'api.agoge-labs.com'}).status_code == 200
