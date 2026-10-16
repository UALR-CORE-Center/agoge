"""CtfEvent.reveal (the admin-only GET /ctf/{ctf_id}/flags/{flag_id}/reveal/ row)."""
from types import SimpleNamespace

import pytest

from common.constants.database import DbCollections
from common.constants.states import CtfStates
from common.exceptions.agoge import NotFound, ServiceUnavailable, Unauthorized
from common.models.users import AgogeUser
from common.utilities.ctf_flags import derive_flag_value
from core.ctf.event import CtfEvent

CTF_ID = "ctfaaaaaaa"
BOARD = "wkaaaaaaaa"
SEED = "test-seed"


class FakeDb:
    def __init__(self, docs):
        self.docs = docs
        self.writes = 0

    def get(self, collection_name, doc_id):
        return self.docs.get((collection_name, doc_id))


def user(admin):
    return AgogeUser(uid="uid", email="gm@example.edu", permissions={"instructor": True, "admin": admin})


def event_doc(**kw):
    return {
        "id": CTF_ID, "unit_id": "unitabcdef", "instructor_id": ["gm@example.edu"],
        "spec": {"name": "CTF", "scoring": {"flag_prefix": "acme"}, "flags": [{
            "id": "web1", "server": "web", "slot": 1, "points": 100,
            "location_type": "file", "path": "/root/flag.txt", "operating_system": "linux",
        }]},
        "creation_timestamp": 1.0, "board_ids": [BOARD], "seed_version": 3,
        "state": CtfStates.RUNNING.value, "state_timestamp": "2026-10-16T00:00:00+00:00", **kw,
    }


def ctf(seed=SEED, doc=None):
    db = FakeDb({(DbCollections.CTF, CTF_ID): doc if doc is not None else event_doc()})
    return CtfEvent(env_dict={}, db=db, env=SimpleNamespace(ctf_flag_seed=seed))


def test_reveal_rederives_with_the_events_seed_version_and_prefix():
    revealed = ctf().reveal(CTF_ID, "web1", BOARD, user(admin=True))

    assert revealed.value == derive_flag_value(SEED, BOARD, "web1", 3, "acme")
    assert revealed.value.startswith("acme{web1_")
    assert (revealed.flag_id, revealed.workout_id) == ("web1", BOARD)


def test_reveal_refuses_a_non_admin_even_on_their_own_event():
    # The route's admin_required already stops this; core refuses too so no other caller can bypass it.
    with pytest.raises(Unauthorized):
        ctf().reveal(CTF_ID, "web1", BOARD, user(admin=False))


@pytest.mark.parametrize("flag_id, workout_id, message", [
    ("nope", BOARD, "Flag not found"),
    ("web1", "wkzzzzzzzz", "Board not found"),
])
def test_reveal_unknown_flag_or_board_is_not_found(flag_id, workout_id, message):
    with pytest.raises(NotFound, match=message):
        ctf().reveal(CTF_ID, flag_id, workout_id, user(admin=True))


def test_reveal_unknown_event_is_not_found():
    with pytest.raises(NotFound):
        CtfEvent(env_dict={}, db=FakeDb({}), env=SimpleNamespace(ctf_flag_seed=SEED)).reveal(
            CTF_ID, "web1", BOARD, user(admin=True)
        )


def test_reveal_without_a_seed_is_service_unavailable():
    with pytest.raises(ServiceUnavailable):
        ctf(seed=None).reveal(CTF_ID, "web1", BOARD, user(admin=True))
