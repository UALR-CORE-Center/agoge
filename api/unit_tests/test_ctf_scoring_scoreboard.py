"""CtfScoring scoreboards (PRD H6): the instructor ranking and the anonymized, freeze-aware public ranking (SC-16)."""
import copy

import pytest

from common.constants.database import DbCollections
from common.constants.states import CtfStates
from common.exceptions.agoge import NotFound, Unauthorized
from common.models.users import AgogeUser
from core.ctf.scoring import CtfScoring

CTF_ID = "ctfaaaaaaa"
A, B, C = "wkaaaaaaaa", "wkbbbbbbbb", "wkcccccccc"
FREEZE = 1_800_000_000.0
FLAGS = [
    {"id": "web1", "server": "web", "slot": 1, "points": 100, "location_type": "file", "path": "/root/1.txt",
     "operating_system": "linux"},
    {"id": "web2", "server": "web", "slot": 2, "points": 200, "location_type": "file", "path": "/root/2.txt",
     "operating_system": "linux"},
    {"id": "trap", "server": "web", "slot": 3, "points": -50, "decoy": True, "location_type": "file",
     "path": "/root/t.txt", "operating_system": "linux"},
]
INSTRUCTOR = AgogeUser(uid="gm", email="gm@example.edu", permissions={"instructor": True, "admin": False})
STRANGER = AgogeUser(uid="other", email="other@example.edu", permissions={"instructor": True, "admin": False})


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


def seed_event(db, board_ids=(A, B, C), **fields):
    db.col(DbCollections.CTF)[CTF_ID] = {
        "id": CTF_ID, "unit_id": "unitabcdef", "instructor_id": ["gm@example.edu"],
        "spec": {"name": "Spring CTF", "flags": FLAGS, "scoring": {"flag_prefix": "spring"}},
        "creation_timestamp": 1_700_000_000.0, "board_ids": list(board_ids),
        "state": CtfStates.RUNNING.value, "state_timestamp": "2026-10-16T00:00:00+00:00",
        "public_scoreboard_enabled": True, **fields,
    }


def seed_board(db, workout_id, solves=None, score=None, decoy_count=0, active=True, team_name=None):
    """`solves` maps flag id → solved_at; score defaults to the solved points."""
    solves = solves or {}
    points = {f["id"]: f["points"] for f in FLAGS}
    db.col(DbCollections.CTF_BOARD)[f"{CTF_ID}-{workout_id}"] = {
        "id": f"{CTF_ID}-{workout_id}", "workout_id": workout_id, "ctf_id": CTF_ID, "active": active,
        "team_name": team_name or f"Team of {workout_id}",
        "score": sum(points[f] for f in solves) if score is None else score,
        "solve_count": len(solves), "decoy_count": decoy_count,
        "last_solve_at": max(solves.values(), default=None),
        "flags": [{"flag_id": f["id"], "digest": "d" * 64, "solved": f["id"] in solves,
                   "solved_at": solves.get(f["id"])} for f in FLAGS],
    }


@pytest.fixture
def db():
    return FakeDb()


# --- instructor scoreboard ---------------------------------------------------------------------

def test_instructor_ranks_by_score_then_earliest_last_solve(db):
    seed_event(db)
    seed_board(db, A, {"web1": 10.0})                      # 100, solved at 10
    seed_board(db, B, {"web1": 20.0, "web2": 30.0})        # 300
    seed_board(db, C, {"web1": 5.0})                       # 100, solved earlier than A

    rows = CtfScoring(db=db).scoreboard(CTF_ID, INSTRUCTOR)

    assert [(r.rank, r.workout_id, r.score) for r in rows] == [(1, B, 300), (2, C, 100), (3, A, 100)]


def test_instructor_rows_carry_names_counts_and_last_solve(db):
    seed_event(db, board_ids=(A,))
    seed_board(db, A, {"web1": 10.0}, score=50, decoy_count=1, team_name="Red Team")

    [row] = CtfScoring(db=db).scoreboard(CTF_ID, INSTRUCTOR)

    assert row.model_dump() == {"rank": 1, "workout_id": A, "team_name": "Red Team", "score": 50,
                                "solve_count": 1, "decoy_count": 1, "last_solve_at": 10.0}


def test_instructor_scoreboard_ignores_the_freeze(db):
    seed_event(db, board_ids=(A, B), scoreboard_frozen_at=FREEZE)
    seed_board(db, A, {"web1": FREEZE - 1})
    seed_board(db, B, {"web1": FREEZE - 1, "web2": FREEZE + 1})

    rows = CtfScoring(db=db).scoreboard(CTF_ID, INSTRUCTOR)

    assert [(r.workout_id, r.score, r.solve_count) for r in rows] == [(B, 300, 2), (A, 100, 1)]


def test_team_without_a_solve_ranks_after_a_tied_team_with_one(db):
    seed_event(db, board_ids=(A, B))
    seed_board(db, A, score=0)                             # never solved
    seed_board(db, B, {"web1": 10.0}, score=0)             # solved, then lost points to hints

    rows = CtfScoring(db=db).scoreboard(CTF_ID, INSTRUCTOR)

    assert [r.workout_id for r in rows] == [B, A]


