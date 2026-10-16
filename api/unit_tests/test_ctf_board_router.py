"""api/routers/ctf_board.py wiring (PRD R2): each unauthenticated /ctf-board route calls its CtfScoring
method, answers in the AgogeResponse envelope, and maps core errors through to_http_exception."""
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import dependencies
from common.exceptions.agoge import Conflict, NotFound, RateLimitExceeded
from common.models.response import (
    CtfHintResponse,
    CtfPublicScoreboardRow,
    CtfStudentBoardResponse,
    CtfSubmitResponse,
)
from routers import ctf_board as ctf_board_module

WORKOUT = "wkaaaaaaaa"
FLAG = "agoge{web1_0123456789abcdef0123}"


class Harness:
    def __init__(self, monkeypatch, enabled=True):
        self.scoring = MagicMock(name="CtfScoring()")
        self.scoring_cls = MagicMock(return_value=self.scoring)
        monkeypatch.setattr(ctf_board_module, "CtfScoring", self.scoring_cls)
        monkeypatch.setattr(dependencies, "is_ctf_enabled", lambda: enabled)
        monkeypatch.setattr(ctf_board_module, "is_ctf_enabled", lambda: enabled)

        app = FastAPI()
        app.include_router(ctf_board_module.ctf_board_router)
        # No get_current_user override and no token sent: these routes must not need one.
        app.dependency_overrides[dependencies.get_cloud_env] = lambda: {}
        self.client = TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def h(monkeypatch):
    return Harness(monkeypatch)


GATED_ROUTES = [
    ("post", f"/ctf-board/{WORKOUT}/submit/", {"flag": FLAG}),
    ("post", f"/ctf-board/{WORKOUT}/hint/web1/", None),
    ("get", f"/ctf-board/{WORKOUT}/scoreboard/", None),
]


def call(client, method, path, body=None):
    if body is None:
        return client.request(method.upper(), path)
    return client.request(method.upper(), path, json=body)


def test_board_is_not_enrolled_when_disabled_and_reads_nothing(monkeypatch):
    h = Harness(monkeypatch, enabled=False)

    response = h.client.get(f"/ctf-board/{WORKOUT}/")

    assert response.status_code == 200
    assert response.json()["data"]["enrolled"] is False
    h.scoring_cls.assert_not_called()


@pytest.mark.parametrize("method, path, body", GATED_ROUTES)
def test_other_student_routes_are_404_when_disabled(monkeypatch, method, path, body):
    h = Harness(monkeypatch, enabled=False)

    response = call(h.client, method, path, body)

    assert response.status_code == 404
    h.scoring_cls.assert_not_called()


def test_board_returns_the_core_response(h):
    h.scoring.board.return_value = CtfStudentBoardResponse(enrolled=True, ctf_id="ctfaaaaaaa", score=7)

    response = h.client.get(f"/ctf-board/{WORKOUT}/")

    assert response.status_code == 200
    data = response.json()["data"]
    assert (data["enrolled"], data["ctf_id"], data["score"]) == (True, "ctfaaaaaaa", 7)
    h.scoring.board.assert_called_once_with(WORKOUT)


def test_board_not_enrolled_from_core_passes_through(h):
    h.scoring.board.return_value = CtfStudentBoardResponse(enrolled=False)

    response = h.client.get(f"/ctf-board/{WORKOUT}/")

    assert response.status_code == 200
    assert response.json()["data"]["enrolled"] is False


def test_submit_passes_flag_and_origin_ip(h):
    h.scoring.submit.return_value = CtfSubmitResponse(
        verdict="correct", correct=True, points_awarded=100, message="Correct! Flag accepted."
    )

    response = h.client.post(f"/ctf-board/{WORKOUT}/submit/", json={"flag": FLAG})

    assert response.status_code == 200
    assert response.json()["data"]["verdict"] == "correct"
    # TestClient reports its client host as "testclient".
    h.scoring.submit.assert_called_once_with(WORKOUT, FLAG, origin_ip="testclient")


@pytest.mark.parametrize("body", [None, {}, {"flag": ""}, {"flag": "x" * 201}, ["agoge{x}"]])
def test_malformed_submit_body_is_400_and_never_echoes_the_value(h, body):
    response = call(h.client, "post", f"/ctf-board/{WORKOUT}/submit/", body)

    assert response.status_code == 400
    assert response.json()["detail"].startswith("Invalid request body:")
    assert "agoge{" not in response.json()["detail"]
    assert "xxxx" not in response.json()["detail"]
    h.scoring.submit.assert_not_called()


@pytest.mark.parametrize("error, status, detail", [
    (Conflict(message="Submissions are closed."), 409, "Submissions are closed."),
    (RateLimitExceeded(message="Too many submissions for this challenge. Try again in 12 seconds."), 429,
     "Too many submissions for this challenge. Try again in 12 seconds."),
    (NotFound(message="CTF board not found"), 404, "CTF board not found"),
    (RuntimeError(FLAG), 500, "Something went wrong"),
])
def test_submit_errors_map_to_the_error_table(h, error, status, detail):
    h.scoring.submit.side_effect = error

    response = h.client.post(f"/ctf-board/{WORKOUT}/submit/", json={"flag": FLAG})

    assert response.status_code == status
    assert response.json()["detail"] == detail


def test_hint_calls_core_with_the_flag_id(h):
    h.scoring.hint.return_value = CtfHintResponse(flag_id="web1", hint="look in /tmp", hint_cost=10, score=40)

    response = h.client.post(f"/ctf-board/{WORKOUT}/hint/web1/")

    assert response.status_code == 200
    assert response.json()["data"] == {"flag_id": "web1", "hint": "look in /tmp", "hint_cost": 10, "score": 40}
    h.scoring.hint.assert_called_once_with(WORKOUT, "web1")


def test_unknown_hint_is_404(h):
    h.scoring.hint.side_effect = NotFound(message="Hint not found")

    response = h.client.post(f"/ctf-board/{WORKOUT}/hint/web1/")

    assert response.status_code == 404
    assert response.json()["detail"] == "Hint not found"


def test_public_scoreboard_is_an_items_envelope(h):
    h.scoring.public_scoreboard.return_value = [
        CtfPublicScoreboardRow(rank=1, team_label="Team 2", score=200, solve_count=2, is_you=False),
        CtfPublicScoreboardRow(rank=2, team_label="Team 1", score=100, solve_count=1, is_you=True),
    ]

    response = h.client.get(f"/ctf-board/{WORKOUT}/scoreboard/")

    assert response.status_code == 200
    items = response.json()["data"]["items"]
    assert [(row["team_label"], row["is_you"]) for row in items] == [("Team 2", False), ("Team 1", True)]
    h.scoring.public_scoreboard.assert_called_once_with(WORKOUT)


def test_public_scoreboard_disabled_is_404(h):
    h.scoring.public_scoreboard.side_effect = NotFound(message="Scoreboard not found")

    response = h.client.get(f"/ctf-board/{WORKOUT}/scoreboard/")

    assert response.status_code == 404


@pytest.mark.parametrize("method, path, body", [
    ("get", "/ctf-board/NOT-AN-ID/", None),
    ("post", "/ctf-board/short/submit/", {"flag": FLAG}),
    ("post", f"/ctf-board/{WORKOUT}/hint/Bad_Id!/", None),
    ("get", "/ctf-board/ABCDEFGHIJ/scoreboard/", None),
])
def test_malformed_path_ids_never_reach_core(h, method, path, body):
    response = call(h.client, method, path, body)

    assert response.status_code == 422
    h.scoring_cls.assert_not_called()
