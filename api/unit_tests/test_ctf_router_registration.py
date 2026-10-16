"""api/main.py registration (PRD R3): the real app serves both CTF routers."""
import importlib
import sys
from unittest.mock import patch

import pytest


@pytest.fixture(scope="module")
def app():
    # main.py calls firebase_admin.initialize_app() at import, which needs credentials; nothing else does.
    sys.modules.pop("main", None)
    with patch("firebase_admin.initialize_app"):
        main = importlib.import_module("main")
    yield main.app
    sys.modules.pop("main", None)


def _routes(app):
    return {(method, route.path) for route in app.routes for method in getattr(route, "methods", None) or ()}


@pytest.mark.parametrize("method,path", [
    ("GET", "/ctf/config/"),
    ("GET", "/ctf/"),
    ("POST", "/ctf/"),
    ("DELETE", "/ctf/{ctf_id}/"),
])
def test_instructor_ctf_routes_are_registered(app, method, path):
    assert (method, path) in _routes(app)


@pytest.mark.parametrize("method,path", [
    ("GET", "/ctf-board/{workout_id}/"),
    ("POST", "/ctf-board/{workout_id}/submit/"),
    ("GET", "/ctf-board/{workout_id}/scoreboard/"),
])
def test_student_ctf_board_routes_are_registered(app, method, path):
    assert (method, path) in _routes(app)


def test_every_ctf_router_route_is_on_the_app(app):
    from routers.ctf import ctf_router
    from routers.ctf_board import ctf_board_router

    registered = _routes(app)
    expected = _routes(ctf_router) | _routes(ctf_board_router)
    assert expected and expected <= registered