def test_full_ties_keep_board_order(db):
    seed_event(db, board_ids=(C, A, B))
    for workout_id in (A, B, C):
        seed_board(db, workout_id)

    rows = CtfScoring(db=db).scoreboard(CTF_ID, INSTRUCTOR)

    assert [(r.rank, r.workout_id) for r in rows] == [(1, C), (2, A), (3, B)]


def test_instructor_scoreboard_includes_archived_boards(db):
    seed_event(db, board_ids=(A, B), state=CtfStates.ARCHIVED.value)
    seed_board(db, A, {"web1": 1.0}, active=False)
    seed_board(db, B, active=False)

    assert [r.workout_id for r in CtfScoring(db=db).scoreboard(CTF_ID, INSTRUCTOR)] == [A, B]


def test_instructor_scoreboard_requires_an_event_instructor(db):
    seed_event(db)

    with pytest.raises(Unauthorized):
        CtfScoring(db=db).scoreboard(CTF_ID, STRANGER)


def test_instructor_scoreboard_allows_an_admin(db):
    seed_event(db, board_ids=(A,))
    seed_board(db, A)
    admin = AgogeUser(uid="root", email="root@example.edu", permissions={"admin": True})

    assert len(CtfScoring(db=db).scoreboard(CTF_ID, admin)) == 1


def test_instructor_scoreboard_missing_event_is_not_found(db):
    with pytest.raises(NotFound):
        CtfScoring(db=db).scoreboard(CTF_ID, INSTRUCTOR)


# --- public scoreboard -------------------------------------------------------------------------

def test_public_rows_are_anonymized_by_board_order_and_mark_the_caller(db):
    seed_event(db, board_ids=(A, B, C))
    seed_board(db, A, {"web1": 10.0})
    seed_board(db, B, {"web1": 20.0, "web2": 30.0})
    seed_board(db, C)

    rows = CtfScoring(db=db).public_scoreboard(A)

    assert [r.model_dump() for r in rows] == [
        {"rank": 1, "team_label": "Team 2", "score": 300, "solve_count": 2, "is_you": False},
        {"rank": 2, "team_label": "Team 1", "score": 100, "solve_count": 1, "is_you": True},
        {"rank": 3, "team_label": "Team 3", "score": 0, "solve_count": 0, "is_you": False},
    ]


def test_public_rows_never_carry_team_names_or_workout_ids(db):
    seed_event(db, board_ids=(A, B))
    seed_board(db, A, team_name="Secret Name A")
    seed_board(db, B, team_name="Secret Name B")

    dumped = str([r.model_dump() for r in CtfScoring(db=db).public_scoreboard(A)])

    assert "Secret Name" not in dumped
    assert A not in dumped and B not in dumped


def test_public_scoreboard_is_not_found_unless_enabled(db):
    seed_event(db, public_scoreboard_enabled=False)
    seed_board(db, A)

    with pytest.raises(NotFound):
        CtfScoring(db=db).public_scoreboard(A)


def test_public_scoreboard_without_an_active_board_is_not_found(db):
    seed_event(db)
    seed_board(db, A, active=False)

    with pytest.raises(NotFound):
        CtfScoring(db=db).public_scoreboard(A)


def test_sc16_frozen_public_scoreboard_ranks_only_solves_up_to_the_freeze(db):
    """SC-16: B overtakes A only after the freeze, so the frozen public board still shows A ahead."""
    seed_event(db, board_ids=(A, B), scoreboard_frozen_at=FREEZE)
    seed_board(db, A, {"web2": FREEZE - 100})                                  # 200 before the freeze
    seed_board(db, B, {"web1": FREEZE - 50, "web2": FREEZE + 1})               # 100 before, 300 now

    rows = CtfScoring(db=db).public_scoreboard(B)

    assert [(r.team_label, r.score, r.solve_count, r.is_you) for r in rows] == [
        ("Team 1", 200, 1, False),
        ("Team 2", 100, 1, True),
    ]


def test_sc16_solve_exactly_at_the_freeze_counts(db):
    seed_event(db, board_ids=(A,), scoreboard_frozen_at=FREEZE)
    seed_board(db, A, {"web1": FREEZE})

    [row] = CtfScoring(db=db).public_scoreboard(A)

    assert (row.score, row.solve_count) == (100, 1)


def test_sc16_freeze_tiebreak_uses_the_last_solve_before_the_freeze(db):
    # Both show 100 while frozen. A's latest pre-freeze solve is earlier, so A ranks first, even
    # though A's board.last_solve_at (a post-freeze solve) is later than B's.
    seed_event(db, board_ids=(B, A), scoreboard_frozen_at=FREEZE)
    seed_board(db, A, {"web1": FREEZE - 100, "web2": FREEZE + 500})
    seed_board(db, B, {"web1": FREEZE - 10})

    rows = CtfScoring(db=db).public_scoreboard(A)

    assert [(r.team_label, r.score, r.is_you) for r in rows] == [("Team 2", 100, True), ("Team 1", 100, False)]


