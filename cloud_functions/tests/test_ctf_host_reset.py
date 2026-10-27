"""HostReset mode dispatch (G4-G7) and SC-9. Firestore, the compute manager and the plant procedure are mocked."""
from unittest.mock import MagicMock, call, patch

import pytest

from cloud_fn_utilities.course_objects.ctf import flag_planter as flag_planter_module
from cloud_fn_utilities.course_objects.ctf import host_reset as host_reset_module
from cloud_fn_utilities.course_objects.ctf.flag_planter import FlagPlanter
from cloud_fn_utilities.course_objects.ctf.host_reset import HostReset
from common.constants.database import DbCollections
from common.exceptions import NotFound
from common.models.agoge import CtfBoardModel, CtfEventModel

CTF_ID = "ctfeventaa"
WORKOUT_A = "aaaaaaaaaa"
WORKOUT_B = "bbbbbbbbbb"
BOARD_A = f"{CTF_ID}-{WORKOUT_A}"
BOARD_B = f"{CTF_ID}-{WORKOUT_B}"
ENV = {"project": "agoge-test-project"}

FLAGS = [
    {'id': 'web-user', 'server': 'web', 'slot': 1, 'location_type': 'file', 'path': '/home/student/user.txt',
     'operating_system': 'linux', 'points': 100},
    {'id': 'db-root', 'server': 'db', 'slot': 1, 'location_type': 'file', 'path': '/root/db.txt',
     'operating_system': 'linux', 'points': 300},
    {'id': 'web-root', 'server': 'web', 'slot': 2, 'location_type': 'env', 'path': 'AGOGE_ROOT_FLAG',
     'operating_system': 'linux', 'points': 200},
]
EVENT = {
    'id': CTF_ID, 'unit_id': 'unitaaaaaa', 'instructor_id': ['gm@example.edu'],
    'spec': {'name': 'Spring CTF', 'flags': FLAGS, 'scoring': {'flag_prefix': 'agoge'}},
    'creation_timestamp': 1.0, 'state': 4, 'state_timestamp': '2026-10-16T00:00:00+00:00',
}


def _board(board_id, workout_id, active=True):
    return CtfBoardModel(
        id=board_id, workout_id=workout_id, ctf_id=CTF_ID, team_name=workout_id, active=active,
        flags=[{'flag_id': f['id'], 'digest': '0' * 64, 'plant_status': 'planted', 'planted_at': 5.0}
               for f in FLAGS],
    ).model_dump()


class FakeDb:
    """Records every get and every transactional board write, so SC-9 can check nothing names board B."""
    def __init__(self, board_a=None, servers=None):
        self.docs = {
            (DbCollections.CTF, CTF_ID): EVENT,
            (DbCollections.CTF_BOARD, BOARD_A): board_a or _board(BOARD_A, WORKOUT_A),
            (DbCollections.CTF_BOARD, BOARD_B): _board(BOARD_B, WORKOUT_B),
        }
        for name, doc in (servers or {f"{WORKOUT_A}-web": {'name': f"{WORKOUT_A}-web"},
                                      f"{WORKOUT_A}-db": {'name': f"{WORKOUT_A}-db"}}).items():
            self.docs[(DbCollections.SERVER, name)] = doc
        self.gets = []
        self.writes = []      # (collection, doc id, update)
        self.db = MagicMock()
        self.db.collection.side_effect = self._collection

    def get(self, collection, doc_id):
        self.gets.append((collection, doc_id))
        return self.docs.get((collection, doc_id)) or {}

    def _collection(self, name):
        collection = MagicMock()
        collection.document.side_effect = lambda doc_id: SimpleRef(self, name, doc_id)
        return collection

    def transaction(self, operation):
        return operation(FakeTransaction(self))


class SimpleRef:
    def __init__(self, db, collection, doc_id):
        self.db, self.collection, self.id = db, collection, doc_id

    def get(self, transaction=None):
        data = next((v for (c, d), v in self.db.docs.items() if c.value == self.collection and d == self.id), None)
        snapshot = MagicMock()
        snapshot.exists = data is not None
        snapshot.to_dict.return_value = {**data, 'flags': [dict(f) for f in data['flags']]} if data else None
        return snapshot


