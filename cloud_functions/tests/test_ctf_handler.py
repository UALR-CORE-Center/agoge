"""CtfHandler routing and the Handlers.CTF branch in main.py (E3, E4b, G4b). FlagPlanter, ArmWorker, HostReset and Firestore are mocked."""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

import main as main_module
from common.constants.database import DbCollections
from common.constants.pub_sub import PubSub
from common.exceptions import NotFound
from common.models.agoge import CtfBoardModel, CtfEventModel
from handlers import ctf_handler as ctf_handler_module
from handlers.ctf_handler import CtfHandler

CTF_ID = "ctfeventaa"
WORKOUT_ID = "abcdefghij"
BOARD_ID = f"{CTF_ID}-{WORKOUT_ID}"
ENV = {"project": "agoge-test-project"}

FLAGS = [
    {'id': 'web-user', 'server': 'web', 'slot': 1, 'location_type': 'file', 'path': '/home/student/user.txt',
     'operating_system': 'linux', 'points': 100},
    {'id': 'db-root', 'server': 'db', 'slot': 1, 'location_type': 'file', 'path': '/root/db.txt',
     'operating_system': 'linux', 'points': 300},
    {'id': 'web-root', 'server': 'web', 'slot': 2, 'location_type': 'env', 'path': 'AGOGE_ROOT_FLAG',
     'operating_system': 'linux', 'points': 200},
    {'id': 'mail-root', 'server': 'mail', 'slot': 1, 'location_type': 'file', 'path': '/root/mail.txt',
     'operating_system': 'linux', 'points': 50},
]
EVENT = {
    'id': CTF_ID, 'unit_id': 'unitaaaaaa', 'instructor_id': ['gm@example.edu'],
    'spec': {'name': 'Spring CTF', 'flags': FLAGS, 'scoring': {'flag_prefix': 'agoge'}},
    'creation_timestamp': 1.0, 'state': 1, 'state_timestamp': '2026-10-16T00:00:00+00:00',
}


def _board(active=True, flag_ids=('web-user', 'db-root', 'web-root')):
    # mail-root is deliberately absent so "all servers" must come from the board's flags, not the spec alone
    return CtfBoardModel(id=BOARD_ID, workout_id=WORKOUT_ID, ctf_id=CTF_ID, team_name='Team 1', active=active,
                         flags=[{'flag_id': fid, 'digest': '0' * 64} for fid in flag_ids]).model_dump()


def _db(event=EVENT, board=None):
    docs = {
        (DbCollections.CTF, CTF_ID): event,
        (DbCollections.CTF_BOARD, BOARD_ID): _board() if board is None else board,
    }
    db = MagicMock()
    # FirestoreDatabase.get returns {} for a missing document
    db.get.side_effect = lambda collection, doc_id: docs.get((collection, doc_id)) or {}
    return db


def _attributes(action=PubSub.Actions.CTF_PLANT, **extra):
    attributes = {
        PubSub.EventAttributes.HANDLER: PubSub.Handlers.CTF.value,
        PubSub.EventAttributes.ACTION: str(action.value) if hasattr(action, 'value') else action,
        PubSub.EventAttributes.CTF_ID: CTF_ID,
        PubSub.EventAttributes.WORKOUT_ID: WORKOUT_ID,
    }
    attributes.update(extra)
    return {k: v for k, v in attributes.items() if v is not None}


@pytest.fixture(autouse=True)
def offline():
    env = MagicMock()
    env.get_env.return_value = ENV
    with (
        patch.object(ctf_handler_module, "CloudEnv", return_value=env),
        patch.object(ctf_handler_module, "Logger"),
        patch.object(ctf_handler_module.DocumentDatabaseFactory, "create_db_object") as create_db,
    ):
        yield create_db


@pytest.fixture
def planter():
    with patch.object(ctf_handler_module, "FlagPlanter") as planter_cls:
        yield planter_cls


@pytest.fixture
def arm_worker():
    with patch.object(ctf_handler_module, "ArmWorker") as worker_cls:
        yield worker_cls


