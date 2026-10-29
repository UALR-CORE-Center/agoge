"""Authorization on /llm-agents (admin only, including the WebSocket) and /puzzle-control
(instructor only), plus /puzzle-control error handling. The real auth dependencies run; only the signed-in user is substituted,
and the core classes are mocked so a call that gets through is visible."""
from unittest.mock import MagicMock

import pytest
import requests
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

import dependencies
from common.exceptions.agoge import AgogeValidationError, Unauthorized
from common.models.competency_assessment_agent import AgentAttributes
from common.models.users import AgogeUser, AnonymousAppUser
from routers import llm_agent as llm_agent_module
from routers import puzzle_control as puzzle_control_module

ANONYMOUS = AnonymousAppUser()
STUDENT = AgogeUser(uid="student", email="student@example.edu", permissions={"student": True})
INSTRUCTOR = AgogeUser(uid="gm", email="gm@example.edu", permissions={"instructor": True})
ADMIN = AgogeUser(uid="admin", email="admin@example.edu", permissions={"instructor": True, "admin": True})

ENV = {"project": "test-project"}

AGENT_FIELDS = [
    "friendly_name", "role", "industry", "education_level", "tone", "prior_experience",
    "technical_proficiency", "relationship_to_learner", "expected_conversation_time",
    "conversation_objective", "task", "feedback_preference", "assessment_criteria",
]
AGENT_BODY = {"id": "agent-one", **{field: "x" for field in AGENT_FIELDS}}

LLM_ROUTES = [
    ("post", "/llm-agents/", AGENT_BODY),
    ("get", "/llm-agents/agent-one", None),
    ("put", "/llm-agents/agent-one", AGENT_BODY),
    ("delete", "/llm-agents/agent-one", None),
]

PUZZLE_ROUTES = [
    ("get", "/puzzle-control/", None),
    ("post", "/puzzle-control/test/", {"title": "t", "questions": [], "sku": "H6008", "device": "d"}),
    ("get", "/puzzle-control/test/", None),
    ("get", "/puzzle-control/test/abcdef", None),
    ("post", "/puzzle-control/question/check", {"test_id": "t", "question_id": "q", "answer": "a"}),
    ("post", "/puzzle-control/control", {"sku": "H6008", "device": "d", "action": ["brightness", 50]}),
]


def _uid(user):
    return user.uid or "anonymous"


class Harness:
    def __init__(self, monkeypatch, user=None):
        self.agent = MagicMock(name="LLMAgent")
        self.agent.get_agent.return_value = AgentAttributes(**AGENT_BODY)
        self.factory = MagicMock(return_value=self.agent)
        self.puzzle = MagicMock(name="PuzzleControl()")
        self.puzzle.list_devices.return_value = [{"device": "d"}]
        self.puzzle.get_tests.return_value = [{"id": "t"}]
        self.puzzle.get_test.return_value = {"id": "t"}
        self.puzzle.check_answer.return_value = {"isCorrect": True}
        self.puzzle.create_test.return_value = {"id": "t"}
        self.puzzle.control_device.return_value = {"code": 200}
        monkeypatch.setattr(llm_agent_module.LLMAgentFactory, "create_llm_agent_object", self.factory)
        self.puzzle_cls = MagicMock(return_value=self.puzzle)
        monkeypatch.setattr(puzzle_control_module, "PuzzleControl", self.puzzle_cls)

        app = FastAPI()
        app.include_router(llm_agent_module.llm_agent_router)
        app.include_router(puzzle_control_module.puzzle_control_router)
        if user is not None:
            app.dependency_overrides[dependencies.get_current_user] = lambda: user
        app.dependency_overrides[dependencies.get_cloud_env] = lambda: ENV
        self.client = TestClient(app, raise_server_exceptions=False)

    def call(self, method, path, body=None):
        if body is None:
            return self.client.request(method.upper(), path)
        return self.client.request(method.upper(), path, json=body)


@pytest.mark.parametrize("method,path,body", LLM_ROUTES + PUZZLE_ROUTES)
def test_no_token_is_rejected(monkeypatch, method, path, body):
    h = Harness(monkeypatch)
    assert h.call(method, path, body).status_code == 403
    h.factory.assert_not_called()
    assert h.puzzle.mock_calls == []


@pytest.mark.parametrize("user", [ANONYMOUS, STUDENT, INSTRUCTOR], ids=_uid)
@pytest.mark.parametrize("method,path,body", LLM_ROUTES)
def test_llm_routes_reject_non_admins(monkeypatch, user, method, path, body):
    h = Harness(monkeypatch, user=user)
    assert h.call(method, path, body).status_code == 403
    h.factory.assert_not_called()


@pytest.mark.parametrize("method,path,body", LLM_ROUTES)
def test_llm_routes_admit_admin(monkeypatch, method, path, body):
    h = Harness(monkeypatch, user=ADMIN)
    assert h.call(method, path, body).status_code == 200
    h.factory.assert_called_once()


@pytest.mark.parametrize("user", [ANONYMOUS, STUDENT], ids=_uid)
@pytest.mark.parametrize("method,path,body", PUZZLE_ROUTES)
def test_puzzle_routes_reject_non_instructors(monkeypatch, user, method, path, body):
    h = Harness(monkeypatch, user=user)
    assert h.call(method, path, body).status_code == 403
    assert h.puzzle.mock_calls == []


@pytest.mark.parametrize("user", [INSTRUCTOR, ADMIN], ids=_uid)
@pytest.mark.parametrize("method,path,body", PUZZLE_ROUTES)
def test_puzzle_routes_admit_instructors(monkeypatch, user, method, path, body):
    h = Harness(monkeypatch, user=user)
    assert h.call(method, path, body).status_code == 200
    assert h.puzzle.mock_calls != []