class FakeTransaction:
    def __init__(self, db):
        self.db = db

    def update(self, ref, update):
        self.db.writes.append((ref.collection, ref.id, update))


@pytest.fixture(autouse=True)
def offline():
    with (
        patch.object(host_reset_module, "Logger"),
        patch.object(flag_planter_module, "Logger"),
    ):
        yield


@pytest.fixture
def factory():
    manager = MagicMock()
    with patch.object(host_reset_module, "ComputeManagerFactory") as factory_cls:
        factory_cls.create_manager_object.return_value = manager
        yield factory_cls


@pytest.fixture
def plant():
    with patch.object(FlagPlanter, "plant") as plant_mock:
        yield plant_mock


def _reset(db, mode, server='web'):
    return HostReset(env_dict=ENV, db=db).run(CTF_ID, WORKOUT_A, server, mode)


# ---- dispatch ----

@pytest.mark.parametrize("mode", ['reboot', '', None, 'REPLANT'])
def test_unknown_mode_raises_value_error_before_any_read(mode, factory, plant):
    db = FakeDb()
    with pytest.raises(ValueError, match="Unsupported CTF host reset mode"):
        _reset(db, mode)
    assert db.gets == []
    factory.create_manager_object.assert_not_called()
    plant.assert_not_called()


def test_missing_server_raises_value_error_before_any_read(factory):
    db = FakeDb()
    with pytest.raises(ValueError, match="server name"):
        _reset(db, 'restart', server=None)
    assert db.gets == []


@pytest.mark.parametrize("mode", ['replant', 'restart', 'rebuild'])
def test_every_mode_is_mapped_to_its_method(mode):
    reset = HostReset(env_dict=ENV, db=FakeDb())
    assert reset.mode_map[mode] == getattr(reset, f"_{mode}")
    assert set(reset.mode_map) == {'replant', 'restart', 'rebuild'}


@pytest.mark.parametrize("missing", [(DbCollections.CTF, CTF_ID), (DbCollections.CTF_BOARD, BOARD_A)])
def test_missing_event_or_board_raises_not_found(missing, factory, plant):
    db = FakeDb()
    del db.docs[missing]
    with pytest.raises(NotFound):
        _reset(db, 'replant')
    plant.assert_not_called()
    factory.create_manager_object.assert_not_called()


@pytest.mark.parametrize("mode", ['replant', 'restart', 'rebuild'])
def test_inactive_board_is_skipped(mode, factory, plant):
    db = FakeDb(board_a=_board(BOARD_A, WORKOUT_A, active=False))
    assert _reset(db, mode) is None
    plant.assert_not_called()
    factory.create_manager_object.assert_not_called()
    assert db.writes == []


# ---- replant (G5) ----

def test_replant_plants_only_the_named_server(factory, plant):
    db = FakeDb()
    assert _reset(db, 'replant') == 'replant'
    plant.assert_called_once()
    board, servers = plant.call_args.args
    assert board.id == BOARD_A
    assert servers == ['web']
    factory.create_manager_object.assert_not_called()


# ---- restart (G6) ----

def test_restart_stops_then_starts_the_board_instance(factory, plant):
    db = FakeDb()
    assert _reset(db, 'restart') == 'restart'
    manager = factory.create_manager_object.return_value
    factory.create_manager_object.assert_called_once_with(env_dict=ENV)
    manager.load.assert_called_once_with(server_name=f"{WORKOUT_A}-web", server_spec={'name': f"{WORKOUT_A}-web"})
    assert manager.method_calls[1:] == [call.stop(), call.start()]
    plant.assert_not_called()
    # restart leaves plant statuses alone: the flags are still on disk
    assert db.writes == []


def test_restart_does_not_start_when_stop_fails(factory):
    manager = factory.create_manager_object.return_value
    manager.stop.side_effect = RuntimeError("stop failed")
    with pytest.raises(RuntimeError):
        _reset(FakeDb(), 'restart')
    manager.start.assert_not_called()


