from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from common.models.users import AgogeUser, AnonymousAppUser
from dependencies import get_current_user


def test_anonymous_user_constructs_without_identity():
    user = AnonymousAppUser()

    assert user.uid is None
    assert user.email is None
    assert user.name == "Anonymous User"
    assert user.is_anonymous is True
    assert user.is_authenticated is False


def test_anonymous_user_has_no_permissions():
    user = AnonymousAppUser()

    assert user.permissions == {}
    assert user.is_instructor is False
    assert user.is_admin is False
    assert user.is_authorized is False


def test_anonymous_user_gets_default_lms_settings():
    # settings must be the parent's default dict, not None, so get_settings_overview works.
    user = AnonymousAppUser()

    assert user.settings == AgogeUser(uid="u", email="u@example.edu").settings
    assert not any(user.get_settings_overview().values())


def test_anonymous_user_does_not_loosen_the_parent_model():
    # The Optional override belongs to the subclass alone; real users still need an identity.
    assert AgogeUser.model_fields["uid"].is_required()
    assert AgogeUser.model_fields["email"].is_required()


def test_get_current_user_returns_anonymous_without_a_token():
    # HTTPBearer(auto_error=True) answers a missing header first, so call the dependency directly.
    user = get_current_user(request=None, token=None)

    assert isinstance(user, AnonymousAppUser)


def test_missing_token_still_refused_by_bearer_scheme():
    app = FastAPI()

    @app.get("/me")
    def me(user: AgogeUser = Depends(get_current_user)):
        return {"uid": user.uid}

    response = TestClient(app).get("/me")

    assert response.status_code == 403
