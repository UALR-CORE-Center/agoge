"""api/routers/ctf.py wiring (PRD R1): each /ctf route calls its core method, answers in the
AgogeResponse envelope, maps core errors through to_http_exception, and audits (SC-18)."""
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import dependencies
from common.exceptions.agoge import AgogeValidationError, Conflict, NotFound, Unauthorized
from common.models.agoge import CtfActionRequest, CtfUpdateRequest
from common.models.response import CtfFlagRevealResponse, CtfTeamRow, CtfTemplateRow
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
        self.setup = MagicMock(name="CtfSetup()")
        monkeypatch.setattr(ctf_router_module, "CtfSetup", MagicMock(return_value=self.setup))
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


CREATE_BODY = {"spec_id": "web-lab", "expires": 1893456000}
TEAM_BODY = {"team_name": "Red", "members": ["a@x.edu"]}
SPEC_BODY = {"ctf": {"name": "N", "flags": [{
    "id": "web-root", "server": "web", "slot": 1, "location_type": "file", "path": "/root/flag.txt",
    "operating_system": "linux", "points": 10,
}]}}

# Every route but /ctf/config/: (method, path, json body).
ROUTES = [
    ("get", "/ctf/", None),
    ("get", "/ctf/templates/", None),
    ("post", "/ctf/", CREATE_BODY),
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
    ("get", f"/ctf/{CTF_ID}/teams/", None),
    ("post", f"/ctf/{CTF_ID}/teams/", TEAM_BODY),
    ("put", f"/ctf/{CTF_ID}/teams/{WORKOUT}/", {"members": ["a@x.edu"]}),
    ("delete", f"/ctf/{CTF_ID}/teams/{WORKOUT}/", None),
    ("put", f"/ctf/{CTF_ID}/spec/", SPEC_BODY),
    ("put", f"/ctf/{CTF_ID}/servers/", {"action": "build"}),
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
    response = h.client.post("/ctf/", json={**CREATE_BODY, "name": "Fall CTF"})

    assert response.status_code == 200
    assert response.json()["data"]["build_id"] == "newctfidxx"
    [call] = h.setup.create.call_args_list
    request, caller = call.args
    assert (request.spec_id, request.name, request.expires) == ("web-lab", "Fall CTF", 1893456000)
    assert caller == GM
    assert call.kwargs == {"ctf_id": "newctfidxx"}
    [row] = h.log_db.rows
    assert (row["ctf_id"], row["action"], row["target"], row["result"]) == ("newctfidxx", "CTF_CREATE", "web-lab", "OK")


def test_core_refusal_is_one_denied_row_and_the_mapped_status(h):
    h.setup.create.side_effect = Unauthorized(message="not on unit")

    response = h.client.post("/ctf/", json=CREATE_BODY)

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


@pytest.mark.parametrize("body", [{"unit_id": "unitabcdef"}, {"spec_id": "x"}, {"spec_id": "", "expires": 5}])
def test_malformed_create_body_is_400(h, body):
    response = h.client.post("/ctf/", json=body)

    assert response.status_code == 400
    h.setup.create.assert_not_called()


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
    h.hosts.reset.assert_called_once_with(CTF_ID, WORKOUT, "web", "restart", GM, guest=None)
    [row] = h.log_db.rows
    assert (row["action"], row["target"], row["detail"]) == ("HOST_RESET", "web", {"workout_id": WORKOUT, "mode": "restart"})


def test_guest_host_reset_passes_the_guest_and_names_it_in_the_audit_detail(h):
    response = h.client.put(
        f"/ctf/{CTF_ID}/boards/{WORKOUT}/hosts/web/reset/", json={"mode": "replant", "guest": "ubuntu-lin"},
    )

    assert response.status_code == 200
    h.hosts.reset.assert_called_once_with(CTF_ID, WORKOUT, "web", "replant", GM, guest="ubuntu-lin")
    [row] = h.log_db.rows
    assert (row["action"], row["target"], row["result"]) == ("HOST_RESET", "web", "OK")
    assert row["detail"] == {"workout_id": WORKOUT, "mode": "replant", "guest": "ubuntu-lin"}


def test_unknown_guest_is_404_and_audited_as_a_failure(h):
    h.hosts.reset.side_effect = NotFound(message="Guest nope is not declared on server web")

    response = h.client.put(
        f"/ctf/{CTF_ID}/boards/{WORKOUT}/hosts/web/reset/", json={"mode": "restart", "guest": "nope"},
    )

    assert response.status_code == 404
    [row] = h.log_db.rows
    assert row["detail"]["guest"] == "nope"
    assert row["result"] != "OK"


def test_guest_that_is_not_a_slug_is_a_bad_request_before_core(h):
    response = h.client.put(
        f"/ctf/{CTF_ID}/boards/{WORKOUT}/hosts/web/reset/", json={"mode": "restart", "guest": "agoge{x}"},
    )

    assert response.status_code == 400
    h.hosts.reset.assert_not_called()


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


# --- setup routes: templates, teams, spec, servers ----------------------------------

def test_templates_are_returned_as_items(h):
    h.setup.templates.return_value = [CtfTemplateRow(
        id="web-lab", name="Web Lab", description=None, ctf_name="CTF", flag_count=2, servers=[],
    )]

    response = h.client.get("/ctf/templates/")

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["data"]["items"]] == ["web-lab"]
    h.setup.templates.assert_called_once_with()


def _team_row(**kw):
    return CtfTeamRow(
        workout_id=WORKOUT, team_name="Red", members=["a@x.edu"], workout_state=0,
        workout_state_name="NOT_BUILT", arm_status="pending", **kw,
    )


