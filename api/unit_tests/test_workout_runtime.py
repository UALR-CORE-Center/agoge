import csv
from datetime import date, datetime, timezone
from io import StringIO
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from common.constants.database import DbCollections, DbOperators
from common.constants.pub_sub import PubSub
from common.constants.states import WorkoutStates
from common.models.users import AgogeUser
from common.utilities.workout_runtime import record_workout_runtime
from core.cloud_monitoring import CloudMonitoring
from dependencies import get_current_user
from routers import cloud_monitoring as routes


class RuntimeDb:
    def __init__(self):
        self.records = {}
        self.db = self

    def collection(self, collection):
        def document(doc_id):
            def get(transaction=None):
                value = self.records.get((collection, doc_id))
                return SimpleNamespace(exists=value is not None, to_dict=lambda: dict(value or {}))

            return SimpleNamespace(key=(collection, doc_id), get=get)

        return SimpleNamespace(document=document)

    def set(self, ref, values, merge=False):
        self.records[ref.key] = {**(self.records.get(ref.key, {}) if merge else {}), **values}

    def delete(self, ref):
        self.records.pop(ref.key, None)

    def query(self, collection, filters):
        field, operator, expected = filters[0]
        return [
            row.copy() for (name, _), row in self.records.items() if name == collection
            and (row.get(field) in expected if operator == DbOperators.IN else row.get(field) == expected)
        ]


def moment(value):
    return datetime.fromisoformat(value).astimezone(timezone.utc)


def change(db, workout, state, at):
    patch = {'state': state.value, 'state_timestamp': at}
    record_workout_runtime(db, db, workout['id'], workout, patch)
    workout.update(patch)


def example_workout():
    return {
        'id': 'workout-1', 'parent_id': 'lab-1', 'state': WorkoutStates.BUILDING_SERVERS.value,
        'summary': {'name': 'Cloud Lab'}, 'student_email': 'sam@example.edu',
    }


def test_running_interval_splits_at_utc_month_boundary_without_restarting_on_repeat():
    db, workout = RuntimeDb(), example_workout()
    change(db, workout, WorkoutStates.RUNNING, '2026-10-31T23:30:00+00:00')
    change(db, workout, WorkoutStates.RUNNING, '2026-10-31T23:45:00+00:00')
    change(db, workout, WorkoutStates.STARTING, '2026-10-31T23:50:00+00:00')
    change(db, workout, WorkoutStates.RUNNING, '2026-10-31T23:55:00+00:00')
    change(db, workout, WorkoutStates.STOPPING, '2026-11-01T01:30:00+00:00')
    change(db, workout, WorkoutStates.READY, '2026-11-01T01:35:00+00:00')
    db.records[DbCollections.USERS, 'sam'] = {'email': 'sam@example.edu', 'name': 'Sam Reader'}
    start, stop = CloudMonitoring.period(start=date(2026, 10, 31), end=date(2026, 11, 1))

    result = CloudMonitoring(db).report(start, stop, now=moment('2026-11-02T00:00:00+00:00'))

    assert result['months'] == [
        {'month': '2026-10', 'workouts': 1, 'run_count': 1, 'runtime_seconds': 1800},
        {'month': '2026-11', 'workouts': 1, 'run_count': 1, 'runtime_seconds': 5400},
    ]
    [row] = result['rows']
    assert row['student_name'] == 'Sam Reader'
    assert row['build_date'] == '2026-10-31T23:30:00+00:00'
    assert row['runtime_seconds'] == 7200
    assert row['run_count'] == 1
    assert row['running'] is False
    assert (DbCollections.WORKOUT_RUNTIME, 'live-workout-1') not in db.records


def test_running_workout_without_history_starts_at_first_observed_transition():
    db, workout = RuntimeDb(), example_workout()
    workout.update(state=WorkoutStates.RUNNING.value, state_timestamp='2026-10-10T00:00:00+00:00')
    start, stop = CloudMonitoring.period(month='2026-11')
    report = CloudMonitoring(db)
    assert report.report(start, stop, now=moment('2026-11-03T02:00:00+00:00'))['rows'] == []

    change(db, workout, WorkoutStates.RUNNING, '2026-11-03T00:00:00+00:00')
    live = report.report(start, stop, now=moment('2026-11-03T02:00:00+00:00'))

    [row] = live['rows']
    assert row['build_date'] is None
    assert row['runtime_seconds'] == 7200
    assert row['running'] is True


