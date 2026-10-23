"""Local debug dispatch with real API decisions and no live GCP calls."""
import importlib
import hashlib
import json
import os
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import debug_lab as cli
from common.constants.database import DbCollections
from common.constants.pub_sub import PubSub
from common.constants.states import UnitStates, WorkoutStates
from common.exceptions import BadRequest, Conflict, Unauthorized
from common.tests.test_wireguard_endpoint_registry import _FakeDatabase
from common.tests.test_wireguard_provisioning import kit_data
from core.workout import Workout


class Database(_FakeDatabase):
    def __init__(self):
        super().__init__()
        self.collections.update({name: {} for name in DbCollections})

    def get(self, collection_name, doc_id):
        return self.collections[collection_name].get(doc_id, {})

    def query(self, collection_name, filters=None):
        return [record for record in self.collections[collection_name].values()
                if all(record.get(field) == value for field, _, value in filters or [])]


@pytest.fixture
def local():
    db = Database()
    env = {'project': cli.TEST_PROJECT, 'region': 'us-central1', 'zone': 'us-central1-a'}
    unit_class, users_class, worker = Mock(), Mock(), Mock()
    users_class.return_value.get_user.return_value = SimpleNamespace(
        is_authorized=True, is_admin=False, email='teacher@example.edu')
    db.collections[DbCollections.WIREGUARD_KIT]['kit-one'] = {
        **kit_data(), 'enabled': True, 'assigned_unit_id': None, 'token_digest': 'private-stored-digest'}
    api = object.__new__(Workout)
    api.collection = DbCollections.WORKOUT
    api.db, api.env, api.env_dict = db, SimpleNamespace(max_workspaces=10), env
    api.pubsub_keys, api.logger, api.pubsub_manager = PubSub.EventAttributes, Mock(), Mock()

    def workout_class(*, env_dict, debug_dispatch):
        api.debug_dispatch = debug_dispatch
        return api

    backend = cli.LocalBackend(env, db, unit_class, workout_class, users_class, worker)
    return SimpleNamespace(backend=backend, db=db, env=env, unit_class=unit_class,
                           users_class=users_class, worker=worker, api=api)


def ready_lab(local):
    unit_id = 'abcdefghij'
    local.db.collections[DbCollections.UNIT][unit_id] = {
        'id': unit_id, 'state': UnitStates.READY.value, 'join_code': '123456',
        'workspace_settings': {'count': 2}, 'wireguard_endpoint': {'id': '10000', 'hostname': 'old.example.edu', 'port': 51820}}
    local.db.collections[DbCollections.WIREGUARD_ENDPOINT]['10000'] = {
        'id': '10000', 'unit_id': unit_id, 'hostname': 'wg.example.edu', 'port': 51820}
    return unit_id


def test_create_lab_commits_through_api_then_dispatches_local_worker(local):
    args = cli.parser().parse_args(['create-lab', '--instructor', 'Teacher@Example.edu', '--kit-id', 'kit-one'])
    unit_id = ready_lab(local)
    local.unit_class.return_value.build.return_value = unit_id
    result = local.backend.create_lab(args)
    local.unit_class.assert_called_once_with(env_dict=local.env, debug=True)
    data = local.unit_class.return_value.build.call_args.kwargs['data']
    assert data['build_file'] == 'wireguard-factory-lab' and data['remote_peer_id'] == 'kit-one'
    assert data['test'] and data['build_count'] == 1 and not data['lms_integration']
    local.users_class.return_value.get_user.assert_called_once_with(user_email='teacher@example.edu')
    attrs, env = local.worker.call_args.args
    assert env is local.env and attrs['course_object'] == str(PubSub.CourseObjects.UNIT.value)
    assert attrs['build_id'] == unit_id and result['state_name'] == 'READY'
    assert result['connection_id'] == f'{cli.TEST_PROJECT}:{unit_id}'
    assert result['endpoint']['hostname'] == 'wg.example.edu'


def test_remote_peer_cli_name_preserves_legacy_flag_alias():
    for flag in ('--remote-peer-id', '--kit-id'):
        args = cli.parser().parse_args(['create-lab', '--instructor', 'teacher@example.edu', flag, 'remote-lab-01'])
        assert args.remote_peer_id == 'remote-lab-01'