@pytest.fixture
def host_reset():
    with patch.object(ctf_handler_module, "HostReset") as reset_cls:
        yield reset_cls


def _handler(attributes, db=None):
    return CtfHandler(attributes, env_dict=ENV, db=db if db is not None else _db())


def test_ctf_plant_with_a_server_reaches_flag_planter_for_that_server(planter):
    db = _db()
    _handler(_attributes(**{PubSub.EventAttributes.SERVER_NAME: 'db'}), db=db).route()

    planter.assert_called_once()
    event, = planter.call_args.args
    assert isinstance(event, CtfEventModel) and event.id == CTF_ID
    assert planter.call_args.kwargs == {'env_dict': ENV, 'db': db}
    board, servers = planter.return_value.plant.call_args.args
    assert isinstance(board, CtfBoardModel) and board.id == BOARD_ID
    assert servers == ['db']


def test_ctf_plant_without_a_server_plants_every_server_carrying_a_board_flag(planter):
    _handler(_attributes()).route()

    _, servers = planter.return_value.plant.call_args.args
    # Spec flag order, de-duplicated; 'mail' has a spec flag but none on this board
    assert servers == ['web', 'db']


def test_ctf_plant_reads_the_event_and_the_board_by_their_ids(planter):
    db = _db()
    _handler(_attributes(), db=db).route()

    assert [c.args for c in db.get.call_args_list] == [(DbCollections.CTF, CTF_ID), (DbCollections.CTF_BOARD, BOARD_ID)]


def test_ctf_plant_on_an_inactive_board_does_not_plant(planter):
    _handler(_attributes(), db=_db(board=_board(active=False))).route()

    planter.assert_not_called()


@pytest.mark.parametrize("missing", ["event", "board"])
def test_ctf_plant_with_a_missing_document_raises_not_found(planter, missing):
    db = _db(event={} if missing == "event" else EVENT, board={} if missing == "board" else None)

    with pytest.raises(NotFound):
        _handler(_attributes(), db=db).route()
    planter.assert_not_called()


def test_planter_errors_propagate(planter):
    planter.return_value.plant.side_effect = RuntimeError("boom")

    with pytest.raises(RuntimeError):
        _handler(_attributes()).route()


def test_ctf_arm_board_reaches_arm_worker(planter, arm_worker):
    db = _db()
    _handler(_attributes(action=PubSub.Actions.CTF_ARM_BOARD), db=db).route()

    arm_worker.assert_called_once_with(env_dict=ENV, db=db)
    arm_worker.return_value.run.assert_called_once_with(CTF_ID, WORKOUT_ID)
    # ArmWorker does its own loads (it must skip stale messages first), so the handler neither reads nor plants
    db.get.assert_not_called()
    planter.assert_not_called()


def test_ctf_plant_does_not_reach_arm_worker(planter, arm_worker):
    _handler(_attributes()).route()

    arm_worker.assert_not_called()
    planter.return_value.plant.assert_called_once()


def test_arm_worker_errors_propagate(arm_worker):
    arm_worker.return_value.run.side_effect = NotFound("missing")

    with pytest.raises(NotFound):
        _handler(_attributes(action=PubSub.Actions.CTF_ARM_BOARD)).route()


@pytest.mark.parametrize("mode", ["replant", "restart", "rebuild"])
def test_ctf_host_reset_reaches_host_reset_with_server_and_mode(planter, arm_worker, host_reset, mode):
    db = _db()
    _handler(_attributes(action=PubSub.Actions.CTF_HOST_RESET, **{
        PubSub.EventAttributes.SERVER_NAME: 'web',
        PubSub.EventAttributes.RESET_MODE: mode,
    }), db=db).route()

    host_reset.assert_called_once_with(env_dict=ENV, db=db)
    host_reset.return_value.run.assert_called_once_with(CTF_ID, WORKOUT_ID, 'web', mode, guest=None)
    # HostReset does its own loads and its own replant, so the handler neither reads nor plants
    db.get.assert_not_called()
    planter.assert_not_called()
    arm_worker.assert_not_called()