def test_web_only_workout_records_build_without_indefinite_runtime():
    db, workout = RuntimeDb(), example_workout()
    workout['web_applications'] = [{'host_name': 'example.edu'}]
    change(db, workout, WorkoutStates.RUNNING, '2026-11-03T00:00:00+00:00')
    start, stop = CloudMonitoring.period(month='2026-11')

    [row] = CloudMonitoring(db).report(start, stop, now=moment('2026-11-03T02:00:00+00:00'))['rows']

    assert row['build_date'] == '2026-11-03T00:00:00+00:00'
    assert row['runtime_seconds'] == row['run_count'] == 0
    assert row['running'] is False


def test_stopping_an_unbuilt_workout_does_not_count_as_a_build():
    db, workout = RuntimeDb(), example_workout()
    workout.update(state=WorkoutStates.NOT_BUILT.value, action=PubSub.Actions.STOP.value)
    change(db, workout, WorkoutStates.READY, '2026-11-03T00:00:00+00:00')

    assert db.records == {}


def test_existing_run_keeps_opening_student_across_reassignment():
    db, workout = RuntimeDb(), example_workout()
    workout['runtime_student_name'] = 'Sam Reader'
    change(db, workout, WorkoutStates.READY, '2026-11-01T00:00:00+00:00')
    start, stop = CloudMonitoring.period(month='2026-11')
    report = CloudMonitoring(db)
    [parked] = report.report(start, stop, now=moment('2026-11-03T00:00:00+00:00'))['rows']
    assert parked['runtime_seconds'] == parked['run_count'] == 0

    change(db, workout, WorkoutStates.RUNNING, '2026-11-03T01:00:00+00:00')
    workout.update(student_email='pat@example.edu', runtime_student_name='Pat Reader')
    change(db, workout, WorkoutStates.STOPPING, '2026-11-03T02:00:00+00:00')
    change(db, workout, WorkoutStates.RUNNING, '2026-11-03T03:00:00+00:00')
    change(db, workout, WorkoutStates.DELETING_SERVERS, '2026-11-03T05:00:00+00:00')

    result = report.report(start, stop, now=moment('2026-11-04T00:00:00+00:00'))
    assert {row['student_name']: row['runtime_seconds'] for row in result['rows']} == {
        'Sam Reader': 3600, 'Pat Reader': 7200,
    }
    assert result['total'] == 2
    assert result['total_workouts'] == 1
    assert result['months'][0]['run_count'] == 2
    sam = report.report(start, stop, q='sam reader', now=moment('2026-11-04T00:00:00+00:00'))
    assert sam['total_runtime_seconds'] == 3600


def test_report_uses_closed_interval_if_a_stop_commits_between_reads():
    workout = example_workout()

    class StoppingDb(RuntimeDb):
        def query(self, collection, filters):
            if filters[0][0] == 'month':
                change(self, workout, WorkoutStates.STOPPING, '2026-11-03T02:00:00+00:00')
            return super().query(collection, filters)

    db = StoppingDb()
    change(db, workout, WorkoutStates.RUNNING, '2026-11-03T00:00:00+00:00')
    start, stop = CloudMonitoring.period(month='2026-11')
    [row] = CloudMonitoring(db).report(start, stop, now=moment('2026-11-03T03:00:00+00:00'))['rows']

    assert row['runtime_seconds'] == 7200
    assert row['run_count'] == 1
    assert row['running'] is False


def test_private_runtime_routes_and_formula_safe_csv(monkeypatch):
    db, workout = RuntimeDb(), example_workout()
    workout['runtime_student_name'] = '=1+1'
    change(db, workout, WorkoutStates.RUNNING, '2026-11-03T00:00:00+00:00')
    change(db, workout, WorkoutStates.STOPPING, '2026-11-03T01:00:00+00:00')
    monkeypatch.setattr(routes, 'CloudMonitoring', type('Monitoring', (CloudMonitoring,), {
        '__init__': lambda self: CloudMonitoring.__init__(self, db=db),
    }))
    user = AgogeUser(uid='teacher', email='teacher@example.edu', permissions={'instructor': True})
    app = FastAPI()
    app.include_router(routes.cloud_monitoring_router)
    app.dependency_overrides[get_current_user] = lambda: user
    client = TestClient(app)
    base = '/cloud-monitoring/workout-runtime/'
    for suffix in ('', 'months/', 'export/'):
        assert client.get(base + suffix).status_code == 403

    user.permissions = {'admin': True}
    rows = client.get(base, params={'month': '2026-11', 'limit': 1})
    assert rows.headers['Cache-Control'] == 'no-store'
    assert rows.json()['data']['rows'][0]['student_name'] == '=1+1'
    export = client.get(base + 'export/', params={'month': '2026-11'})
    assert export.headers['Content-Type'].startswith('text/csv')
    [row] = csv.DictReader(StringIO(export.text))
    assert row['student_name'] == "'=1+1"
    assert client.get(base, params={'start': '2026-11-01'}).status_code == 400