def write_json(tmp_path, value, name='debug.local.json'):
    target = tmp_path / name
    target.write_text(json.dumps(value), encoding='utf-8')
    return target


def profile_data(**changes):
    return {'template': 'wireguard-factory-lab', 'instructor': 'Teacher@Example.edu',
            'remote_peer_id': 'kit-one', 'count': 3, 'expires_hours': 1.5,
            'student_email': 'Student@Example.edu', **changes}


def peer_spec(**changes):
    data = kit_data('remote-lab-02', subnet='192.168.50.0/24', key_number=2)
    data['remote_network_cidr'] = data.pop('equipment_subnet')
    return {**data, **changes}


def test_profile_supplies_normalized_lab_settings_without_cloud_access(tmp_path):
    profile = write_json(tmp_path, profile_data(
        project=cli.TEST_PROJECT, wireguard_api_url='https://debug.example.edu/'))
    args = cli.parser().parse_args(['create-lab', '--profile', str(profile)])
    assert args.project == cli.TEST_PROJECT
    assert args.template == 'wireguard-factory-lab'
    assert args.instructor == 'teacher@example.edu'
    assert args.remote_peer_id == 'kit-one'
    assert args.count == 3 and args.expires_hours == 1.5
    assert args.student_email == 'student@example.edu'
    assert args.wireguard_api_url == 'https://debug.example.edu'


@pytest.mark.parametrize('peer_flag', ['--remote-peer-id', '--kit-id'])
def test_explicit_flags_override_profile_including_legacy_peer_alias(tmp_path, peer_flag):
    profile = write_json(tmp_path, profile_data(project='not-the-test-project'))
    args = cli.parser().parse_args([
        '--project', cli.TEST_PROJECT, '--wireguard-api-url', 'https://override.example.edu',
        'create-lab', '--profile', str(profile), '--instructor', 'Override@Example.edu',
        peer_flag, 'another-peer', '--count', '1', '--expires-hours', '2',
        '--student-email', 'Another@Example.edu', '--template', 'another-template'])
    assert args.instructor == 'override@example.edu'
    assert args.remote_peer_id == 'another-peer' and args.template == 'another-template'
    assert args.count == 1 and args.expires_hours == 2
    assert args.student_email == 'another@example.edu'
    assert args.wireguard_api_url == 'https://override.example.edu'
    assert args.project == cli.TEST_PROJECT


def test_minimal_profile_keeps_existing_cli_defaults(tmp_path):
    profile = write_json(tmp_path, {'instructor': 'teacher@example.edu', 'remote_peer_id': 'kit-one'})
    args = cli.parser().parse_args(['create-lab', '--profile', str(profile)])
    assert args.template == 'wireguard-factory-lab'
    assert args.count == 1 and args.expires_hours == 2
    assert args.student_email is None and args.wireguard_api_url is None
    assert args.project == cli.TEST_PROJECT


def test_profile_accepts_utf8_bom_from_windows_editors(tmp_path):
    profile = tmp_path / 'windows-profile.json'
    profile.write_text(json.dumps(profile_data()), encoding='utf-8-sig')
    args = cli.parser().parse_args(['create-lab', '--profile', str(profile)])
    assert args.remote_peer_id == 'kit-one' and args.count == 3


@pytest.mark.parametrize('change', [
    {'kit_id': 'kit-one'}, {'private_key': 'private-profile-secret'},
    {'count': True}, {'count': '2'}, {'count': 0}, {'count': 101},
    {'expires_hours': False}, {'expires_hours': 0}, {'expires_hours': 169},
    {'expires_hours': '2'}, {'expires_hours': float('nan')},
    {'instructor': ['teacher@example.edu']}, {'instructor': 'bad-email'},
    {'remote_peer_id': '../another'}, {'remote_peer_id': None},
    {'student_email': 'bad-email'}, {'template': ['wireguard-factory-lab']},
    {'project': 'agoge-ualr'}, {'wireguard_api_url': 'http://localhost'},
    {'wireguard_api_url': 'https://user:private-profile-secret@example.edu'},
])
def test_invalid_profiles_fail_before_cloud_access(monkeypatch, tmp_path, capsys, change):
    profile = write_json(tmp_path, profile_data(**change))
    load = Mock()
    monkeypatch.setattr(cli, 'load_backend', load)
    with pytest.raises(SystemExit) as error:
        cli.main(['create-lab', '--profile', str(profile)])
    assert error.value.code == 2
    load.assert_not_called()
    assert 'private-profile-secret' not in capsys.readouterr().err


