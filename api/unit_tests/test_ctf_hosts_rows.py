"""CtfHosts.hosts (PRD G2; endpoint table GET /ctf/{ctf_id}/hosts/)."""
import copy

import pytest

from common.constants.database import DbCollections, DbOperators
from common.constants.states import CtfStates, ServerStates
from common.exceptions.agoge import NotFound, Unauthorized
from common.models.users import AgogeUser
from core.ctf.hosts import CtfHosts

GM = "gm@example.edu"
CTF_ID = "ctfaaaaaaa"
BOARDS = ("wkaaaaaaaa", "wkbbbbbbbb")
# Two flags share "web" and a decoy sits alone on "db": the flag-bearing servers are web then db.
FLAGS = [
    {"id": "web1", "server": "web", "slot": 1, "points": 100, "location_type": "file",
     "path": "/root/flag.txt", "operating_system": "linux"},
    {"id": "db1", "server": "db", "slot": 1, "points": 50, "location_type": "file",
     "path": "/root/decoy.txt", "operating_system": "linux", "decoy": True},
    {"id": "web2", "server": "web", "slot": 2, "points": 100, "location_type": "file",
     "path": "/root/flag2.txt", "operating_system": "linux"},
]


class FakeDb:
    """get/query only (host rows never write); every read is recorded and `in` is honored."""
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
                if op == DbOperators.EQUAL and doc.get(field) != value:
                    break
                if op == DbOperators.IN:
                    assert len(value) <= 30, "Firestore caps `in` at 30 values"
                    if doc.get(field) not in value:
                        break
            else:
                out.append(copy.deepcopy(doc))
        return out


def user(email=GM, admin=False):
    return AgogeUser(uid="uid", email=email, permissions={"instructor": True, "admin": admin})


def seed_event(db, board_ids=BOARDS):
    db.collection(DbCollections.CTF)[CTF_ID] = {
        "id": CTF_ID, "unit_id": "unitabcdef", "instructor_id": [GM],
        "spec": {"name": "Spring CTF", "flags": copy.deepcopy(FLAGS)},
        "creation_timestamp": 1_700_000_000.0, "board_ids": list(board_ids),
        "state": CtfStates.RUNNING.value, "state_timestamp": "2026-10-16T00:00:00+00:00",
    }
    for index, workout_id in enumerate(board_ids):
        db.collection(DbCollections.CTF_BOARD)[f"{CTF_ID}-{workout_id}"] = {
            "id": f"{CTF_ID}-{workout_id}", "workout_id": workout_id, "ctf_id": CTF_ID,
            "team_name": f"Team {index + 1}",
            "flags": [{"flag_id": f["id"], "digest": f"d-{workout_id}-{f['id']}"} for f in FLAGS],
        }


def seed_server(db, workout_id, name, state=ServerStates.RUNNING.value, **extra):
    db.collection(DbCollections.SERVER)[f"{workout_id}-{name}"] = {
        "name": name, "parent_id": workout_id, "image": "img", "state": state, **extra,
    }


@pytest.fixture
def db():
    fake = FakeDb()
    seed_event(fake)
    for workout_id in BOARDS:
        seed_server(fake, workout_id, "web")
        seed_server(fake, workout_id, "db", state=ServerStates.STOPPED.value)
    return fake


def hosts(db, who=None):
    return CtfHosts(env_dict={}, db=db).hosts(CTF_ID, who or user())


def keyed(rows):
    return {(row.workout_id, row.server): row for row in rows}


# --- the join -----------------------------------------------------------------------------

def test_one_row_per_board_per_server_in_board_then_spec_order(db):
    rows = hosts(db)
    assert [(r.workout_id, r.server) for r in rows] == [(w, s) for w in BOARDS for s in ("web", "db")]
    assert [r.team_name for r in rows] == ["Team 1", "Team 1", "Team 2", "Team 2"]


def test_server_state_and_name_come_from_the_workouts_server_document(db):
    db.collection(DbCollections.SERVER)[f"{BOARDS[1]}-web"]["state"] = ServerStates.RESETTING.value
    rows = keyed(hosts(db))
    assert rows[(BOARDS[0], "web")].server_state == ServerStates.RUNNING.value
    assert rows[(BOARDS[0], "web")].server_state_name == "RUNNING"
    assert rows[(BOARDS[0], "db")].server_state_name == "STOPPED"
    assert rows[(BOARDS[1], "web")].server_state_name == "RESETTING"


