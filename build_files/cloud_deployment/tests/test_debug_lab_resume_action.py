"""A returned build worker cannot hide a broken or absent gateway."""
from types import SimpleNamespace
from unittest.mock import Mock

from google.api_core.exceptions import InvalidArgument
import pytest

import debug_lab as cli
from common.constants.database import DbCollections, DbOperators
from common.constants.pub_sub import PubSub
from common.constants.states import ServerStates, UnitStates


UNIT = 'uljrlxqhjm'
GATEWAY = f'{UNIT}-wireguard'


class Database:
    def __init__(self):
        self.collections = {collection: {} for collection in DbCollections}
        self.queries = []

    def get(self, collection_name, doc_id):
        return self.collections[collection_name].get(doc_id, {})

    def query(self, collection_name, filters=None):
        self.queries.append((collection_name, filters))
        for _, operator, _ in filters or []:
            assert operator == DbOperators.EQUAL
        return [record for record in self.collections[collection_name].values()
                if all(record.get(field) == value for field, _, value in filters or [])]


@pytest.fixture
def resume():
    db, worker = Database(), Mock()
    unit = {
        'id': UNIT, 'state': UnitStates.BROKEN.value,
        'servers': [{'name': 'wireguard', 'community_server': True,
                     'wireguard_gateway': True, 'wireguard_managed': True}],
        'wireguard_lease': {'remote_peer_id': 'remote-lab-01'},
    }
    gateway = {'name': 'wireguard', 'parent_id': UNIT, 'state': ServerStates.BROKEN.value}
    db.collections[DbCollections.UNIT][UNIT] = unit
    db.collections[DbCollections.SERVER][GATEWAY] = gateway
    backend = cli.LocalBackend({'project': cli.TEST_PROJECT}, db, Mock(), Mock(), Mock(), worker)
    return SimpleNamespace(db=db, worker=worker, unit=unit, gateway=gateway, backend=backend)


def test_unit_build_worker_return_is_not_success_when_unit_remains_broken(resume):
    with pytest.raises(cli.DebugLabStageError, match=f'Lab {UNIT} did not complete build; state is BROKEN'):
        resume.backend.action('unit', UNIT, 'build')

    resume.worker.assert_called_once()
    attributes, environment = resume.worker.call_args.args
    assert environment['project'] == cli.TEST_PROJECT
    assert attributes == {
        'handler': PubSub.Handlers.BUILD.value,
        'action': str(PubSub.Actions.BUILD.value),
        'build_id': UNIT, 'course_object': str(PubSub.CourseObjects.UNIT.value),
    }


@pytest.mark.parametrize('gateway_state', [None, ServerStates.BROKEN.value, ServerStates.STOPPED.value])
def test_ready_parent_cannot_hide_an_unbuilt_gateway_after_resume(resume, gateway_state):
    resume.unit['state'] = UnitStates.READY.value
    if gateway_state is None:
        del resume.db.collections[DbCollections.SERVER][GATEWAY]
    else:
        resume.gateway['state'] = gateway_state

    with pytest.raises(cli.DebugLabStageError, match=f'Server {GATEWAY} did not complete build'):
        resume.backend.action('unit', UNIT, 'build')

    resume.worker.assert_called_once()


@pytest.mark.parametrize('completed_state', [UnitStates.READY.value, UnitStates.RUNNING.value])
def test_resume_checks_state_after_worker_finishes_and_accepts_completed_build(resume, completed_state):
    def finish(attributes, environment):
        assert resume.unit['state'] == UnitStates.BROKEN.value
        resume.unit['state'] = completed_state
        resume.gateway['state'] = ServerStates.RUNNING.value

    resume.worker.side_effect = finish

    result = resume.backend.action('unit', UNIT, 'build')

    assert result['scope'] == 'unit' and result['id'] == UNIT
    assert result['action'] == 'build' and result['worker_returned'] is True
    assert resume.db.queries  # A persisted-state check occurred after dispatch.


def test_worker_exception_propagates_before_success_verification(resume):
    error = InvalidArgument('private-worker-response')
    resume.worker.side_effect = error

    with pytest.raises(InvalidArgument) as caught:
        resume.backend.action('unit', UNIT, 'build')

    assert caught.value is error
    assert resume.db.queries == []


@pytest.mark.parametrize('scope,operation', [
    ('unit', 'start'), ('unit', 'stop'), ('unit', 'delete'),
    ('workout', 'build'), ('workout', 'start'), ('workout', 'stop'), ('workout', 'delete'),
])
def test_new_build_verification_does_not_change_other_action_dispatch(resume, scope, operation):
    workout_id = 'abcdefghij'
    resume.db.collections[DbCollections.WORKOUT][workout_id] = {'id': workout_id, 'state': 0}
    identifier = UNIT if scope == 'unit' else workout_id
    resume.backend._verify_lab_stage = Mock()

    result = resume.backend.action(scope, identifier, operation, duration=3)

    assert result['worker_returned'] and result['scope'] == scope
    resume.backend._verify_lab_stage.assert_not_called()
    attributes, _ = resume.worker.call_args.args
    assert attributes['build_id'] == identifier
    if operation == 'start':
        assert attributes['duration'] == '3'


def test_cli_resume_returns_failure_with_safe_state_diagnostic_when_worker_did_nothing(resume, monkeypatch, capsys):
    monkeypatch.setattr(cli, 'load_backend', Mock(return_value=resume.backend))

    code = cli.main(['unit-action', '--unit-id', UNIT, '--action', 'build'])

    captured = capsys.readouterr()
    assert code == 1
    assert f'Lab {UNIT} did not complete build; state is BROKEN' in captured.err
    assert 'worker_returned' not in captured.out