@pytest.mark.parametrize('contents', [
    '[]', 'null', '{"instructor":"private-file-secret",',
    '{"instructor":"teacher@example.edu"}',
    '{"remote_peer_id":"kit-one"}',
    '{"instructor":"teacher@example.edu","remote_peer_id":"kit-one","count":1,"count":2}',
])
def test_malformed_or_incomplete_profiles_fail_before_cloud_access(monkeypatch, tmp_path, capsys, contents):
    profile = tmp_path / 'bad-profile.json'
    profile.write_text(contents, encoding='utf-8')
    load = Mock()
    monkeypatch.setattr(cli, 'load_backend', load)
    with pytest.raises(SystemExit) as error:
        cli.main(['create-lab', '--profile', str(profile)])
    assert error.value.code == 2
    load.assert_not_called()
    assert 'private-file-secret' not in capsys.readouterr().err


def test_missing_profile_file_fails_before_cloud_access(monkeypatch, tmp_path):
    load = Mock()
    monkeypatch.setattr(cli, 'load_backend', load)
    with pytest.raises(SystemExit) as error:
        cli.main(['create-lab', '--profile', str(tmp_path / 'missing.json')])
    assert error.value.code == 2
    load.assert_not_called()


def test_profile_is_resolved_before_backend_changes_working_directory(monkeypatch, tmp_path):
    profile = write_json(tmp_path, profile_data())
    other = tmp_path / 'backend-working-directory'
    other.mkdir()
    monkeypatch.chdir(tmp_path)
    backend = Mock()
    backend.create_lab.return_value = {'unit_id': 'abcdefghij'}
    def load(project, wireguard_api_url=None):
        monkeypatch.chdir(other)
        return backend
    monkeypatch.setattr(cli, 'load_backend', load)
    assert cli.main(['create-lab', '--profile', profile.name]) == 0
    args = backend.create_lab.call_args.args[0]
    assert args.profile == profile.resolve()
    assert args.remote_peer_id == 'kit-one' and args.count == 3


@pytest.mark.parametrize('change', [None, {'enabled': False},
    {'authorized_instructors': ['other@example.edu']}, {'assigned_unit_id': 'anotherlab'}])
def test_peer_preflight_fails_before_unit_creation_or_worker_dispatch(local, change):
    if change is None:
        local.db.collections[DbCollections.WIREGUARD_KIT].pop('kit-one')
    else:
        local.db.collections[DbCollections.WIREGUARD_KIT]['kit-one'].update(change)
    args = cli.parser().parse_args(['create-lab', '--instructor', 'teacher@example.edu',
                                   '--remote-peer-id', 'kit-one'])
    with pytest.raises((ValueError, Unauthorized)):
        local.backend.create_lab(args)
    local.unit_class.assert_not_called()
    local.worker.assert_not_called()


def test_peer_list_filters_instructors_and_never_returns_credentials(local):
    records = local.db.collections[DbCollections.WIREGUARD_KIT]
    records['disabled-peer'] = {**kit_data('disabled-peer', key_number=2),
                                'enabled': False, 'assigned_unit_id': None, 'token_digest': 'private-list-secret'}
    records['assigned-peer'] = {**kit_data('assigned-peer', key_number=3),
                                'enabled': True, 'assigned_unit_id': 'abcdefghij'}
    records['someone-elses-peer'] = {**kit_data('someone-elses-peer', key_number=4),
        'enabled': True, 'assigned_unit_id': None, 'authorized_instructors': ['other@example.edu']}
    result = local.backend.list_peers('teacher@example.edu')
    assert result['project'] == cli.TEST_PROJECT and result['total'] == 3
    items = {item['id']: item for item in result['items']}
    assert items['kit-one']['available'] is True
    assert items['disabled-peer']['available'] is False
    assert items['assigned-peer']['available'] is False
    assert items['kit-one']['remote_network_cidr'] == '172.30.0.0/24'
    assert 'equipment_subnet' not in items['kit-one']
    output = json.dumps(result)
    assert 'token_digest' not in output and 'private-list-secret' not in output
    assert 'private-stored-digest' not in output and 'someone-elses-peer' not in output
    local.unit_class.assert_not_called()
    local.worker.assert_not_called()


