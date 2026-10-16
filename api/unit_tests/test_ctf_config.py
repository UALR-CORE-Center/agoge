from unittest.mock import MagicMock

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

import dependencies
from common.constants.database import ADMIN_INFO_DOCUMENT, DbCollections
from core.ctf import config


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


@pytest.fixture
def clock(monkeypatch):
    fake = FakeClock()
    monkeypatch.setattr(config.time, "monotonic", fake)
    return fake


@pytest.fixture
def db(monkeypatch):
    fake = MagicMock()
    fake.get.return_value = {"ctf_enabled": False}
    monkeypatch.setattr(config, "_db", fake)
    config.reset_cache()
    yield fake
    config.reset_cache()


def test_reads_admin_info_project(db, clock):
    db.get.return_value = {"ctf_enabled": True}

    assert config.is_ctf_enabled() is True
    db.get.assert_called_once_with(collection_name=DbCollections.ADMIN_INFO, doc_id=ADMIN_INFO_DOCUMENT)


def test_cached_value_is_reused_within_60_seconds(db, clock):
    db.get.return_value = {"ctf_enabled": True}
    assert config.is_ctf_enabled() is True

    db.get.return_value = {"ctf_enabled": False}
    clock.now += 59.9

    assert config.is_ctf_enabled() is True
    assert db.get.call_count == 1


def test_changed_flag_is_seen_after_cache_expires(db, clock):
    assert config.is_ctf_enabled() is False

    db.get.return_value = {"ctf_enabled": True}
    clock.now += config.CACHE_SECONDS

    assert config.is_ctf_enabled() is True
    assert db.get.call_count == 2

    db.get.return_value = {"ctf_enabled": False}
    clock.now += config.CACHE_SECONDS

    assert config.is_ctf_enabled() is False
    assert db.get.call_count == 3


def test_cache_window_is_60_seconds():
    assert config.CACHE_SECONDS == 60


@pytest.mark.parametrize("admin_info", [{}, {"ctf_enabled": None}, {"ctf_enabled": "true"}, {"ctf_enabled": 1}])
def test_absent_or_non_boolean_flag_is_disabled(db, clock, admin_info):
    db.get.return_value = admin_info

    assert config.is_ctf_enabled() is False


def test_missing_admin_info_is_disabled(db, clock):
    db.get.return_value = None

    assert config.is_ctf_enabled() is False


def test_read_failure_fails_closed_and_is_not_cached(db, clock):
    db.get.side_effect = RuntimeError("firestore unavailable")
    assert config.is_ctf_enabled() is False

    # The next request retries immediately rather than waiting out a cached failure.
    db.get.side_effect = None
    db.get.return_value = {"ctf_enabled": True}
    assert config.is_ctf_enabled() is True
    assert db.get.call_count == 2


def test_reset_cache_forces_reread(db, clock):
    config.is_ctf_enabled()
    config.reset_cache()
    config.is_ctf_enabled()

    assert db.get.call_count == 2


def _client() -> TestClient:
    app = FastAPI()

    @app.get("/ctf/thing", dependencies=[Depends(dependencies.ctf_enabled_required)])
    def thing():
        return {"ok": True}

    return TestClient(app, raise_server_exceptions=False)


def test_ctf_enabled_required_returns_404_when_disabled(db, clock):
    response = _client().get("/ctf/thing")

    assert response.status_code == 404


def test_ctf_enabled_required_passes_when_enabled(db, clock):
    db.get.return_value = {"ctf_enabled": True}

    response = _client().get("/ctf/thing")

    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_ctf_enabled_required_sees_toggle_after_cache_expires(db, clock):
    client = _client()
    assert client.get("/ctf/thing").status_code == 404

    db.get.return_value = {"ctf_enabled": True}
    assert client.get("/ctf/thing").status_code == 404

    clock.now += config.CACHE_SECONDS
    assert client.get("/ctf/thing").status_code == 200