def test_freeze_keeps_non_solve_points(db):
    # Only solves are frozen: a decoy penalty or hint cost already in the score stays in it.
    seed_event(db, board_ids=(A,), scoreboard_frozen_at=FREEZE)
    seed_board(db, A, {"web1": FREEZE - 1, "web2": FREEZE + 1}, score=300 - 50 - 25)

    [row] = CtfScoring(db=db).public_scoreboard(A)

    assert (row.score, row.solve_count) == (100 - 50 - 25, 1)


def test_unfrozen_public_scoreboard_uses_live_scores(db):
    seed_event(db, board_ids=(A,), scoreboard_frozen_at=None)
    seed_board(db, A, {"web1": FREEZE - 1, "web2": FREEZE + 1})

    [row] = CtfScoring(db=db).public_scoreboard(A)

    assert (row.score, row.solve_count) == (300, 2)


def test_scoreboards_write_nothing(db):
    seed_event(db, scoreboard_frozen_at=FREEZE)
    for workout_id in (A, B, C):
        seed_board(db, workout_id, {"web1": FREEZE + 1})

    CtfScoring(db=db).scoreboard(CTF_ID, INSTRUCTOR)
    CtfScoring(db=db).public_scoreboard(A)

    assert db.writes == 0


def test_team_labels_follow_board_ids_even_when_a_board_is_invalid(db):
    seed_event(db, board_ids=(A, B, C))
    seed_board(db, A)
    seed_board(db, B)
    seed_board(db, C, {"web1": 1.0})
    del db.col(DbCollections.CTF_BOARD)[f"{CTF_ID}-{B}"]["team_name"]  # B fails validation and is skipped

    rows = CtfScoring(db=db).public_scoreboard(A)

    assert [(r.team_label, r.is_you) for r in rows] == [("Team 3", False), ("Team 1", True)]


# --- decoy masking -----------------------------------------------------------------------------

def seed_decoy_boards(db, **event_fields):
    """A has 100 solved and hit a -50 decoy (raw 50); B is clean at 75."""
    seed_event(db, board_ids=(A, B), **event_fields)
    seed_board(db, A, {"web1": 10.0}, score=50)
    db.col(DbCollections.CTF_BOARD)[f"{CTF_ID}-{A}"]["decoy_points"] = -50
    seed_board(db, B, {"web1": 20.0}, score=75)


def test_public_scoreboard_masks_decoy_points_and_ranks_on_the_masked_score(db):
    seed_decoy_boards(db)

    rows = CtfScoring(db=db).public_scoreboard(B)

    # A shows 50 - (-50) = 100 and so outranks B at 75, though its raw score is lower.
    assert [(r.rank, r.team_label, r.score, r.is_you) for r in rows] == [
        (1, "Team 1", 100, False),
        (2, "Team 2", 75, True),
    ]


def test_public_scoreboard_uses_raw_scores_and_ranking_when_the_penalty_is_revealed(db):
    seed_decoy_boards(db)
    db.col(DbCollections.CTF)[CTF_ID]["spec"]["scoring"]["reveal_decoy_penalty"] = True

    rows = CtfScoring(db=db).public_scoreboard(B)

    assert [(r.rank, r.team_label, r.score) for r in rows] == [(1, "Team 2", 75), (2, "Team 1", 50)]


def test_public_scoreboard_masks_decoy_points_on_top_of_the_freeze(db):
    seed_event(db, board_ids=(A, B), scoreboard_frozen_at=FREEZE)
    # A: 100 + 200 - 50 decoy = 250 raw, web2 after the freeze -> frozen 50, masked 100.
    seed_board(db, A, {"web1": FREEZE - 5, "web2": FREEZE + 5}, score=250)
    db.col(DbCollections.CTF_BOARD)[f"{CTF_ID}-{A}"]["decoy_points"] = -50
    seed_board(db, B, {"web1": FREEZE - 4}, score=100 - 10)         # frozen 90, no decoys

    rows = CtfScoring(db=db).public_scoreboard(A)

    assert [(r.team_label, r.score, r.solve_count) for r in rows] == [("Team 1", 100, 1), ("Team 2", 90, 1)]


def test_instructor_scoreboard_keeps_the_true_score_despite_decoy_points(db):
    seed_decoy_boards(db)

    rows = CtfScoring(db=db).scoreboard(CTF_ID, INSTRUCTOR)

    assert [(r.rank, r.workout_id, r.score, r.decoy_count) for r in rows] == [(1, B, 75, 0), (2, A, 50, 0)]


def test_public_scoreboard_board_without_decoy_points_key_is_unmasked(db):
    seed_event(db, board_ids=(A,))
    seed_board(db, A, {"web1": 10.0})
    assert "decoy_points" not in db.col(DbCollections.CTF_BOARD)[f"{CTF_ID}-{A}"]

    [row] = CtfScoring(db=db).public_scoreboard(A)

    assert row.score == 100