def test_peer_list_uses_actual_agoge_account_authorization(local):
    local.users_class.return_value.get_user.return_value.is_authorized = False
    with pytest.raises((ValueError, Unauthorized)):
        local.backend.list_peers('student@example.edu')
    local.worker.assert_not_called()


def test_list_peers_command_dispatches_normalized_instructor_and_prints_safe_json(monkeypatch, capsys):
    backend = Mock()
    backend.list_peers.return_value = {'project': cli.TEST_PROJECT, 'items': [], 'total': 0}
    load = Mock(return_value=backend)
    monkeypatch.setattr(cli, 'load_backend', load)
    assert cli.main(['list-peers', '--instructor', 'Teacher@Example.edu']) == 0
    backend.list_peers.assert_called_once_with('teacher@example.edu')
    assert json.loads(capsys.readouterr().out)['total'] == 0
    backend.create_lab.assert_not_called()
    backend.enroll_peer.assert_not_called()


def test_expected_peer_failure_returns_actionable_error_without_traceback(monkeypatch, capsys):
    backend = Mock()
    backend.create_lab.side_effect = ValueError('Register the missing peer with enroll-peer')
    monkeypatch.setattr(cli, 'load_backend', Mock(return_value=backend))
    assert cli.main(['create-lab', '--instructor', 'teacher@example.edu', '--remote-peer-id', 'kit-one']) == 1
    captured = capsys.readouterr()
    assert 'enroll-peer' in captured.err and 'Traceback' not in captured.err
    assert captured.out == ''


def test_enrollment_spec_and_token_path_are_parsed_before_backend_changes_directory(monkeypatch, tmp_path):
    spec = write_json(tmp_path, peer_spec(), name='peer.json')
    other = tmp_path / 'backend-working-directory'
    other.mkdir()
    monkeypatch.chdir(tmp_path)
    backend = Mock()
    backend.enroll_peer.return_value = {'remote_peer': {'id': 'remote-lab-02'}}
    def load(project, wireguard_api_url=None):
        monkeypatch.chdir(other)
        return backend
    monkeypatch.setattr(cli, 'load_backend', load)
    assert cli.main(['enroll-peer', '--admin', 'Admin@Example.edu', '--spec', spec.name,
                     '--token-out', 'remote-lab-02.token']) == 0
    admin, parsed_spec, token_path = backend.enroll_peer.call_args.args
    assert admin == 'admin@example.edu'
    assert parsed_spec == peer_spec()
    assert token_path == tmp_path / 'remote-lab-02.token'


@pytest.mark.parametrize('change', [
    {'remote_network_cidr': '8.8.8.0/24'}, {'remote_network_cidr': '192.168.50.1/24'},
    {'remote_network_cidr': 'private-enrollment-secret'},
    {'peer_public_key': 'private-invalid-key'}, {'private_key': 'private-enrollment-secret'},
    {'authorized_instructors': []}, {'id': '../another'}, {'device_id': ''},
])
def test_invalid_enrollment_spec_fails_before_cloud_access(monkeypatch, tmp_path, capsys, change):
    spec = write_json(tmp_path, peer_spec(**change), name='peer.json')
    load = Mock()
    monkeypatch.setattr(cli, 'load_backend', load)
    with pytest.raises(SystemExit) as error:
        cli.main(['enroll-peer', '--admin', 'admin@example.edu', '--spec', str(spec),
                  '--token-out', str(tmp_path / 'peer.token')])
    assert error.value.code == 2
    load.assert_not_called()
    output = capsys.readouterr().err
    assert 'private-invalid-key' not in output and 'private-enrollment-secret' not in output


def test_enrollment_requires_explicit_token_output_before_cloud_access(monkeypatch, tmp_path):
    spec = write_json(tmp_path, peer_spec(), name='peer.json')
    load = Mock()
    monkeypatch.setattr(cli, 'load_backend', load)
    with pytest.raises(SystemExit) as error:
        cli.main(['enroll-peer', '--admin', 'admin@example.edu', '--spec', str(spec)])
    assert error.value.code == 2
    load.assert_not_called()


