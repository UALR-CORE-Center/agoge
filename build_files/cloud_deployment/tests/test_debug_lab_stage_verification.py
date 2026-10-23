"""Verify prompted lifecycle steps against persisted records without GCP."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import debug_lab as cli
from common.constants.database import DbCollections
from common.constants.states import ServerStates, UnitStates, WorkoutStates
from common.document_database.firestore_database import FirestoreDatabase


class FakeSnapshot:
    def __init__(self, record):
        self.record = record
        self.exists = record is not None

    def to_dict(self):
        return self.record


class FakeCollection:
    """Only the SDK boundary is replaced; real database adapters run above it."""
    def __init__(self, name, records, queries):
        self.name, self.records, self.queries = name, records, queries

    def document(self, identifier):
        return SimpleNamespace(get=lambda: FakeSnapshot(self.records.get(identifier)))

    def where(self, *, filter):
        self.queries.append((self.name, filter.field_path, filter.op_string, filter.value))
        assert filter.op_string == '=='
        selected = [FakeSnapshot(record) for record in self.records.values()
                    if record.get(filter.field_path) == filter.value]
        return SimpleNamespace(stream=lambda: iter(selected))


@pytest.fixture
def persisted():
    unit_id, workout_id = 'abcdefghij', 'klmnopqrst'
    records = {collection.value: {} for collection in DbCollections}
    unit = {
        'id': unit_id, 'state': UnitStates.READY.value,
        'servers': [{'name': 'wireguard', 'community_server': True},
                    {'name': 'student', 'community_server': False}],
        'wireguard_lease': {'remote_peer_id': 'remote-lab-01'},
    }
    workout = {'id': workout_id, 'parent_id': unit_id,
               'state': WorkoutStates.READY.value, 'student_email': 'student@example.edu'}
    records[DbCollections.UNIT.value][unit_id] = unit
    records[DbCollections.WORKOUT.value][workout_id] = workout
    names = (f'{unit_id}-wireguard', f'{workout_id}-student',
             f'{workout_id}-display-guacamole-server')
    servers = records[DbCollections.SERVER.value]
    for name in names:
        parent, short_name = name.split('-', 1)
        servers[name] = {'name': short_name, 'parent_id': parent, 'state': ServerStates.RUNNING.value}
    queries = []
    database = object.__new__(FirestoreDatabase)
    database.logger = Mock()
    database.db = SimpleNamespace(collection=lambda name: FakeCollection(name, records[name], queries))
    backend = cli.LocalBackend({'project': cli.TEST_PROJECT}, database, Mock(), Mock(), Mock(), Mock())
    return SimpleNamespace(backend=backend, records=records, unit=unit, workout=workout,
                           servers=servers, names=names, unit_id=unit_id,
                           workout_id=workout_id, queries=queries)


def complete_stage(persisted, stage):
    persisted.unit['state'] = UnitStates.RUNNING.value if stage == 'start' else UnitStates.READY.value
    persisted.workout['state'] = WorkoutStates.RUNNING.value if stage == 'start' else WorkoutStates.READY.value
    for server in persisted.servers.values():
        server['state'] = ServerStates.STOPPED.value if stage == 'stop' else ServerStates.RUNNING.value


@pytest.mark.parametrize('stage', ['build', 'start', 'stop'])
def test_stage_checks_real_firestore_queries_and_all_expected_records(persisted, stage):
    complete_stage(persisted, stage)

    status = persisted.backend._verify_lab_stage(persisted.unit_id, stage)

    assert status['unit_id'] == persisted.unit_id
    assert {row['workout_id'] for row in status['workouts']} == {persisted.workout_id}
    assert set(persisted.queries) == {
        (DbCollections.WORKOUT.value, 'parent_id', '==', persisted.unit_id),
        (DbCollections.SERVER.value, 'parent_id', '==', persisted.unit_id),
        (DbCollections.SERVER.value, 'parent_id', '==', persisted.workout_id),
    }


@pytest.mark.parametrize('stage', ['build', 'start', 'stop'])
@pytest.mark.parametrize('server_index', [0, 1, 2], ids=['gateway', 'student', 'display-proxy'])
@pytest.mark.parametrize('problem', ['missing', 'broken'])
def test_ready_parent_cannot_hide_missing_or_broken_servers(persisted, stage, server_index, problem):
    complete_stage(persisted, stage)
    name = persisted.names[server_index]
    if problem == 'missing':
        del persisted.servers[name]
    else:
        persisted.servers[name]['state'] = ServerStates.BROKEN.value

    with pytest.raises(RuntimeError, match=f'Server {name} did not complete {stage}'):
        persisted.backend._verify_lab_stage(persisted.unit_id, stage)


@pytest.mark.parametrize('stage', ['build', 'start', 'stop'])
def test_server_success_cannot_hide_a_broken_unit(persisted, stage):
    complete_stage(persisted, stage)
    persisted.unit['state'] = UnitStates.BROKEN.value
    with pytest.raises(RuntimeError, match=f'Lab {persisted.unit_id} did not complete {stage}'):
        persisted.backend._verify_lab_stage(persisted.unit_id, stage)


@pytest.mark.parametrize('stage', ['build', 'start', 'stop'])
def test_unit_success_cannot_hide_a_broken_workout(persisted, stage):
    complete_stage(persisted, stage)
    persisted.workout['state'] = WorkoutStates.BROKEN.value
    with pytest.raises(RuntimeError, match=f'Workout {persisted.workout_id} did not complete {stage}'):
        persisted.backend._verify_lab_stage(persisted.unit_id, stage)


def test_broken_dynamic_resource_is_checked_even_when_not_in_template(persisted):
    name = f'{persisted.unit_id}-extra-firewall'
    persisted.servers[name] = {'name': 'extra-firewall', 'parent_id': persisted.unit_id,
                               'state': ServerStates.BROKEN.value}
    with pytest.raises(RuntimeError, match=f'Server {name} did not complete build'):
        persisted.backend._verify_lab_stage(persisted.unit_id, 'build')


def test_previously_deleted_dynamic_record_does_not_block_new_stage(persisted):
    persisted.servers[f'{persisted.unit_id}-old-firewall'] = {
        'name': 'old-firewall', 'parent_id': persisted.unit_id, 'state': ServerStates.DELETED.value}
    assert persisted.backend._verify_lab_stage(persisted.unit_id, 'build')['state_name'] == 'READY'


def test_dynamic_license_server_with_full_name_is_not_prefixed_twice(persisted):
    name = f'{persisted.unit_id}-fortimanager'
    persisted.servers[name] = {'name': name, 'parent_id': persisted.unit_id,
                               'state': ServerStates.RUNNING.value}
    assert persisted.backend._verify_lab_stage(persisted.unit_id, 'build')['state_name'] == 'READY'


def test_gateway_only_build_does_not_require_unclaimed_student_servers(persisted):
    persisted.records[DbCollections.WORKOUT.value].clear()
    assert persisted.backend._verify_lab_stage(persisted.unit_id, 'build')['workouts'] == []


def test_run_captures_created_id_before_real_build_failure(persisted, capsys):
    args = cli.parser().parse_args([
        'run-lab', '--instructor', 'teacher@example.edu', '--remote-peer-id', 'remote-lab-01',
        '--skip-cleanup'])
    persisted.backend.users_class.return_value.get_user.return_value = SimpleNamespace(
        is_authorized=True, is_admin=False, email=args.instructor)
    persisted.backend._peer_service = Mock()
    persisted.backend._peer_service.return_value.get_authorized_remote_peer.return_value = SimpleNamespace(
        id=args.remote_peer_id, assigned_unit_id=None)
    persisted.backend.unit_class.return_value.build.return_value = persisted.unit_id
    persisted.backend._build_unit = Mock(side_effect=TimeoutError('private-worker-error'))
    prompt = Mock(side_effect=AssertionError('failed builds must not proceed to a prompt'))

    result = persisted.backend.run_lab(args, read_input=prompt)

    assert result['unit_id'] == persisted.unit_id
    assert result['outcome'] == 'failed' and result['exit_code'] == 1
    assert result['failed_step'] == 'build' and result['completed_steps'] == []
    assert result['error'] == 'TimeoutError'
    prompt.assert_not_called()
    output = capsys.readouterr().out
    assert f'Cleanup: debug_lab.py delete-labs --instructor {args.instructor} --unit-id {persisted.unit_id} --yes' in output
    assert 'private-worker-error' not in output