def test_get_teams_are_returned_as_items(h):
    h.setup.teams.return_value = [_team_row()]

    response = h.client.get(f"/ctf/{CTF_ID}/teams/")

    assert response.status_code == 200
    assert response.json()["data"]["items"][0]["team_name"] == "Red"
    h.setup.teams.assert_called_once_with(CTF_ID, GM)


def test_add_team_audits_counts_only_and_the_new_workout(h):
    h.setup.add_team.return_value = _team_row()

    response = h.client.post(f"/ctf/{CTF_ID}/teams/", json={"team_name": "Red", "members": ["A@X.edu", "b@x.edu"]})

    assert response.status_code == 200
    assert response.json()["data"]["workout_id"] == WORKOUT
    [[ctf_id, request, caller]] = [c.args for c in h.setup.add_team.call_args_list]
    assert (ctf_id, caller) == (CTF_ID, GM)
    assert request.members == ["a@x.edu", "b@x.edu"]
    [row] = h.log_db.rows
    assert (row["action"], row["result"]) == ("TEAM_ADD", "OK")
    assert row["detail"] == {"members": 2, "workout_id": WORKOUT}
    assert "a@x.edu" not in str(row) and "Red" not in str(row)


@pytest.mark.parametrize("body", [{"team_name": "Red", "members": []}, {"team_name": "Red", "members": ["nope"]},
                                  {"members": ["a@x.edu"]}, {"team_name": " ", "members": ["a@x.edu"]}])
def test_add_team_malformed_body_is_400(h, body):
    response = h.client.post(f"/ctf/{CTF_ID}/teams/", json=body)

    assert response.status_code == 400
    h.setup.add_team.assert_not_called()


def test_add_team_conflict_is_409_and_a_denied_row(h):
    h.setup.add_team.side_effect = Conflict(message="a@x.edu is already on team Blue in an active CTF event")

    response = h.client.post(f"/ctf/{CTF_ID}/teams/", json=TEAM_BODY)

    assert response.status_code == 409
    assert [(row["action"], row["result"]) for row in h.log_db.rows] == [("TEAM_ADD", "DENIED")]


def test_set_team_members_passes_the_normalized_roster(h):
    h.setup.set_members.return_value = _team_row()

    response = h.client.put(f"/ctf/{CTF_ID}/teams/{WORKOUT}/", json={"members": [" C@x.edu ", "c@x.edu"]})

    assert response.status_code == 200
    [[ctf_id, workout_id, request, caller]] = [c.args for c in h.setup.set_members.call_args_list]
    assert (ctf_id, workout_id, caller) == (CTF_ID, WORKOUT, GM)
    assert request.members == ["c@x.edu"]
    [row] = h.log_db.rows
    assert (row["action"], row["target"], row["detail"]) == ("TEAM_UPDATE", WORKOUT, {"members": 1})


def test_remove_team_returns_the_id_and_audits_the_workout(h):
    response = h.client.delete(f"/ctf/{CTF_ID}/teams/{WORKOUT}/")

    assert response.status_code == 200
    assert response.json()["data"]["build_id"] == WORKOUT
    h.setup.remove_team.assert_called_once_with(CTF_ID, WORKOUT, GM)
    [row] = h.log_db.rows
    assert (row["action"], row["target"]) == ("TEAM_REMOVE", WORKOUT)


def test_remove_built_team_conflict_is_409(h):
    h.setup.remove_team.side_effect = Conflict(message="already built")
    assert h.client.delete(f"/ctf/{CTF_ID}/teams/{WORKOUT}/").status_code == 409


def test_update_spec_passes_the_ctf_block_and_audits_the_flag_count(h):
    h.setup.update_spec.return_value = None

    response = h.client.put(f"/ctf/{CTF_ID}/spec/", json=SPEC_BODY)

    assert response.status_code == 200
    [[ctf_id, ctf, caller]] = [c.args for c in h.setup.update_spec.call_args_list]
    assert (ctf_id, caller) == (CTF_ID, GM)
    assert ctf.name == "N"
    [row] = h.log_db.rows
    assert (row["action"], row["detail"]) == ("SPEC_UPDATE", {"flags": 1})


def test_update_spec_validation_failure_is_400(h):
    h.setup.update_spec.side_effect = AgogeValidationError("Invalid CTF flag web-root")

    response = h.client.put(f"/ctf/{CTF_ID}/spec/", json=SPEC_BODY)

    assert response.status_code == 400
    assert [row["result"] for row in h.log_db.rows] == ["ERROR"]


def test_update_spec_malformed_body_is_400(h):
    assert h.client.put(f"/ctf/{CTF_ID}/spec/", json={"ctf": {"name": "N", "flags": []}}).status_code == 400
    h.setup.update_spec.assert_not_called()


@pytest.mark.parametrize("action", ["build", "start", "stop"])
def test_servers_action_is_audited_and_reports_the_message_count(h, action):
    h.setup.servers.return_value = 3

    response = h.client.put(f"/ctf/{CTF_ID}/servers/", json={"action": action})

    assert response.status_code == 200
    assert response.json()["data"] == {"messages": 3}
    h.setup.servers.assert_called_once_with(CTF_ID, action, GM)
    [row] = h.log_db.rows
    assert (row["action"], row["detail"]) == (f"SERVERS_{action.upper()}", {"messages": 3})


@pytest.mark.parametrize("body", [{"action": "delete"}, {}, None])
def test_servers_unknown_action_is_400(h, body):
    response = h.client.put(f"/ctf/{CTF_ID}/servers/", json=body)

    assert response.status_code == 400
    h.setup.servers.assert_not_called()


def test_servers_stop_conflict_while_running_is_409(h):
    h.setup.servers.side_effect = Conflict(message="Cannot stop the servers of a CTF event that is RUNNING")
    assert h.client.put(f"/ctf/{CTF_ID}/servers/", json={"action": "stop"}).status_code == 409