def test_enrollment_reuses_transactional_service_and_writes_only_token_to_protected_file(local, tmp_path, capsys):
    local.users_class.return_value.get_user.return_value.is_admin = True
    token_path = tmp_path / 'remote-lab-02.token'
    result = local.backend.enroll_peer('admin@example.edu', peer_spec(), token_path)
    token = token_path.read_text(encoding='utf-8').strip()
    assert token
    stored = local.db.collections[DbCollections.WIREGUARD_KIT]['remote-lab-02']
    assert stored['token_digest'] == hashlib.sha256(token.encode()).hexdigest()
    assert stored['equipment_subnet'] == '192.168.50.0/24'
    assert stored['assigned_unit_id'] is None and stored['enabled'] is True
    assert 'remote_network_cidr' in json.dumps(result)
    assert 'enrollment_token' not in result and token not in json.dumps(result)
    assert token not in capsys.readouterr().out
    if os.name != 'nt':
        assert token_path.stat().st_mode & 0o777 == 0o600
    local.unit_class.assert_not_called()
    local.worker.assert_not_called()


def test_enrollment_uses_actual_agoge_admin_role(local, tmp_path):
    target = tmp_path / 'peer.token'
    with pytest.raises((ValueError, Unauthorized)):
        local.backend.enroll_peer('teacher@example.edu', peer_spec(), target)
    assert 'remote-lab-02' not in local.db.collections[DbCollections.WIREGUARD_KIT]
    assert not target.exists()


def test_enrollment_does_not_replace_existing_peer_or_reissue_its_token(local, tmp_path):
    local.users_class.return_value.get_user.return_value.is_admin = True
    first_path, second_path = tmp_path / 'first.token', tmp_path / 'second.token'
    local.backend.enroll_peer('admin@example.edu', peer_spec(), first_path)
    stored = dict(local.db.collections[DbCollections.WIREGUARD_KIT]['remote-lab-02'])
    first_token = first_path.read_text(encoding='utf-8')
    with pytest.raises((ValueError, Conflict)):
        local.backend.enroll_peer('admin@example.edu', peer_spec(), second_path)
    assert local.db.collections[DbCollections.WIREGUARD_KIT]['remote-lab-02'] == stored
    assert first_path.read_text(encoding='utf-8') == first_token
    assert not second_path.exists()


def test_existing_token_output_is_preserved_before_any_peer_is_enrolled(local, tmp_path):
    local.users_class.return_value.get_user.return_value.is_admin = True
    target = tmp_path / 'peer.token'
    target.write_text('existing-private-token', encoding='utf-8')
    with pytest.raises((ValueError, OSError)):
        local.backend.enroll_peer('admin@example.edu', peer_spec(), target)
    assert target.read_text(encoding='utf-8') == 'existing-private-token'
    assert 'remote-lab-02' not in local.db.collections[DbCollections.WIREGUARD_KIT]


def test_status_never_falls_back_to_stale_dns_for_reused_gateway_number(local):
    unit_id = ready_lab(local)
    local.db.collections[DbCollections.WIREGUARD_ENDPOINT]['10000']['unit_id'] = 'anotherlab'
    status = local.backend.status(unit_id)
    assert status['connection_id'] is None and status['endpoint']['hostname'] is None


def test_claim_executes_real_api_decisions_locally_without_publishing(local):
    unit_id = ready_lab(local)
    def provision(attrs, env):
        identifier = attrs['child_id']
        local.db.collections[DbCollections.WORKOUT][identifier] = {
            'id': identifier, 'parent_id': unit_id, 'student_email': 'student@example.edu',
            'state': WorkoutStates.RUNNING.value}
    local.worker.side_effect = provision
    result = local.backend.create_workout(unit_id, 'student@example.edu')
    assert result['state'] == WorkoutStates.RUNNING.value and not result['exists']
    attrs = local.worker.call_args.args[0]
    assert json.loads(attrs['claimed_by'])['student_email'] == 'student@example.edu'
    assert attrs['build_id'] == unit_id and attrs['child_id'] == result['workout_id']
    local.api.pubsub_manager.msg.assert_not_called()
    assert local.backend.create_workout(unit_id, 'student@example.edu')['exists']
    assert local.worker.call_count == 1  # Same student reuses the existing workout.


