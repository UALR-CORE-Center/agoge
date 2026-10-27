"""CtfHosts.reset (PRD G3; endpoint table PUT /ctf/{ctf_id}/boards/{workout_id}/hosts/{server}/reset/)."""
import copy
from concurrent.futures import Future

import pytest

from common.constants.database import DbCollections
from common.constants.pub_sub import PubSub
from common.constants.states import CtfStates
from common.exceptions.agoge import BadRequest, Conflict, NotFound, Unauthorized
from common.models.users import AgogeUser
from core.ctf.hosts import CtfHosts

GM = "gm@example.edu"
CTF_ID = "ctfaaaaaaa"
BOARDS = ("wkaaaaaaaa", "wkbbbbbbbb")
FLAGS = [
    {"id": "web1", "server": "web", "slot": 1, "points": 100, "location_type": "file",
     "path": "/root/flag.txt", "operating_system": "linux"},
    {"id": "db1", "server": "db", "slot": 1, "points": 50, "location_type": "file",
     "path": "/root/decoy.txt", "operating_system": "linux", "decoy": True},
]


class FakeDb:
    """Only `get` exists: reset reads the event and the target server and must write nothing."""
    def __init__(self):
        self.store = {}
        self.reads = []

    def get(self, collection_name, doc_id):
        self.reads.append((collection_name.value, doc_id))
        return copy.deepcopy(self.store.get(collection_name.value, {}).get(doc_id))


class FakePubSub:
    """`raise_inline` raises from msg; `future_error` is what the publish future resolves with, which is
    how the real client reports network and permission failures."""
    def __init__(self, raise_inline=False, future_error=None):
        self.messages = []
        self.raise_inline = raise_inline
        self.future_error = future_error

    def msg(self, **attrs):
        if self.raise_inline:
            raise RuntimeError("client unusable")
        self.messages.append(attrs)
        future = Future()
        if self.future_error:
            future.set_exception(self.future_error)
        else:
            future.set_result("message-id")
        return future


def user(email=GM, admin=False):
    return AgogeUser(uid="uid", email=email, permissions={"instructor": True, "admin": admin})


def seed(db, state=CtfStates.RUNNING):
    db.store.setdefault(DbCollections.CTF.value, {})[CTF_ID] = {
        "id": CTF_ID, "unit_id": "unitabcdef", "instructor_id": [GM],
        "spec": {"name": "Spring CTF", "flags": copy.deepcopy(FLAGS)},
        "creation_timestamp": 1_700_000_000.0, "board_ids": list(BOARDS),
        "state": state.value, "state_timestamp": "2026-10-16T00:00:00+00:00",
    }
    servers = db.store.setdefault(DbCollections.SERVER.value, {})
    for workout_id in BOARDS:
        # "kali" carries no flags; "vpn" is a WireGuard server (Host Reset Modes refuses rebuild there).
        for name in ("web", "db", "kali"):
            servers[f"{workout_id}-{name}"] = {"name": name, "parent_id": workout_id, "state": 4}
        servers[f"{workout_id}-vpn"] = {
            "name": "vpn", "parent_id": workout_id, "state": 4, "wireguard_endpoint_id": "wg-1",
        }


def message(workout_id, server, mode):
    return {
        "handler": PubSub.Handlers.CTF.value,
        "action": str(PubSub.Actions.CTF_HOST_RESET.value),
        "ctf_id": CTF_ID,
        "workout_id": workout_id,
        "server_name": server,
        "reset_mode": mode,
    }


@pytest.fixture
def db():
    db = FakeDb()
    seed(db)
    return db


def hosts(db, pubsub):
    return CtfHosts(env_dict={}, db=db, pubsub=pubsub)


@pytest.mark.parametrize("mode", ["replant", "restart", "rebuild"])
def test_publishes_exactly_one_reset_for_the_target(db, mode):
    pubsub = FakePubSub()
    hosts(db, pubsub).reset(CTF_ID, BOARDS[1], "web", mode, user())
    assert pubsub.messages == [message(BOARDS[1], "web", mode)]


def test_attribute_names_match_the_pubsub_contract(db):
    # The handler reads these keys, so the literal names in message() must stay the contract's names.
    attrs = PubSub.EventAttributes
    assert (attrs.WORKOUT_ID, attrs.SERVER_NAME, attrs.RESET_MODE) == ("workout_id", "server_name", "reset_mode")


@pytest.mark.parametrize("state", [CtfStates.ARMED, CtfStates.RUNNING, CtfStates.PAUSED, CtfStates.BROKEN])
def test_allowed_states_publish(db, state):
    seed(db, state)
    pubsub = FakePubSub()
    hosts(db, pubsub).reset(CTF_ID, BOARDS[0], "web", "restart", user())
    assert len(pubsub.messages) == 1


