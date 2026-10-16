"""CTF router authorization (PRD R4): who may reach each /ctf route, and how a disabled deployment
hides the feature (SC-19). The real auth dependencies run; only the signed-in user is substituted."""
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import dependencies
from common.models.response import CtfFlagRevealResponse, CtfStudentBoardResponse
from common.models.users import AgogeUser
from core.ctf.audit import CtfAudit
from routers import ctf as ctf_module
from routers import ctf_board as ctf_board_module

CTF_ID = "ctfaaaaaaa"
WORKOUT = "wkaaaaaaaa"
FLAG = "agoge{web1_0123456789abcdef0123}"

# AnonymousAppUser() fails its own validation (uid/email None), so a no-permission user stands in.
ANONYMOUS = AgogeUser(uid="anonymous", email="anonymous@example.edu", permissions={})
STUDENT = AgogeUser(uid="student", email="student@example.edu", permissions={"student": True})
PENDING = AgogeUser(uid="pending", email="pending@example.edu", permissions={"pending": True})
GM = AgogeUser(uid="gm", email="gm@example.edu", permissions={"instructor": True})
ADMIN = AgogeUser(uid="admin", email="admin@example.edu", permissions={"instructor": True, "admin": True})
# An admin flag alone passes teacher_required (is_authorized = instructor or admin).
ADMIN_ONLY = AgogeUser(uid="adminonly", email="adminonly@example.edu", permissions={"admin": True})

NON_INSTRUCTORS = [ANONYMOUS, STUDENT, PENDING]
NON_ADMINS = [ANONYMOUS, STUDENT, PENDING, GM]


def _uid(user):
    return user.uid


class FakeLogDb:
    def __init__(self):
        self.rows = []

    def insert(self, collection_name, data):
        self.rows.append(data)


class Harness:
    """Both CTF routers on one app, with every core class mocked so a call that gets through is visible."""

    def __init__(self, monkeypatch, user=None, enabled=True):
        self.log_db = FakeLogDb()
        self.event = MagicMock(name="CtfEvent()")
        self.hosts = MagicMock(name="CtfHosts()")
        self.scoring = MagicMock(name="CtfScoring()")
        self.board_scoring = MagicMock(name="board CtfScoring()")
        monkeypatch.setattr(ctf_module, "CtfEvent", MagicMock(return_value=self.event))
        monkeypatch.setattr(ctf_module, "CtfHosts", MagicMock(return_value=self.hosts))
        monkeypatch.setattr(ctf_module, "CtfScoring", MagicMock(return_value=self.scoring))
        monkeypatch.setattr(ctf_module, "CtfAudit", lambda env_dict=None: CtfAudit(db=self.log_db))
        monkeypatch.setattr(ctf_module.IdGenerator, "build_id", staticmethod(lambda: "newctfidxx"))
        monkeypatch.setattr(ctf_board_module, "CtfScoring", MagicMock(return_value=self.board_scoring))
        for module in (dependencies, ctf_module, ctf_board_module):
            monkeypatch.setattr(module, "is_ctf_enabled", lambda: enabled)

        app = FastAPI()
        app.include_router(ctf_module.ctf_router)
        app.include_router(ctf_board_module.ctf_board_router)
        if user is not None:
            app.dependency_overrides[dependencies.get_current_user] = lambda: user
        app.dependency_overrides[dependencies.get_cloud_env] = lambda: {}
        self.client = TestClient(app, raise_server_exceptions=False)

    def core_calls(self):
        return self.event.mock_calls + self.hosts.mock_calls + self.scoring.mock_calls + self.board_scoring.mock_calls


def call(client, method, path, body=None):
    if body is None:
        return client.request(method.upper(), path)
    return client.request(method.upper(), path, json=body)


