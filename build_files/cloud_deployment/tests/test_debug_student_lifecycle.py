"""Two student joins exercise the real debug sequence, never manual Unit controls."""
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from tools.debug_lab import cli
from common.constants.database import DbCollections
from common.constants.states import ServerStates, UnitStates, WorkoutStates


class Database:
    def __init__(self):
        self.collections = {name: {} for name in DbCollections}

    def get(self, collection_name, doc_id):
        return self.collections[collection_name].get(doc_id, {})

    def query(self, collection_name, filters=None):
        return [record for record in self.collections[collection_name].values()
                if all(record.get(field) == value for field, _, value in filters or [])]


@pytest.fixture
def flow():
    db, events = Database(), []
    unit_id, gateway_name = 'abcdefghij', 'abcdefghij-wireguard'
    cloud = SimpleNamespace(status='TERMINATED', student_states={})
    def read_status(name):
        return cloud.student_states.get(name, cloud.status)
    backend = cli.LocalBackend({'project': cli.TEST_PROJECT}, db, Mock(), Mock(), Mock(),
                               gateway_status_reader=read_status)
    unit = {'id': unit_id, 'state': UnitStates.READY.value,
            'servers': [{'name': 'wireguard', 'community_server': True, 'wireguard_gateway': True},
                        {'name': 'display-guacamole-server', 'community_server': True, 'community_proxy': True},
                        {'name': 'student', 'community_server': False}],
            'wireguard_lease': {'remote_peer_id': 'remote-lab-01'}}
    gateway = {'name': 'wireguard', 'parent_id': unit_id, 'state': ServerStates.STOPPED.value}
    db.collections[DbCollections.UNIT][unit_id] = unit
    db.collections[DbCollections.SERVER][gateway_name] = gateway
    proxy = {'name': 'display-guacamole-server', 'parent_id': unit_id, 'state': ServerStates.STOPPED.value}
    db.collections[DbCollections.SERVER][f'{unit_id}-display-guacamole-server'] = proxy
    students = iter(['klmnopqrst', 'uvwxyzabcd'])

    def build(args, *, on_created):
        assert args.student_email is None and args.count >= 2
        events.append(('build', unit_id))
        on_created(unit_id)
        return backend.status(unit_id)

    def join(identifier, email):
        assert identifier == unit_id
        workout_id = next(students)
        db.collections[DbCollections.WORKOUT][workout_id] = {
            'id': workout_id, 'parent_id': unit_id, 'student_email': email, 'state': WorkoutStates.READY.value}
        for name in ('student',):
            db.collections[DbCollections.SERVER][f'{workout_id}-{name}'] = {
                'name': name, 'parent_id': workout_id, 'state': ServerStates.STOPPED.value}
            cloud.student_states[f'{workout_id}-{name}'] = 'TERMINATED'
        events.append(('join', workout_id))
        return {'workout_id': workout_id, 'exists': False, 'state': WorkoutStates.READY.value}

    def action(scope, identifier, operation, duration):
        assert scope == 'workout', 'Unit controls would mask the automatic behavior under test'
        events.append((operation, identifier))
        record = db.collections[DbCollections.WORKOUT][identifier]
        record['state'] = WorkoutStates.RUNNING.value if operation == 'start' else WorkoutStates.READY.value
        for server in db.collections[DbCollections.SERVER].values():
            if server.get('parent_id') == identifier:
                server['state'] = ServerStates.RUNNING.value if operation == 'start' else ServerStates.STOPPED.value
                cloud.student_states[f'{identifier}-{server["name"]}'] = 'RUNNING' if operation == 'start' else 'TERMINATED'
        active = any(item['state'] == WorkoutStates.RUNNING.value
                     for item in db.collections[DbCollections.WORKOUT].values())
        gateway['state'] = ServerStates.RUNNING.value if active else ServerStates.STOPPED.value
        proxy['state'] = gateway['state']
        cloud.status = 'RUNNING' if active else 'TERMINATED'

    backend.create_lab = Mock(side_effect=build)
    backend.create_workout = Mock(side_effect=join)
    backend.action = Mock(side_effect=action)
    backend.delete_labs = Mock(return_value={'failed': 0, 'deleted': 1})
    args = cli.parser().parse_args([
        'student-lifecycle', '--instructor', 'teacher@example.edu', '--remote-peer-id', 'remote-lab-01',
        '--student-email', 'one@example.edu', '--student-email', 'two@example.edu', '--skip-cleanup'])
    return SimpleNamespace(backend=backend, args=args, db=db, events=events, unit=unit,
                           gateway=gateway, proxy=proxy, cloud=cloud, unit_id=unit_id, read_status=read_status)


