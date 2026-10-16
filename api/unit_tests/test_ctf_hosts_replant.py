"""CtfHosts.replant (PRD G1; endpoint table PUT /ctf/{ctf_id}/flags/)."""
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
BOARDS = ("wkaaaaaaaa", "wkbbbbbbbb", "wkcccccccc")
# Two flags share "web" and a decoy sits alone on "db", so the flag-bearing servers are web, db, then ftp.
FLAGS = [
    {"id": "web1", "server": "web", "slot": 1, "points": 100, "location_type": "file",
     "path": "/root/flag.txt", "operating_system": "linux"},
    {"id": "db1", "server": "db", "slot": 1, "points": 50, "location_type": "file",
     "path": "/root/decoy.txt", "operating_system": "linux", "decoy": True},
    {"id": "web2", "server": "web", "slot": 2, "points": 100, "location_type": "file",
     "path": "/root/flag2.txt", "operating_system": "linux"},
    {"id": "ftp1", "server": "ftp", "slot": 1, "points": 100, "location_type": "file",
     "path": "/root/flag.txt", "operating_system": "linux"},
]
SERVERS = ("web", "db", "ftp")


class FakeDb:
    """Only `get` exists: replant reads the event and must write nothing."""
    def __init__(self):
        self.store = {}

    def get(self, collection_name, doc_id):
        return copy.deepcopy(self.store.get(collection_name.value, {}).get(doc_id))


class FakePubSub:
    """`fail_after` raises in-line; `future_errors` maps (workout, server) to the error its publish
    future resolves with, which is how the real client reports network and permission failures."""
    def __init__(self, fail_after=None, future_errors=None):
        self.messages = []
        self.fail_after = fail_after
        self.future_errors = future_errors or {}

    def msg(self, **attrs):
        if self.fail_after is not None and len(self.messages) == self.fail_after:
            raise RuntimeError("client unusable")
        self.messages.append(attrs)
        future = Future()
        key = (attrs[PubSub.EventAttributes.WORKOUT_ID], attrs[PubSub.EventAttributes.SERVER_NAME])
        if key in self.future_errors:
            future.set_exception(self.future_errors[key])
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


def message(workout_id, server):
    return {
        "handler": PubSub.Handlers.CTF.value,
        "action": str(PubSub.Actions.CTF_PLANT.value),
        "ctf_id": CTF_ID,
        "workout_id": workout_id,
        "server_name": server,
    }


@pytest.fixture
def db():
    fake = FakeDb()
    seed(fake)
    return fake


@pytest.fixture
def pubsub():
    return FakePubSub()


def replant(db, pubsub, workout_ids=None, servers=None, who=None):
    return CtfHosts(env_dict={}, db=db, pubsub=pubsub).replant(CTF_ID, workout_ids, servers, who or user())


# --- fan-out: one CTF_PLANT per board+server -------------------------------------------

def test_null_selection_publishes_one_plant_per_board_and_flag_bearing_server(db, pubsub):
    count = replant(db, pubsub)
    assert pubsub.messages == [message(w, s) for w in BOARDS for s in SERVERS]
    assert count == len(BOARDS) * len(SERVERS)


def test_every_message_names_its_server_so_the_handler_plants_only_that_one(db, pubsub):
    # Without SERVER_NAME the handler plants every server of the board, which would multiply the work.
    replant(db, pubsub)
    assert all(m["server_name"] for m in pubsub.messages)


def test_scoped_selection_publishes_only_the_chosen_boards_and_servers(db, pubsub):
    count = replant(db, pubsub, workout_ids=[BOARDS[2], BOARDS[0]], servers=["ftp"])
    assert pubsub.messages == [message(BOARDS[0], "ftp"), message(BOARDS[2], "ftp")]
    assert count == 2


def test_one_board_null_servers_covers_every_flag_bearing_server(db, pubsub):
    replant(db, pubsub, workout_ids=[BOARDS[1]])
    assert pubsub.messages == [message(BOARDS[1], s) for s in SERVERS]


