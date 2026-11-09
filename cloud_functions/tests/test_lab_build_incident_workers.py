from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from cloud_fn_utilities import build_execution as execution_module
from cloud_fn_utilities.build_execution import (
    BuildExecution, BuildSuperseded, build_execution, tracked_compute_create, wait_for_pending_creates,
)
from cloud_fn_utilities.gcp import vpc_manager as vpc_module
from handlers.build_handler import BuildHandler
from handlers.control_handler import ControlHandler
from common.constants.database import DbCollections
from common.constants.google import OperationType, ResourceType
from common.constants.pub_sub import PubSub
from common.constants.states import ServerStates, UnitStates, WorkoutStates
from common.exceptions import NotFound
from common.utilities.build_incidents import BuildIncidents, BuildQuotaHold
from common.utilities.gcp.compute.quota_failure import ComputeQuotaFailure


class MemoryDatabase:
    def __init__(self, records):
        self.records = records
        self.db = self

    def collection(self, name):
        return SimpleNamespace(document=lambda doc_id: MemoryReference(self, name, doc_id))

    def get(self, collection, doc_id):
        return deepcopy(self.records.get((collection.value, doc_id), {}))

    def set(self, ref, patch, merge=False):
        key = (ref.collection_name, ref.doc_id)
        current = self.records.get(key, {}) if merge else {}
        self.records[key] = {**current, **deepcopy(patch)}

    def update(self, ref, patch):
        self.set(ref, patch, merge=True)

    def transaction(self, callback):
        return callback(self)

    def query(self, collection_name, filters):
        field, _, expected = filters[0]
        return [row for (name, _), row in self.records.items()
                if name == collection_name.value and row.get(field) == expected]


class MemoryReference:
    def __init__(self, db, collection_name, doc_id):
        self.db = db
        self.collection_name = collection_name
        self.doc_id = doc_id
        self.id = doc_id

    def get(self, transaction=None):
        row = deepcopy(self.db.records.get((self.collection_name, self.doc_id)))
        return SimpleNamespace(exists=row is not None, to_dict=lambda: row)


def _database():
    return MemoryDatabase({
        ('unit', 'unit-a'): {'id': 'unit-a', 'state': UnitStates.BUILDING_NETWORKS.value,
                            'build_attempt_id': 'unit-attempt', 'unit_type': 'community'},
        ('workout', 'workout-a'): {'id': 'workout-a', 'state': WorkoutStates.BUILDING_SERVERS.value,
                                  'parent_id': 'unit-a', 'build_attempt_id': 'workout-attempt'},
        ('agoge-server', 'workout-a-server'): {'parent_id': 'workout-a', 'parent_build_type': 'workout',
                                             'state': ServerStates.BUILDING.value},
    })


def _build_events(db):
    return [row for (collection, _), row in db.records.items() if collection == DbCollections.BUILD_EVENT.value]


def _handler(db, course_object, *, target='unit-a', attempt='unit-attempt'):
    handler = object.__new__(BuildHandler)
    handler.db = db
    handler.env = SimpleNamespace(project='example-project')
    handler.debug_mode = False
    handler.logger = Mock()
    handler.event_id = 'event-example'
    handler.event_attr_keys = PubSub.EventAttributes
    handler.event_attributes = {
        'course_object': str(course_object.value),
        'build_id': target,
        'build_attempt_id': attempt,
    }
    return handler


def _quota(**overrides):
    return ComputeQuotaFailure(**{
        'category': 'allocation', 'reason': 'QUOTA_EXCEEDED', 'metric': 'NETWORKS', 'limit': 30,
        'scope': 'global', 'project': 'example-project', 'operation_id': 'operation-synthetic',
        'resource_type': 'NETWORKS', **overrides,
    })


def test_current_build_logs_one_start_and_completion_despite_redelivery():
    db = _database()
    handler = _handler(db, PubSub.CourseObjects.UNIT)

    def build():
        assert [row['kind'] for row in _build_events(db)] == ['build_started']
        db.records['unit', 'unit-a']['state'] = UnitStates.READY.value

    handler._dispatch = Mock(side_effect=build)
    handler.route()
    handler.event_id = 'second-delivery'
    handler.route()

    handler._dispatch.assert_called_once()
    assert [row['kind'] for row in _build_events(db)] == ['build_started', 'build_completed']


