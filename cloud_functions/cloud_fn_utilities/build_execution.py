from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
import time
from uuid import uuid4

from google.api_core.exceptions import NotFound as GoogleNotFound

from common.constants.build_constants import BuildConstants
from common.constants.database import DbCollections
from common.constants.google import OperationType
from common.constants.pub_sub import PubSub
from common.constants.states import ServerStates, UnitStates, WorkoutStates
from common.exceptions import BadRequest, Conflict
from common.utilities.gcp.compute.compute_operations import ComputeOperationsAPI
from common.utilities.gcp.compute.quota_failure import ComputeQuotaFailure


class BuildSuperseded(Exception):
    """The build was replaced, failed, or entered cleanup."""


_PENDING_CREATES = 'pending_compute_creates'
# The deployed Pub/Sub function has a 540-second timeout. A worker that
# stopped before recording an operation cannot issue a request after this.
_SUBMISSION_WINDOW_SECONDS = 600


def server_owner(db, server_id):
    """Resolve a child job through its persisted ownership, never its name."""
    server = db.get(DbCollections.SERVER, server_id) or {}
    parent_id = server.get('parent_id')
    parent_type = server.get('parent_build_type')
    if not parent_id:
        return None, None
    if parent_type in (BuildConstants.BuildType.WORKOUT, BuildConstants.BuildType.ESCAPE_ROOM):
        return DbCollections.WORKOUT, parent_id
    if parent_type == BuildConstants.BuildType.UNIT:
        return DbCollections.UNIT, parent_id

    workout = db.get(DbCollections.WORKOUT, parent_id)
    unit = db.get(DbCollections.UNIT, parent_id)
    if bool(workout) == bool(unit):
        return None, None
    return (DbCollections.WORKOUT if workout else DbCollections.UNIT), parent_id


@dataclass(frozen=True)
class BuildExecution:
    db: object
    collection: DbCollections
    target_id: str
    unit_id: str
    attempt_id: str | None
    server_id: str | None = None

    def _check(self, owner, unit, server=None):
        if (
            not owner
            or owner.get('build_attempt_id') != self.attempt_id
            or owner.get('state') in (WorkoutStates.EXPIRED.value, WorkoutStates.MISFIT.value)
            or (owner.get('state') or 0) >= WorkoutStates.DELETING_SERVERS.value
            or (owner.get('state') == WorkoutStates.BROKEN.value and owner.get('build_failure_id'))
            or not unit
            or unit.get('state') in (UnitStates.EXPIRED.value, UnitStates.MISFIT.value)
            or (unit.get('state') or 0) >= UnitStates.DELETING_SERVERS.value
            or (self.collection == DbCollections.WORKOUT and unit.get('state') == UnitStates.BROKEN.value)
        ):
            raise BuildSuperseded()
        if self.server_id and server and server.get('state') in (
            ServerStates.DELETING.value, ServerStates.DELETED.value,
        ):
            raise BuildSuperseded()
        if self.server_id and owner.get('state') in (UnitStates.RUNNING.value, UnitStates.READY.value):
            raise BuildSuperseded()

    def check(self):
        owner = self.db.get(self.collection, self.target_id) or {}
        unit = owner if self.collection == DbCollections.UNIT else self.db.get(DbCollections.UNIT, self.unit_id)
        server = self.db.get(DbCollections.SERVER, self.server_id) if self.server_id else None
        self._check(owner, unit, server)
        return owner

    def update(self, collection, doc_id, patch, *, create=False):
        """Check the active attempt and write state in the same transaction."""
        owner_ref = self.db.db.collection(self.collection.value).document(self.target_id)
        unit_ref = self.db.db.collection(DbCollections.UNIT.value).document(self.unit_id)
        destination = self.db.db.collection(collection.value).document(doc_id)

        def write(transaction):
            owner = owner_ref.get(transaction=transaction).to_dict() or {}
            unit = owner if self.collection == DbCollections.UNIT else unit_ref.get(transaction=transaction).to_dict()
            if collection == self.collection and doc_id == self.target_id:
                existing = owner
            else:
                existing = destination.get(transaction=transaction).to_dict() or {}
            server = existing if collection == DbCollections.SERVER else None
            self._check(owner, unit, server)
            state = existing.get('state')
            next_state = patch.get('state')
            if state is not None and next_state is not None:
                if (collection == self.collection and doc_id == self.target_id and next_state < state
                        and state != WorkoutStates.BROKEN.value):
                    raise BuildSuperseded()
                if collection == DbCollections.SERVER and state in (
                    ServerStates.RUNNING.value, ServerStates.DELETING.value, ServerStates.DELETED.value,
                ) and next_state in (ServerStates.START.value, ServerStates.BUILDING.value):
                    raise BuildSuperseded()
            if create and existing:
                # Build redelivery must never replace a newer child or reset
                # a child that has already progressed in its own build.
                if (existing.get('parent_id') != self.unit_id
                        or existing.get('build_attempt_id') != patch.get('build_attempt_id')):
                    raise BuildSuperseded()
                return
            transaction.set(destination, patch, merge=True)

        self.db.transaction(write)

    def reserve_create(self, key, pending, server_id):
        owner_ref = self.db.db.collection(self.collection.value).document(self.target_id)
        unit_ref = self.db.db.collection(DbCollections.UNIT.value).document(self.unit_id)
        server_ref = self.db.db.collection(DbCollections.SERVER.value).document(server_id) if server_id else None

        def reserve(transaction):
            owner = owner_ref.get(transaction=transaction).to_dict() or {}
            unit = owner if self.collection == DbCollections.UNIT else unit_ref.get(transaction=transaction).to_dict()
            server = server_ref.get(transaction=transaction).to_dict() if server_ref else None
            self._check(owner, unit, server)
            if server and server.get('state') in (ServerStates.DELETING.value, ServerStates.DELETED.value):
                raise BuildSuperseded()
            operations = owner.get(_PENDING_CREATES) or {}
            existing = operations.get(key)
            if existing and existing.get('operation_id'):
                return existing
            if existing and existing['expires_at'] > time.time():
                raise ConnectionError('Compute creation is awaiting its provider operation')
            transaction.update(owner_ref, {_PENDING_CREATES: {**operations, key: pending}})
            return pending

        return self.db.transaction(reserve)