@pytest.mark.parametrize("state", [CtfStates.DRAFT, CtfStates.ARMING, CtfStates.ENDED, CtfStates.ARCHIVED])
def test_other_states_conflict_and_publish_nothing(db, state):
    seed(db, state)
    pubsub = FakePubSub()
    with pytest.raises(Conflict) as exc:
        hosts(db, pubsub).reset(CTF_ID, BOARDS[0], "web", "restart", user())
    assert state.name in str(exc.value.message)
    assert pubsub.messages == []


def test_rebuild_of_a_wireguard_server_is_a_bad_request(db):
    pubsub = FakePubSub()
    with pytest.raises(BadRequest) as exc:
        hosts(db, pubsub).reset(CTF_ID, BOARDS[0], "vpn", "rebuild", user())
    assert "WireGuard" in exc.value.message
    assert pubsub.messages == []


def test_wireguard_server_can_still_be_restarted(db):
    # Only rebuild deletes the instance, so the WireGuard refusal is limited to it.
    pubsub = FakePubSub()
    hosts(db, pubsub).reset(CTF_ID, BOARDS[0], "vpn", "restart", user())
    assert pubsub.messages == [message(BOARDS[0], "vpn", "restart")]


def test_replant_of_a_server_without_flags_is_a_bad_request(db):
    pubsub = FakePubSub()
    with pytest.raises(BadRequest):
        hosts(db, pubsub).reset(CTF_ID, BOARDS[0], "kali", "replant", user())
    assert pubsub.messages == []


def test_decoy_only_server_can_be_replanted(db):
    pubsub = FakePubSub()
    hosts(db, pubsub).reset(CTF_ID, BOARDS[0], "db", "replant", user())
    assert pubsub.messages == [message(BOARDS[0], "db", "replant")]


@pytest.mark.parametrize("mode", ["restart", "rebuild"])
def test_flagless_server_can_be_restarted_or_rebuilt(db, mode):
    pubsub = FakePubSub()
    hosts(db, pubsub).reset(CTF_ID, BOARDS[0], "kali", mode, user())
    assert pubsub.messages == [message(BOARDS[0], "kali", mode)]


def test_unknown_mode_is_a_bad_request_before_any_read(db):
    pubsub = FakePubSub()
    with pytest.raises(BadRequest):
        hosts(db, pubsub).reset(CTF_ID, BOARDS[0], "web", "snapshot", user())
    assert db.reads == [] and pubsub.messages == []


def test_workout_that_is_not_a_board_is_not_found(db):
    pubsub = FakePubSub()
    with pytest.raises(NotFound):
        hosts(db, pubsub).reset(CTF_ID, "wkzzzzzzzz", "web", "restart", user())
    assert pubsub.messages == []
    assert all(collection != DbCollections.SERVER.value for collection, _ in db.reads)


def test_missing_server_document_is_not_found(db):
    del db.store[DbCollections.SERVER.value][f"{BOARDS[0]}-web"]
    pubsub = FakePubSub()
    with pytest.raises(NotFound):
        hosts(db, pubsub).reset(CTF_ID, BOARDS[0], "web", "replant", user())
    assert pubsub.messages == []


def test_reads_only_the_target_boards_server(db):
    # SC-9: a reset scoped to one board touches no other board's documents.
    hosts(db, FakePubSub()).reset(CTF_ID, BOARDS[0], "web", "rebuild", user())
    assert db.reads == [(DbCollections.CTF.value, CTF_ID), (DbCollections.SERVER.value, f"{BOARDS[0]}-web")]


def test_unknown_event_is_not_found(db):
    pubsub = FakePubSub()
    with pytest.raises(NotFound):
        hosts(db, pubsub).reset("ctfzzzzzzz", BOARDS[0], "web", "restart", user())
    assert pubsub.messages == []


def test_non_instructor_is_unauthorized_before_reading_the_server(db):
    pubsub = FakePubSub()
    with pytest.raises(Unauthorized):
        hosts(db, pubsub).reset(CTF_ID, BOARDS[0], "web", "restart", user("other@example.edu"))
    assert pubsub.messages == []
    assert db.reads == [(DbCollections.CTF.value, CTF_ID)]


def test_admin_not_on_the_event_may_reset(db):
    pubsub = FakePubSub()
    hosts(db, pubsub).reset(CTF_ID, BOARDS[0], "web", "restart", user("root@example.edu", admin=True))
    assert len(pubsub.messages) == 1


def test_failed_publish_future_raises(db):
    # The real client reports delivery failures only through the future.
    error = PermissionError("topic denied")
    with pytest.raises(PermissionError):
        hosts(db, FakePubSub(future_error=error)).reset(CTF_ID, BOARDS[0], "web", "restart", user())


def test_inline_publish_error_raises(db):
    with pytest.raises(RuntimeError):
        hosts(db, FakePubSub(raise_inline=True)).reset(CTF_ID, BOARDS[0], "web", "restart", user())