def test_unhandled_workout_error_logs_exception_class_and_preserves_retry():
    db = _database()
    handler = _handler(db, PubSub.CourseObjects.WORKOUT, target='workout-a', attempt='workout-attempt')
    handler._dispatch = Mock(side_effect=TimeoutError('provider detail that must not be stored'))

    with pytest.raises(TimeoutError):
        handler.route()

    events = _build_events(db)
    assert [row['kind'] for row in events] == ['build_started', 'build_error']
    assert events[-1]['stage'] == 'workout'
    assert events[-1]['reason'] == 'TimeoutError'
    assert 'provider detail' not in str(events)


@pytest.mark.parametrize('course_object, target, stage, resource', [
    (PubSub.CourseObjects.LAB_SERVER, 'untrusted', 'server', 'workout-a-server'),
    (PubSub.CourseObjects.DISPLAY_PROXY, 'workout-a', 'display_proxy', 'workout-a-display-guacamole-server'),
])
def test_unhandled_child_error_logs_owning_workout_and_resource(course_object, target, stage, resource):
    db = _database()
    handler = _handler(db, course_object, target=target, attempt='workout-attempt')
    handler.event_attributes.update(server_name='workout-a-server', key_type=DbCollections.WORKOUT.value)
    handler._dispatch = Mock(side_effect=RuntimeError('provider detail that must not be stored'))

    for delivery in ('first-delivery', 'second-delivery'):
        handler.event_id = delivery
        with pytest.raises(RuntimeError):
            handler.route()

    event, = _build_events(db)
    assert event['kind'] == 'build_error'
    assert event['unit_id'] == 'unit-a'
    assert event['workout_id'] == 'workout-a'
    assert event['stage'] == stage
    assert event['resource'] == resource
    assert event['reason'] == 'RuntimeError'
    assert 'provider detail' not in str(event)


def test_network_quota_fails_current_shared_lab_and_opens_project_hold():
    db = _database()
    handler = _handler(db, PubSub.CourseObjects.UNIT)
    handler._dispatch = Mock(side_effect=_quota())

    handler.route()
    handler.route()  # A Pub/Sub redelivery does no further provisioning.

    handler._dispatch.assert_called_once()
    incidents = BuildIncidents(db, 'example-project')
    failure = incidents.current_failure(unit_id='unit-a')
    assert failure['stage'] == 'network'
    assert failure['operation_id'] == 'operation-synthetic'
    assert db.get(DbCollections.UNIT, 'unit-a')['state'] == UnitStates.BROKEN.value
    assert incidents.active_hold()['limit'] == 30
    assert db.get(DbCollections.WORKOUT, 'workout-a')['state'] == WorkoutStates.BUILDING_SERVERS.value
    assert [row['kind'] for row in _build_events(db)] == ['build_started']


def test_async_vm_quota_fails_only_its_authoritative_workout():
    db = _database()
    db.records['unit', 'unit-a']['state'] = UnitStates.READY.value
    handler = _handler(db, PubSub.CourseObjects.LAB_SERVER, target='untrusted', attempt='workout-attempt')
    handler.event_attributes['server_name'] = 'workout-a-server'
    handler._dispatch = Mock(side_effect=_quota(metric='CPUS', scope='us-central1', resource_type='INSTANCE'))

    handler.route()

    incidents = BuildIncidents(db, 'example-project')
    assert incidents.current_failure(unit_id='unit-a', workout_id='workout-a')['stage'] == 'server'
    assert incidents.current_failure(unit_id='unit-a') is None
    assert incidents.active_hold() is None
    assert db.get(DbCollections.UNIT, 'unit-a')['state'] == UnitStates.READY.value
    assert _build_events(db) == []


def test_rate_rejection_remains_retryable_and_older_attempt_is_skipped():
    db = _database()
    handler = _handler(db, PubSub.CourseObjects.UNIT)
    handler._dispatch = Mock(side_effect=_quota(category='rate', reason='RATE_LIMIT_EXCEEDED'))
    with pytest.raises(ComputeQuotaFailure):
        handler.route()

    db.records['unit', 'unit-a']['build_attempt_id'] = 'new-attempt'
    handler.route()

    handler._dispatch.assert_called_once()
    assert BuildIncidents(db, 'example-project').active_hold() is None
    assert db.get(DbCollections.UNIT, 'unit-a')['state'] == UnitStates.BUILDING_NETWORKS.value


