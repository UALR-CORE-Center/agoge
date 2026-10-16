"""CtfScoring.board (PRD H5): the student board read hides decoys and locked flags, and never leaks a location (SC-17)."""
import copy
import json

import pytest

from common.constants.database import DbCollections
from common.constants.states import CtfStates
from common.models.response import CtfStudentBoardResponse
from core.ctf import scoring as scoring_module
from core.ctf.scoring import CtfScoring

CTF_ID = "ctfaaaaaaa"
A, B = "wkaaaaaaaa", "wkbbbbbbbb"
NOW = 1_800_000_000.0
FLAGS = [
    {"id": "web1", "server": "web", "slot": 1, "category": "Web", "points": 100, "hint": "Look at robots.txt",
     "hint_cost": 25, "location_type": "file", "path": "/root/flag.txt", "operating_system": "linux",
     "access_level": "root"},
    {"id": "web2", "server": "web", "slot": 2, "category": "Web", "points": 200, "unlocks_after": ["web1"],
     "location_type": "file", "path": "/root/flag2.txt", "operating_system": "linux"},
    {"id": "both", "server": "dc", "slot": 3, "points": 300, "unlocks_after": ["web1", "win1"],
     "location_type": "registry", "path": r"HKLM\SOFTWARE\Agoge:Flag", "operating_system": "windows",
     "access_level": "admin"},
    {"id": "win1", "server": "dc", "slot": 1, "category": "Windows", "points": 150, "hint": "Check the share",
     "hint_cost": 10, "location_type": "file", "path": r"C:\Users\Public\flag.txt", "operating_system": "windows"},
    {"id": "trap", "server": "web", "slot": 1, "points": -50, "decoy": True, "hint": "Secret",
     "location_type": "file", "path": "/root/trap.txt", "operating_system": "linux"},
]
LEAK_KEYS = {"path", "server", "location_type", "digest", "access_level"}


class FakeDb:
    def __init__(self):
        self.store = {}
        self.writes = 0

    def col(self, collection):
        return self.store.setdefault(collection.value, {})

    def get(self, collection_name, doc_id):
        return copy.deepcopy(self.col(collection_name).get(doc_id))

    def query(self, collection_name, filters=None, limit=None):
        docs = self.col(collection_name).values()
        return [copy.deepcopy(d) for d in docs if all(d.get(field) == value for field, _, value in filters or [])]

    def insert(self, *args, **kwargs):
        self.writes += 1

    def transaction(self, *args, **kwargs):
        self.writes += 1


def seed(db, state=CtfStates.RUNNING, solved=(), hints=(), score=0, **event_fields):
    db.col(DbCollections.CTF)[CTF_ID] = {
        "id": CTF_ID, "unit_id": "unitabcdef", "instructor_id": ["gm@example.edu"],
        "spec": {"name": "Spring CTF", "description": "Capture them all", "rules_url": "https://example.edu/roe",
                 "flags": FLAGS, "scoring": {"flag_prefix": "spring"}},
        "creation_timestamp": 1_700_000_000.0, "board_ids": [A, B],
        "state": state.value, "state_timestamp": "2026-10-16T00:00:00+00:00", **event_fields,
    }
    for workout_id in (A, B):
        db.col(DbCollections.CTF_BOARD)[f"{CTF_ID}-{workout_id}"] = {
            "id": f"{CTF_ID}-{workout_id}", "workout_id": workout_id, "ctf_id": CTF_ID,
            "team_name": workout_id, "active": True, "score": score if workout_id == A else 999,
            "flags": [{"flag_id": f["id"], "digest": "d" * 64, "plant_status": "planted",
                       "solved": f["id"] in solved and workout_id == A,
                       "solved_at": NOW - 10 if f["id"] in solved and workout_id == A else None,
                       "hint_taken": f["id"] in hints and workout_id == A} for f in FLAGS],
        }


@pytest.fixture
def db():
    return FakeDb()


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch):
    monkeypatch.setattr(scoring_module.time, "time", lambda: NOW)


def ids(response):
    return [c.flag_id for c in response.challenges]


def all_keys(value):
    if isinstance(value, dict):
        return set(value) | set().union(*(all_keys(v) for v in value.values()))
    if isinstance(value, list):
        return set().union(*(all_keys(v) for v in value)) if value else set()
    return set()


def test_no_active_board_is_not_enrolled(db):
    assert CtfScoring(db=db).board(A) == CtfStudentBoardResponse(enrolled=False)


def test_inactive_board_is_not_enrolled(db):
    seed(db)
    db.col(DbCollections.CTF_BOARD)[f"{CTF_ID}-{A}"]["active"] = False

    assert CtfScoring(db=db).board(A).enrolled is False