def test_flag_count_counts_the_boards_flags_on_that_server_decoys_included(db):
    rows = keyed(hosts(db))
    assert rows[(BOARDS[0], "web")].flag_count == 2
    assert rows[(BOARDS[0], "db")].flag_count == 1


def test_servers_without_flags_are_listed_after_the_flag_bearing_ones_by_name(db):
    # Restart and rebuild apply to any host the team owns, not only the flag-bearing ones.
    seed_server(db, BOARDS[0], "zeta")
    seed_server(db, BOARDS[0], "attacker")
    rows = [r for r in hosts(db) if r.workout_id == BOARDS[0]]
    assert [r.server for r in rows] == ["web", "db", "attacker", "zeta"]
    assert rows[2].flag_count == 0


def test_a_flag_bearing_server_with_no_document_still_gets_a_row_without_state(db):
    del db.collection(DbCollections.SERVER)[f"{BOARDS[1]}-db"]
    row = keyed(hosts(db))[(BOARDS[1], "db")]
    assert row.server_state is None and row.server_state_name is None
    assert row.flag_count == 1
    assert row.rebuild_allowed is False


def test_an_unknown_server_state_is_shown_as_its_number(db):
    db.collection(DbCollections.SERVER)[f"{BOARDS[0]}-web"]["state"] = 99
    assert keyed(hosts(db))[(BOARDS[0], "web")].server_state_name == "99"


def test_servers_of_other_workouts_and_shared_unit_servers_are_not_listed(db):
    seed_server(db, "wkzzzzzzzz", "web")
    seed_server(db, "unitabcdef", "shared")  # community servers are parented to the unit
    rows = hosts(db)
    assert {r.workout_id for r in rows} == set(BOARDS)
    assert "shared" not in {r.server for r in rows}


# --- rebuild_allowed ----------------------------------------------------------------------

def test_rebuild_is_allowed_for_an_ordinary_server(db):
    assert all(r.rebuild_allowed for r in hosts(db))


def test_rebuild_is_refused_for_a_server_with_a_wireguard_endpoint(db):
    # Host Reset Modes: LabServerManager.nuke() leaves WireGuard servers deleted.
    db.collection(DbCollections.SERVER)[f"{BOARDS[0]}-web"]["wireguard_endpoint_id"] = "51820"
    rows = keyed(hosts(db))
    assert rows[(BOARDS[0], "web")].rebuild_allowed is False
    assert rows[(BOARDS[1], "web")].rebuild_allowed is True


# --- reads --------------------------------------------------------------------------------

def test_reads_are_one_event_get_one_board_query_and_one_server_query(db):
    hosts(db)
    assert [(kind, coll) for kind, coll, _ in db.reads] == [
        ("get", DbCollections.CTF), ("query", DbCollections.CTF_BOARD), ("query", DbCollections.SERVER),
    ]
    assert db.reads[2][2] == [("parent_id", DbOperators.IN, list(BOARDS))]


def test_server_queries_are_chunked_at_thirty_boards():
    db = FakeDb()
    board_ids = tuple(f"wk{chr(97 + i // 26)}{chr(97 + i % 26)}aaaaaa" for i in range(65))
    seed_event(db, board_ids)
    for workout_id in board_ids:
        seed_server(db, workout_id, "web")
    rows = hosts(db)
    server_queries = [r for r in db.reads if r[1] == DbCollections.SERVER]
    assert [len(f[0][2]) for _, _, f in server_queries] == [30, 30, 5]
    assert len(rows) == 65 * 2  # web has a document, db does not
    assert all(r.server_state is not None for r in rows if r.server == "web")


def test_an_event_with_no_boards_has_no_rows_and_no_server_query():
    db = FakeDb()
    seed_event(db, ())
    assert hosts(db) == []
    assert DbCollections.SERVER not in [coll for _, coll, _ in db.reads]


# --- authorization ------------------------------------------------------------------------

