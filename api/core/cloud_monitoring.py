import csv
from datetime import date, datetime, time, timedelta, timezone
from hashlib import sha256
from io import StringIO

from common.constants.database import DATABASE_NAME, DatabaseTypes, DbCollections, DbOperators
from common.document_database import DocumentDatabaseFactory
from common.exceptions import BadRequest
from common.utilities.gcp.cloud_logger import LoggerNames
from common.utilities.workout_runtime import next_month, utc_time


NOTES = [
    'Runtime measures time in Agoge’s Running state in UTC. It is separate from billable Google Cloud usage.',
    'Open runs are counted through the report time and may change when the workout stops.',
    'Web-only workouts can appear as successful builds with zero VM workout runtime.',
    'Earlier runs and first build dates are unavailable unless Agoge observed their transitions after tracking was deployed.',
    'A reassigned workout can appear under multiple students. Each run stays with the student recorded when it began.',
]

CSV_FIELDS = (
    'workout_id', 'unit_id', 'lab_name', 'student_name', 'student_email', 'build_date',
    'started_at', 'last_seen_at', 'runtime_seconds', 'run_count', 'running',
)


class CloudMonitoring:
    def __init__(self, db=None):
        self.db = db if db is not None else DocumentDatabaseFactory.create_db_object(
            db_type=DatabaseTypes.firestore, database_name=DATABASE_NAME, log_name=LoggerNames.API,
        )

    @staticmethod
    def period(month=None, start=None, end=None, *, now=None, history=False):
        now = now or datetime.now(timezone.utc)
        if month:
            try:
                first = date.fromisoformat(f'{month}-01')
                month_end = (next_month(datetime.combine(first, time.min, timezone.utc)) - timedelta(days=1)).date()
            except ValueError as error:
                raise BadRequest('Choose a month in YYYY-MM format.') from error
            start, end = start or first, end or month_end
            if not first <= start <= end <= month_end:
                raise BadRequest('Choose dates within the selected month.')
        elif start is None and end is None:
            first = now.date().replace(day=1)
            month_end = (next_month(datetime.combine(first, time.min, timezone.utc)) - timedelta(days=1)).date()
            if history:
                for _ in range(11):
                    first = (first - timedelta(days=1)).replace(day=1)
            start, end = first, month_end
        elif start is None or end is None:
            raise BadRequest('Choose both a start date and an end date.')
        if start > end or (end - start).days >= 366:
            raise BadRequest('Choose a date range of up to 366 days.')
        if end >= date.max - timedelta(days=31):
            raise BadRequest('Choose an earlier end date.')
        return datetime.combine(start, time.min, timezone.utc), datetime.combine(
            end + timedelta(days=1), time.min, timezone.utc,
        )

    @staticmethod
    def _months(start, stop):
        value = start.replace(day=1)
        while value < stop:
            yield value.strftime('%Y-%m'), value, next_month(value)
            value = next_month(value)

    def report(self, start, stop, *, q='', sort='build_date', direction='desc', now=None):
        now = now or datetime.now(timezone.utc)
        windows = list(self._months(start, stop))
        live_runs = self.db.query(DbCollections.WORKOUT_RUNTIME, [('kind', DbOperators.EQUAL, 'live')]) or []
        records = self.db.query(
            DbCollections.WORKOUT_RUNTIME, [('month', DbOperators.IN, [month for month, _, _ in windows])],
        ) or []
        # A stop can commit between the two reads. Prefer its closed segments
        # over the live row returned by the earlier query.
        closed_ids = {record['session_id'] for record in records if record.get('session_id')}
        records.extend(record for record in live_runs if record.get('session_id') not in closed_ids)
        entries = {}
        for record in records:
            workout_id = record.get('workout_id')
            if not workout_id:
                continue
            if record.get('kind') == 'build':
                built = utc_time(record.get('build_date'))
                if built and start <= built < min(stop, now):
                    self._entry(entries, record)['months'].setdefault(built.strftime('%Y-%m'), 0.0)
                continue

            opened = utc_time(record.get('started_at'))
            live = record.get('kind') == 'live'
            closed = now if live else utc_time(record.get('ended_at'))
            if not opened or not closed or max(start, opened) >= min(stop, closed, now):
                continue
            entry = self._entry(entries, record)
            session = record.get('session_id') or f'{workout_id}-{opened:%Y%m%d%H%M%S%f}'
            entry['runs'].add(session)
            entry['running'] = entry['running'] or live
            for month, first, after in windows:
                segment_start, segment_stop = max(start, opened, first), min(stop, closed, now, after)
                if segment_start >= segment_stop:
                    continue
                entry['months'][month] = entry['months'].get(month, 0.0) + (segment_stop - segment_start).total_seconds()
                entry['month_runs'].setdefault(month, set()).add(session)
                entry['started_at'] = min(entry['started_at'] or segment_start, segment_start)
                entry['last_seen_at'] = max(entry['last_seen_at'] or segment_stop, segment_stop)

        self._load_student_names(entries)
        needle = q.strip().casefold()
        filtered = [entry for entry in entries.values() if self._matches(entry, needle)]
        rows = [self._row(entry) for entry in filtered]
        self._sort(rows, sort, direction)
        months = [
            {
                'month': month,
                'workouts': len({entry['workout_id'] for entry in filtered if month in entry['months']}),
                'run_count': len(set().union(*(entry['month_runs'].get(month, set()) for entry in filtered))),
                'runtime_seconds': round(sum(entry['months'].get(month, 0) for entry in filtered), 3),
            }
            for month, _, _ in windows
        ]
        return {
            'month': windows[0][0] if len(windows) == 1 else None,
            'start': start.date().isoformat(),
            'end': (stop - timedelta(days=1)).date().isoformat(),
            'rows': rows, 'total': len(rows),
            'total_workouts': len({entry['workout_id'] for entry in filtered}),
            'total_runtime_seconds': round(sum(sum(entry['months'].values()) for entry in filtered), 3),
            'months': months, 'notes': NOTES,
        }

    @staticmethod
    def _entry(entries, record):
        workout_id = record['workout_id']
        identity = str(record.get('student_email') or record.get('student_name') or '').casefold()
        row_id = f'{workout_id}-{sha256(identity.encode()).hexdigest()[:12]}'
        entry = entries.setdefault(row_id, {
            'row_id': row_id, 'workout_id': workout_id, 'unit_id': None, 'lab_name': None,
            'student_name': None, 'student_email': None, 'build_date': None,
            'started_at': None, 'last_seen_at': None, 'running': False, 'runs': set(),
            'months': {}, 'month_runs': {},
        })
        for field in ('unit_id', 'lab_name', 'student_name', 'student_email', 'build_date'):
            if entry[field] is None:
                entry[field] = utc_time(record.get(field)) if field == 'build_date' else record.get(field)
        return entry

    def _load_student_names(self, entries):
        emails = sorted({entry['student_email'] for entry in entries.values()
                         if entry['student_email'] and not entry['student_name']})
        names = {}
        for first in range(0, len(emails), 30):
            users = self.db.query(DbCollections.USERS, [('email', DbOperators.IN, emails[first:first + 30])]) or []
            names.update({user['email']: user.get('name') for user in users if user.get('email')})
        for entry in entries.values():
            if not entry['student_name']:
                entry['student_name'] = names.get(entry['student_email'])

    @staticmethod
    def _matches(entry, needle):
        return not needle or any(needle in str(entry.get(field) or '').casefold() for field in (
            'workout_id', 'unit_id', 'lab_name', 'student_name', 'student_email',
        ))

    @staticmethod
    def _row(entry):
        row = {field: value for field, value in entry.items() if field not in ('months', 'month_runs', 'runs')}
        row['runtime_seconds'] = round(sum(entry['months'].values()), 3)
        row['run_count'] = len(entry['runs'])
        for field in ('build_date', 'started_at', 'last_seen_at'):
            if row[field]:
                row[field] = row[field].isoformat()
        return row

    @staticmethod
    def _sort(rows, sort, direction):
        def sort_value(row):
            value = row[sort]
            return value.casefold() if isinstance(value, str) else value

        rows.sort(key=lambda row: row['row_id'])
        known = sorted((row for row in rows if row[sort] is not None), key=sort_value, reverse=direction == 'desc')
        rows[:] = known + [row for row in rows if row[sort] is None]

    @staticmethod
    def csv(rows):
        output = StringIO(newline='')
        writer = csv.writer(output)
        writer.writerow(CSV_FIELDS)
        for row in rows:
            writer.writerow(CloudMonitoring._csv_value(row.get(field)) for field in CSV_FIELDS)
        return output.getvalue()

    @staticmethod
    def _csv_value(value):
        if isinstance(value, str) and (
            value.startswith(('\t', '\r', '\n')) or value.lstrip().startswith(('=', '+', '-', '@'))
        ):
            return "'" + value
        return value
