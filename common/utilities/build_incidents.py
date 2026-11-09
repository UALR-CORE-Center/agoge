"""Durable build incidents and the project-wide Compute NETWORKS admission hold."""

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from uuid import uuid4

from google.cloud.firestore_v1 import FieldFilter

from common.constants.database import DbCollections, DbOperators
from common.constants.states import UnitStates, WorkoutStates
from common.exceptions import ServiceUnavailable


class LabBuildUnavailable(ServiceUnavailable):
    def __init__(self, message: str, *, public: bool = False):
        super().__init__(message)
        self.public = public


class BuildQuotaHold(LabBuildUnavailable):
    def __init__(self, hold: dict, *, public: bool = False):
        super().__init__(
            'New labs that need a Google Cloud network are paused. Contact your Agoge administrator.',
            public=public,
        )
        self.hold = hold


class BuildIncidents:
    """Use narrow, attempt-checked Firestore writes to keep workers and the UI in sync."""

    NETWORK_METRICS = {'NETWORKS', 'compute.googleapis.com/networks'}
    STAFF_FIELDS = (
        'id', 'unit_id', 'workout_id', 'project', 'kind', 'status', 'stage', 'reason',
        'metric', 'limit_name', 'limit', 'scope', 'occurred_at', 'resolved_at', 'resolution',
    )
    ADMIN_FIELDS = ('operation_id', 'operation_type', 'resource', 'resource_type',
                    'action', 'event_id', 'category', 'dimensions')

    def __init__(self, db, project: str):
        self.db = db
        self.project = project

    @staticmethod
    def _key(*parts) -> str:
        return sha256(repr(parts).encode()).hexdigest()[:32]

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _ref(self, collection, doc_id):
        return self.db.db.collection(collection.value).document(doc_id)

    @staticmethod
    def _read(ref, transaction=None) -> dict:
        snapshot = ref.get(transaction=transaction) if transaction is not None else ref.get()
        return snapshot.to_dict() if snapshot.exists is True else {}

    def _hold_ref(self, project=None):
        return self._ref(DbCollections.BUILD_QUOTA_HOLD, self._key(project or self.project, 'NETWORKS', 'global'))

    def active_hold(self) -> dict | None:
        hold = self._read(self._hold_ref())
        return hold if hold.get('active') is True else None

    def require_network_capacity(self, *, public: bool = False) -> None:
        if hold := self.active_hold():
            raise BuildQuotaHold(hold, public=public)

    def require_lab_build(self, unit: dict, *, needs_network: bool, public: bool = False,
                          retry_shared: bool = False) -> None:
        state = unit.get('state')
        if state in (UnitStates.DELETING_SERVERS.value, UnitStates.COMPLETED_DELETING_SERVERS.value,
                     UnitStates.DELETED.value) or (unit.get('build_failure_id') and not retry_shared):
            raise LabBuildUnavailable(
                'This lab is currently unavailable. Contact your instructor or Agoge administrator.',
                public=public,
            )
        if needs_network:
            self.require_network_capacity(public=public)

    @staticmethod
    def _target(unit_id, workout_id):
        if workout_id:
            return DbCollections.WORKOUT, workout_id
        return DbCollections.UNIT, unit_id

    @staticmethod
    def _matches(target, attempt_id):
        return bool(target) and target.get('build_attempt_id') == attempt_id

    def begin_attempt(self, collection, target_id, *, retry=False, attempt_id=None) -> str | None:
        ref = self._ref(collection, target_id)
        states = WorkoutStates if collection == DbCollections.WORKOUT else UnitStates
        fresh_id = attempt_id or uuid4().hex

        def begin(transaction):
            target = self._read(ref, transaction)
            if not target:
                return None
            state = target.get('state') or states.START.value
            existing_id = target.get('build_attempt_id')
            if state == states.BROKEN.value and retry and target.get('build_failure_id'):
                transaction.update(ref, {
                    'build_attempt_id': fresh_id, 'build_failure_id': None,
                    'state': states.START.value,
                })
                return fresh_id
            if state >= states.RUNNING.value or target.get('build_failure_id'):
                return None
            if existing_id:
                return existing_id if attempt_id is None or existing_id == attempt_id else None
            transaction.update(ref, {'build_attempt_id': fresh_id})
            return fresh_id

        return self.db.transaction(begin)

    def current_failure(self, *, unit_id, workout_id=None) -> dict | None:
        collection, target_id = self._target(unit_id, workout_id)
        if not target_id:
            return None
        target = self._read(self._ref(collection, target_id))
        if failure_id := target.get('build_failure_id'):
            incident = self._read(self._ref(DbCollections.BUILD_INCIDENT, failure_id))
            if incident.get('status') == 'open' and incident.get('attempt_id') == target.get('build_attempt_id'):
                return incident
        return None

    def record_quota(self, error, *, unit_id=None, workout_id=None, stage=None, event_id=None,
                     attempt_id=None, target_patch=None) -> dict | None:
        data = error.as_dict()
        data['project'] = error.project or self.project
        global_networks = (
            error.category == 'allocation' and error.scope == 'global'
            and (error.metric in self.NETWORK_METRICS or error.limit_name == 'NETWORKS-per-project')
        )
        return self._record(
            'build_failure', data, unit_id, workout_id, stage, event_id, attempt_id, target_patch,
            open_hold=global_networks,
        )

    def record_blocked(self, error: BuildQuotaHold, *, unit_id=None, workout_id=None, stage=None,
                       event_id=None, attempt_id=None, target_patch=None) -> dict | None:
        details = {field: error.hold.get(field) for field in ('project', 'metric', 'limit_name', 'limit', 'scope')}
        details['reason'] = 'PROJECT_QUOTA_HOLD'
        return self._record('build_blocked', details, unit_id, workout_id, stage, event_id, attempt_id, target_patch)

    def record_cleanup_failure(self, *, unit_id, workout_id=None, stage=None, event_id=None,
                               attempt_id=None) -> dict | None:
        return self._record(
            'cleanup_failed', {'project': self.project, 'reason': 'CLEANUP_UNCONFIRMED'},
            unit_id, workout_id, stage or 'cleanup', event_id, attempt_id, None,
        )

    def _record(self, kind, details, unit_id, workout_id, stage, event_id, attempt_id, target_patch, *, open_hold=False):
        collection, target_id = self._target(unit_id, workout_id)
        target_ref = self._ref(collection, target_id) if target_id else None
        parent_ref = self._ref(DbCollections.UNIT, unit_id) if workout_id and unit_id else None
        project = details['project']
        delivery = event_id if kind == 'cleanup_failed' or stage in ('rebuild', 'server_rebuild') else attempt_id
        if open_hold and details.get('operation_id'):
            # Distinct provider operations can both reject a concurrent write.
            # A newer observation must be able to reopen a just-cleared hold.
            delivery = (attempt_id, details['operation_id'])
        key = self._key(project, kind, target_id, delivery or event_id or details.get('operation_id'),
                        stage, details.get('resource'), details.get('metric'), details['reason'])
        ref = self._ref(DbCollections.BUILD_INCIDENT, key)
        hold_ref = self._hold_ref(project) if open_hold else None
        now = self._now()
        generation = uuid4().hex
        states = WorkoutStates if workout_id else UnitStates

        def record(transaction):
            if existing := self._read(ref, transaction):
                return existing
            target = self._read(target_ref, transaction) if target_ref is not None else {}
            parent = self._read(parent_ref, transaction) if parent_ref is not None else None
            hold = self._read(hold_ref, transaction) if hold_ref is not None else {}
            state = target.get('state') or states.START.value
            current = self._matches(target, attempt_id)
            eligible = current and (
                state < states.RUNNING.value or (state == states.BROKEN.value and target.get('build_failure_id'))
            )
            if parent is not None:
                eligible = (
                    eligible and bool(parent) and target.get('parent_id') == unit_id
                    and (parent.get('state') or UnitStates.START.value) < UnitStates.EXPIRED.value
                )
            stale_cleanup = kind == 'cleanup_failed' and (
                (attempt_id is not None and not current) or state == states.DELETED.value
            )
            if hold_ref is not None:
                transaction.set(hold_ref, self._open_hold(hold, project, now, generation, details, key))
            if stale_cleanup or (target_id and kind != 'cleanup_failed' and not eligible and not open_hold):
                return None
            # A real provider rejection may still justify the project hold after the
            # lab was deleted or superseded. Keep that observation unattached.
            if target_id and kind != 'cleanup_failed' and not eligible:
                attached_unit, attached_workout = None, None
            else:
                attached_unit, attached_workout = unit_id, workout_id
            fields = set(self.STAFF_FIELDS + self.ADMIN_FIELDS)
            incident = {field: value for field, value in details.items() if field in fields and value is not None}
            incident.update(
                id=key, unit_id=attached_unit, workout_id=attached_workout, attempt_id=attempt_id,
                event_id=event_id, kind=kind, stage=stage or 'provisioning', status='open',
                occurred_at=now, open_sort_at=f'{now}/{key}',
            )
            transaction.set(ref, incident)
            if target_patch and eligible:
                previous_failure = target.get('build_failure_id')
                if state != states.BROKEN.value or not previous_failure:
                    transaction.update(target_ref, {**target_patch, 'build_failure_id': previous_failure or key})
            return incident

        return self.db.transaction(record)

    @staticmethod
    def _open_hold(existing, project, now, generation, details, incident_id):
        active = existing.get('active') is True
        return {
            'id': existing.get('id') or BuildIncidents._key(project, 'NETWORKS', 'global'),
            'active': True, 'project': project, 'metric': 'NETWORKS', 'scope': 'global',
            'limit': details.get('limit') if details.get('limit') is not None else existing.get('limit'),
            'limit_name': details.get('limit_name') or existing.get('limit_name'),
            'usage': details.get('usage') if 'usage' in details else None,
            'verified_at': details.get('verified_at') if 'verified_at' in details else None,
            'incident_id': incident_id or (existing.get('incident_id') if active else None),
            'first_seen_at': existing.get('first_seen_at') if active else now,
            'last_seen_at': now, 'generation': generation,
        }

    def update_verified_quota(self, previous: dict | None, *, usage: float, limit: float, verified_by: str) -> dict | None:
        """Apply a fresh provider reading if no intervening worker has changed the hold."""
        ref = self._hold_ref()
        now = self._now()
        generation = uuid4().hex
        expected = (previous or {}).get('generation')

        def verify(transaction):
            existing = self._read(ref, transaction)
            active = existing.get('active') is True
            if active and existing.get('generation') != expected:
                return existing
            if not active and expected is not None:
                return None
            details = {'usage': usage, 'limit': limit, 'verified_at': now}
            if limit - usage < 1:
                hold = self._open_hold(existing, self.project, now, generation, details, None)
                transaction.set(ref, {**hold, 'verified_by': verified_by})
                return hold
            if active:
                transaction.update(ref, {
                    **details, 'active': False, 'cleared_at': now,
                    'verified_by': verified_by, 'generation': generation,
                })
            return None

        return self.db.transaction(verify)

    @classmethod
    def projection(cls, incident, *, admin=False):
        fields = cls.STAFF_FIELDS + cls.ADMIN_FIELDS if admin else cls.STAFF_FIELDS
        return {field: incident[field] for field in fields if incident.get(field) is not None}

    @staticmethod
    def hold_projection(hold):
        if not hold:
            return None
        fields = (
            'id', 'project', 'metric', 'limit_name', 'limit', 'scope', 'usage', 'incident_id',
            'first_seen_at', 'last_seen_at', 'verified_at',
        )
        return {field: hold[field] for field in fields if hold.get(field) is not None}

    def for_unit(self, unit_id):
        incidents = self._unit_incidents(unit_id)
        current = [incident for incident in incidents if incident.get('status') == 'open'
                   and incident.get('kind') in ('build_failure', 'build_blocked', 'cleanup_failed')]
        return [self.projection(incident) for incident in sorted(current, key=lambda row: row['occurred_at'], reverse=True)]

    def _unit_incidents(self, unit_id):
        return self.db.query(
            collection_name=DbCollections.BUILD_INCIDENT,
            filters=[('unit_id', DbOperators.EQUAL, unit_id)],
        ) or []

    def resolve_target(self, *, unit_id, workout_id=None, resolution='cleanup_confirmed', attempt_id=None):
        collection, target_id = self._target(unit_id, workout_id)
        if not target_id or not unit_id:
            return
        target_ref = self._ref(collection, target_id)
        now = self._now()
        expires = datetime.now(timezone.utc) + timedelta(days=30)
        states = WorkoutStates if workout_id else UnitStates
        finished = (states.DELETED.value,) if resolution == 'cleanup_confirmed' else (
            states.READY.value, states.RUNNING.value,
        )
        for incident in self._unit_incidents(unit_id):
            if (incident.get('workout_id') != workout_id or incident.get('status') != 'open'
                    or (resolution == 'build_succeeded' and incident.get('kind') == 'cleanup_failed')):
                continue
            incident_ref = self._ref(DbCollections.BUILD_INCIDENT, incident['id'])

            def resolve(transaction):
                target = self._read(target_ref, transaction)
                current = self._read(incident_ref, transaction)
                if (target and target.get('state') in finished
                        and (attempt_id is None or self._matches(target, attempt_id))
                        and current.get('status') == 'open' and current.get('occurred_at', now) <= now):
                    transaction.update(incident_ref, {
                        'status': 'resolved', 'resolution': resolution,
                        'resolved_at': now, 'expires_at': expires, 'open_sort_at': None,
                    })
                    if resolution == 'build_succeeded' and target.get('build_failure_id') == current.get('id'):
                        transaction.update(target_ref, {'build_failure_id': None})

            self.db.transaction(resolve)

    def list_recent(self, *, cursor=None, page_size=50, include_resolved=False):
        collection = self.db.db.collection(DbCollections.BUILD_INCIDENT.value)
        if include_resolved:
            query = collection.order_by('occurred_at', direction='DESCENDING')
        else:
            query = collection.where(filter=FieldFilter('open_sort_at', '>', '')).order_by(
                'open_sort_at', direction='DESCENDING',
            )
        if cursor:
            snapshot = collection.document(cursor).get()
            if not snapshot.exists:
                raise ValueError('Invalid incident cursor')
            position = snapshot if include_resolved else {'open_sort_at': f"{snapshot.get('occurred_at')}/{cursor}"}
            query = query.start_after(position)
        rows = list(query.limit(page_size + 1).stream())
        return {
            'incidents': [self.projection(row.to_dict(), admin=True) for row in rows[:page_size]],
            'next_cursor': rows[page_size - 1].id if len(rows) > page_size else None,
        }