def test_pending_create_is_reused_and_cleanup_waits_for_provider(monkeypatch):
    db = _database()
    execution = BuildExecution(db, DbCollections.UNIT, 'unit-a', 'unit-a', 'unit-attempt')
    client = Mock(project='example-project', region='us-central1', zone='us-central1-a',
                  resource_type=ResourceType.NETWORKS)
    client.create.return_value = SimpleNamespace(name='operation-synthetic')
    client.wait_for_operation.side_effect = [False, True]

    with build_execution(execution):
        assert not tracked_compute_create(client, 'unit-a-network', OperationType.GLOBAL)
        assert tracked_compute_create(client, 'unit-a-network', OperationType.GLOBAL)
    client.create.assert_called_once_with(resource_name='unit-a-network', wait=False)
    assert db.get(DbCollections.UNIT, 'unit-a')['pending_compute_creates'] == {}

    client.wait_for_operation.side_effect = None
    client.wait_for_operation.return_value = False
    with build_execution(execution):
        assert not tracked_compute_create(client, 'unit-a-network', OperationType.GLOBAL)
    db.records['unit', 'unit-a']['state'] = UnitStates.DELETING_SERVERS.value
    operations = Mock()
    operations.wait.side_effect = [False, True]
    monkeypatch.setattr(execution_module, 'ComputeOperationsAPI', Mock(return_value=operations))

    with pytest.raises(ConnectionError, match='cleanup can retry'):
        wait_for_pending_creates(db, DbCollections.UNIT, 'unit-a')
    wait_for_pending_creates(db, DbCollections.UNIT, 'unit-a')
    with pytest.raises(BuildSuperseded):
        execution.update(DbCollections.UNIT, 'unit-a', {'state': UnitStates.READY.value})


def test_confirmed_throttle_is_retried_and_recorded_without_opening_project_hold(monkeypatch):
    db = _database()
    handler = _handler(db, PubSub.CourseObjects.UNIT)
    client = Mock(project='example-project', region='us-central1', zone='us-central1-a',
                  resource_type=ResourceType.NETWORKS)
    client.create.side_effect = _quota(category='rate', reason='RATE_LIMIT_EXCEEDED', action='insert')
    handler._dispatch = lambda: tracked_compute_create(client, 'unit-a-network', OperationType.GLOBAL)
    monkeypatch.setattr(execution_module.time, 'sleep', Mock())

    handler.route()

    assert client.create.call_count == 3
    assert db.get(DbCollections.UNIT, 'unit-a')['pending_compute_creates'] == {}
    incidents = BuildIncidents(db, 'example-project')
    assert incidents.current_failure(unit_id='unit-a')['reason'] == 'RATE_LIMIT_EXCEEDED'
    assert incidents.active_hold() is None


def test_vpc_hold_allows_an_existing_vpc_and_rejects_a_new_one(monkeypatch):
    db = _database()
    BuildIncidents(db, 'example-project').record_quota(_quota())
    monkeypatch.setattr(vpc_module.DocumentDatabaseFactory, 'create_db_object', Mock(return_value=db))
    manager = object.__new__(vpc_module.VpcManager)
    manager.build_id = 'unit-a'
    manager.class_name = 'VpcManager'
    manager.env = SimpleNamespace(project='example-project')
    manager.logger = Mock()
    manager.network_resource = Mock()
    manager.networks_client = Mock()
    network = SimpleNamespace(name='network', subnets=[])

    manager.build(network)
    manager.networks_client.get.side_effect = NotFound()
    with pytest.raises(BuildQuotaHold):
        manager.build(network)
    manager.networks_client.create.assert_not_called()


def test_cleanup_failure_is_kept_until_delete_is_verified():
    db = _database()
    handler = object.__new__(ControlHandler)
    handler.db = db
    handler.env = SimpleNamespace(project='example-project')
    handler.logger = Mock()
    handler.course_object = str(PubSub.CourseObjects.WORKOUT.value)
    handler.build_id = 'workout-a'
    handler.event_id = 'cleanup-event'
    incidents = BuildIncidents(db, 'example-project')

    with pytest.raises(ConnectionError, match='not confirmed'):
        handler._tracked_delete(Mock(return_value=None))
    assert incidents.for_unit('unit-a')[0]['kind'] == 'cleanup_failed'
    assert _build_events(db) == []

    def delete():
        db.records['workout', 'workout-a']['state'] = WorkoutStates.DELETED.value

    handler._tracked_delete(delete)
    handler.event_id = 'another-cleanup-delivery'
    handler._tracked_delete(delete)
    assert incidents.for_unit('unit-a') == []
    assert [row['kind'] for row in _build_events(db)] == ['cleanup_completed']
