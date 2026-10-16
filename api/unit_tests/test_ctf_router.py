"""api/routers/ctf.py wiring (PRD R1): each /ctf route calls its core method, answers in the
AgogeResponse envelope, maps core errors through to_http_exception, and audits (SC-18)."""
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import dependencies
from common.exceptions.agoge import Conflict, NotFound, Unauthorized
from common.models.agoge import CtfActionRequest, CtfUpdateRequest
from common.models.response import CtfFlagRevealResponse
from common.models.users import AgogeUser
from core.ctf.audit import CtfAudit
from routers import ctf as ctf_router_module

CTF_ID = "ctfaaaaaaa"
WORKOUT = "wkaaaaaaaa"
GM = AgogeUser(uid="gm", email="gm@example.edu", permissions={"instructor": True})
ADMIN = AgogeUser(uid="admin", email="admin@example.edu", permissions={"instructor": True, "admin": True})


class FakeLogDb:
    def __init__(self):
        self.rows = []

    def insert(self, collection_name, data):
        self.rows.append(data)


class Harness:
    def __init__(self, monkeypatch, user=GM, enabled=True):
        self.log_db = FakeLogDb()
        self.event = MagicMock(name="CtfEvent()")
        self.hosts = MagicMock(name="CtfHosts()")
        self.scoring = MagicMock(name="CtfScoring()")
        monkeypatch.setattr(ctf_router_module, "CtfEvent", MagicMock(return_value=self.event))
        monkeypatch.setattr(ctf_router_module, "CtfHosts", MagicMock(return_value=self.hosts))
        monkeypatch.setattr(ctf_router_module, "CtfScoring", MagicMock(return_value=self.scoring))
        # The real audit helper over a fake log collection, so row count and result are the real ones.
        monkeypatch.setattr(ctf_router_module, "CtfAudit", lambda env_dict=None: CtfAudit(db=self.log_db))
        monkeypatch.setattr(ctf_router_module.IdGenerator, "build_id", staticmethod(lambda: "newctfidxx"))
        monkeypatch.setattr(dependencies, "is_ctf_enabled", lambda: enabled)
        monkeypatch.setattr(ctf_router_module, "is_ctf_enabled", lambda: enabled)

        app = FastAPI()
        app.include_router(ctf_router_module.ctf_router)
        app.dependency_overrides[dependencies.get_current_user] = lambda: user
        app.dependency_overrides[dependencies.get_cloud_env] = lambda: {}
        self.client = TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def h(monkeypatch):
    return Harness(monkeypatch)


# Every route but /ctf/config/: (method, path, json body).
ROUTES = [
    ("get", "/ctf/", None),
    ("post", "/ctf/", {"unit_id": "unitabcdef"}),
    ("get", f"/ctf/{CTF_ID}/", None),
    ("put", f"/ctf/{CTF_ID}/", {"public_scoreboard_enabled": True}),
    ("delete", f"/ctf/{CTF_ID}/", None),
    ("get", f"/ctf/{CTF_ID}/state/", None),
    ("put", f"/ctf/{CTF_ID}/action/", {"action": "start"}),
    ("get", f"/ctf/{CTF_ID}/flags/", None),
    ("put", f"/ctf/{CTF_ID}/flags/", {}),
    ("get", f"/ctf/{CTF_ID}/flags/web1/reveal/?workout_id={WORKOUT}", None),
    ("get", f"/ctf/{CTF_ID}/boards/", None),
    ("get", f"/ctf/{CTF_ID}/hosts/", None),
    ("put", f"/ctf/{CTF_ID}/boards/{WORKOUT}/hosts/web/reset/", {"mode": "replant"}),
    ("put", f"/ctf/{CTF_ID}/boards/{WORKOUT}/score/", {"delta": 5, "reason": "bonus"}),
    ("get", f"/ctf/{CTF_ID}/scoreboard/", None),
    ("get", f"/ctf/{CTF_ID}/submissions/", None),
    ("get", f"/ctf/{CTF_ID}/log/", None),
]


def call(client, method, path, body=None):
    if body is None:
        return client.request(method.upper(), path)
    return client.request(method.upper(), path, json=body)


@pytest.mark.parametrize("method, path, body", ROUTES)
def test_every_route_but_config_is_404_when_ctf_is_disabled(monkeypatch, method, path, body):
    h = Harness(monkeypatch, user=ADMIN, enabled=False)

    response = call(h.client, method, path, body)

    assert response.status_code == 404
    assert h.log_db.rows == []


def test_config_answers_even_when_disabled(monkeypatch):
    h = Harness(monkeypatch, enabled=False)

    response = h.client.get("/ctf/config/")

    assert response.status_code == 200
    assert response.json()["data"] == {"ctf_enabled": False}