def test_claim_requires_ready_lab(local):
    unit_id = ready_lab(local)
    local.db.collections[DbCollections.UNIT][unit_id]['state'] = UnitStates.BUILDING_SERVERS.value
    with pytest.raises(ValueError, match='finish provisioning'):
        local.backend.create_workout(unit_id, 'student@example.edu')
    local.worker.assert_not_called()


def test_unregistered_instructor_cannot_create_lab(local):
    local.users_class.return_value.get_user.return_value.is_authorized = False
    args = cli.parser().parse_args(['create-lab', '--instructor', 'student@example.edu', '--kit-id', 'kit-one'])
    with pytest.raises(ValueError, match='instructor or admin'):
        local.backend.create_lab(args)
    local.unit_class.assert_not_called()


def test_http_debug_flag_cannot_activate_local_worker(local):
    ready_lab(local)
    local.api.debug_dispatch = None
    with pytest.raises(BadRequest, match='configured local dispatcher'):
        local.api.build({'input_email': 'student@example.edu', 'join_code': '123456', 'debug': True})
    local.api.pubsub_manager.msg.assert_not_called()
    local.worker.assert_not_called()


def test_normal_api_claim_still_publishes(local):
    ready_lab(local)
    local.api.debug_dispatch = None
    local.api.build({'input_email': 'student@example.edu', 'join_code': '123456'})
    local.api.pubsub_manager.msg.assert_called_once()
    local.worker.assert_not_called()


@pytest.mark.parametrize('scope,action', [('unit', 'build'), ('unit', 'delete'), ('unit', 'stop'),
                                         ('workout', 'start'), ('workout', 'build'), ('workout', 'delete')])
def test_lifecycle_actions_dispatch_explicit_target_locally(local, scope, action):
    identifier = ready_lab(local)
    local.db.collections[DbCollections.WORKOUT][identifier] = {'id': identifier}
    result = local.backend.action(scope, identifier, action, duration=3)
    attrs = local.worker.call_args.args[0]
    assert attrs['build_id'] == identifier and result['worker_returned']
    assert attrs['handler'] == ('BUILD' if action == 'build' else 'CONTROL')
    assert attrs['course_object'] == str((PubSub.CourseObjects.UNIT if scope == 'unit'
                                         else PubSub.CourseObjects.WORKOUT).value)
    if action == 'start':
        assert attrs['duration'] == '3'


def test_status_omits_credentials_and_internal_secret_reference(local):
    unit_id = ready_lab(local)
    local.db.collections[DbCollections.UNIT][unit_id]['password'] = 'must-not-print'
    local.db.collections[DbCollections.WIREGUARD_LEASE][unit_id] = {
        'secret_version_name': 'must-not-print', 'kit_id': 'kit-one', 'service_ready': True,
        'tunnel_ready': False, 'health_timestamp': 123}
    output = json.dumps(local.backend.status(unit_id))
    assert 'must-not-print' not in output
    assert 'kit-one' in output and 'health_timestamp' in output


@pytest.mark.parametrize('argv', [
    ['--project', 'agoge-ualr', 'status', '--unit-id', 'abcdefghij'],
    ['create-workout', '--unit-id', '../other', '--student-email', 'student@example.edu'],
    ['create-lab', '--instructor', 'invalid', '--kit-id', 'kit-one'],
    ['create-lab', '--instructor', 'teacher@example.edu', '--kit-id', 'kit-one', '--count', '0'],
    ['create-lab', '--instructor', 'teacher@example.edu', '--kit-id', 'kit-one', '--expires-hours', 'nan'],
    ['--wireguard-api-url', 'http://localhost', 'status', '--unit-id', 'abcdefghij'],
    ['--wireguard-api-url', 'https://user:password@example.edu', 'status', '--unit-id', 'abcdefghij'],
])
def test_invalid_arguments_fail_before_cloud_access(monkeypatch, argv):
    load = Mock()
    monkeypatch.setattr(cli, 'load_backend', load)
    with pytest.raises(SystemExit) as error:
        cli.main(argv)
    assert error.value.code == 2
    load.assert_not_called()