def test_restart_of_a_missing_server_doc_raises_not_found(factory):
    with pytest.raises(NotFound):
        _reset(FakeDb(), 'restart', server='mail')
    factory.create_manager_object.assert_not_called()


# ---- rebuild (G7) ----

def test_rebuild_nukes_then_marks_only_that_servers_flags_stale(factory):
    db = FakeDb()
    assert _reset(db, 'rebuild') == 'rebuild'
    manager = factory.create_manager_object.return_value
    manager.nuke.assert_called_once_with()
    assert len(db.writes) == 1
    collection, doc_id, update = db.writes[0]
    assert (collection, doc_id) == (DbCollections.CTF_BOARD.value, BOARD_A)
    by_id = {f['flag_id']: f for f in update['flags']}
    for fid in ('web-user', 'web-root'):
        assert by_id[fid]['plant_status'] == 'stale'
        assert by_id[fid]['planted_at'] is None
    # db carries a flag on another server, which keeps its status
    assert by_id['db-root']['plant_status'] == 'planted'
    assert by_id['db-root']['planted_at'] == 5.0


def test_rebuild_of_a_server_without_flags_writes_nothing(factory):
    db = FakeDb(servers={f"{WORKOUT_A}-kali": {'name': f"{WORKOUT_A}-kali"}})
    assert _reset(db, 'rebuild', server='kali') == 'rebuild'
    factory.create_manager_object.return_value.nuke.assert_called_once_with()
    assert db.writes == []


def test_rebuild_is_refused_on_a_wireguard_server(factory):
    db = FakeDb(servers={f"{WORKOUT_A}-web": {'name': f"{WORKOUT_A}-web", 'wireguard_endpoint_id': 'wg-1'}})
    with pytest.raises(ValueError, match="WireGuard"):
        _reset(db, 'rebuild')
    factory.create_manager_object.assert_not_called()
    assert db.writes == []


def test_failed_rebuild_still_marks_flags_stale_and_reraises(factory):
    db = FakeDb()
    factory.create_manager_object.return_value.nuke.side_effect = RuntimeError("Cannot rebuild")
    with pytest.raises(RuntimeError, match="Cannot rebuild"):
        _reset(db, 'rebuild')
    statuses = {f['flag_id']: f['plant_status'] for f in db.writes[0][2]['flags']}
    assert statuses == {'web-user': 'stale', 'db-root': 'planted', 'web-root': 'stale'}


def test_failed_rebuild_reraises_the_nuke_error_when_marking_stale_fails(factory):
    db = FakeDb()
    factory.create_manager_object.return_value.nuke.side_effect = RuntimeError("Cannot rebuild")
    with patch.object(FlagPlanter, "mark_stale", side_effect=OSError("firestore down")):
        with pytest.raises(RuntimeError, match="Cannot rebuild"):
            _reset(db, 'rebuild')


# ---- SC-9 ----

@pytest.mark.parametrize("mode", ['replant', 'restart', 'rebuild'])
def test_sc9_a_reset_on_board_a_never_names_board_b(mode, factory, plant):
    db = FakeDb()
    _reset(db, mode)
    named = [doc_id for _, doc_id in db.gets] + [doc_id for _, doc_id, _ in db.writes]
    assert not [n for n in named if WORKOUT_B in n]
    manager = factory.create_manager_object.return_value
    compute_names = [str(c) for c in manager.mock_calls]
    assert not [c for c in compute_names if WORKOUT_B in c]
    for c in plant.call_args_list:
        board, servers = c.args
        assert board.id == BOARD_A
    if mode != 'replant':
        assert manager.load.call_args.kwargs['server_name'] == f"{WORKOUT_A}-web"


def test_mark_stale_touches_only_plant_fields():
    db = FakeDb()
    board = CtfBoardModel(**_board(BOARD_A, WORKOUT_A))
    board.flags[0].solved = True
    db.docs[(DbCollections.CTF_BOARD, BOARD_A)] = board.model_dump()
    result = FlagPlanter(CtfEventModel(**EVENT), env_dict=ENV, db=db).mark_stale(board, 'web')
    flag = next(f for f in result.flags if f.flag_id == 'web-user')
    assert flag.plant_status == 'stale'
    assert flag.solved is True
