"""Debug lab discovery and selected cleanup without cloud access."""
from copy import deepcopy
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import debug_lab as cli
from common.constants.database import DbCollections
from common.constants.pub_sub import PubSub
from common.constants.states import UnitStates


class Database:
    def __init__(self):
        self.collections = {collection: {} for collection in DbCollections}

    def get(self, collection_name, doc_id):
        return self.collections[collection_name].get(doc_id, {})

    def query(self, collection_name, filters=None):
        return [record for record in self.collections[collection_name].values()
                if all(record.get(field) == value for field, _, value in filters or [])]


@pytest.fixture
def cleanup():
    db = Database()
    user = SimpleNamespace(is_authorized=True, is_admin=False, email='teacher@example.edu')
    users = Mock()
    users.return_value.get_user.return_value = user
    worker = Mock()
    env = {'project': cli.TEST_PROJECT, 'region': 'us-central1', 'zone': 'us-central1-a'}
    backend = cli.LocalBackend(env, db, Mock(), Mock(), users, worker)
    return SimpleNamespace(db=db, user=user, users=users, worker=worker, env=env, backend=backend)


def add_lab(cleanup, unit_id='abcdefghij', *, peer='remote-lab-01', endpoint='10000', **changes):
    unit = {
        'id': unit_id, 'test': True, 'instructor_id': ['teacher@example.edu'],
        'state': UnitStates.BUILDING_SERVERS.value, 'creation_timestamp': 1000,
        'summary': {'name': f'Test {unit_id}'}, 'workspace_settings': {'expires': 2000},
        'wireguard_lease': {'kit_id': peer, 'remote_peer_id': peer},
        'wireguard_endpoint': {'id': endpoint, 'hostname': 'gateway.example.edu', 'port': 51820},
        'password': 'private-unit-secret', **changes,
    }
    cleanup.db.collections[DbCollections.UNIT][unit_id] = unit
    cleanup.db.collections[DbCollections.WIREGUARD_LEASE][unit_id] = {
        'unit_id': unit_id, 'kit_id': peer, 'remote_peer_id': peer,
        'endpoint_id': endpoint, 'status': 'reserved',
        'secret_version_name': 'private-secret-reference',
    }
    cleanup.db.collections[DbCollections.WIREGUARD_KIT][peer] = {
        'id': peer, 'enabled': True, 'assigned_unit_id': unit_id,
        'token_digest': 'private-token-digest',
    }
    cleanup.db.collections[DbCollections.WIREGUARD_ENDPOINT][endpoint] = {
        'id': endpoint, 'unit_id': unit_id, 'status': 'reserved',
    }
    return unit


def finish_delete(cleanup, unit_id):
    cleanup.db.collections[DbCollections.UNIT][unit_id]['state'] = UnitStates.DELETED.value
    lease = cleanup.db.collections[DbCollections.WIREGUARD_LEASE].get(unit_id)
    if lease:
        lease['status'] = 'released'
        cleanup.db.collections[DbCollections.WIREGUARD_KIT][lease['kit_id']]['assigned_unit_id'] = None
        cleanup.db.collections[DbCollections.WIREGUARD_ENDPOINT][lease['endpoint_id']]['status'] = 'released'


