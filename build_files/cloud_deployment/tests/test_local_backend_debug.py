"""Local debug dispatch with real API decisions and no live GCP calls."""
import importlib
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
from common.exceptions import BadRequest
from core.workout import Workout


class Database:
    def __init__(self):
        self.collections = {name: {} for name in DbCollections}

    def get(self, collection_name, doc_id):
        return self.collections[collection_name].get(doc_id, {})

    def query(self, collection_name, filters):
        return [record for record in self.collections[collection_name].values()
                if all(record.get(field) == value for field, _, value in filters)]


@pytest.fixture
def local():
    db = Database()
    env = {'project': cli.TEST_PROJECT, 'region': 'us-central1', 'zone': 'us-central1-a'}
    unit_class, users_class, worker = Mock(), Mock(), Mock()
    users_class.return_value.get_user.return_value = SimpleNamespace(is_authorized=True)
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
        'workspace_settings': {'count': 2}, 'wireguard_endpoint': {'hostname': 'wg.example.edu', 'port': 51820}}
    return unit_id


def test_create_lab_commits_through_api_then_dispatches_local_worker(local):
    args = cli.parser().parse_args(['create-lab', '--instructor', 'Teacher@Example.edu', '--kit-id', 'kit-one'])
    unit_id = ready_lab(local)
    local.unit_class.return_value.build.return_value = unit_id
    result = local.backend.create_lab(args)
    local.unit_class.assert_called_once_with(env_dict=local.env, debug=True)
    data = local.unit_class.return_value.build.call_args.kwargs['data']
    assert data['build_file'] == 'wireguard-factory-lab' and data['kit_id'] == 'kit-one'
    assert data['test'] and data['build_count'] == 1 and not data['lms_integration']
    local.users_class.return_value.get_user.assert_called_once_with(user_email='teacher@example.edu')
    attrs, env = local.worker.call_args.args
    assert env is local.env and attrs['course_object'] == str(PubSub.CourseObjects.UNIT.value)
    assert attrs['build_id'] == unit_id and result['state_name'] == 'READY'


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