def _fake_verify(users_by_token):
    def verify(request, token):
        if token.credentials not in users_by_token:
            raise Unauthorized("Authentication failed! Invalid token")
        return users_by_token[token.credentials]
    return verify


@pytest.mark.parametrize("query", ["", "?token=bogus", "?token=student", "?token=instructor"])
def test_websocket_rejects_handshake_without_admin_token(monkeypatch, query):
    monkeypatch.setattr(dependencies, "verify_token", _fake_verify({"student": STUDENT, "instructor": INSTRUCTOR}))
    h = Harness(monkeypatch)
    with pytest.raises(WebSocketDisconnect) as exc:
        with h.client.websocket_connect(f"/llm-agents/agent-one/chat{query}"):
            pass
    assert exc.value.code == 1008
    h.factory.assert_not_called()


def test_websocket_accepts_admin_token(monkeypatch):
    monkeypatch.setattr(dependencies, "verify_token", _fake_verify({"admin": ADMIN}))
    h = Harness(monkeypatch)
    with h.client.websocket_connect("/llm-agents/agent-one/chat?token=admin"):
        pass
    h.factory.assert_called_once_with(agent_name="agent-one")


# --- /puzzle-control error handling ---------------------------------------------------------

@pytest.mark.parametrize("method,path,body", PUZZLE_ROUTES)
def test_puzzle_routes_thread_env_dict(monkeypatch, method, path, body):
    h = Harness(monkeypatch, user=INSTRUCTOR)
    h.call(method, path, body)
    h.puzzle_cls.assert_called_once_with(env_dict=ENV)


def test_get_test_unknown_join_code_is_404(monkeypatch):
    h = Harness(monkeypatch, user=INSTRUCTOR)
    h.puzzle.get_test.return_value = None
    response = h.call("get", "/puzzle-control/test/abcdef")
    assert response.status_code == 404
    assert response.json()["detail"] == "No tests found"


def test_check_unknown_question_is_404(monkeypatch):
    h = Harness(monkeypatch, user=INSTRUCTOR)
    h.puzzle.check_answer.return_value = None
    response = h.call("post", "/puzzle-control/question/check", {"test_id": "t", "question_id": "q", "answer": "a"})
    assert response.status_code == 404


@pytest.mark.parametrize("body", [
    {"question_id": "q", "answer": "a"},
    {"test_id": "t", "answer": "a"},
    {"test_id": "t", "question_id": "q"},
])
def test_check_missing_fields_is_400(monkeypatch, body):
    h = Harness(monkeypatch, user=INSTRUCTOR)
    assert h.call("post", "/puzzle-control/question/check", body).status_code == 400
    h.puzzle.check_answer.assert_not_called()


def test_no_tests_is_an_empty_list(monkeypatch):
    h = Harness(monkeypatch, user=INSTRUCTOR)
    h.puzzle.get_tests.return_value = []
    response = h.call("get", "/puzzle-control/test/")
    assert response.status_code == 200
    assert response.json() == {"tests": []}


def test_create_test_missing_field_is_422(monkeypatch):
    h = Harness(monkeypatch, user=INSTRUCTOR)
    assert h.call("post", "/puzzle-control/test/", {"title": "t", "questions": []}).status_code == 422
    h.puzzle.create_test.assert_not_called()


def test_create_test_validation_error_is_400(monkeypatch):
    h = Harness(monkeypatch, user=INSTRUCTOR)
    h.puzzle.create_test.side_effect = AgogeValidationError("question 0 is missing a title")
    response = h.call("post", "/puzzle-control/test/", PUZZLE_ROUTES[1][2])
    assert response.status_code == 400
    assert "missing a title" in response.json()["detail"]


@pytest.mark.parametrize("method,path,body", PUZZLE_ROUTES)
def test_unexpected_errors_do_not_echo_exception_text(monkeypatch, method, path, body):
    h = Harness(monkeypatch, user=INSTRUCTOR)
    h.puzzle_cls.side_effect = RuntimeError("secret-internal-detail")
    response = h.call(method, path, body)
    assert response.status_code == 500
    assert "secret-internal-detail" not in response.text


def test_govee_failure_is_502_without_upstream_text(monkeypatch):
    h = Harness(monkeypatch, user=INSTRUCTOR)
    h.puzzle.control_device.side_effect = requests.HTTPError("401 Govee-API-Key rejected")
    response = h.call("post", "/puzzle-control/control", PUZZLE_ROUTES[5][2])
    assert response.status_code == 502
    assert "Govee-API-Key" not in response.text


@pytest.mark.parametrize("body", [
    {"device": "d", "action": ["brightness", 50]},
    {"sku": "H6008", "device": "d"},
    {"sku": "H6008", "device": "d", "action": ["brightness", 50], "actions": [["brightness", 10]]},
    {"sku": "H6008", "device": "d", "action": ["teleport", 1]},
])
def test_control_bad_request_is_400_and_never_reaches_govee(monkeypatch, body):
    h = Harness(monkeypatch, user=INSTRUCTOR)
    assert h.call("post", "/puzzle-control/control", body).status_code == 400
    h.puzzle.control_device.assert_not_called()


def test_control_applies_each_action(monkeypatch):
    h = Harness(monkeypatch, user=INSTRUCTOR)
    body = {"sku": "H6008", "device": "d", "actions": [["brightness", 50], ["switchColor", "#00ff00"]]}
    response = h.call("post", "/puzzle-control/control", body)
    assert response.status_code == 200
    assert response.json()["applied"]["count"] == 2
    assert h.puzzle.control_device.call_count == 2