def test_list_only_authorized_test_labs_and_handles_legacy_instructor_field(cleanup):
    add_lab(cleanup)
    add_lab(cleanup, 'klmnopqrst', peer='other-peer', endpoint='10001', instructor_id='teacher@example.edu')
    add_lab(cleanup, 'uvwxyzabcd', peer='foreign-peer', endpoint='10002', instructor_id=['other@example.edu'])
    add_lab(cleanup, 'efghijklmn', peer='production-peer', endpoint='10003', test=False)
    add_lab(cleanup, 'opqrstuvwx', peer='not-boolean-peer', endpoint='10004', test='true')
    add_lab(cleanup, 'yzabcdefgh', peer='deleted-peer', endpoint='10005', state=UnitStates.DELETED.value)

    result = cleanup.backend.list_labs('teacher@example.edu')

    assert result['project'] == cli.TEST_PROJECT and result['total'] == 2
    items = {item['unit_id']: item for item in result['items']}
    assert set(items) == {'abcdefghij', 'klmnopqrst'}
    first = items['abcdefghij']
    assert first['name'] == 'Test abcdefghij'
    assert first['state_name'] == 'BUILDING_SERVERS'
    assert first['creation_timestamp'] == 1000 and first['expires'] == 2000
    assert first['remote_peer_id'] == 'remote-lab-01'
    output = json.dumps(result)
    for private in ('private-unit-secret', 'private-secret-reference', 'private-token-digest'):
        assert private not in output
    cleanup.worker.assert_not_called()


def test_list_filters_peer_and_can_include_deleted_runs(cleanup):
    add_lab(cleanup)
    add_lab(cleanup, 'klmnopqrst', peer='other-peer', endpoint='10001', state=UnitStates.DELETED.value)
    result = cleanup.backend.list_labs('teacher@example.edu', remote_peer_id='other-peer', include_deleted=True)
    assert [item['unit_id'] for item in result['items']] == ['klmnopqrst']
    assert result['items'][0]['state_name'] == 'DELETED'


def test_list_uses_the_real_firestore_query_adapter_without_cloud_access(cleanup):
    from common.document_database.firestore_database import FirestoreDatabase

    unit = add_lab(cleanup)
    database = object.__new__(FirestoreDatabase)
    database.db, database.logger = Mock(), Mock()
    query = database.db.collection.return_value.where.return_value
    query.stream.return_value = [SimpleNamespace(to_dict=lambda: unit)]
    cleanup.backend.db = database

    result = cleanup.backend.list_labs('teacher@example.edu')

    assert [item['unit_id'] for item in result['items']] == ['abcdefghij']
    database.db.collection.assert_called_once_with(DbCollections.UNIT.value)
    query.stream.assert_called_once_with()


@pytest.mark.parametrize('timestamp', [1000, None, float('nan')])
def test_status_uses_firestore_query_and_safely_reports_health(cleanup, timestamp):
    from common.document_database.firestore_database import FirestoreDatabase

    add_lab(cleanup)
    lease = cleanup.db.collections[DbCollections.WIREGUARD_LEASE]['abcdefghij']
    lease.update(health_timestamp=timestamp, health_error='private-worker-error')
    database = object.__new__(FirestoreDatabase)
    database.db, database.logger = Mock(), Mock()
    database.get = cleanup.db.get
    query = database.db.collection.return_value.where.return_value
    query.stream.return_value = [SimpleNamespace(to_dict=lambda: {
        'id': 'klmnopqrst', 'state': 0, 'student_email': 'student@example.edu'})]
    cleanup.backend.db = database

    result = cleanup.backend.status('abcdefghij')

    assert result['workouts'][0]['workout_id'] == 'klmnopqrst'
    assert result['wireguard']['health_error'] == 'other_error'
    if timestamp == 1000:
        assert result['wireguard']['health_age_seconds'] > 0
    else:
        assert result['wireguard']['health_age_seconds'] is None
    assert result['endpoint']['status'] == 'reserved'
    assert 'private-worker-error' not in json.dumps(result)
    database.db.collection.assert_called_once_with(DbCollections.WORKOUT.value)
    query.stream.assert_called_once_with()


@pytest.mark.parametrize('state,expected', [(11, 'BROKEN'), (None, 'UNKNOWN')])
def test_status_distinguishes_gateway_failure_from_parent_build_stage(cleanup, state, expected):
    add_lab(cleanup, servers=[{'name': 'wireguard', 'wireguard_gateway': True}])
    if state is not None:
        cleanup.db.collections[DbCollections.SERVER]['abcdefghij-wireguard'] = {
            'state': state, 'metadata': 'private-bootstrap-value', 'password': 'private-server-password'}

    result = cleanup.backend.status('abcdefghij')

    assert result['state_name'] == 'BUILDING_SERVERS'
    assert result['gateway'] == {'server_name': 'abcdefghij-wireguard', 'state': state, 'state_name': expected}
    assert 'private-bootstrap-value' not in json.dumps(result)
    assert 'private-server-password' not in json.dumps(result)


