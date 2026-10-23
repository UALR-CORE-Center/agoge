"""Prompted local lifecycle runs and narrowly scoped preflight cleanup."""
from datetime import datetime, timezone
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import debug_lab as cli
from common.constants.database import DbCollections
from common.constants.states import UnitStates, WorkoutStates


class Database:
    def __init__(self):
        self.collections = {collection: {} for collection in DbCollections}

    def get(self, collection_name, doc_id):
        return self.collections[collection_name].get(doc_id, {})

    def query(self, collection_name, filters=None):
        return [record for record in self.collections[collection_name].values()
                if all(record.get(field) == value for field, _, value in filters or [])]


@pytest.fixture
def local():
    db = Database()
    user = SimpleNamespace(is_authorized=True, is_admin=False, email='teacher@example.edu')
    users = Mock()
    users.return_value.get_user.return_value = user
    backend = cli.LocalBackend({'project': cli.TEST_PROJECT}, db, Mock(), Mock(), users, Mock())
    return SimpleNamespace(db=db, user=user, backend=backend)


@pytest.fixture
def run(local):
    args = SimpleNamespace(
        instructor='teacher@example.edu', remote_peer_id='remote-lab-01',
        recent_cleanup='ask', recent_hours=24, duration_hours=2,
        template='wireguard-factory-lab', count=1, expires_hours=2,
        student_email='student@example.edu', project=cli.TEST_PROJECT, wireguard_api_url=None)
    unit_id, workout_id = 'abcdefghij', 'klmnopqrst'
    snapshot = {
        'project': cli.TEST_PROJECT, 'unit_id': unit_id, 'state': UnitStates.READY.value,
        'state_name': 'READY', 'workouts': [{'workout_id': workout_id, 'state': WorkoutStates.READY.value}],
        'workout': {'workout_id': workout_id, 'state': WorkoutStates.READY.value},
    }
    events, cleanup_calls, prompts = [], [], []

    def create(settings, *, on_created=None):
        assert settings is args
        events.append(('build', unit_id))
        if on_created:
            on_created(unit_id)
        return snapshot

    def verify(identifier, stage):
        assert identifier == unit_id
        events.append(('verify', stage))
        return snapshot

    def action(scope, identifier, operation, duration=2):
        events.append((operation, scope, identifier, duration))
        return {'worker_returned': True}

    def cleanup(instructor, unit_ids, execute=False):
        assert instructor == args.instructor
        cleanup_calls.append((list(unit_ids), execute))
        events.append(('delete', *unit_ids))
        return {'project': cli.TEST_PROJECT, 'failed': 0, 'deleted': len(unit_ids),
                'items': [{'unit_id': identifier, 'deleted': True} for identifier in unit_ids]}

    local.backend.create_lab = Mock(side_effect=create)
    local.backend._verify_lab_stage = Mock(side_effect=verify)
    local.backend.action = Mock(side_effect=action)
    local.backend.delete_labs = Mock(side_effect=cleanup)
    local.backend.recent_labs = Mock(return_value={'items': [], 'total': 0, 'project': cli.TEST_PROJECT})
    local.backend.status = Mock(return_value=snapshot)
    return SimpleNamespace(**vars(local), args=args, snapshot=snapshot, events=events,
                           cleanup_calls=cleanup_calls, prompts=prompts,
                           unit_id=unit_id, workout_id=workout_id)


def replies(run, *answers):
    values = iter(answers)

    def read(prompt):
        run.prompts.append(prompt)
        value = next(values)
        if isinstance(value, BaseException):
            raise value
        return value

    return read


def recent_item(identifier='uvwxyzabcd'):
    return {'unit_id': identifier, 'name': 'Previous debug run', 'state': UnitStates.BROKEN.value,
            'state_name': 'BROKEN', 'creation_timestamp': 1000,
            'instructor_id': ['teacher@example.edu'], 'remote_peer_id': 'remote-lab-01'}


def test_run_executes_and_verifies_complete_lifecycle_with_workout_order(run):
    result = run.backend.run_lab(run.args, read_input=replies(run, '', '', 'yes'))

    assert result['outcome'] == 'deleted' and result['unit_id'] == run.unit_id
    assert result['completed_steps'] == ['build', 'start', 'stop', 'delete']
    assert result.get('exit_code', 0) == 0
    assert run.events == [
        ('build', run.unit_id), ('verify', 'build'),
        ('start', 'unit', run.unit_id, 2), ('start', 'workout', run.workout_id, 2), ('verify', 'start'),
        ('stop', 'workout', run.workout_id, 2), ('stop', 'unit', run.unit_id, 2), ('verify', 'stop'),
        ('delete', run.unit_id),
    ]
    assert run.cleanup_calls == [([run.unit_id], True)]
    assert len(run.prompts) == 3