def test_duplicate_selections_publish_once(db, pubsub):
    replant(db, pubsub, workout_ids=[BOARDS[0], BOARDS[0]], servers=["web", "web"])
    assert pubsub.messages == [message(BOARDS[0], "web")]


def test_a_server_with_only_a_decoy_is_flag_bearing(db, pubsub):
    replant(db, pubsub, workout_ids=[BOARDS[0]], servers=["db"])
    assert pubsub.messages == [message(BOARDS[0], "db")]


# --- states -----------------------------------------------------------------------------

@pytest.mark.parametrize("state", [CtfStates.ARMED, CtfStates.RUNNING, CtfStates.PAUSED, CtfStates.BROKEN])
def test_replant_is_allowed_in_armed_running_paused_and_broken(db, pubsub, state):
    seed(db, state)
    assert replant(db, pubsub) == len(BOARDS) * len(SERVERS)


@pytest.mark.parametrize("state", [CtfStates.DRAFT, CtfStates.ARMING, CtfStates.ENDED, CtfStates.ARCHIVED])
def test_replant_in_any_other_state_is_a_conflict_naming_it_and_publishes_nothing(db, pubsub, state):
    seed(db, state)
    with pytest.raises(Conflict, match=state.name):
        replant(db, pubsub)
    assert pubsub.messages == []


# --- refusals before any publish --------------------------------------------------------

def test_unknown_board_is_a_bad_request_naming_it(db, pubsub):
    with pytest.raises(BadRequest, match="wkzzzzzzzz"):
        replant(db, pubsub, workout_ids=[BOARDS[0], "wkzzzzzzzz"])
    assert pubsub.messages == []


def test_server_without_flags_is_a_bad_request_naming_it(db, pubsub):
    with pytest.raises(BadRequest, match="kali"):
        replant(db, pubsub, servers=["web", "kali"])
    assert pubsub.messages == []


@pytest.mark.parametrize("field", ["workout_ids", "servers"])
def test_an_empty_list_is_a_bad_request_not_a_silent_no_op(db, pubsub, field):
    with pytest.raises(BadRequest):
        replant(db, pubsub, **{field: []})
    assert pubsub.messages == []


def test_missing_event_is_not_found(pubsub):
    with pytest.raises(NotFound):
        replant(FakeDb(), pubsub)
    assert pubsub.messages == []


def test_non_instructor_is_unauthorized(db, pubsub):
    with pytest.raises(Unauthorized):
        replant(db, pubsub, who=user(email="other@example.edu"))
    assert pubsub.messages == []


def test_admin_who_is_not_an_instructor_may_replant(db, pubsub):
    assert replant(db, pubsub, who=user(email="admin@example.edu", admin=True)) == len(BOARDS) * len(SERVERS)


# --- publish failures surface through the future ----------------------------------------

def test_a_failed_publish_future_is_raised_after_every_message_is_tried(db):
    pubsub = FakePubSub(future_errors={(BOARDS[0], "web"): PermissionError("denied")})
    with pytest.raises(PermissionError, match="denied"):
        replant(db, pubsub)
    assert len(pubsub.messages) == len(BOARDS) * len(SERVERS)


def test_an_unresolved_future_times_out_instead_of_hanging(db, monkeypatch):
    class Hanging(FakePubSub):
        def msg(self, **attrs):
            self.messages.append(attrs)
            return Future()  # never resolves

    monkeypatch.setattr(CtfHosts, "PUBLISH_TIMEOUT_SECONDS", 0)
    with pytest.raises(TimeoutError):
        replant(db, Hanging(), workout_ids=[BOARDS[0]], servers=["web"])


def test_an_in_line_raise_stops_publishing_and_is_raised(db):
    pubsub = FakePubSub(fail_after=1)
    with pytest.raises(RuntimeError, match="client unusable"):
        replant(db, pubsub)
    assert len(pubsub.messages) == 1