def test_board_whose_event_is_missing_is_not_enrolled(db):
    seed(db)
    del db.col(DbCollections.CTF)[CTF_ID]

    assert CtfScoring(db=db).board(A).enrolled is False


def test_enrolled_board_carries_event_details_and_team_score(db):
    seed(db, score=75, public_scoreboard_enabled=True)

    response = CtfScoring(db=db).board(A)

    assert response.enrolled is True
    assert response.ctf_id == CTF_ID
    assert response.name == "Spring CTF"
    assert response.description == "Capture them all"
    assert response.rules_url == "https://example.edu/roe"
    assert response.state_name == "RUNNING"
    assert response.flag_format == "spring{<challenge>_<20 hex characters>}"
    assert response.score == 75
    assert response.public_scoreboard_enabled is True


def test_reads_only_and_writes_nothing(db):
    seed(db)

    CtfScoring(db=db).board(A)

    assert db.writes == 0


def test_decoys_are_never_listed(db):
    seed(db, solved=("web1", "win1"))

    assert "trap" not in ids(CtfScoring(db=db).board(A))


def test_flags_with_unsolved_unlocks_after_are_hidden(db):
    seed(db)

    assert ids(CtfScoring(db=db).board(A)) == ["web1", "win1"]


def test_a_flag_is_listed_once_every_prerequisite_is_solved(db):
    seed(db, solved=("web1",))
    assert ids(CtfScoring(db=db).board(A)) == ["web1", "web2", "win1"]

    seed(db, solved=("web1", "win1"))
    assert ids(CtfScoring(db=db).board(A)) == ["web1", "web2", "both", "win1"]


def test_unlocks_follow_the_callers_board_not_another_team(db):
    seed(db, solved=("web1", "win1"))

    assert ids(CtfScoring(db=db).board(B)) == ["web1", "win1"]


def test_challenge_fields_reflect_spec_and_board_state(db):
    seed(db, solved=("web1",))

    challenges = {c.flag_id: c for c in CtfScoring(db=db).board(A).challenges}

    web1 = challenges["web1"]
    assert (web1.category, web1.points, web1.solved, web1.solved_at) == ("Web", 100, True, NOW - 10)
    assert (web1.hint_available, web1.hint_cost) == (True, 25)
    web2 = challenges["web2"]
    assert (web2.solved, web2.solved_at, web2.hint_available, web2.hint_cost) == (False, None, False, 0)


def test_hint_text_appears_only_once_taken(db):
    seed(db, hints=("win1",))

    challenges = {c.flag_id: c for c in CtfScoring(db=db).board(A).challenges}

    assert challenges["web1"].hint is None
    assert challenges["win1"].hint == "Check the share"


def test_flag_missing_from_the_board_is_not_listed(db):
    seed(db)
    board = db.col(DbCollections.CTF_BOARD)[f"{CTF_ID}-{A}"]
    board["flags"] = [f for f in board["flags"] if f["flag_id"] != "win1"]

    assert ids(CtfScoring(db=db).board(A)) == ["web1"]


@pytest.mark.parametrize("state", list(CtfStates))
def test_sc17_no_location_key_in_any_state(db, state):
    # Everything unlocked and every hint taken, so the response is as full as it gets.
    seed(db, state=state, solved=[f["id"] for f in FLAGS], hints=[f["id"] for f in FLAGS],
         ends_at=NOW + 600, paused_at=NOW - 60)

    response = CtfScoring(db=db).board(A)
    dumped = response.model_dump()

    assert response.enrolled is True
    assert len(response.challenges) == 4
    assert all_keys(dumped).isdisjoint(LEAK_KEYS)
    serialized = json.dumps(dumped)
    # Server names ("web") can't be checked by value: they occur inside flag ids ("web1").
    for flag in FLAGS:
        assert flag["path"] not in serialized
    assert "d" * 64 not in serialized


def test_remaining_seconds_open_ended_is_none(db):
    seed(db)

    assert CtfScoring(db=db).board(A).remaining_seconds is None


def test_remaining_seconds_counts_down_while_running(db):
    seed(db, ends_at=NOW + 600.2)

    assert CtfScoring(db=db).board(A).remaining_seconds == 601


def test_remaining_seconds_never_negative(db):
    seed(db, ends_at=NOW - 30)

    assert CtfScoring(db=db).board(A).remaining_seconds == 0


def test_remaining_seconds_held_while_paused(db):
    # Paused 100 s ago with 500 s left at the time: the clock does not keep running.
    seed(db, state=CtfStates.PAUSED, ends_at=NOW + 400, paused_at=NOW - 100)

    assert CtfScoring(db=db).board(A).remaining_seconds == 500


def test_remaining_seconds_zero_once_ended(db):
    seed(db, state=CtfStates.ENDED, ends_at=NOW + 400)

    assert CtfScoring(db=db).board(A).remaining_seconds == 0