def test_missing_event_is_not_found(db):
    with pytest.raises(NotFound):
        CtfHosts(env_dict={}, db=db).hosts("ctfzzzzzzz", user())


def test_a_user_not_on_the_event_is_unauthorized_before_any_server_read(db):
    with pytest.raises(Unauthorized):
        hosts(db, user("other@example.edu"))
    assert [coll for _, coll, _ in db.reads] == [DbCollections.CTF]


def test_an_admin_not_on_the_event_can_read_host_rows(db):
    assert len(hosts(db, user("root@example.edu", admin=True))) == 4


# --- nested guests (N10) ------------------------------------------------------------------------

GUEST_FLAG = {"id": "web-g1", "server": "web", "guest": "ubuntu-lin", "slot": 1, "points": 100,
              "location_type": "file", "path": "/root/flag.txt", "operating_system": "linux"}
NESTED_GUESTS = [
    {"name": "ubuntu-lin", "server": "web", "domain": "ubuntu", "operating_system": "linux"},
    {"name": "win", "server": "web", "domain": "win10", "operating_system": "windows"},
]


@pytest.fixture
def nested_db(db):
    event = db.collection(DbCollections.CTF)[CTF_ID]
    event["spec"]["flags"].append(copy.deepcopy(GUEST_FLAG))
    event["spec"]["nested_guests"] = copy.deepcopy(NESTED_GUESTS)
    for board in db.collection(DbCollections.CTF_BOARD).values():
        board["flags"].append({"flag_id": GUEST_FLAG["id"], "digest": f"d-{board['workout_id']}-g"})
    return db


def test_each_guest_gets_a_row_per_board_right_after_its_parent(nested_db):
    rows = hosts(nested_db)
    assert [(r.workout_id, r.server, r.guest) for r in rows] == [
        (workout_id, server, guest) for workout_id in BOARDS
        for server, guest in [("web", None), ("web", "ubuntu-lin"), ("web", "win"), ("db", None)]
    ]


def test_guest_rows_allow_rebuild_and_show_the_parents_state(nested_db):
    # Even a WireGuard parent: a guest rebuild is a snapshot revert, not an instance nuke.
    seed_server(nested_db, BOARDS[0], "web", state=ServerStates.STOPPED.value, wireguard_endpoint_id="wg-1")
    by_key = {(r.workout_id, r.server, r.guest): r for r in hosts(nested_db)}
    parent, guest = by_key[(BOARDS[0], "web", None)], by_key[(BOARDS[0], "web", "win")]
    assert (parent.rebuild_allowed, guest.rebuild_allowed) == (False, True)
    assert (guest.server_state, guest.server_state_name) == (ServerStates.STOPPED.value, "STOPPED")
    assert guest.team_name == parent.team_name == "Team 1"


def test_a_guests_flags_count_on_the_guest_row_not_its_parent(nested_db):
    by_key = {(r.server, r.guest): r.flag_count for r in hosts(nested_db) if r.workout_id == BOARDS[0]}
    assert by_key == {("web", None): 2, ("web", "ubuntu-lin"): 1, ("web", "win"): 0, ("db", None): 1}


def test_a_parent_whose_only_flags_are_on_guests_is_still_listed_first():
    db = FakeDb()
    seed_event(db)
    event = db.collection(DbCollections.CTF)[CTF_ID]
    event["spec"]["flags"] = [copy.deepcopy(GUEST_FLAG)]
    event["spec"]["nested_guests"] = copy.deepcopy(NESTED_GUESTS[:1])
    for workout_id in BOARDS:
        seed_server(db, workout_id, "kali")
        seed_server(db, workout_id, "web")
    rows = [r for r in hosts(db) if r.workout_id == BOARDS[0]]
    assert [(r.server, r.guest, r.flag_count) for r in rows] == [
        ("web", None, 0), ("web", "ubuntu-lin", 0), ("kali", None, 0),
    ]


def test_guest_rows_of_a_parent_with_no_document_have_no_state(nested_db):
    del nested_db.collection(DbCollections.SERVER)[f"{BOARDS[0]}-web"]
    row = next(r for r in hosts(nested_db) if (r.workout_id, r.guest) == (BOARDS[0], "ubuntu-lin"))
    assert (row.server_state, row.server_state_name) == (None, None)
