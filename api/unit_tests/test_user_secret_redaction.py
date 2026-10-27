from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from common.models.users import AgogeUser, APISettings
from routers import user as routes

OWNER_ID = "owner-uid"


def _stored_user() -> AgogeUser:
    return AgogeUser(
        uid=OWNER_ID,
        email="owner@example.edu",
        permissions={"instructor": True, "admin": False},
        settings={
            "canvas": APISettings(api="canvas-api-key", url="https://canvas.example.edu", secret="canvas-secret"),
            "blackboard": APISettings(api="bb-api-key", url="https://bb.example.edu", secret="bb-secret"),
        },
    )


@pytest.fixture
def users(monkeypatch):
    handler = MagicMock()
    handler.get_user_from_request.return_value = _stored_user()
    handler.update_settings.return_value = _stored_user()
    monkeypatch.setattr(routes, "Users", MagicMock(return_value=handler))
    return handler


def _client(requester: AgogeUser) -> TestClient:
    app = FastAPI()
    app.include_router(routes.user_router)
    app.dependency_overrides[routes.teacher_required] = lambda: requester
    return TestClient(app)


def _requester(uid: str, admin: bool = False) -> AgogeUser:
    return AgogeUser(uid=uid, email=f"{uid}@example.edu", permissions={"instructor": True, "admin": admin})


def _settings(response) -> dict:
    assert response.status_code == 200
    return response.json()["data"]["settings"]


def test_owner_gets_api_key_and_url_but_never_secret(users):
    settings = _settings(_client(_requester(OWNER_ID)).get(f"/users/{OWNER_ID}/"))

    for lms in ("canvas", "blackboard"):
        assert settings[lms]["secret"] is None
    assert settings["canvas"]["api"] == "canvas-api-key"
    assert settings["canvas"]["url"] == "https://canvas.example.edu"


def test_admin_viewing_another_user_gets_no_credentials(users):
    settings = _settings(_client(_requester("admin-uid", admin=True)).get(f"/users/{OWNER_ID}/"))

    for lms in ("canvas", "blackboard"):
        assert settings[lms]["secret"] is None
        assert settings[lms]["api"] is None
    assert settings["canvas"]["url"] == "https://canvas.example.edu"


def test_settings_update_response_omits_secret(users):
    response = _client(_requester(OWNER_ID)).post(
        f"/users/{OWNER_ID}/settings/", json={"settings": {"canvas": {"secret": "new-secret"}}}
    )

    settings = _settings(response)
    assert all(settings[lms]["secret"] is None for lms in ("canvas", "blackboard"))
    assert "secret" not in response.text.replace('"secret":null', "")


def test_redaction_does_not_modify_the_stored_user():
    user = _stored_user()

    user.redacted()

    assert user.settings["canvas"].secret == "canvas-secret"
    assert user.settings["canvas"].api == "canvas-api-key"