def test_full_sequence_joins_two_students_and_checks_real_gateway_status_after_every_boundary(flow):
    checks = []
    flow.backend.gateway_status_reader = lambda name: checks.append((name, flow.read_status(name))) or flow.read_status(name)

    result = flow.backend.run_lab(flow.args, read_input=lambda _: 'yes')

    assert result['outcome'] == 'deleted' and result['exit_code'] == 0
    assert result['completed_steps'] == [
        'build', 'join_student_1', 'join_student_2', 'start_student_1', 'start_student_2',
        'stop_student_1', 'stop_student_2', 'delete']
    shared_checks = [item for item in checks if item[0].startswith(flow.unit_id)]
    assert [item[1] for item in shared_checks] == [status for status in
        ('TERMINATED', 'TERMINATED', 'TERMINATED', 'RUNNING', 'RUNNING', 'RUNNING', 'TERMINATED')
        for _ in range(2)]
    assert {item[0] for item in shared_checks} == {'abcdefghij-wireguard', 'abcdefghij-display-guacamole-server'}
    assert [status for name, status in checks if name == 'klmnopqrst-student'] == [
        'TERMINATED', 'TERMINATED', 'RUNNING', 'RUNNING', 'TERMINATED', 'TERMINATED']
    assert [status for name, status in checks if name == 'uvwxyzabcd-student'] == [
        'TERMINATED', 'TERMINATED', 'RUNNING', 'RUNNING', 'TERMINATED']
    assert flow.events == [('build', flow.unit_id), ('join', 'klmnopqrst'), ('join', 'uvwxyzabcd'),
                           ('start', 'klmnopqrst'), ('start', 'uvwxyzabcd'),
                           ('stop', 'klmnopqrst'), ('stop', 'uvwxyzabcd')]
    flow.backend.delete_labs.assert_called_once_with(flow.args.instructor, [flow.unit_id], execute=True)
    assert [item['workout_id'] for item in result['students']] == ['klmnopqrst', 'uvwxyzabcd']


def test_running_vm_cannot_be_hidden_by_a_stopped_gateway_database_record(flow):
    flow.cloud.status = 'RUNNING'

    result = flow.backend.run_lab(flow.args, read_input=lambda _: 'yes')

    assert result['outcome'] == 'failed' and result['exit_code'] == 1
    assert 'GCP reports' in result['detail']
    flow.backend.create_workout.assert_not_called()
    flow.backend.action.assert_not_called()
    flow.backend.delete_labs.assert_not_called()


@pytest.mark.parametrize('resource', ['student', 'extra-student'])
def test_join_checks_student_vms_are_stopped_and_retains_ids_on_failure(flow, resource):
    join = flow.backend.create_workout.side_effect

    def leaves_vm_running(unit_id, email):
        result = join(unit_id, email)
        flow.db.collections[DbCollections.SERVER][f'{result["workout_id"]}-{resource}'] = {
            'name': resource, 'parent_id': result['workout_id'], 'state': ServerStates.RUNNING.value}
        return result

    flow.backend.create_workout.side_effect = leaves_vm_running
    result = flow.backend.run_lab(flow.args, read_input=lambda _: 'yes')

    assert result['outcome'] == 'failed' and result['exit_code'] == 1
    assert 'Student server' in result['detail']
    assert result['students'][0]['workout_id'] == 'klmnopqrst'
    flow.backend.action.assert_not_called()
    flow.backend.delete_labs.assert_not_called()


def test_shared_proxy_must_follow_gateway_in_actual_gcp_state(flow):
    flow.backend.gateway_status_reader = lambda name: 'RUNNING' if name.endswith('display-guacamole-server') else 'TERMINATED'

    result = flow.backend.run_lab(flow.args, read_input=lambda _: 'yes')

    assert result['outcome'] == 'failed'
    assert 'Guacamole proxy' in result['detail']
    flow.backend.create_workout.assert_not_called()


