from unittest.mock import MagicMock

import pytest

from common.constants.database import DbCollections
from common.exceptions.agoge import (
    BadRequest, Conflict, Forbidden, NotFound, ServiceUnavailable, Unauthorized,
)
from common.models.agoge import CtfLogModel
from core.ctf import audit as audit_module
from core.ctf.audit import CtfAudit

ACTOR = "gm@example.edu"


@pytest.fixture
def db():
    return MagicMock()


@pytest.fixture
def audit(db):
    return CtfAudit(db=db)


def rows(db):
    """Every row the audit inserted, validated against the stored model."""
    out = []
    for call in db.insert.call_args_list:
        assert call.kwargs["collection_name"] == DbCollections.CTF_LOG
        out.append(CtfLogModel(**call.kwargs["data"]))
    return out


def test_ok_writes_one_row_with_fields(audit, db, monkeypatch):
    monkeypatch.setattr(audit_module.time, "time", lambda: 1234.5)
    with audit.action("ctfidabcde", "CTF_START", ACTOR, target="wkoutabcde", detail={"boards": 3}) as entry:
        entry.add_detail(published=True)

    [row] = rows(db)
    assert row.result == "OK"
    assert row.ctf_id == "ctfidabcde"
    assert row.action == "CTF_START"
    assert row.actor == ACTOR
    assert row.target == "wkoutabcde"
    assert row.detail == {"boards": 3, "published": True}
    assert row.created_at == 1234.5
    assert len(row.id) == 32


def test_ok_without_detail_stores_null(audit, db):
    with audit.action("ctfidabcde", "CTF_ARM", ACTOR):
        pass
    [row] = rows(db)
    assert row.detail is None
    assert row.target is None


def test_target_set_inside_block_is_recorded(audit, db):
    with audit.action("ctfidabcde", "HOST_RESET", ACTOR) as entry:
        entry.target = "kali"
    assert rows(db)[0].target == "kali"


@pytest.mark.parametrize("exc", [Unauthorized, Forbidden, Conflict, BadRequest])
def test_denied_exceptions_write_denied_and_propagate(audit, db, exc):
    with pytest.raises(exc):
        with audit.action("ctfidabcde", "CTF_END", ACTOR):
            raise exc("no")
    [row] = rows(db)
    assert row.result == "DENIED"


@pytest.mark.parametrize("exc", [NotFound, ServiceUnavailable, RuntimeError, KeyError])
def test_other_exceptions_write_error_and_propagate(audit, db, exc):
    # PRD SC-18 lists only Unauthorized/Forbidden/Conflict/BadRequest as DENIED.
    with pytest.raises(exc):
        with audit.action("ctfidabcde", "CTF_DELETE", ACTOR):
            raise exc("boom")
    [row] = rows(db)
    assert row.result == "ERROR"


def test_detail_added_before_failure_is_kept(audit, db):
    with pytest.raises(Conflict):
        with audit.action("ctfidabcde", "FLAG_REPLANT", ACTOR) as entry:
            entry.add_detail(boards=2)
            raise Conflict("state")
    [row] = rows(db)
    assert (row.result, row.detail) == ("DENIED", {"boards": 2})


@pytest.mark.parametrize("value", [
    "agoge{0123456789abcdef0123}",
    "AGOGE{abc}",
    "  agoge{abc}",
    "submitted agoge{abc} twice",
])
def test_detail_rejects_flag_value_at_entry(audit, db, value):
    body = MagicMock()
    with pytest.raises(ValueError) as info:
        with audit.action("ctfidabcde", "SCORE_ADJUST", ACTOR, detail={"reason": value}):
            body()
    body.assert_not_called()
    # The error names the key, never the value.
    assert "agoge{" not in str(info.value).lower()
    [row] = rows(db)
    assert row.result == "ERROR"
    assert row.detail is None
    assert "agoge{" not in str(db.insert.call_args.kwargs["data"]).lower()


def test_detail_rejects_flag_value_added_in_block(audit, db):
    with pytest.raises(ValueError):
        with audit.action("ctfidabcde", "FLAG_REVEAL", ACTOR) as entry:
            entry.add_detail(flag_id="f1", value="agoge{deadbeef}")
    [row] = rows(db)
    assert row.result == "ERROR"
    # The whole add_detail call is rejected, including its harmless keys.
    assert row.detail is None


def test_detail_rejects_event_specific_prefix(audit, db):
    with pytest.raises(ValueError):
        with audit.action("ctfidabcde", "SCORE_ADJUST", ACTOR, detail={"reason": "ctf{x}"}, flag_prefix="ctf"):
            pass
    assert rows(db)[0].detail is None


def test_detail_rejects_flag_in_key(audit, db):
    with pytest.raises(ValueError):
        with audit.action("ctfidabcde", "SCORE_ADJUST", ACTOR, detail={"agoge{abc}": 1}):
            pass


def test_detail_accepts_prefix_without_brace(audit, db):
    with audit.action("ctfidabcde", "SCORE_ADJUST", ACTOR, detail={"reason": "agoge flag hint"}):
        pass
    assert rows(db)[0].detail == {"reason": "agoge flag hint"}


@pytest.mark.parametrize("value", [1.5, None, ["a"], {"a": 1}])
def test_detail_rejects_non_scalar(audit, db, value):
    with pytest.raises(ValueError):
        with audit.action("ctfidabcde", "CTF_UPDATE", ACTOR, detail={"k": value}):
            pass
    assert rows(db)[0].result == "ERROR"


def test_detail_keeps_bool_and_int_types(audit, db):
    with audit.action("ctfidabcde", "CTF_UPDATE", ACTOR, detail={"frozen": True, "delta": -5}):
        pass
    detail = db.insert.call_args.kwargs["data"]["detail"]
    assert detail == {"frozen": True, "delta": -5}
    assert type(detail["frozen"]) is bool


def test_write_failure_does_not_mask_success(audit, db):
    db.insert.side_effect = RuntimeError("firestore down")
    with audit.action("ctfidabcde", "CTF_PAUSE", ACTOR) as entry:
        entry.add_detail(ok=True)
    db.insert.assert_called_once()


def test_write_failure_does_not_mask_action_exception(audit, db):
    db.insert.side_effect = RuntimeError("firestore down")
    with pytest.raises(Conflict):
        with audit.action("ctfidabcde", "CTF_PAUSE", ACTOR):
            raise Conflict("state")


def test_each_action_gets_its_own_row_id(audit, db):
    for _ in range(2):
        with audit.action("ctfidabcde", "CTF_RESUME", ACTOR):
            pass
    first, second = rows(db)
    assert first.id != second.id