# Every /ctf route in the PRD endpoint table: (method, path, json body).
CONFIG_ROUTE = ("get", "/ctf/config/", None)
DELETE_ROUTE = ("delete", f"/ctf/{CTF_ID}/", None)
REVEAL_ROUTE = ("get", f"/ctf/{CTF_ID}/flags/web1/reveal/?workout_id={WORKOUT}", None)
GATED_ROUTES = [
    ("get", "/ctf/", None),
    ("post", "/ctf/", {"unit_id": "unitabcdef"}),
    ("get", f"/ctf/{CTF_ID}/", None),
    ("put", f"/ctf/{CTF_ID}/", {"public_scoreboard_enabled": True}),
    DELETE_ROUTE,
    ("get", f"/ctf/{CTF_ID}/state/", None),
    ("put", f"/ctf/{CTF_ID}/action/", {"action": "start"}),
    ("get", f"/ctf/{CTF_ID}/flags/", None),
    ("put", f"/ctf/{CTF_ID}/flags/", {}),
    REVEAL_ROUTE,
    ("get", f"/ctf/{CTF_ID}/boards/", None),
    ("get", f"/ctf/{CTF_ID}/hosts/", None),
    ("put", f"/ctf/{CTF_ID}/boards/{WORKOUT}/hosts/web/reset/", {"mode": "replant"}),
    ("put", f"/ctf/{CTF_ID}/boards/{WORKOUT}/score/", {"delta": 5, "reason": "bonus"}),
    ("get", f"/ctf/{CTF_ID}/scoreboard/", None),
    ("get", f"/ctf/{CTF_ID}/submissions/", None),
    ("get", f"/ctf/{CTF_ID}/log/", None),
]
ALL_CTF_ROUTES = [CONFIG_ROUTE] + GATED_ROUTES
GATED_BOARD_ROUTES = [
    ("post", f"/ctf-board/{WORKOUT}/submit/", {"flag": FLAG}),
    ("post", f"/ctf-board/{WORKOUT}/hint/web1/", None),
    ("get", f"/ctf-board/{WORKOUT}/scoreboard/", None),
]


def test_route_table_covers_every_instructor_route():
    # A route added to ctf_router without a row here would silently escape these auth tests.
    def key(method, path):
        return method.upper(), path.split("?")[0]

    def template(path):
        return (path.replace("{ctf_id}", CTF_ID).replace("{workout_id}", WORKOUT)
                .replace("{flag_id}", "web1").replace("{server}", "web"))

    registered = {key(m, template(r.path)) for r in ctf_module.ctf_router.routes for m in r.methods}
    assert registered == {key(m, p) for m, p, _ in ALL_CTF_ROUTES}


@pytest.mark.parametrize("user", NON_INSTRUCTORS, ids=_uid)
@pytest.mark.parametrize("method, path, body", ALL_CTF_ROUTES)
def test_non_instructor_gets_403_on_every_ctf_route(monkeypatch, user, method, path, body):
    h = Harness(monkeypatch, user=user)

    response = call(h.client, method, path, body)

    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient permissions"
    assert h.core_calls() == []
    # Refused before the route body runs, so no audit row is written either.
    assert h.log_db.rows == []


@pytest.mark.parametrize("method, path, body", ALL_CTF_ROUTES)
def test_request_without_a_token_never_reaches_a_ctf_route(monkeypatch, method, path, body):
    # No get_current_user override: HTTPBearer (auto_error) refuses a missing Authorization header with 403.
    h = Harness(monkeypatch, user=None)

    response = call(h.client, method, path, body)

    assert response.status_code == 403
    assert h.core_calls() == []
    assert h.log_db.rows == []


@pytest.mark.parametrize("user", [GM, ADMIN, ADMIN_ONLY], ids=_uid)
@pytest.mark.parametrize("method, path, body", [
    r for r in ALL_CTF_ROUTES if r not in (DELETE_ROUTE, REVEAL_ROUTE)
])
def test_instructor_passes_auth_on_every_teacher_route(monkeypatch, user, method, path, body):
    h = Harness(monkeypatch, user=user)

    response = call(h.client, method, path, body)

    # Core is a MagicMock, so a response may fail to serialize (500); auth is what is under test.
    assert response.status_code not in (401, 403, 404)


