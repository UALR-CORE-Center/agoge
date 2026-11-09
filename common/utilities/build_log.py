"""Administrative build history from lifecycle events and recorded incidents."""

from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
from heapq import merge
import re

from google.cloud.firestore_v1 import FieldFilter

from common.constants.database import DbCollections
from common.utilities.build_incidents import BuildIncidents


class BuildLog:
    EVENT_KINDS = frozenset({'build_started', 'build_completed', 'build_error', 'cleanup_completed'})
    INCIDENT_KINDS = frozenset({'build_failure', 'build_blocked', 'cleanup_failed'})
    KINDS = EVENT_KINDS | INCIDENT_KINDS
    SCAN_LIMIT = 400
    SEARCH_FIELDS = BuildIncidents.STAFF_FIELDS + BuildIncidents.ADMIN_FIELDS

    def __init__(self, db, project: str):
        self.db = db
        self.project = project

    def record_event(self, kind, *, unit_id, workout_id=None, attempt_id=None, event_id=None,
                     stage=None, reason=None, resource=None):
        """Save one row per build attempt and outcome, without changing lab state."""
        if kind not in self.EVENT_KINDS or not unit_id:
            raise ValueError('Invalid build lifecycle event')
        if kind == 'build_error':
            stage = self._label(stage) or 'build'
        else:
            stage = 'cleanup' if kind == 'cleanup_completed' else 'build'
        reason = self._label(reason)
        resource = self._label(resource)
        collection = self.db.db.collection(DbCollections.BUILD_EVENT.value)
        identity = (self.project, unit_id, workout_id, attempt_id or event_id or 'legacy')

        def ref_for(event_kind, event_stage, event_reason, event_resource=None):
            key = sha256(repr((identity, event_kind, event_stage, event_reason, event_resource)).encode()).hexdigest()[:32]
            return collection.document(key)

        # A deletion redelivery can carry a different event ID for a legacy lab.
        if kind == 'cleanup_completed':
            identity = (self.project, unit_id, workout_id, attempt_id or 'legacy')
        ref = ref_for(kind, stage, reason, resource)
        now = datetime.now(timezone.utc).isoformat()
        event = {
            'id': ref.id, 'unit_id': unit_id, 'workout_id': workout_id, 'project': self.project,
            'kind': kind, 'stage': stage, 'reason': reason, 'resource': resource,
            'event_id': event_id, 'occurred_at': now,
        }

        def record(transaction):
            if ref.get(transaction=transaction).exists:
                return
            if kind == 'build_completed':
                start_ref = ref_for('build_started', 'build', None)
                if not start_ref.get(transaction=transaction).exists:
                    return
            transaction.set(ref, event)

        self.db.transaction(record)

    @staticmethod
    def _label(value):
        return value if isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9_ -]{1,80}', value) else None

    @staticmethod
    def _sort_key(row):
        return row['occurred_at'], row['id']

    @staticmethod
    def _parse_cursor(cursor):
        if not cursor:
            return None
        timestamp, separator, identifier = cursor.partition('|')
        if not separator or not re.fullmatch(r'[a-f0-9]{32}', identifier):
            raise ValueError('Invalid build log cursor')
        try:
            parsed = datetime.fromisoformat(timestamp)
        except ValueError as error:
            raise ValueError('Invalid build log cursor timestamp') from error
        if parsed.utcoffset() != timedelta(0) or parsed.isoformat() != timestamp:
            raise ValueError('Invalid build log cursor timestamp')
        return timestamp, identifier

    def _source(self, source, *, ascending, start, end, cursor):
        collection = self.db.db.collection(source.value)
        query = collection
        if start:
            query = query.where(filter=FieldFilter('occurred_at', '>=', start.isoformat()))
        if end and end < date.max:
            until = end + timedelta(days=1)
            query = query.where(filter=FieldFilter('occurred_at', '<', until.isoformat()))
        order = 'ASCENDING' if ascending else 'DESCENDING'
        query = query.order_by('occurred_at', direction=order).order_by('__name__', direction=order)
        if cursor:
            timestamp, identifier = cursor
            query = query.start_after({'occurred_at': timestamp, '__name__': collection.document(identifier)})
        for snapshot in query.limit(self.SCAN_LIMIT + 1).stream():
            yield {**snapshot.to_dict(), 'id': snapshot.id}

    def list_events(self, *, date_from=None, date_to=None, kind=None, search=None, sort='desc',
                    cursor=None, page_size=50):
        if date_from and date_to and date_from > date_to:
            raise ValueError('From date must be on or before the to date')
        position = self._parse_cursor(cursor)
        ascending = sort == 'asc'
        sources = []
        if not kind or kind in self.EVENT_KINDS:
            sources.append(DbCollections.BUILD_EVENT)
        if not kind or kind in self.INCIDENT_KINDS:
            sources.append(DbCollections.BUILD_INCIDENT)
        rows = merge(
            *(self._source(source, ascending=ascending, start=date_from, end=date_to, cursor=position)
              for source in sources),
            key=self._sort_key, reverse=not ascending,
        )
        words = (search or '').casefold().split()
        events = []
        next_cursor = None
        previous = None
        for scanned, row in enumerate(rows, 1):
            if row.get('kind') in self.KINDS and (not kind or row['kind'] == kind):
                haystack = ' '.join(str(row.get(field, '')) for field in self.SEARCH_FIELDS).casefold()
                if all(word in haystack for word in words):
                    if len(events) == page_size:
                        next_cursor = '|'.join(self._sort_key(previous))
                        break
                    events.append(BuildIncidents.projection(row, admin=True))
            previous = row
            if scanned >= self.SCAN_LIMIT:
                if next(rows, None) is not None:
                    next_cursor = '|'.join(self._sort_key(row))
                break
        return {'events': events, 'next_cursor': next_cursor}