def test_unit_action_sdk_failure_prints_safe_location_without_sdk_body(monkeypatch, capsys):
    from google.api_core.exceptions import InvalidArgument

    def fail(*args, **kwargs):
        raise InvalidArgument('private-sdk-error-body')

    backend = Mock()
    backend.action.side_effect = fail
    monkeypatch.setattr(cli, 'load_backend', Mock(return_value=backend))

    code = cli.main(['unit-action', '--unit-id', 'abcdefghij', '--action', 'build'])

    output = capsys.readouterr()
    assert code == 1 and 'InvalidArgument' in output.err
    assert 'test_debug_lab_cleanup.py:' in output.err and 'in fail' in output.err
    assert 'private-sdk-error-body' not in output.out + output.err
    assert str(cli.ROOT) not in output.out + output.err


def test_actual_admin_can_list_other_instructors_test_labs(cleanup):
    cleanup.user.is_admin = True
    add_lab(cleanup, instructor_id=['other@example.edu'])
    assert cleanup.backend.list_labs('admin@example.edu')['total'] == 1


def test_non_instructor_cannot_list_or_delete_labs(cleanup):
    cleanup.user.is_authorized = False
    add_lab(cleanup)
    with pytest.raises(ValueError):
        cleanup.backend.list_labs('student@example.edu')
    with pytest.raises(ValueError):
        cleanup.backend.delete_labs('student@example.edu', ['abcdefghij'], execute=True)
    cleanup.worker.assert_not_called()


@pytest.mark.parametrize('changes', [{'test': False}, {'test': 'true'}, {'test': None},
                                  {'instructor_id': ['other@example.edu']}])
def test_delete_validates_every_target_before_any_dispatch(cleanup, changes):
    add_lab(cleanup)
    add_lab(cleanup, 'klmnopqrst', peer='second-peer', endpoint='10001', **changes)
    before = deepcopy(cleanup.db.collections)

    with pytest.raises(ValueError):
        cleanup.backend.delete_labs('teacher@example.edu', ['abcdefghij', 'klmnopqrst'], execute=True)

    cleanup.worker.assert_not_called()
    assert cleanup.db.collections == before


def test_missing_batch_target_stops_before_deleting_valid_target(cleanup):
    add_lab(cleanup)
    with pytest.raises(ValueError):
        cleanup.backend.delete_labs('teacher@example.edu', ['abcdefghij', 'klmnopqrst'], execute=True)
    cleanup.worker.assert_not_called()


def test_preview_is_read_only_and_deduplicates_selected_ids(cleanup):
    add_lab(cleanup)
    before = deepcopy(cleanup.db.collections)
    result = cleanup.backend.delete_labs('teacher@example.edu', ['abcdefghij', 'abcdefghij'])
    assert result['dry_run'] is True and result['total'] == 1
    assert [item['unit_id'] for item in result['items']] == ['abcdefghij']
    assert cleanup.db.collections == before
    cleanup.worker.assert_not_called()


def test_execute_uses_normal_delete_worker_and_confirms_all_release_states(cleanup):
    add_lab(cleanup)
    add_lab(cleanup, 'klmnopqrst', peer='second-peer', endpoint='10001', instructor_id='teacher@example.edu')
    cleanup.worker.side_effect = lambda attrs, env: finish_delete(cleanup, attrs['build_id'])

    result = cleanup.backend.delete_labs('teacher@example.edu', ['abcdefghij', 'klmnopqrst', 'abcdefghij'], execute=True)

    assert result['dry_run'] is False
    assert result['total'] == result['deleted'] == 2 and result['failed'] == 0
    assert cleanup.worker.call_count == 2
    for call in cleanup.worker.call_args_list:
        attrs, env = call.args
        assert env is cleanup.env
        assert attrs['handler'] == PubSub.Handlers.CONTROL.value
        assert attrs['action'] == str(PubSub.Actions.DELETE.value)
        assert attrs['course_object'] == str(PubSub.CourseObjects.UNIT.value)
    for item in result['items']:
        assert item['deleted'] and item['state'] == UnitStates.DELETED.value
        assert item['lease_released'] and item['peer_released'] and item['endpoint_released']
    assert len(cleanup.db.collections[DbCollections.UNIT]) == 2  # Keep audit tombstones.


