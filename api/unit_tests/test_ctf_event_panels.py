"""CtfEvent.state / boards / flags / log / submissions (PRD F7 and the panel GET endpoint rows)."""
import copy

import pytest

from common.constants.database import DbCollections, DbOperators
from common.constants.states import CtfStates
from common.exceptions.agoge import BadRequest, NotFound, Unauthorized
from common.models.agoge import CtfLogModel, CtfSubmissionModel
from common.models.response import CtfBoardStatus, CtfFlagRow, CtfStateResponse
from common.models.users import AgogeUser
from core.ctf import config
from core.ctf.event import CtfEvent

GM = "gm@example.edu"
CTF_ID = "ctfaaaaaaa"
WA, WB, WC = "wkaaaaaaaa", "wkbbbbbbbb", "wkcccccccc"


class FakeDb:
    """Only get/query: panel reads never write. Every read is recorded so read counts can be asserted."""
    def __init__(self):
        self.store = {}
        self.reads = []

    def collection(self, name):
        return self.store.setdefault(getattr(name, "value", name), {})

    def get(self, collection_name, doc_id):
        self.reads.append(("get", collection_name, doc_id))
        doc = self.collection(collection_name).get(doc_id)
        return copy.deepcopy(doc) if doc is not None else None

    def query(self, collection_name, filters=None):
        self.reads.append(("query", collection_name, filters))
        out = []
        for doc in self.collection(collection_name).values():
            for field, op, value in filters or []:
                assert op == DbOperators.EQUAL, f"unexpected operator {op}"
                if doc.get(field) != value:
                    break
            else:
                out.append(copy.deepcopy(doc))
        return out


def user(email=GM, admin=False):
    return AgogeUser(uid="uid", email=email, permissions={"instructor": True, "admin": admin})


FLAGS = [
    {"id": "web1", "server": "web", "slot": 1, "category": "Web", "points": 100,
     "location_type": "file", "path": "/root/flag.txt", "operating_system": "linux"},
    {"id": "dc-decoy", "server": "dc", "slot": 2, "points": -50, "decoy": True,
     "location_type": "registry", "path": r"HKLM\SOFTWARE\Agoge:flag", "operating_system": "windows"},
]


def board_doc(workout_id, team, statuses=("planted", "planted"), **kw):
    return {
        "id": f"{CTF_ID}-{workout_id}", "ctf_id": CTF_ID, "workout_id": workout_id, "team_name": team,
        "flags": [
            {"flag_id": flag["id"], "digest": f"{workout_id}{flag['id']}", "plant_status": status,
             "planted_at": 5.0 if status == "planted" else None,
             "plant_error": "timeout" if status == "failed" else None}
            for flag, status in zip(FLAGS, statuses)
        ],
        **kw,
    }


def seed(db, board_ids=(WB, WA), state=CtfStates.RUNNING, **kw):
    db.collection(DbCollections.CTF)[CTF_ID] = {
        "id": CTF_ID, "unit_id": "unitabcdef", "instructor_id": [GM],
        "spec": {"name": "Spring CTF", "flags": FLAGS},
        "creation_timestamp": 1.0, "board_ids": list(board_ids), "starts_at": 10.0, "ends_at": 9000.0,
        "paused_at": None, "accumulated_pause_seconds": 30.0, "scoreboard_frozen_at": 8000.0,
        "public_scoreboard_enabled": True,
        "state": state.value, "state_timestamp": "2026-10-16T00:00:00+00:00", **kw,
    }
    boards = db.collection(DbCollections.CTF_BOARD)
    boards[f"{CTF_ID}-{WA}"] = board_doc(WA, "Alpha", ("failed", "stale"), arm_status="failed", arm_error="boom")
    boards[f"{CTF_ID}-{WB}"] = board_doc(WB, "Bravo", ("planted", "stale"), arm_status="armed")
    # Another event's board must never appear.
    boards[f"otherevent-{WC}"] = {**board_doc(WC, "Other"), "id": f"otherevent-{WC}", "ctf_id": "otherevent"}


@pytest.fixture
def db():
    return FakeDb()


@pytest.fixture
def budget(monkeypatch):
    state = {"exceeded": False}
    monkeypatch.setattr(config, "is_budget_exceeded", lambda: state["exceeded"])
    return state


def ctf(db):
    return CtfEvent(env_dict={}, db=db)


# --- state --------------------------------------------------------------------------

def test_state_reads_the_event_once_and_queries_boards_once(db, budget):
    seed(db)

    ctf(db).state(CTF_ID, user())

    assert db.reads == [
        ("get", DbCollections.CTF, CTF_ID),
        ("query", DbCollections.CTF_BOARD, [("ctf_id", DbOperators.EQUAL, CTF_ID)]),
    ]


