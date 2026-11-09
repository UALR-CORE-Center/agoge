from datetime import date
from types import SimpleNamespace

import pytest

from common.constants.database import DbCollections
from common.utilities.build_log import BuildLog


class MemoryLog:
    def __init__(self):
        self.db = self
        self.rows = {}

    def collection(self, name):
        def document(identifier):
            key = name, identifier
            return SimpleNamespace(
                id=identifier, key=key,
                get=lambda transaction: SimpleNamespace(exists=key in self.rows),
            )
        return SimpleNamespace(document=document)

    def transaction(self, operation):
        operation(self)

    def set(self, ref, row):
        self.rows[ref.key] = row


def test_lifecycle_events_deduplicate_and_never_invent_completed_builds():
    db = MemoryLog()
    log = BuildLog(db, 'project-a')
    args = dict(unit_id='lab-a', workout_id='workout-a', attempt_id='attempt-a')

    log.record_event('build_completed', **args)
    assert db.rows == {}
    log.record_event('build_started', **args, event_id='worker-a')
    log.record_event('build_started', **args, event_id='worker-b')
    log.record_event('build_error', **args, stage='network', reason='TimeoutError')
    log.record_event('build_error', **args, stage='network', reason='TimeoutError')
    log.record_event('build_completed', **args, event_id='worker-b')
    log.record_event('build_completed', **args, event_id='worker-c')
    log.record_event('cleanup_completed', **args, event_id='cleanup-a')
    log.record_event('cleanup_completed', **args, event_id='cleanup-b')

    assert [row['kind'] for row in db.rows.values()] == [
        'build_started', 'build_error', 'build_completed', 'cleanup_completed',
    ]
    assert {row['workout_id'] for row in db.rows.values()} == {'workout-a'}


def _entry(kind, day, number, **fields):
    return {
        'kind': kind, 'id': f'{number:032x}', 'occurred_at': f'2026-11-{day:02d}T12:00:00+00:00',
        **fields,
    }


def _fixture_log(monkeypatch):
    log = BuildLog(None, 'project-a')
    fixtures = {
        DbCollections.BUILD_EVENT: [
            _entry('build_started', 2, 1, unit_id='alpha'),
            _entry('build_completed', 4, 4, unit_id='alpha'),
            _entry('cleanup_completed', 5, 5, unit_id='beta'),
        ],
        DbCollections.BUILD_INCIDENT: [
            _entry('build_failure', 4, 3, unit_id='alpha', reason='QUOTA_EXCEEDED', metric='NETWORKS'),
            _entry('cleanup_failed', 3, 2, unit_id='beta', reason='TIMEOUT'),
        ],
    }

    def source(collection, *, ascending, start, end, cursor):
        rows = sorted(fixtures[collection], key=log._sort_key, reverse=not ascending)
        for row in rows:
            day = date.fromisoformat(row['occurred_at'][:10])
            if (start and day < start) or (end and day > end):
                continue
            if cursor and (log._sort_key(row) <= cursor if ascending else log._sort_key(row) >= cursor):
                continue
            yield row

    monkeypatch.setattr(log, '_source', source)
    return log


@pytest.mark.parametrize('sort', ['asc', 'desc'])
def test_search_date_and_cursor_span_both_collections(monkeypatch, sort):
    log = _fixture_log(monkeypatch)
    options = dict(search='AlPhA', date_from=date(2026, 11, 3), date_to=date(2026, 11, 4),
                   page_size=1, sort=sort)
    first = log.list_events(**options)
    second = log.list_events(**options, cursor=first['next_cursor'])
    keys = [first['events'][0]['kind'], second['events'][0]['kind']]
    assert keys == (['build_failure', 'build_completed'] if sort == 'asc'
                    else ['build_completed', 'build_failure'])
    assert second['next_cursor'] is None


def test_kind_filter_and_cursor_allow_incremental_search(monkeypatch):
    log = _fixture_log(monkeypatch)
    log.SCAN_LIMIT = 1
    first = log.list_events(kind='build_failure', search='networks')
    assert first['events'][0]['metric'] == 'NETWORKS'
    assert first['next_cursor']


def test_invalid_cursor_and_date_range_fail(monkeypatch):
    log = _fixture_log(monkeypatch)
    with pytest.raises(ValueError):
        log.list_events(cursor='invalid')
    with pytest.raises(ValueError):
        log.list_events(date_from=date(2026, 11, 9), date_to=date(2026, 11, 8))