@pytest.mark.parametrize('incomplete', ['unit', 'lease', 'missing_lease', 'peer', 'endpoint'])
def test_worker_return_is_not_enough_to_claim_cleanup_success(cleanup, incomplete):
    add_lab(cleanup)
    def incomplete_delete(attrs, env):
        finish_delete(cleanup, attrs['build_id'])
        if incomplete == 'unit':
            cleanup.db.collections[DbCollections.UNIT]['abcdefghij']['state'] = UnitStates.BROKEN.value
        elif incomplete == 'lease':
            cleanup.db.collections[DbCollections.WIREGUARD_LEASE]['abcdefghij']['status'] = 'reserved'
        elif incomplete == 'missing_lease':
            cleanup.db.collections[DbCollections.WIREGUARD_LEASE].pop('abcdefghij')
        elif incomplete == 'peer':
            cleanup.db.collections[DbCollections.WIREGUARD_KIT]['remote-lab-01']['assigned_unit_id'] = 'abcdefghij'
        else:
            cleanup.db.collections[DbCollections.WIREGUARD_ENDPOINT]['10000']['status'] = 'releasing'
    cleanup.worker.side_effect = incomplete_delete

    result = cleanup.backend.delete_labs('teacher@example.edu', ['abcdefghij'], execute=True)

    assert result['deleted'] == 0 and result['failed'] == 1
    assert result['items'][0]['deleted'] is False


def test_already_complete_cleanup_is_idempotent_without_dispatch(cleanup):
    add_lab(cleanup)
    finish_delete(cleanup, 'abcdefghij')
    result = cleanup.backend.delete_labs('teacher@example.edu', ['abcdefghij'], execute=True)
    assert result['deleted'] == 1 and result['failed'] == 0
    cleanup.worker.assert_not_called()


def test_deleted_unit_with_unreleased_claim_is_retried(cleanup):
    add_lab(cleanup, state=UnitStates.DELETED.value)
    cleanup.worker.side_effect = lambda attrs, env: finish_delete(cleanup, attrs['build_id'])
    result = cleanup.backend.delete_labs('teacher@example.edu', ['abcdefghij'], execute=True)
    cleanup.worker.assert_called_once()
    assert result['items'][0]['deleted'] and result['failed'] == 0


def test_failure_of_one_run_does_not_prevent_selected_other_runs(cleanup):
    add_lab(cleanup)
    add_lab(cleanup, 'klmnopqrst', peer='second-peer', endpoint='10001')
    def delete(attrs, env):
        if attrs['build_id'] == 'abcdefghij':
            raise RuntimeError('private-worker-error-body')
        finish_delete(cleanup, attrs['build_id'])
    cleanup.worker.side_effect = delete

    result = cleanup.backend.delete_labs('teacher@example.edu', ['abcdefghij', 'klmnopqrst'], execute=True)

    assert result['deleted'] == 1 and result['failed'] == 1 and cleanup.worker.call_count == 2
    assert 'private-worker-error-body' not in json.dumps(result)
    assert result['items'][0]['deleted'] is False and result['items'][1]['deleted'] is True