def test_student_gcp_state_cannot_be_hidden_by_a_stopped_database_record(flow):
    join = flow.backend.create_workout.side_effect

    def leaves_vm_running(unit_id, email):
        result = join(unit_id, email)
        flow.cloud.student_states[f'{result["workout_id"]}-student'] = 'RUNNING'
        return result

    flow.backend.create_workout.side_effect = leaves_vm_running
    result = flow.backend.run_lab(flow.args, read_input=lambda _: 'yes')

    assert result['outcome'] == 'failed'
    assert 'GCP reports student server' in result['detail']
    flow.backend.action.assert_not_called()
    flow.backend.delete_labs.assert_not_called()


def test_per_student_proxy_is_rejected_in_a_shared_community_run(flow):
    join = flow.backend.create_workout.side_effect

    def old_proxy(unit_id, email):
        result = join(unit_id, email)
        flow.db.collections[DbCollections.SERVER][f'{result["workout_id"]}-display-guacamole-server'] = {
            'name': 'display-guacamole-server', 'parent_id': result['workout_id'], 'state': ServerStates.STOPPED.value}
        return result

    flow.backend.create_workout.side_effect = old_proxy
    result = flow.backend.run_lab(flow.args, read_input=lambda _: 'yes')

    assert result['outcome'] == 'failed'
    assert 'not its own proxy VM' in result['detail']
    flow.backend.action.assert_not_called()


def test_first_student_stop_must_keep_gateway_running_until_second_stops(flow):
    reader = lambda name: ('TERMINATED' if name.startswith(flow.unit_id) and flow.events[-1] == ('stop', 'klmnopqrst')
                           else flow.read_status(name))
    flow.backend.gateway_status_reader = reader

    result = flow.backend.run_lab(flow.args, read_input=lambda _: 'yes')

    assert result['outcome'] == 'failed' and result['exit_code'] == 1
    assert result['completed_steps'][-1] == 'start_student_2'
    assert ('stop', 'uvwxyzabcd') not in flow.events
    flow.backend.delete_labs.assert_not_called()


def test_declining_second_join_retains_first_student_and_lab_for_inspection(flow):
    answers = iter(['yes', 'no'])

    result = flow.backend.run_lab(flow.args, read_input=lambda _: next(answers))

    assert result['outcome'] == 'kept' and result['completed_steps'] == ['build', 'join_student_1']
    assert result['students'][0]['workout_id'] == 'klmnopqrst'
    flow.backend.action.assert_not_called()
    flow.backend.delete_labs.assert_not_called()


def test_profile_supplies_two_students_and_cli_can_replace_them(tmp_path):
    profile = tmp_path / 'students.json'
    profile.write_text(json.dumps({'instructor': 'teacher@example.edu', 'remote_peer_id': 'remote-lab-01',
                                   'student_emails': ['ONE@Example.edu', 'two@example.edu']}))
    args = cli.parser().parse_args(['student-lifecycle', '--profile', str(profile)])
    assert args.count == 2 and args.student_email is None
    assert args.student_emails == ['one@example.edu', 'two@example.edu']
    args = cli.parser().parse_args(['student-lifecycle', '--profile', str(profile),
                                   '--student-email', 'three@example.edu', '--student-email', 'four@example.edu'])
    assert args.student_emails == ['three@example.edu', 'four@example.edu']


@pytest.mark.parametrize('students,count', [
    ([], 2), (['one@example.edu'], 2), (['one@example.edu'] * 2, 2),
    (['one@example.edu', 'ONE@example.edu'], 2),
    (['one@example.edu', 'two@example.edu', 'three@example.edu'], 3),
    (['one@example.edu', 'two@example.edu'], 1),
])
def test_invalid_student_lifecycle_is_rejected_before_loading_cloud(monkeypatch, students, count):
    load = Mock()
    monkeypatch.setattr(cli, 'load_backend', load)
    arguments = ['student-lifecycle', '--instructor', 'teacher@example.edu', '--remote-peer-id', 'remote-lab-01',
                 '--count', str(count)]
    for email in students:
        arguments.extend(['--student-email', email])
    with pytest.raises(SystemExit) as error:
        cli.main(arguments)
    assert error.value.code == 2
    load.assert_not_called()