def test_runner_rejects_mismatched_environment(local):
    with pytest.raises(ValueError, match='require project'):
        cli.LocalBackend({**local.env, 'project': 'agoge-ualr'}, local.db, Mock(), Mock(), Mock())


def test_bootstrap_pins_default_and_explicit_projects_without_editing_environment(local, monkeypatch, tmp_path):
    from common.document_database import DocumentDatabaseFactory
    from common.utilities.gcp import cloud_env

    monkeypatch.setenv('GOOGLE_CLOUD_PROJECT', 'old-project')
    monkeypatch.setenv('GCLOUD_PROJECT', 'old-project')
    monkeypatch.setattr(sys, 'path', sys.path.copy())
    monkeypatch.chdir(tmp_path)
    def load_environment(*, project):
        assert project == os.environ['GOOGLE_CLOUD_PROJECT'] == os.environ['GCLOUD_PROJECT'] == cli.TEST_PROJECT
        return SimpleNamespace(get_env=lambda: local.env)
    monkeypatch.setattr(cloud_env, 'CloudEnv', load_environment)
    database = Mock(return_value=local.db)
    monkeypatch.setattr(DocumentDatabaseFactory, 'create_db_object', database)
    backend = cli.load_backend(cli.TEST_PROJECT, 'https://debug.example.edu')
    assert database.call_args.kwargs['project_id'] == cli.TEST_PROJECT
    assert database.call_args.kwargs['database_name'] == 'agoge-v1'
    assert backend.env_dict['wireguard_api_url'] == 'https://debug.example.edu'
    assert 'wireguard_api_url' not in local.env


def test_local_worker_failure_propagates_without_queue_fallback(local):
    ready_lab(local)
    local.worker.side_effect = RuntimeError('Provisioning failed')
    with pytest.raises(RuntimeError, match='Provisioning failed'):
        local.backend.create_workout('abcdefghij', 'student@example.edu')
    local.api.pubsub_manager.msg.assert_not_called()


def test_worker_entrypoint_receives_debug_flag_and_environment(monkeypatch):
    module = importlib.import_module('cloud_functions.main')
    entrypoint = Mock()
    monkeypatch.setattr(module, 'agoge_cloud_function', entrypoint)
    attrs, env = {'handler': 'BUILD'}, {'project': cli.TEST_PROJECT}
    cli.invoke_local_worker(attrs, env)
    event, context = entrypoint.call_args.args
    assert event == {'attributes': attrs} and context.event_id.startswith('local-')
    assert entrypoint.call_args.kwargs == {'debug_mode': True, 'env_dict': env}


@pytest.mark.parametrize('handler,flag', [('BUILD', 'debug_mode'), ('CONTROL', 'debug'), ('MAINTENANCE', 'debug')])
def test_cloud_function_entrypoint_forwards_local_environment(monkeypatch, handler, flag):
    module = importlib.import_module('cloud_functions.main')
    budget = Mock()
    budget.return_value.check_budget.return_value = True
    monkeypatch.setattr(module, 'BudgetManager', budget)
    factory = Mock()
    monkeypatch.setattr(module, {'BUILD': 'BuildHandler', 'CONTROL': 'ControlHandler',
                                'MAINTENANCE': 'MaintenanceHandler'}[handler], factory)
    env = {'project': cli.TEST_PROJECT}
    module.agoge_cloud_function({'attributes': {'handler': handler}},
                               SimpleNamespace(event_id='test', timestamp='now'), debug_mode=True, env_dict=env)
    assert factory.call_args.kwargs['env_dict'] is env and factory.call_args.kwargs[flag]
    factory.return_value.route.assert_called_once()


def test_budget_block_is_reported_in_local_debug(monkeypatch):
    module = importlib.import_module('cloud_functions.main')
    budget = Mock()
    budget.return_value.check_budget.return_value = False
    monkeypatch.setattr(module, 'BudgetManager', budget)
    factory = Mock()
    monkeypatch.setattr(module, 'BuildHandler', factory)
    event, context = {'attributes': {'handler': 'BUILD'}}, SimpleNamespace(event_id='test', timestamp='now')
    with pytest.raises(RuntimeError, match='Budget exceeded'):
        module.agoge_cloud_function(event, context, debug_mode=True)
    module.agoge_cloud_function(event, context)  # Preserve deployed budget behavior.
    factory.assert_not_called()