def test_create_uses_the_audited_id_and_returns_it(h):
    response = h.client.post("/ctf/", json={"unit_id": "unitabcdef"})

    assert response.status_code == 200
    assert response.json()["data"]["build_id"] == "newctfidxx"
    h.event.create.assert_called_once_with("unitabcdef", GM, ctf_id="newctfidxx")
    [row] = h.log_db.rows
    assert (row["ctf_id"], row["action"], row["target"], row["result"]) == ("newctfidxx", "CTF_CREATE", "unitabcdef", "OK")


def test_core_refusal_is_one_denied_row_and_the_mapped_status(h):
    h.event.create.side_effect = Unauthorized(message="not on unit")

    response = h.client.post("/ctf/", json={"unit_id": "unitabcdef"})

    assert response.status_code == 403
    assert response.json()["detail"] == "Requesting user is not authorized to make this request"
    assert [row["result"] for row in h.log_db.rows] == ["DENIED"]


def test_core_not_found_is_404_and_an_error_row(monkeypatch):
    h = Harness(monkeypatch, user=ADMIN)
    h.event.delete.side_effect = NotFound(message="CTF event not found")

    response = h.client.delete(f"/ctf/{CTF_ID}/")

    assert response.status_code == 404
    assert response.json()["detail"] == "CTF event not found"
    assert [(row["action"], row["result"]) for row in h.log_db.rows] == [("CTF_DELETE", "ERROR")]


def test_unhandled_core_error_is_a_generic_500(h):
    h.event.state.side_effect = RuntimeError("firestore exploded")

    response = h.client.get(f"/ctf/{CTF_ID}/state/")

    assert response.status_code == 500
    assert response.json()["detail"] == "Something went wrong"


@pytest.mark.parametrize("action", ["arm", "start", "pause", "resume", "end", "archive"])
def test_action_is_audited_under_its_log_action(h, action):
    h.event.process_action.return_value = None

    response = h.client.put(f"/ctf/{CTF_ID}/action/", json={"action": action})

    assert response.status_code == 200
    h.event.process_action.assert_called_once_with(CTF_ID, CtfActionRequest(action=action), GM)
    assert [row["action"] for row in h.log_db.rows] == [f"CTF_{action.upper()}"]


def test_illegal_action_conflict_is_409_with_core_message(h):
    h.event.process_action.side_effect = Conflict(message="Cannot start an event in state DRAFT")

    response = h.client.put(f"/ctf/{CTF_ID}/action/", json={"action": "start"})

    assert response.status_code == 409
    assert response.json()["detail"] == "Cannot start an event in state DRAFT"
    assert [row["result"] for row in h.log_db.rows] == ["DENIED"]


@pytest.mark.parametrize("path, body", [
    (f"/ctf/{CTF_ID}/action/", {"action": "explode"}),
    (f"/ctf/{CTF_ID}/action/", None),
    (f"/ctf/{CTF_ID}/boards/{WORKOUT}/hosts/web/reset/", {"mode": "reimage"}),
    (f"/ctf/{CTF_ID}/boards/{WORKOUT}/score/", {"delta": 5, "reason": ""}),
    (f"/ctf/{CTF_ID}/", {"ends_at": "soon"}),
    (f"/ctf/{CTF_ID}/flags/", ["not", "an", "object"]),
])
def test_malformed_body_is_400_and_never_reaches_core(h, path, body):
    response = call(h.client, "put", path, body)

    assert response.status_code == 400
    assert response.json()["detail"].startswith("Invalid request body: ")
    assert h.log_db.rows == []
    assert h.event.method_calls == h.hosts.method_calls == h.scoring.method_calls == []


def test_malformed_create_body_is_400(h):
    response = h.client.post("/ctf/", json={"unit_id": "NOT-AN-ID"})

    assert response.status_code == 400
    h.event.create.assert_not_called()


def test_update_passes_only_the_sent_fields(h):
    h.event.update.return_value = None

    response = h.client.put(f"/ctf/{CTF_ID}/", json={"scoreboard_frozen_at": None})

    assert response.status_code == 200
    [[ctf_id, request, caller]] = [c.args for c in h.event.update.call_args_list]
    assert (ctf_id, caller) == (CTF_ID, GM)
    assert isinstance(request, CtfUpdateRequest) and request.model_fields_set == {"scoreboard_frozen_at"}
    assert h.log_db.rows[0]["detail"] == {"fields": "scoreboard_frozen_at"}


def test_replant_passes_scope_and_records_message_count(h):
    h.hosts.replant.return_value = 4

    response = h.client.put(f"/ctf/{CTF_ID}/flags/", json={"workout_ids": [WORKOUT], "servers": None})

    assert response.status_code == 200
    assert response.json()["data"] == {"messages": 4}
    h.hosts.replant.assert_called_once_with(CTF_ID, [WORKOUT], None, GM)
    [row] = h.log_db.rows
    assert (row["action"], row["result"]) == ("FLAG_REPLANT", "OK")
    assert row["detail"] == {"boards": 1, "servers": "all", "messages": 4}