def test_run_uses_requested_workout_duration(run):
    run.args.duration_hours = 4
    run.backend.run_lab(run.args, read_input=replies(run, 'y', 'n'))
    assert ('start', 'workout', run.workout_id, 4) in run.events


def test_run_without_student_workout_still_operates_unit_lifecycle(run):
    run.args.student_email = None
    run.snapshot['workouts'] = []
    run.snapshot.pop('workout')
    result = run.backend.run_lab(run.args, read_input=replies(run, 'y', 'y', 'y'))
    assert result['outcome'] == 'deleted'
    assert not any(len(event) > 1 and event[1] == 'workout' for event in run.events)


@pytest.mark.parametrize('answers,steps', [
    (['no'], ['build']), (['q'], ['build']),
    (['yes', 'quit'], ['build', 'start']),
    (['yes', 'yes', ''], ['build', 'start', 'stop']),
])
def test_declining_next_stage_keeps_lab_and_stops_remaining_sequence(run, answers, steps):
    result = run.backend.run_lab(run.args, read_input=replies(run, *answers))
    assert result['outcome'] == 'kept'
    assert result['unit_id'] == run.unit_id and result['completed_steps'] == steps
    run.backend.delete_labs.assert_not_called()


def test_invalid_prompt_answer_reprompts_before_mutation(run):
    result = run.backend.run_lab(run.args, read_input=replies(run, 'perhaps', 'NO'))
    assert result['outcome'] == 'kept' and len(run.prompts) == 2
    run.backend.action.assert_not_called()


def test_default_preflight_shows_and_can_delete_only_selected_recent_candidates(run, capsys):
    run.backend.recent_labs.return_value = {'items': [recent_item()], 'total': 1}
    result = run.backend.run_lab(run.args, read_input=replies(run, 'yes', 'no'))
    assert result['outcome'] == 'kept'
    assert run.cleanup_calls == [(['uvwxyzabcd'], True)]
    assert run.events[0] == ('delete', 'uvwxyzabcd')
    assert run.events[1] == ('build', run.unit_id)
    assert 'uvwxyzabcd' in capsys.readouterr().out


def test_declining_preflight_cleanup_proceeds_to_build_without_deleting(run):
    run.backend.recent_labs.return_value = {'items': [recent_item()], 'total': 1}
    result = run.backend.run_lab(run.args, read_input=replies(run, '', 'no'))
    assert result['outcome'] == 'kept'
    assert run.events[0] == ('build', run.unit_id)
    run.backend.delete_labs.assert_not_called()


def test_quitting_preflight_cancels_before_any_new_resources(run):
    run.backend.recent_labs.return_value = {'items': [recent_item()], 'total': 1}
    result = run.backend.run_lab(run.args, read_input=replies(run, 'q'))
    assert result['outcome'] == 'cancelled' and result.get('exit_code', 0) == 0
    run.backend.create_lab.assert_not_called()
    run.backend.delete_labs.assert_not_called()


def test_preflight_never_adds_newly_discovered_labs_to_approved_cleanup(run):
    run.backend.recent_labs.side_effect = [
        {'items': [recent_item()], 'total': 1},
        {'items': [recent_item(), recent_item('efghijklmn')], 'total': 2},
    ]
    result = run.backend.run_lab(run.args, read_input=replies(run, 'y', 'n'))
    assert result['outcome'] == 'kept'
    assert run.cleanup_calls == [(['uvwxyzabcd'], True)]


def test_delete_recent_automates_only_preflight_and_keeps_lifecycle_prompts(run):
    run.args.recent_cleanup = 'delete'
    run.backend.recent_labs.return_value = {'items': [recent_item()], 'total': 1}
    result = run.backend.run_lab(run.args, read_input=replies(run, 'n'))
    assert result['outcome'] == 'kept' and len(run.prompts) == 1
    assert run.cleanup_calls == [(['uvwxyzabcd'], True)]


def test_skip_cleanup_does_not_discover_or_delete_old_labs(run):
    run.args.recent_cleanup = 'skip'
    result = run.backend.run_lab(run.args, read_input=replies(run, 'n'))
    assert result['outcome'] == 'kept'
    run.backend.recent_labs.assert_not_called()
    run.backend.delete_labs.assert_not_called()


def test_failed_preflight_cleanup_prevents_new_build(run):
    run.args.recent_cleanup = 'delete'
    run.backend.recent_labs.return_value = {'items': [recent_item()], 'total': 1}
    run.backend.delete_labs.return_value = {'failed': 1, 'deleted': 0}
    run.backend.delete_labs.side_effect = None
    result = run.backend.run_lab(run.args, read_input=replies(run))
    assert result['outcome'] == 'failed' and result['exit_code'] == 1
    run.backend.create_lab.assert_not_called()
    run.backend.action.assert_not_called()