def test_writes_nothing(db):
    # FakeDb has no write methods, so any write would raise AttributeError; this pins that contract.
    before = copy.deepcopy(db.store)
    hosts(db, FakePubSub()).reset(CTF_ID, BOARDS[0], "web", "rebuild", user())
    assert db.store == before


# --- nested guests (N10) ------------------------------------------------------------------------

# "ubuntu-lin" carries a flag on web; "win" is a flagless guest on web; "kali-lin" lives on db.
GUEST_FLAG = {"id": "web-g1", "server": "web", "guest": "ubuntu-lin", "slot": 1, "points": 100,
              "location_type": "file", "path": "/root/flag.txt", "operating_system": "linux"}
NESTED_GUESTS = [
    {"name": "ubuntu-lin", "server": "web", "domain": "ubuntu", "operating_system": "linux"},
    {"name": "win", "server": "web", "domain": "win10", "operating_system": "windows"},
    {"name": "kali-lin", "server": "db", "domain": "kali", "operating_system": "linux"},
]


@pytest.fixture
def nested_db(db):
    spec = db.store[DbCollections.CTF.value][CTF_ID]["spec"]
    spec["flags"].append(copy.deepcopy(GUEST_FLAG))
    spec["nested_guests"] = copy.deepcopy(NESTED_GUESTS)
    return db


@pytest.mark.parametrize("mode", ["replant", "restart", "rebuild"])
def test_guest_reset_publishes_the_guest_attribute(nested_db, mode):
    pubsub = FakePubSub()
    hosts(nested_db, pubsub).reset(CTF_ID, BOARDS[0], "web", mode, user(), guest="ubuntu-lin")
    assert pubsub.messages == [{**message(BOARDS[0], "web", mode), PubSub.EventAttributes.GUEST: "ubuntu-lin"}]


def test_server_reset_carries_no_guest_attribute(nested_db):
    pubsub = FakePubSub()
    hosts(nested_db, pubsub).reset(CTF_ID, BOARDS[0], "web", "restart", user())
    assert PubSub.EventAttributes.GUEST not in pubsub.messages[0]


@pytest.mark.parametrize("server, guest", [("web", "nope"), ("web", "kali-lin"), ("db", "ubuntu-lin")])
def test_undeclared_guest_is_not_found_and_publishes_nothing(nested_db, server, guest):
    # kali-lin exists, but on db: a guest is declared per (server, guest), not per spec.
    pubsub = FakePubSub()
    with pytest.raises(NotFound):
        hosts(nested_db, pubsub).reset(CTF_ID, BOARDS[0], server, "restart", user(), guest=guest)
    assert pubsub.messages == []


def test_guest_on_an_event_without_nested_guests_is_not_found(db):
    pubsub = FakePubSub()
    with pytest.raises(NotFound):
        hosts(db, pubsub).reset(CTF_ID, BOARDS[0], "web", "restart", user(), guest="ubuntu-lin")
    assert pubsub.messages == []


def test_replant_of_a_flagless_guest_is_a_bad_request(nested_db):
    # web itself has flags, but the replant targets only the guest's.
    pubsub = FakePubSub()
    with pytest.raises(BadRequest):
        hosts(nested_db, pubsub).reset(CTF_ID, BOARDS[0], "web", "replant", user(), guest="win")
    assert pubsub.messages == []


@pytest.mark.parametrize("mode", ["restart", "rebuild"])
def test_flagless_guest_can_be_restarted_or_rebuilt(nested_db, mode):
    pubsub = FakePubSub()
    hosts(nested_db, pubsub).reset(CTF_ID, BOARDS[0], "web", mode, user(), guest="win")
    assert len(pubsub.messages) == 1


def test_guest_on_a_wireguard_parent_can_be_rebuilt(nested_db):
    # A guest rebuild reverts a snapshot inside the parent; the WireGuard nuke limit does not apply.
    nested_db.store[DbCollections.CTF.value][CTF_ID]["spec"]["nested_guests"].append(
        {"name": "vpn-guest", "server": "vpn", "domain": "g", "operating_system": "linux"})
    pubsub = FakePubSub()
    hosts(nested_db, pubsub).reset(CTF_ID, BOARDS[0], "vpn", "rebuild", user(), guest="vpn-guest")
    assert pubsub.messages[0][PubSub.EventAttributes.GUEST] == "vpn-guest"


def test_guest_of_a_missing_parent_document_is_not_found(nested_db):
    del nested_db.store[DbCollections.SERVER.value][f"{BOARDS[0]}-web"]
    pubsub = FakePubSub()
    with pytest.raises(NotFound):
        hosts(nested_db, pubsub).reset(CTF_ID, BOARDS[0], "web", "restart", user(), guest="ubuntu-lin")
    assert pubsub.messages == []