def test_ctf_host_reset_passes_missing_server_and_mode_through(host_reset):
    # HostReset rejects a missing server or mode with ValueError; the handler must not substitute defaults
    _handler(_attributes(action=PubSub.Actions.CTF_HOST_RESET)).route()

    host_reset.return_value.run.assert_called_once_with(CTF_ID, WORKOUT_ID, None, None, guest=None)


@pytest.mark.parametrize("mode", ["replant", "restart", "rebuild"])
def test_ctf_host_reset_passes_guest_to_host_reset(planter, host_reset, mode):
    # Without GUEST a guest reset would act on the whole parent server (N11)
    _handler(_attributes(action=PubSub.Actions.CTF_HOST_RESET, **{
        PubSub.EventAttributes.SERVER_NAME: 'hv-host',
        PubSub.EventAttributes.RESET_MODE: mode,
        PubSub.EventAttributes.GUEST: 'win-dc',
    })).route()

    host_reset.return_value.run.assert_called_once_with(CTF_ID, WORKOUT_ID, 'hv-host', mode, guest='win-dc')
    planter.assert_not_called()


def test_host_reset_errors_propagate(host_reset):
    host_reset.return_value.run.side_effect = ValueError("Unsupported reset mode")

    with pytest.raises(ValueError):
        _handler(_attributes(action=PubSub.Actions.CTF_HOST_RESET, **{
            PubSub.EventAttributes.SERVER_NAME: 'web',
            PubSub.EventAttributes.RESET_MODE: 'explode',
        })).route()


def test_ctf_plant_does_not_reach_host_reset(planter, host_reset):
    _handler(_attributes()).route()

    host_reset.assert_not_called()


@pytest.mark.parametrize("action", ["999", str(PubSub.Actions.START.value), str(PubSub.Actions.NUKE.value)])
def test_unknown_action_raises_value_error(planter, arm_worker, host_reset, action):
    with pytest.raises(ValueError):
        _handler(_attributes(action=action)).route()
    planter.assert_not_called()
    arm_worker.assert_not_called()
    host_reset.assert_not_called()


def test_missing_action_raises_value_error():
    attributes = _attributes()
    del attributes[PubSub.EventAttributes.ACTION]
    with pytest.raises(ValueError):
        _handler(attributes)


@pytest.mark.parametrize("key", [PubSub.EventAttributes.CTF_ID, PubSub.EventAttributes.WORKOUT_ID])
def test_missing_ctf_or_workout_id_raises_value_error(key):
    attributes = _attributes()
    del attributes[key]
    with pytest.raises(ValueError):
        _handler(attributes)


def test_handler_reads_ctf_attributes():
    handler = _handler(_attributes(**{
        PubSub.EventAttributes.SERVER_NAME: 'web',
        PubSub.EventAttributes.RESET_MODE: 'restart',
    }))

    assert (handler.ctf_id, handler.workout_id, handler.server_name, handler.reset_mode) == \
        (CTF_ID, WORKOUT_ID, 'web', 'restart')
    assert handler.env_dict == ENV


def test_handler_builds_its_own_firestore_client_when_none_is_given(offline):
    handler = CtfHandler(_attributes(), env_dict=ENV)

    offline.assert_called_once()
    assert handler.db is offline.return_value


def test_main_routes_the_ctf_handler():
    attributes = _attributes()
    context = SimpleNamespace(event_id="evt-1", timestamp="2026-10-16T00:00:00Z")
    with (
        patch.object(main_module, "BudgetManager") as budget,
        patch.object(main_module, "CtfHandler") as handler_cls,
        patch.object(main_module, "ControlHandler") as control_cls,
    ):
        budget.return_value.check_budget.return_value = True
        main_module.agoge_cloud_function({'attributes': attributes}, context)

    handler_cls.assert_called_once_with(attributes, debug=False)
    handler_cls.return_value.route.assert_called_once_with()
    control_cls.assert_not_called()