def test_state_returns_event_fields_and_board_statuses_in_board_order(db, budget):
    seed(db)
    budget["exceeded"] = True

    result = ctf(db).state(CTF_ID, user())

    assert isinstance(result, CtfStateResponse)
    assert (result.id, result.state, result.state_name) == (CTF_ID, CtfStates.RUNNING.value, "RUNNING")
    assert result.state_timestamp == "2026-10-16T00:00:00+00:00"
    assert (result.starts_at, result.ends_at, result.paused_at) == (10.0, 9000.0, None)
    assert result.accumulated_pause_seconds == 30.0
    assert result.scoreboard_frozen_at == 8000.0
    assert result.public_scoreboard_enabled is True
    assert result.budget_exceeded is True
    # board_ids is [WB, WA], so Bravo comes first.
    assert result.boards == [
        CtfBoardStatus(workout_id=WB, team_name="Bravo", arm_status="armed", arm_error=None,
                       plant_failed_count=0, plant_stale_count=1),
        CtfBoardStatus(workout_id=WA, team_name="Alpha", arm_status="failed", arm_error="boom",
                       plant_failed_count=1, plant_stale_count=1),
    ]


def test_state_reports_budget_not_exceeded(db, budget):
    seed(db)

    assert ctf(db).state(CTF_ID, user()).budget_exceeded is False


def test_state_skips_an_invalid_board_document(db, budget):
    seed(db)
    db.collection(DbCollections.CTF_BOARD)[f"{CTF_ID}-{WA}"] = {"ctf_id": CTF_ID, "workout_id": WA}

    result = ctf(db).state(CTF_ID, user())

    assert [b.workout_id for b in result.boards] == [WB]


def test_state_lists_a_board_missing_from_board_ids_last(db, budget):
    seed(db, board_ids=(WA,))

    result = ctf(db).state(CTF_ID, user())

    assert [b.workout_id for b in result.boards] == [WA, WB]


def test_state_of_an_archived_event_still_shows_its_inactive_boards(db, budget):
    seed(db, state=CtfStates.ARCHIVED)
    for board in db.collection(DbCollections.CTF_BOARD).values():
        board["active"] = False

    assert len(ctf(db).state(CTF_ID, user()).boards) == 2


def test_state_allows_an_admin_not_on_the_event(db, budget):
    seed(db)

    assert ctf(db).state(CTF_ID, user("admin@example.edu", admin=True)).id == CTF_ID


# --- boards -------------------------------------------------------------------------

def test_boards_returns_board_statuses(db):
    seed(db)

    result = ctf(db).boards(CTF_ID, user())

    assert [(b.workout_id, b.plant_failed_count, b.plant_stale_count) for b in result] == [(WB, 0, 1), (WA, 1, 1)]


def test_boards_of_an_event_with_no_board_documents_is_empty(db):
    seed(db)
    db.collection(DbCollections.CTF_BOARD).clear()

    assert ctf(db).boards(CTF_ID, user()) == []


# --- flags --------------------------------------------------------------------------

def test_flags_returns_one_row_per_spec_flag_including_decoys(db):
    seed(db)

    rows = ctf(db).flags(CTF_ID, user())

    assert all(isinstance(row, CtfFlagRow) for row in rows)
    assert [(r.flag_id, r.server, r.slot, r.category, r.location_type, r.points, r.decoy) for r in rows] == [
        ("web1", "web", 1, "Web", "file", 100, False),
        ("dc-decoy", "dc", 2, None, "registry", -50, True),
    ]


def test_flags_rows_name_the_nested_guest_holding_the_flag(db):
    seed(db)
    spec = db.collection(DbCollections.CTF)[CTF_ID]["spec"]
    spec["nested_guests"] = [{"name": "deb", "server": "web", "domain": "debian", "operating_system": "linux"}]
    spec["flags"] = [{**FLAGS[0], "guest": "deb"}, FLAGS[1]]

    rows = ctf(db).flags(CTF_ID, user())

    assert [(r.flag_id, r.server, r.guest) for r in rows] == [("web1", "web", "deb"), ("dc-decoy", "dc", None)]


def test_flags_rows_carry_each_boards_plant_status(db):
    seed(db)
    db.collection(DbCollections.CTF_BOARD)[f"{CTF_ID}-{WB}"]["flags"][0]["solved"] = True

    web1 = ctf(db).flags(CTF_ID, user())[0]

    assert [(b.workout_id, b.team_name, b.plant_status, b.planted_at, b.plant_error, b.solved)
            for b in web1.boards] == [
        (WB, "Bravo", "planted", 5.0, None, True),
        (WA, "Alpha", "failed", None, "timeout", False),
    ]


def test_flags_never_expose_a_digest_or_value(db):
    seed(db)

    dumped = str([row.model_dump() for row in ctf(db).flags(CTF_ID, user())])

    assert f"{WA}web1" not in dumped
    assert "agoge{" not in dumped


def test_flags_skips_a_board_without_state_for_that_flag(db):
    seed(db)
    db.collection(DbCollections.CTF_BOARD)[f"{CTF_ID}-{WA}"]["flags"].pop()

    rows = ctf(db).flags(CTF_ID, user())

    assert [b.workout_id for b in rows[0].boards] == [WB, WA]
    assert [b.workout_id for b in rows[1].boards] == [WB]


# --- log ----------------------------------------------------------------------------