def test_failed_build_keeps_captured_unit_id_and_never_auto_deletes(run, capsys):
    def fail(settings, *, on_created=None):
        on_created(run.unit_id)
        raise TimeoutError('private-sdk-response')

    run.backend.create_lab.side_effect = fail
    result = run.backend.run_lab(run.args, read_input=replies(run))
    assert result['outcome'] == 'failed' and result['exit_code'] == 1
    assert result['unit_id'] == run.unit_id and result['error'] == 'TimeoutError'
    assert 'private-sdk-response' not in json.dumps(result)
    output = capsys.readouterr()
    assert run.unit_id in output.out
    assert 'private-sdk-response' not in output.out + output.err
    run.backend.delete_labs.assert_not_called()
    run.backend.action.assert_not_called()


def test_known_peer_diagnostic_remains_visible_when_new_build_is_blocked(run, capsys):
    run.backend.create_lab.side_effect = cli.DebugLabInputError(
        'Remote peer is already assigned to lab uvwxyzabcd. Delete that lab to release it.')
    result = run.backend.run_lab(run.args, read_input=replies(run))
    assert result['outcome'] == 'failed' and result['exit_code'] == 1
    assert 'uvwxyzabcd' in result['detail']
    assert 'Delete that lab' in capsys.readouterr().out
    run.backend.delete_labs.assert_not_called()


def test_verification_failure_does_not_advance_to_next_phase_or_auto_delete(run):
    run.backend._verify_lab_stage.side_effect = RuntimeError('unconfirmed server state')
    result = run.backend.run_lab(run.args, read_input=replies(run))
    assert result['outcome'] == 'failed' and result['exit_code'] == 1
    run.backend.action.assert_not_called()
    run.backend.delete_labs.assert_not_called()


def test_failed_workout_stop_prevents_unit_stop_and_final_deletion(run):
    action = run.backend.action.side_effect

    def fail(scope, identifier, operation, duration=2):
        action(scope, identifier, operation, duration)
        if operation == 'stop':
            raise RuntimeError('private-stop-response')

    run.backend.action.side_effect = fail
    result = run.backend.run_lab(run.args, read_input=replies(run, 'y', 'y'))

    assert result['outcome'] == 'failed' and result['exit_code'] == 1
    assert result['failed_step'] == 'stop'
    assert result['completed_steps'] == ['build', 'start']
    assert run.events[-1] == ('stop', 'workout', run.workout_id, 2)
    assert not any(event[:2] == ('stop', 'unit') for event in run.events)
    run.backend.delete_labs.assert_not_called()
    assert 'private-stop-response' not in json.dumps(result)


def test_unconfirmed_final_deletion_is_failure(run):
    run.backend.delete_labs.side_effect = None
    run.backend.delete_labs.return_value = {'failed': 1, 'deleted': 0}
    result = run.backend.run_lab(run.args, read_input=replies(run, 'y', 'y', 'y'))
    assert result['outcome'] == 'failed' and result['exit_code'] == 1
    assert 'delete' not in result['completed_steps']


@pytest.mark.parametrize('error,code', [(EOFError(), 1), (KeyboardInterrupt(), 130)])
def test_interrupted_stage_keeps_known_lab_and_reports_resumable_id(run, capsys, error, code):
    result = run.backend.run_lab(run.args, read_input=replies(run, error))
    assert result['outcome'] == 'cancelled' and result['exit_code'] == code
    assert result['unit_id'] == run.unit_id
    assert run.unit_id in capsys.readouterr().out
    run.backend.action.assert_not_called()
    run.backend.delete_labs.assert_not_called()


def test_eof_during_preflight_does_not_build_or_delete(run):
    run.backend.recent_labs.return_value = {'items': [recent_item()], 'total': 1}
    result = run.backend.run_lab(run.args, read_input=replies(run, EOFError()))
    assert result['outcome'] == 'cancelled' and result['exit_code'] == 1
    run.backend.create_lab.assert_not_called()
    run.backend.delete_labs.assert_not_called()


class FrozenDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        return datetime(2026, 10, 23, 12, tzinfo=timezone.utc)


def add_candidate(local, unit_id, *, timestamp, owner='teacher@example.edu', peer='remote-lab-01',
                  state=UnitStates.BROKEN.value, test=True, lease_status='reserved'):
    local.db.collections[DbCollections.UNIT][unit_id] = {
        'id': unit_id, 'test': test, 'instructor_id': owner, 'state': state,
        'creation_timestamp': timestamp, 'summary': {'name': 'Debug'},
        'wireguard_lease': {'kit_id': peer},
    }
    local.db.collections[DbCollections.WIREGUARD_LEASE][unit_id] = {
        'kit_id': peer, 'status': lease_status}