_execution = ContextVar('build_execution', default=None)


@contextmanager
def build_execution(execution):
    token = _execution.set(execution)
    try:
        yield
    finally:
        _execution.reset(token)


def current_build_execution():
    return _execution.get()


def ensure_current_build():
    if execution := current_build_execution():
        execution.check()


def build_message_attempt():
    execution = current_build_execution()
    if execution and execution.attempt_id:
        return {PubSub.EventAttributes.BUILD_ATTEMPT_ID: execution.attempt_id}
    return {}


def _change_pending_create(db, collection, target_id, key, token, *, operation_id=None):
    ref = db.db.collection(collection.value).document(target_id)

    def change(transaction):
        record = ref.get(transaction=transaction).to_dict() or {}
        operations = record.get(_PENDING_CREATES) or {}
        existing = operations.get(key)
        if not existing or existing['token'] != token:
            return
        if operation_id:
            operations[key] = {**existing, 'operation_id': operation_id}
        else:
            operations.pop(key)
        transaction.update(ref, {_PENDING_CREATES: operations})

    db.transaction(change)


def _wait_for_create(client, pending, *, seconds=150):
    """Return whether the accepted operation ended, or raise its terminal error."""
    return client.wait_for_operation(
        pending['operation_id'],
        OperationType[pending['operation_type']],
        wait_seconds=seconds,
        project=pending['project'],
        location=pending['location'],
        action='create',
    )


def tracked_compute_create(client, resource_name, operation_type, *, server_id=None, **resource):
    """Persist the provider operation so a concurrent delete can reconcile it."""
    execution = current_build_execution()
    if execution is None:
        return client.create(resource_name=resource_name, wait=True, **resource)

    for delay in (1, 2, None):
        try:
            return _tracked_compute_create(execution, client, resource_name, operation_type, server_id, resource)
        except ComputeQuotaFailure as error:
            # Retry a known rejection; never resubmit after an ambiguous poll.
            if delay is None or error.category != 'rate' or error.action not in ('create', 'insert'):
                raise
            time.sleep(delay)


def _tracked_compute_create(execution, client, resource_name, operation_type, server_id, resource):

    location = {
        OperationType.GLOBAL: None,
        OperationType.REGION: client.region,
        OperationType.ZONE: client.zone,
    }[operation_type]
    key = f'{client.resource_type.name}/{location or "global"}/{resource_name}'
    pending = execution.reserve_create(key, {
        'token': uuid4().hex,
        'resource': resource_name,
        'resource_type': client.resource_type.name,
        'project': client.project,
        'operation_type': operation_type.name,
        'location': location,
        'expires_at': time.time() + _SUBMISSION_WINDOW_SECONDS,
    }, server_id)

    def change(**changes):
        _change_pending_create(
            execution.db, execution.collection, execution.target_id, key, pending['token'], **changes,
        )

    if not pending.get('operation_id'):
        try:
            operation = client.create(resource_name=resource_name, wait=False, **resource)
        except (ComputeQuotaFailure, Conflict, BadRequest):
            change()
            raise
        pending = {**pending, 'operation_id': operation.name}
        change(operation_id=operation.name)

    try:
        finished = _wait_for_create(client, pending)
    except ComputeQuotaFailure as error:
        error.add_context(resource=resource_name, resource_type=client.resource_type.name)
        if error.action != 'wait':
            change()
        raise
    except RuntimeError:
        # The Compute waiter raises RuntimeError for a completed operation
        # that contains a non-quota provider error.
        change()
        raise
    if finished:
        change()
    return finished


def wait_for_pending_creates(db, collection, target_id, *, server_id=None):
    """Keep cleanup pending until accepted creates can no longer race deletion."""
    record = db.get(collection, target_id) or {}
    for key, pending in (record.get(_PENDING_CREATES) or {}).items():
        if server_id and pending.get('resource') != server_id:
            continue
        if operation_id := pending.get('operation_id'):
            operations = ComputeOperationsAPI(
                project=pending['project'], region=pending['location'], zone=pending['location'],
            )
            try:
                finished = operations.wait(
                    operation_id, type_=OperationType[pending['operation_type']], wait_seconds=15,
                    action='create', project=pending['project'], location=pending['location'],
                )
            except ComputeQuotaFailure as error:
                if error.action == 'wait':
                    raise
                finished = True
            except (RuntimeError, GoogleNotFound):
                finished = True
            if not finished:
                raise ConnectionError('Compute creation is still pending; cleanup can retry')
        elif pending['expires_at'] > time.time():
            raise ConnectionError('Compute creation submission is still pending; cleanup can retry')
        _change_pending_create(db, collection, target_id, key, pending['token'])
