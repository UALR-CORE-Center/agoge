from types import SimpleNamespace

import pytest

from common.constants.database import DbCollections
from common.constants.states import UnitStates, WorkoutStates
from common.utilities.build_incidents import BuildIncidents, BuildQuotaHold
from common.utilities.gcp.compute.quota_failure import ComputeQuotaFailure


class MemoryRef:
    def __init__(self, records, key):
        self.records = records
        self.key = key

    def get(self, transaction=None):
        record = self.records.get(self.key)
        return SimpleNamespace(exists=record is not None, to_dict=lambda: dict(record or {}))


class MemoryDb:
    def __init__(self):
        self.records = {}
        self.db = self

    def collection(self, collection):
        return SimpleNamespace(document=lambda doc_id: MemoryRef(self.records, (collection, doc_id)))

    def transaction(self, operation):
        return operation(self)

    def update(self, ref, patch):
        self.records[ref.key].update(patch)

    def set(self, ref, record):
        self.records[ref.key] = dict(record)

    def query(self, collection_name, filters):
        field, _, value = filters[0]
        return [record for (collection, _), record in self.records.items()
                if collection == collection_name and record.get(field) == value]


UNIT = 'exampleunit'
WORKOUT = 'exampleworkout'
PROJECT = 'example-project'


@pytest.fixture
def state():
    db = MemoryDb()
    db.records[DbCollections.UNIT, UNIT] = {'state': UnitStates.START.value}
    db.records[DbCollections.WORKOUT, WORKOUT] = {'state': WorkoutStates.NOT_BUILT.value, 'parent_id': UNIT}
    return db, BuildIncidents(db, PROJECT)


def _quota(project=PROJECT, operation_id='operation-example'):
    return ComputeQuotaFailure(
        reason='QUOTA_EXCEEDED', category='allocation', metric='NETWORKS', limit=30,
        scope='global', project=project, operation_id=operation_id,
    )


def test_quota_atomically_marks_only_failed_workout_and_opens_project_hold(state):
    db, incidents = state
    attempt = incidents.begin_attempt(DbCollections.WORKOUT, WORKOUT)
    kwargs = dict(unit_id=UNIT, workout_id=WORKOUT, stage='network', attempt_id=attempt,
                  target_patch={'state': WorkoutStates.BROKEN.value, 'active': False})
    failure = incidents.record_quota(_quota(), event_id='first', **kwargs)
    duplicate = incidents.record_quota(_quota(), event_id='duplicate', **kwargs)

    assert duplicate == failure
    assert db.records[DbCollections.UNIT, UNIT]['state'] == UnitStates.START.value
    assert db.records[DbCollections.WORKOUT, WORKOUT]['build_failure_id'] == failure['id']
    assert incidents.current_failure(unit_id=UNIT, workout_id=WORKOUT) == failure
    assert len(incidents.for_unit(UNIT)) == 1
    assert 'operation_id' not in incidents.for_unit(UNIT)[0]
    with pytest.raises(BuildQuotaHold) as caught:
        incidents.require_network_capacity()
    assert caught.value.hold['limit'] == 30
    assert caught.value.hold['incident_id'] == failure['id']
    BuildIncidents(db, 'other-project').require_network_capacity()


def test_late_quota_preserves_deleting_unit_and_never_attaches_stale_workout_failure(state):
    db, incidents = state
    attempt = incidents.begin_attempt(DbCollections.WORKOUT, WORKOUT)
    db.records[DbCollections.UNIT, UNIT]['state'] = UnitStates.DELETING_SERVERS.value
    failure = incidents.record_quota(
        _quota(), unit_id=UNIT, workout_id=WORKOUT, attempt_id=attempt,
        target_patch={'state': WorkoutStates.BROKEN.value},
    )
    assert failure['unit_id'] is None and failure['workout_id'] is None
    assert incidents.for_unit(UNIT) == []
    assert db.records[DbCollections.WORKOUT, WORKOUT]['state'] == WorkoutStates.NOT_BUILT.value
    assert incidents.active_hold()


def test_recheck_requires_capacity_and_cannot_overwrite_newer_failure(state):
    _, incidents = state
    old_hold = incidents.update_verified_quota(None, usage=30, limit=30, verified_by='admin')
    still_active = incidents.update_verified_quota(old_hold, usage=30, limit=30, verified_by='admin')
    assert still_active['usage'] == 30
    incidents.record_quota(_quota(), event_id='new')
    assert incidents.update_verified_quota(still_active, usage=29, limit=30, verified_by='admin')
    assert incidents.update_verified_quota(incidents.active_hold(), usage=29, limit=30, verified_by='admin') is None
    assert incidents.active_hold() is None


def test_explicit_retry_rotates_attempt_and_confirmed_cleanup_resolves_history(state):
    db, incidents = state
    original = incidents.begin_attempt(DbCollections.UNIT, UNIT)
    kwargs = dict(unit_id=UNIT, stage='network', attempt_id=original,
                  target_patch={'state': UnitStates.BROKEN.value})
    failure = incidents.record_quota(_quota(), **kwargs)
    assert incidents.begin_attempt(DbCollections.UNIT, UNIT) is None
    replacement = incidents.begin_attempt(DbCollections.UNIT, UNIT, retry=True)
    assert replacement != original
    assert db.records[DbCollections.UNIT, UNIT]['state'] == UnitStates.START.value
    assert incidents.current_failure(unit_id=UNIT) is None

    incidents.resolve_target(unit_id=UNIT, attempt_id=original)
    assert incidents.for_unit(UNIT)[0]['id'] == failure['id']
    db.records[DbCollections.UNIT, UNIT]['state'] = UnitStates.DELETED.value
    incidents.resolve_target(unit_id=UNIT, attempt_id=replacement)
    assert incidents.for_unit(UNIT) == []
    assert incidents.active_hold()


def test_verified_build_clears_failure_pointer_but_preserves_cleanup_incidents(state):
    db, incidents = state
    attempt = incidents.begin_attempt(DbCollections.WORKOUT, WORKOUT)
    incidents.record_quota(
        _quota(), unit_id=UNIT, workout_id=WORKOUT, attempt_id=attempt,
        target_patch={'state': WorkoutStates.BROKEN.value},
    )
    incidents.record_cleanup_failure(unit_id=UNIT, workout_id=WORKOUT, attempt_id=attempt)

    db.records[DbCollections.WORKOUT, WORKOUT]['state'] = WorkoutStates.READY.value
    incidents.resolve_target(unit_id=UNIT, workout_id=WORKOUT, attempt_id=attempt, resolution='build_succeeded')

    assert db.records[DbCollections.WORKOUT, WORKOUT]['build_failure_id'] is None
    assert [row['kind'] for row in incidents.for_unit(UNIT)] == ['cleanup_failed']