def test_recent_scope_excludes_other_owners_peers_old_future_and_completed_labs(local, monkeypatch):
    monkeypatch.setattr(cli, 'datetime', FrozenDateTime)
    now = FrozenDateTime.now().timestamp()
    local.user.is_admin = True
    add_candidate(local, 'abcdefghij', timestamp=now - 3600, owner=['Teacher@Example.edu'])
    add_candidate(local, 'klmnopqrst', timestamp=now - 24 * 3600)
    add_candidate(local, 'uvwxyzabcd', timestamp=now - 24 * 3600 - 1)
    add_candidate(local, 'efghijklmn', timestamp=now + 1)
    add_candidate(local, 'opqrstuvwx', timestamp=now - 100, owner='other@example.edu')
    add_candidate(local, 'yzabcdefgh', timestamp=now - 100, peer='other-peer')
    add_candidate(local, 'ijklmnopqr', timestamp=now - 100, test=False)
    add_candidate(local, 'stuvwxyzab', timestamp=now - 100, state=UnitStates.DELETED.value, lease_status='released')
    add_candidate(local, 'cdefghijkl', timestamp=now - 100, state=UnitStates.DELETED.value)

    result = local.backend.recent_labs('teacher@example.edu', 'remote-lab-01', hours=24)

    assert {item['unit_id'] for item in result['items']} == {'abcdefghij', 'klmnopqrst', 'cdefghijkl'}
    assert result['total'] == 3 and result['project'] == cli.TEST_PROJECT
    local.backend.worker.assert_not_called()


@pytest.mark.parametrize('timestamp', [None, True, False, '1234', float('nan'), float('inf'), -float('inf')])
def test_recent_scope_never_auto_selects_unknown_or_invalid_creation_time(local, monkeypatch, timestamp):
    monkeypatch.setattr(cli, 'datetime', FrozenDateTime)
    add_candidate(local, 'abcdefghij', timestamp=timestamp)
    add_candidate(local, 'klmnopqrst', timestamp=FrozenDateTime.now().timestamp() - 100)
    result = local.backend.recent_labs('teacher@example.edu', 'remote-lab-01')
    assert [item['unit_id'] for item in result['items']] == ['klmnopqrst']


def test_run_parser_reuses_profile_and_cli_overrides(tmp_path):
    profile = tmp_path / 'profile.json'
    profile.write_text(json.dumps({'instructor': 'Teacher@Example.edu', 'remote_peer_id': 'remote-lab-01',
                                   'count': 3, 'student_email': 'student@example.edu'}))
    args = cli.parser().parse_args(['run-lab', '--profile', str(profile), '--count', '2'])
    assert args.command == 'run-lab' and args.instructor == 'teacher@example.edu'
    assert args.remote_peer_id == 'remote-lab-01' and args.count == 2
    assert args.student_email == 'student@example.edu'
    assert args.recent_cleanup == 'ask' and args.recent_hours == 24 and args.duration_hours == 2


@pytest.mark.parametrize('switch,mode', [('--delete-recent', 'delete'), ('--skip-cleanup', 'skip')])
def test_run_parser_cleanup_switches_and_window(switch, mode):
    args = cli.parser().parse_args(['run-lab', '--instructor', 'teacher@example.edu',
                                   '--remote-peer-id', 'remote-lab-01', switch,
                                   '--recent-hours', '3', '--duration-hours', '4'])
    assert args.recent_cleanup == mode and args.recent_hours == 3 and args.duration_hours == 4


@pytest.mark.parametrize('flags', [
    ['--delete-recent', '--skip-cleanup'], ['--recent-hours', '0'],
    ['--recent-hours', 'nan'], ['--recent-hours', '169'], ['--duration-hours', '0'],
])
def test_run_parser_rejects_conflicting_or_invalid_controls(flags):
    with pytest.raises(SystemExit):
        cli.parser().parse_args(['run-lab', '--instructor', 'teacher@example.edu',
                                '--remote-peer-id', 'remote-lab-01', *flags])


@pytest.mark.parametrize('exit_code', [0, 1, 130])
def test_main_dispatches_run_lab_and_preserves_workflow_exit_code(monkeypatch, exit_code):
    backend = Mock()
    backend.run_lab.return_value = {'project': cli.TEST_PROJECT, 'exit_code': exit_code,
                                    'outcome': 'deleted' if exit_code == 0 else 'failed'}
    monkeypatch.setattr(cli, 'load_backend', Mock(return_value=backend))
    assert cli.main(['run-lab', '--instructor', 'teacher@example.edu',
                     '--remote-peer-id', 'remote-lab-01', '--skip-cleanup']) == exit_code
    args = backend.run_lab.call_args.args[0]
    assert args.command == 'run-lab' and args.recent_cleanup == 'skip'