def test_reused_endpoint_or_peer_belonging_to_another_lab_does_not_block_old_cleanup(cleanup):
    add_lab(cleanup, state=UnitStates.DELETED.value)
    cleanup.db.collections[DbCollections.WIREGUARD_LEASE]['abcdefghij']['status'] = 'released'
    cleanup.db.collections[DbCollections.WIREGUARD_KIT]['remote-lab-01']['assigned_unit_id'] = 'anotherlab'
    cleanup.db.collections[DbCollections.WIREGUARD_ENDPOINT]['10000'].update(unit_id='anotherlab', status='active')
    result = cleanup.backend.delete_labs('teacher@example.edu', ['abcdefghij'], execute=True)
    assert result['items'][0]['deleted'] and result['failed'] == 0
    cleanup.worker.assert_not_called()


def test_admin_can_delete_selected_foreign_test_lab(cleanup):
    cleanup.user.is_admin = True
    add_lab(cleanup, instructor_id='other@example.edu')
    cleanup.worker.side_effect = lambda attrs, env: finish_delete(cleanup, attrs['build_id'])
    result = cleanup.backend.delete_labs('admin@example.edu', ['abcdefghij'], execute=True)
    assert result['deleted'] == 1 and result['failed'] == 0


def test_main_lists_labs_with_explicit_filters(monkeypatch):
    backend = Mock()
    backend.list_labs.return_value = {'project': cli.TEST_PROJECT, 'items': [], 'total': 0}
    monkeypatch.setattr(cli, 'load_backend', Mock(return_value=backend))
    assert cli.main(['list-labs', '--instructor', 'Teacher@Example.edu',
                     '--remote-peer-id', 'remote-lab-01', '--include-deleted']) == 0
    backend.list_labs.assert_called_once_with('teacher@example.edu', 'remote-lab-01', True)


@pytest.mark.parametrize('execute', [False, True])
def test_main_delete_defaults_preview_and_passes_explicit_ids(monkeypatch, execute):
    backend = Mock()
    backend.delete_labs.return_value = {'project': cli.TEST_PROJECT, 'dry_run': not execute,
                                       'items': [], 'total': 2, 'failed': 0}
    monkeypatch.setattr(cli, 'load_backend', Mock(return_value=backend))
    arguments = ['delete-labs', '--instructor', 'Teacher@Example.edu',
                 '--unit-id', 'abcdefghij', '--unit-id', 'klmnopqrst']
    if execute:
        arguments.append('--yes')
    assert cli.main(arguments) == 0
    backend.delete_labs.assert_called_once_with('teacher@example.edu', ['abcdefghij', 'klmnopqrst'], execute=execute)


def test_main_reports_failed_cleanup_as_nonzero_exit(monkeypatch, capsys):
    backend = Mock()
    backend.delete_labs.return_value = {'project': cli.TEST_PROJECT, 'dry_run': False,
        'items': [{'unit_id': 'abcdefghij', 'deleted': False}], 'total': 1, 'deleted': 0, 'failed': 1}
    monkeypatch.setattr(cli, 'load_backend', Mock(return_value=backend))
    assert cli.main(['delete-labs', '--instructor', 'teacher@example.edu',
                     '--unit-id', 'abcdefghij', '--yes']) == 1
    assert json.loads(capsys.readouterr().out)['failed'] == 1


@pytest.mark.parametrize('arguments', [
    ['list-labs', '--instructor', 'not-email'],
    ['list-labs', '--instructor', 'teacher@example.edu', '--remote-peer-id', '../other'],
    ['delete-labs', '--instructor', 'teacher@example.edu'],
    ['delete-labs', '--instructor', 'teacher@example.edu', '--unit-id', '../other'],
    ['--project', 'agoge-ualr', 'delete-labs', '--instructor', 'teacher@example.edu', '--unit-id', 'abcdefghij'],
])
def test_invalid_cleanup_arguments_fail_before_cloud_access(monkeypatch, arguments):
    loader = Mock()
    monkeypatch.setattr(cli, 'load_backend', loader)
    with pytest.raises(SystemExit) as error:
        cli.main(arguments)
    assert error.value.code == 2
    loader.assert_not_called()
