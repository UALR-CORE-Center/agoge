from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

import dependencies
from common.exceptions.agoge import BadRequest, Unauthorized


def _client(dependency, user=None) -> TestClient:
    app = FastAPI()

    @app.get("/protected")
    def protected(current_user=Depends(dependency)):
        return {"uid": current_user.uid}

    if user is not None:
        app.dependency_overrides[dependencies.get_current_user] = lambda: user
    return TestClient(app, raise_server_exceptions=False)


@pytest.mark.parametrize("dependency", [dependencies.teacher_required, dependencies.admin_required])
def test_insufficient_permissions_return_403(dependency):
    user = SimpleNamespace(uid="student", is_authorized=False, is_admin=False)

    response = _client(dependency, user).get("/protected")

    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient permissions"


def test_teacher_passes_teacher_required():
    user = SimpleNamespace(uid="teacher", is_authorized=True, is_admin=False)

    response = _client(dependencies.teacher_required, user).get("/protected")

    assert response.status_code == 200
    assert response.json() == {"uid": "teacher"}


def test_teacher_is_rejected_by_admin_required():
    user = SimpleNamespace(uid="teacher", is_authorized=True, is_admin=False)

    assert _client(dependencies.admin_required, user).get("/protected").status_code == 403


@pytest.mark.parametrize("error, status", [
    (Unauthorized("Authentication failed! Invalid token"), 401),
    (BadRequest("Unexpected error occurred"), 400),
])
def test_token_verification_errors_map_to_http_status(monkeypatch, error, status):
    monkeypatch.setattr(dependencies, "verify_token", MagicMock(side_effect=error))

    response = _client(dependencies.get_current_user).get(
        "/protected", headers={"Authorization": "Bearer not-a-real-token"}
    )

    assert response.status_code == status
    assert response.json()["detail"] == error.message