def log_row(row_id, created_at, action="CTF_START", ctf_id=CTF_ID):
    return {"id": row_id, "ctf_id": ctf_id, "action": action, "actor": GM, "result": "OK",
            "created_at": created_at}


def test_log_returns_only_this_events_rows_newest_first(db):
    seed(db)
    logs = db.collection(DbCollections.CTF_LOG)
    logs["a"] = log_row("a", 1.0)
    logs["b"] = log_row("b", 3.0)
    logs["c"] = log_row("c", 2.0)
    logs["x"] = log_row("x", 9.0, ctf_id="otherevent")

    rows = ctf(db).log(CTF_ID, user())

    assert all(isinstance(row, CtfLogModel) for row in rows)
    assert [row.id for row in rows] == ["b", "c", "a"]


def test_log_filters_by_action_in_the_query(db):
    seed(db)
    logs = db.collection(DbCollections.CTF_LOG)
    logs["a"] = log_row("a", 1.0, action="CTF_ARM")
    logs["b"] = log_row("b", 2.0, action="FLAG_REVEAL")

    rows = ctf(db).log(CTF_ID, user(), action="FLAG_REVEAL")

    assert [row.id for row in rows] == ["b"]
    assert db.reads[-1] == ("query", DbCollections.CTF_LOG, [
        ("ctf_id", DbOperators.EQUAL, CTF_ID), ("action", DbOperators.EQUAL, "FLAG_REVEAL"),
    ])


def test_log_is_capped_at_500_newest(db):
    seed(db)
    logs = db.collection(DbCollections.CTF_LOG)
    for i in range(501):
        logs[f"r{i}"] = log_row(f"r{i}", float(i))

    rows = ctf(db).log(CTF_ID, user())

    assert len(rows) == 500
    assert rows[0].id == "r500"
    assert rows[-1].id == "r1"


def test_log_skips_an_invalid_row(db):
    seed(db)
    logs = db.collection(DbCollections.CTF_LOG)
    logs["a"] = log_row("a", 1.0)
    logs["bad"] = {"id": "bad", "ctf_id": CTF_ID}

    assert [row.id for row in ctf(db).log(CTF_ID, user())] == ["a"]


def test_log_rejects_an_unknown_action_before_reading(db):
    seed(db)

    with pytest.raises(BadRequest):
        ctf(db).log(CTF_ID, user(), action="DROP_TABLE")
    assert db.reads == []


# --- submissions --------------------------------------------------------------------

def submission(row_id, submitted_at, verdict="incorrect", ctf_id=CTF_ID):
    return {"id": row_id, "ctf_id": ctf_id, "workout_id": WA, "submitted_digest": "d" * 64,
            "verdict": verdict, "submitted_at": submitted_at}


def test_submissions_returns_only_this_events_rows_newest_first(db):
    seed(db)
    subs = db.collection(DbCollections.CTF_SUBMISSION)
    subs["a"] = submission("a", 2.0)
    subs["b"] = submission("b", 1.0)
    subs["x"] = submission("x", 5.0, ctf_id="otherevent")

    rows = ctf(db).submissions(CTF_ID, user())

    assert all(isinstance(row, CtfSubmissionModel) for row in rows)
    assert [row.id for row in rows] == ["a", "b"]


def test_submissions_filters_by_verdict(db):
    seed(db)
    subs = db.collection(DbCollections.CTF_SUBMISSION)
    subs["a"] = submission("a", 1.0, verdict="correct")
    subs["b"] = submission("b", 2.0, verdict="cross_submission")

    assert [row.id for row in ctf(db).submissions(CTF_ID, user(), verdict="cross_submission")] == ["b"]


def test_submissions_is_capped_at_500_newest(db):
    seed(db)
    subs = db.collection(DbCollections.CTF_SUBMISSION)
    for i in range(600):
        subs[f"s{i}"] = submission(f"s{i}", float(i))

    rows = ctf(db).submissions(CTF_ID, user())

    assert len(rows) == 500
    assert rows[0].id == "s599"
    assert rows[-1].id == "s100"


def test_submissions_rejects_an_unknown_verdict(db):
    seed(db)

    with pytest.raises(BadRequest):
        ctf(db).submissions(CTF_ID, user(), verdict="maybe")


# --- shared: not found and authorization ---------------------------------------------

PANELS = [
    lambda c, u: c.state(CTF_ID, u),
    lambda c, u: c.boards(CTF_ID, u),
    lambda c, u: c.flags(CTF_ID, u),
    lambda c, u: c.log(CTF_ID, u),
    lambda c, u: c.submissions(CTF_ID, u),
]


@pytest.mark.parametrize("read", PANELS)
def test_panel_read_of_a_missing_event_is_not_found(db, budget, read):
    with pytest.raises(NotFound):
        read(ctf(db), user())


@pytest.mark.parametrize("read", PANELS)
def test_panel_read_refuses_an_instructor_not_on_the_event_before_reading_rows(db, budget, read):
    seed(db)

    with pytest.raises(Unauthorized):
        read(ctf(db), user("other@example.edu"))
    assert db.reads == [("get", DbCollections.CTF, CTF_ID)]