@pytest.mark.parametrize("user", NON_ADMINS, ids=_uid)
def test_non_admin_gets_403_on_delete(monkeypatch, user):
    h = Harness(monkeypatch, user=user)

    response = h.client.delete(f"/ctf/{CTF_ID}/")

    assert response.status_code == 403
    h.event.delete.assert_not_called()
    assert h.log_db.rows == []


@pytest.mark.parametrize("user", NON_ADMINS, ids=_uid)
def test_reveal_is_403_for_an_instructor_and_below(monkeypatch, user):
    h = Harness(monkeypatch, user=user)

    response = h.client.get(f"/ctf/{CTF_ID}/flags/web1/reveal/?workout_id={WORKOUT}")

    assert response.status_code == 403
    h.event.reveal.assert_not_called()
    assert h.log_db.rows == []
    assert "agoge{" not in response.text


def test_admin_may_delete(monkeypatch):
    h = Harness(monkeypatch, user=ADMIN)

    response = h.client.delete(f"/ctf/{CTF_ID}/")

    assert response.status_code == 200
    h.event.delete.assert_called_once_with(CTF_ID, ADMIN)


def test_admin_may_reveal(monkeypatch):
    h = Harness(monkeypatch, user=ADMIN)
    h.event.reveal.return_value = CtfFlagRevealResponse(flag_id="web1", workout_id=WORKOUT, value=FLAG)

    response = h.client.get(f"/ctf/{CTF_ID}/flags/web1/reveal/?workout_id={WORKOUT}")

    assert response.status_code == 200
    h.event.reveal.assert_called_once_with(CTF_ID, "web1", WORKOUT, ADMIN)


# SC-19: with ctf_enabled false the feature is hidden.

@pytest.mark.parametrize("user", [ADMIN, GM, STUDENT, ANONYMOUS], ids=_uid)
@pytest.mark.parametrize("method, path, body", GATED_ROUTES)
def test_disabled_is_404_on_every_route_but_config_whoever_asks(monkeypatch, user, method, path, body):
    # The enabled gate runs before the role check, so a 403 can't reveal that a route exists.
    h = Harness(monkeypatch, user=user, enabled=False)

    response = call(h.client, method, path, body)

    assert response.status_code == 404
    assert h.core_calls() == []
    assert h.log_db.rows == []


def test_disabled_config_answers_an_instructor(monkeypatch):
    h = Harness(monkeypatch, user=GM, enabled=False)

    response = h.client.get("/ctf/config/")

    assert response.status_code == 200
    assert response.json()["data"] == {"ctf_enabled": False}


@pytest.mark.parametrize("user", NON_INSTRUCTORS, ids=_uid)
def test_disabled_config_still_refuses_a_non_instructor(monkeypatch, user):
    h = Harness(monkeypatch, user=user, enabled=False)

    assert h.client.get("/ctf/config/").status_code == 403


@pytest.mark.parametrize("method, path, body", GATED_BOARD_ROUTES)
def test_disabled_student_routes_are_404(monkeypatch, method, path, body):
    h = Harness(monkeypatch, enabled=False)

    response = call(h.client, method, path, body)

    assert response.status_code == 404
    assert h.core_calls() == []


def test_disabled_student_board_is_not_enrolled(monkeypatch):
    h = Harness(monkeypatch, enabled=False)

    response = h.client.get(f"/ctf-board/{WORKOUT}/")

    assert response.status_code == 200
    assert response.json()["data"] == CtfStudentBoardResponse(enrolled=False).model_dump(mode="json")
    assert h.core_calls() == []


@pytest.mark.parametrize("method, path, body", GATED_BOARD_ROUTES + [("get", f"/ctf-board/{WORKOUT}/", None)])
def test_student_routes_need_no_token(monkeypatch, method, path, body):
    # The student board is reached from the workout page, which has no sign-in.
    h = Harness(monkeypatch, user=None)

    response = call(h.client, method, path, body)

    assert response.status_code not in (401, 403)