def test_host_reset_publishes_through_core_and_audits_once(h):
    response = h.client.put(f"/ctf/{CTF_ID}/boards/{WORKOUT}/hosts/web/reset/", json={"mode": "restart"})

    assert response.status_code == 200
    h.hosts.reset.assert_called_once_with(CTF_ID, WORKOUT, "web", "restart", GM)
    [row] = h.log_db.rows
    assert (row["action"], row["target"], row["detail"]) == ("HOST_RESET", "web", {"workout_id": WORKOUT, "mode": "restart"})


def test_flag_shaped_server_segment_still_reaches_core(h):
    # A server name is never put in `detail`, whose flag check would turn this into a 500.
    h.hosts.reset.side_effect = NotFound(message="Server not found")

    response = h.client.put(f"/ctf/{CTF_ID}/boards/{WORKOUT}/hosts/agoge{{x}}/reset/", json={"mode": "restart"})

    assert response.status_code == 404
    assert len(h.log_db.rows) == 1


def test_score_adjust_relies_on_cores_own_audit_row(h):
    h.scoring.adjust.return_value = 42

    response = h.client.put(f"/ctf/{CTF_ID}/boards/{WORKOUT}/score/", json={"delta": -3, "reason": "typo"})

    assert response.status_code == 200
    assert response.json()["data"] == {"workout_id": WORKOUT, "score": 42}
    h.scoring.adjust.assert_called_once_with(CTF_ID, WORKOUT, -3, "typo", GM)
    # SC-18: adjust writes SCORE_ADJUST itself; the router must not add a second row.
    assert h.log_db.rows == []


def test_reveal_is_admin_only(h):
    response = h.client.get(f"/ctf/{CTF_ID}/flags/web1/reveal/?workout_id={WORKOUT}")

    assert response.status_code == 403
    h.event.reveal.assert_not_called()


def test_reveal_returns_value_and_never_logs_it(monkeypatch):
    h = Harness(monkeypatch, user=ADMIN)
    value = "agoge{web1_0123456789abcdef0123}"
    h.event.reveal.return_value = CtfFlagRevealResponse(flag_id="web1", workout_id=WORKOUT, value=value)

    response = h.client.get(f"/ctf/{CTF_ID}/flags/web1/reveal/?workout_id={WORKOUT}")

    assert response.status_code == 200
    assert response.json()["data"]["value"] == value
    h.event.reveal.assert_called_once_with(CTF_ID, "web1", WORKOUT, ADMIN)
    [row] = h.log_db.rows
    assert (row["action"], row["target"], row["result"]) == ("FLAG_REVEAL", "web1", "OK")
    assert value not in repr(row)


@pytest.mark.parametrize("query", ["", "?workout_id=", "?workout_id=agoge{x}"])
def test_reveal_without_a_valid_workout_id_is_400(monkeypatch, query):
    h = Harness(monkeypatch, user=ADMIN)

    response = h.client.get(f"/ctf/{CTF_ID}/flags/web1/reveal/{query}")

    assert response.status_code == 400
    assert h.log_db.rows == []


def test_delete_is_admin_only(h):
    response = h.client.delete(f"/ctf/{CTF_ID}/")

    assert response.status_code == 403
    h.event.delete.assert_not_called()


@pytest.mark.parametrize("path, target, method, kwargs", [
    ("/ctf/", "event", "list", {}),
    (f"/ctf/{CTF_ID}/flags/", "event", "flags", {}),
    (f"/ctf/{CTF_ID}/boards/", "event", "boards", {}),
    (f"/ctf/{CTF_ID}/hosts/", "hosts", "hosts", {}),
    (f"/ctf/{CTF_ID}/scoreboard/", "scoring", "scoreboard", {}),
    (f"/ctf/{CTF_ID}/submissions/?verdict=correct", "event", "submissions", {"verdict": "correct"}),
    (f"/ctf/{CTF_ID}/log/?action=CTF_ARM", "event", "log", {"action": "CTF_ARM"}),
])
def test_collection_reads_use_the_items_envelope(h, path, target, method, kwargs):
    getattr(getattr(h, target), method).return_value = [{"row": 1}]

    response = h.client.get(path)

    assert response.status_code == 200
    assert response.json()["data"] == {"items": [{"row": 1}]}
    args = (GM,) if method == "list" else (CTF_ID, GM)
    getattr(getattr(h, target), method).assert_called_once_with(*args, **kwargs)
    assert h.log_db.rows == []


def test_malformed_ctf_id_never_reaches_core(h):
    assert h.client.get("/ctf/NOTANID123/").status_code == 422
    h.event.get.assert_not_called()
