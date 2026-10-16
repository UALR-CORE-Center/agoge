import time
from datetime import datetime, timezone
from typing import List, Optional, get_args

from google.cloud.firestore_v1 import FieldFilter
from google.cloud.firestore_v1.field_path import FieldPath
from pydantic import ValidationError

from common.constants.database import DATABASE_NAME, DatabaseTypes, DbCollections, DbOperationTypes, DbOperators
from common.constants.pub_sub import PubSub
from common.constants.states import CtfStates, WorkoutStates
from common.exceptions.agoge import BadRequest, Conflict, NotFound, ServiceUnavailable, Unauthorized
from common.models.agoge import (
    CtfActionRequest,
    CtfBoardModel,
    CtfDigestModel,
    CtfEventModel,
    CtfFlagStateModel,
    CtfLogModel,
    CtfSpecModel,
    CtfSubmissionModel,
    CtfUpdateRequest,
    LogAction,
    Verdict,
)
from common.models.model_validators.model_validator import ModelValidator
from common.models.response import (
    CtfBoardStatus,
    CtfEventSummary,
    CtfFlagBoardStatus,
    CtfFlagRow,
    CtfStateResponse,
)
from common.models.users import AgogeUser
from common.utilities.ctf_flags import derive_flag_value, flag_digest
from common.utilities.ctf_state_manager import CtfStateManager
from common.utilities.gcp.cloud_logger import Logger, LoggerNames
from common.utilities.id_generator import IdGenerator
from core.ctf import config

UNAUTHORIZED_MESSAGE = "Requesting user is not authorized to make this request"
NOT_PROVISIONED_MESSAGE = (
    "CTF is not provisioned on this deployment. Ask an administrator to enable it in setup."
)


class CtfEvent:
    """CTF event lifecycle for the instructor API (collection `agoge-ctf`)."""
    DEFAULT_MAX_BOARDS = 100
    # Firestore commits at most 500 writes; chunks are kept at or under it so
    # db.batch_write never takes its splitting path, which swallows batch errors.
    MAX_WRITES_PER_COMMIT = 500
    # Firestore's limit on the number of values in an `in` filter.
    MAX_IN_VALUES = 30
    # Cap on the submissions and log panels (endpoint table: newest first, max 500).
    MAX_PANEL_ROWS = 500
    # A workout being torn down gets no board: it can never be armed.
    EXCLUDED_WORKOUT_STATES = {
        WorkoutStates.DELETING_SERVERS.value,
        WorkoutStates.COMPLETED_DELETING_SERVERS.value,
        WorkoutStates.DELETED.value,
    }

    # Board arm statuses an arm worker has already aggregated into boards_pending.
    TERMINAL_ARM_STATUSES = ('armed', 'failed')
    ARM_PUBLISH_FAILED = "Arm message could not be published"
    # Shared deadline for every arm publish future; the request is waiting on it.
    ARM_PUBLISH_TIMEOUT_SECONDS = 30

    S = CtfStates
    # action -> (states it may start from, target state). The From sets are narrower than the
    # state manager's allow-list: (PAUSED, RUNNING) is legal there but only `resume` may use it.
    ACTIONS = {
        'arm': ({S.DRAFT, S.ARMED, S.BROKEN}, S.ARMING),
        'start': ({S.ARMED}, S.RUNNING),
        'pause': ({S.RUNNING}, S.PAUSED),
        'resume': ({S.PAUSED}, S.RUNNING),
        'end': ({S.RUNNING, S.PAUSED}, S.ENDED),
        'archive': ({S.DRAFT, S.ARMED, S.ENDED, S.BROKEN}, S.ARCHIVED),
    }

    def __init__(self, env_dict: dict = None, db=None, env=None, pubsub=None) -> None:
        self.class_name = self.__class__.__name__
        self.log_name = LoggerNames.API
        self.logger = Logger(self.log_name, class_name=self.class_name)
        self.env_dict = env_dict
        self._env = env
        if db is None:
            # Imported lazily so tests supplying a fake db need no Firestore client.
            from common.document_database.factory import DocumentDatabaseFactory

            db = DocumentDatabaseFactory.create_db_object(
                db_type=DatabaseTypes.firestore,
                database_name=DATABASE_NAME,
                log_name=self.log_name,
            )
        self.db = db
        self.state_manager = CtfStateManager(db=self.db, log_name=self.log_name)
        self._pubsub = pubsub

    @property
    def pubsub(self):
        """PubSubManager, built on first use: only `arm` publishes."""
        if self._pubsub is None:
            from common.utilities.gcp.pubsub_manager import PubSubManager

            self._pubsub = PubSubManager(topic=PubSub.Topics.AGOGE, log_name=self.log_name, env_dict=self.env_dict)
        return self._pubsub

    @property
    def env(self):
        """CloudEnv, built on first use: only operations needing the seed pay for it."""
        if self._env is None:
            from common.utilities.gcp.cloud_env import CloudEnv

            self._env = CloudEnv(log_name=self.log_name, env_dict=self.env_dict)
        return self._env

    def create(self, unit_id: str, user: AgogeUser) -> str:
        """Create a DRAFT event from a unit's `ctf` block with one board per workout and one
        digest document per board per flag. Returns the new ctf_id.

        Every check runs before the first write. Flag values are derived only to hash them
        and are never stored.
        """
        unit = self.db.get(collection_name=DbCollections.UNIT, doc_id=unit_id)
        if not unit:
            raise NotFound(message="Unit not found")
        if not unit.get('ctf'):
            raise BadRequest(message="Unit has no ctf specification")
        try:
            spec = ModelValidator(CtfSpecModel).load(unit['ctf'])
        except ValidationError as e:
            raise BadRequest(message=f"Unit ctf specification is invalid: {e.error_count()} error(s)")

        instructor_ids = unit.get('instructor_id') or []
        if isinstance(instructor_ids, str):
            instructor_ids = [instructor_ids]
        self._authorize(instructor_ids, user)

        workouts = self._unit_workouts(unit_id)
        if not workouts:
            raise BadRequest(message="Unit has no workouts")
        max_boards = self._max_boards()
        if len(workouts) > max_boards:
            raise BadRequest(
                message=f"Unit has {len(workouts)} workouts; a CTF event allows at most {max_boards}"
            )
        workout_ids = [workout['id'] for workout in workouts]
        if busy := self._workouts_on_active_boards(workout_ids):
            raise Conflict(message=f"Workout {busy[0]} is already on an active CTF board")

        seed = self.env.ctf_flag_seed
        if not seed:
            raise ServiceUnavailable(message=NOT_PROVISIONED_MESSAGE)

        ctf_id = IdGenerator.build_id()
        event = CtfEventModel(
            id=ctf_id,
            unit_id=unit_id,
            instructor_id=instructor_ids,
            spec=spec,
            creation_timestamp=time.time(),
            board_ids=workout_ids,
            state=CtfStates.DRAFT.value,
            state_timestamp=datetime.now(timezone.utc).isoformat(),
        )
        digest_docs, board_docs = [], []
        for workout in workouts:
            board, digests = self._new_board(event, workout, seed)
            board_docs.append((DbCollections.CTF_BOARD, board.id, board.model_dump()))
            digest_docs.extend((DbCollections.CTF_DIGEST, d.digest, d.model_dump()) for d in digests)
        # The event goes last, so a failed commit never leaves an event pointing at missing boards.
        event_doc = (DbCollections.CTF, ctf_id, event.model_dump(mode='json'))
        self._commit(ctf_id, [*digest_docs, *board_docs, event_doc])
        self.logger.info(
            f"{self.class_name}:{ctf_id} - Created CTF event",
            unit_id=unit_id, boards=len(board_docs), digests=len(digest_docs),
        )
        return ctf_id

    def get(self, ctf_id: str, user: AgogeUser) -> CtfEventModel:
        """The event, for an admin or one of its instructors."""
        event = self._load(ctf_id)
        self._authorize(event.instructor_id, user)
        return event

    def list(self, user: AgogeUser) -> List[CtfEventSummary]:
        """Every event the caller may operate (all of them for an admin), newest first.
        A document that fails validation is skipped, so one bad event cannot hide the rest."""
        filters = None if user.is_admin else [('instructor_id', DbOperators.ARRAY_CONTAINS, user.email)]
        docs = self.db.query(collection_name=DbCollections.CTF, filters=filters) or []
        events = ModelValidator(CtfEventModel, log_location=self.log_name).load(docs, halt_on_error=False)
        # halt_on_error=False leaves None in place of each invalid document.
        events = sorted((e for e in events if e is not None), key=lambda e: e.creation_timestamp, reverse=True)
        return [self._summary(event) for event in events]

    def update(self, ctf_id: str, request: CtfUpdateRequest, user: AgogeUser) -> CtfEventModel:
        """Apply only the fields present in the request body (`model_fields_set`), so an explicit
        `scoreboard_frozen_at: null` unfreezes while an absent one is left alone. ARCHIVED is
        read-only. Read and write share one transaction so a concurrent archive is not overrun."""
        fields = {name: getattr(request, name) for name in request.model_fields_set}
        return self.db.transaction(lambda transaction: self._update_in_transaction(transaction, ctf_id, fields, user))

    def _update_in_transaction(self, transaction, ctf_id: str, fields: dict, user: AgogeUser) -> CtfEventModel:
        doc_ref = self.db.db.collection(DbCollections.CTF.value).document(ctf_id)
        snapshot = doc_ref.get(transaction=transaction)
        if not snapshot.exists:
            raise NotFound(message="CTF event not found")
        event = ModelValidator(CtfEventModel, log_location=self.log_name).load(snapshot.to_dict())
        self._authorize(event.instructor_id, user)
        if event.state == CtfStates.ARCHIVED.value:
            raise Conflict(message="CTF event is ARCHIVED and read-only")
        if not fields:
            return event
        updated = ModelValidator(CtfEventModel, log_location=self.log_name).load({**event.model_dump(), **fields})
        dumped = updated.model_dump()
        transaction.update(doc_ref, {name: dumped[name] for name in fields})
        self.logger.info(f"{self.class_name}:{ctf_id} - Updated CTF event", fields=",".join(sorted(fields)))
        return updated

    def process_action(self, ctf_id: str, request: CtfActionRequest, user: AgogeUser) -> CtfEventModel:
        """Apply one lifecycle action (the PRD's action map) and return the transitioned event.

        The event's state, its side-effect fields, and the board updates (`arm` resets every board's
        arm_status; `archive` deactivates every board) commit in one transaction, so a failed commit
        leaves nothing half-applied. Only `arm` publishes: one CTF_ARM_BOARD per board, after the
        commit, so a worker never sees the event before it is ARMING.
        """
        action = request.action
        event = self.db.transaction(lambda transaction: self._action_in_transaction(transaction, ctf_id, action, user))
        if action == 'arm':
            self._publish_arm(event)
        return event

    def _action_in_transaction(self, transaction, ctf_id: str, action: str, user: AgogeUser) -> CtfEventModel:
        doc_ref = self.db.db.collection(DbCollections.CTF.value).document(ctf_id)
        snapshot = doc_ref.get(transaction=transaction)
        if not snapshot.exists:
            raise NotFound(message="CTF event not found")
        stored = snapshot.to_dict()
        event = ModelValidator(CtfEventModel, log_location=self.log_name).load(stored)
        self._authorize(event.instructor_id, user)
        from_states, new_state = self.ACTIONS[action]
        if event.state not in {state.value for state in from_states}:
            raise Conflict(message=f"Cannot {action} a CTF event that is {self._state_name(event.state)}")

        now = time.time()
        fields, board_update = {}, None
        if action == 'arm':
            if not event.board_ids:
                # Nothing would ever decrement boards_pending, leaving the event in ARMING for good.
                raise BadRequest(message="CTF event has no boards to arm")
            fields = {'boards_pending': len(event.board_ids)}
            board_update = {'arm_status': 'pending', 'arm_error': None}
        elif action == 'start':
            fields = {'starts_at': now}
        elif action == 'pause':
            fields = {'paused_at': now}
        elif action == 'resume':
            paused_for = max(now - (event.paused_at or now), 0.0)
            fields = {
                'accumulated_pause_seconds': event.accumulated_pause_seconds + paused_for,
                'paused_at': None,
            }
            if event.ends_at is not None:
                fields['ends_at'] = event.ends_at + paused_for
        elif action == 'end':
            fields = {'ends_at': now}
        elif action == 'archive':
            board_update = {'active': False}

        # Every read is done; Firestore requires that before the first write in a transaction.
        updated = self.state_manager.transition_in_transaction(
            transaction, ctf_id, new_state, event=stored, **fields
        )
        if board_update:
            # One write per board in the same transaction; creation caps boards at ctf_max_boards
            # (default 100), well inside a transaction's write limit.
            boards = self.db.db.collection(DbCollections.CTF_BOARD.value)
            for workout_id in event.board_ids:
                transaction.update(boards.document(f"{ctf_id}-{workout_id}"), dict(board_update))
        self.logger.info(
            f"{self.class_name}:{ctf_id} - Applied CTF action",
            action=action, new_state=new_state.name,
        )
        return updated

    def _publish_arm(self, event: CtfEventModel) -> None:
        """Publish one CTF_ARM_BOARD per board and wait for each publish to resolve.

        `PubSubManager.msg` returns the client's publish future, and the client reports real failures
        (network, permission, a missing topic, a timeout) only through that future, so each one is
        resolved here against one shared deadline. A board whose message raised, failed, or did not
        resolve in time counts as unpublished. A timed-out message may still be delivered later; its
        worker then finds the board already `failed` and skips it.
        """
        attrs = PubSub.EventAttributes
        pending = []
        unpublished = []
        errors = []
        for index, workout_id in enumerate(event.board_ids):
            try:
                pending.append((workout_id, self.pubsub.msg(**{
                    attrs.HANDLER: PubSub.Handlers.CTF.value,
                    attrs.ACTION: str(PubSub.Actions.CTF_ARM_BOARD.value),
                    attrs.CTF_ID: event.id,
                    attrs.WORKOUT_ID: workout_id,
                })))
            except Exception as e:
                # A synchronous raise means the client itself is unusable, so the rest are not tried.
                errors.append(e)
                unpublished.extend(event.board_ids[index:])
                break
        deadline = time.monotonic() + self.ARM_PUBLISH_TIMEOUT_SECONDS
        for workout_id, future in pending:
            try:
                future.result(timeout=max(deadline - time.monotonic(), 0))
            except Exception as e:
                errors.append(e)
                unpublished.append(workout_id)
        if not errors:
            return
        self.logger.error(
            f"{self.class_name}:{event.id} - Arm publish failed",
            error_type=type(errors[0]).__name__, unpublished=len(unpublished), boards=len(event.board_ids),
        )
        # The event is already ARMING and only arm workers count boards_pending down, so the boards
        # that got no message are counted down here; otherwise the event would stay ARMING for good.
        try:
            self.db.transaction(lambda transaction: self._fail_unpublished(transaction, event.id, unpublished))
        except Exception as recovery_error:
            self.logger.error(
                f"{self.class_name}:{event.id} - Could not fail unpublished boards; event may stay ARMING",
                error_type=type(recovery_error).__name__,
            )
        raise errors[0]

    def _fail_unpublished(self, transaction, ctf_id: str, workout_ids: List[str]) -> None:
        """Mark boards whose arm message was never published `failed` and count them off boards_pending,
        moving the event to ARMED/BROKEN at 0 — the same aggregation an arm worker does for its board.

        The board whose publish raised may still have been delivered, so a board an arm worker already
        finished (terminal status) is left alone and not counted twice; a worker that finishes later finds
        this board terminal and skips its own aggregation.
        """
        collection = self.db.db.collection(DbCollections.CTF.value)
        boards = self.db.db.collection(DbCollections.CTF_BOARD.value)
        snapshot = collection.document(ctf_id).get(transaction=transaction)
        if not snapshot.exists:
            return
        stored = snapshot.to_dict()
        statuses = {}
        for workout_id in stored.get('board_ids', []):
            board = boards.document(f"{ctf_id}-{workout_id}").get(transaction=transaction)
            statuses[workout_id] = board.to_dict().get('arm_status') if board.exists else None
        to_fail = [w for w in workout_ids if statuses.get(w) not in (None, *self.TERMINAL_ARM_STATUSES)]

        # Every read is done; Firestore requires that before the first write in a transaction.
        for workout_id in to_fail:
            transaction.update(
                boards.document(f"{ctf_id}-{workout_id}"),
                {'arm_status': 'failed', 'arm_error': self.ARM_PUBLISH_FAILED},
            )
        if not to_fail or stored.get('state') != CtfStates.ARMING.value:
            return
        boards_pending = max(int(stored.get('boards_pending', 0)) - len(to_fail), 0)
        if boards_pending > 0:
            transaction.update(collection.document(ctf_id), {'boards_pending': boards_pending})
            return
        any_armed = any(status == 'armed' for w, status in statuses.items() if w not in to_fail)
        self.state_manager.transition_in_transaction(
            transaction, ctf_id, CtfStates.ARMED if any_armed else CtfStates.BROKEN,
            event=stored, boards_pending=0,
        )

    def state(self, ctf_id: str, user: AgogeUser) -> CtfStateResponse:
        """The dashboard poll: one event read plus one board query, never a read per board."""
        event = self.get(ctf_id, user)
        return CtfStateResponse(
            id=event.id,
            state=event.state,
            state_name=self._state_name(event.state),
            state_timestamp=event.state_timestamp,
            starts_at=event.starts_at,
            ends_at=event.ends_at,
            paused_at=event.paused_at,
            accumulated_pause_seconds=event.accumulated_pause_seconds,
            scoreboard_frozen_at=event.scoreboard_frozen_at,
            public_scoreboard_enabled=event.public_scoreboard_enabled,
            # From the cached admin-info read ctf_enabled_required already made, so no extra read.
            budget_exceeded=config.is_budget_exceeded(),
            boards=[self._board_status(board) for board in self._boards(event)],
        )

    def boards(self, ctf_id: str, user: AgogeUser) -> List[CtfBoardStatus]:
        event = self.get(ctf_id, user)
        return [self._board_status(board) for board in self._boards(event)]

    def flags(self, ctf_id: str, user: AgogeUser) -> List[CtfFlagRow]:
        """One row per spec flag, decoys included, each with every board's plant status for it."""
        event = self.get(ctf_id, user)
        boards = self._boards(event)
        rows = []
        for flag in event.spec.flags:
            statuses = []
            for board in boards:
                state = next((f for f in board.flags if f.flag_id == flag.id), None)
                if state is None:
                    continue
                statuses.append(CtfFlagBoardStatus(
                    workout_id=board.workout_id,
                    team_name=board.team_name,
                    plant_status=state.plant_status,
                    planted_at=state.planted_at,
                    plant_error=state.plant_error,
                    solved=state.solved,
                ))
            rows.append(CtfFlagRow(
                flag_id=flag.id,
                server=flag.server,
                slot=flag.slot,
                category=flag.category,
                location_type=flag.location_type,
                points=flag.points,
                decoy=flag.decoy,
                boards=statuses,
            ))
        return rows

    def log(self, ctf_id: str, user: AgogeUser, action: Optional[str] = None) -> List[CtfLogModel]:
        """The event's log rows, newest first, at most MAX_PANEL_ROWS, optionally one action only."""
        if action is not None and action not in get_args(LogAction):
            raise BadRequest(message=f"Unknown log action: {action}")
        self.get(ctf_id, user)
        rows = self._panel_rows(DbCollections.CTF_LOG, CtfLogModel, ctf_id, 'action', action)
        return sorted(rows, key=lambda row: row.created_at, reverse=True)[:self.MAX_PANEL_ROWS]

    def submissions(self, ctf_id: str, user: AgogeUser, verdict: Optional[str] = None) -> List[CtfSubmissionModel]:
        """The event's submissions, newest first, at most MAX_PANEL_ROWS, optionally one verdict only."""
        if verdict is not None and verdict not in get_args(Verdict):
            raise BadRequest(message=f"Unknown verdict: {verdict}")
        self.get(ctf_id, user)
        rows = self._panel_rows(DbCollections.CTF_SUBMISSION, CtfSubmissionModel, ctf_id, 'verdict', verdict)
        return sorted(rows, key=lambda row: row.submitted_at, reverse=True)[:self.MAX_PANEL_ROWS]

    def _panel_rows(self, collection: DbCollections, model, ctf_id: str, field: str, value: Optional[str]) -> List:
        # Equality filters only, sorted and capped here: a server-side order_by on created_at or
        # submitted_at would need a composite index, and this repo deploys none.
        filters = [('ctf_id', DbOperators.EQUAL, ctf_id)]
        if value is not None:
            filters.append((field, DbOperators.EQUAL, value))
        docs = self.db.query(collection_name=collection, filters=filters) or []
        rows = ModelValidator(model, log_location=self.log_name).load(docs, halt_on_error=False)
        return [row for row in rows if row is not None]

    def _boards(self, event: CtfEventModel) -> List[CtfBoardModel]:
        """Every board of the event (archived ones too) in board_ids order, from one query.
        An invalid board document is skipped so it cannot blank the whole dashboard."""
        docs = self.db.query(
            collection_name=DbCollections.CTF_BOARD,
            filters=[('ctf_id', DbOperators.EQUAL, event.id)],
        ) or []
        boards = ModelValidator(CtfBoardModel, log_location=self.log_name).load(docs, halt_on_error=False)
        order = {workout_id: index for index, workout_id in enumerate(event.board_ids)}
        boards = [board for board in boards if board is not None]
        return sorted(boards, key=lambda board: (order.get(board.workout_id, len(order)), board.workout_id))

    @staticmethod
    def _board_status(board: CtfBoardModel) -> CtfBoardStatus:
        return CtfBoardStatus(
            workout_id=board.workout_id,
            team_name=board.team_name,
            arm_status=board.arm_status,
            arm_error=board.arm_error,
            plant_failed_count=sum(1 for flag in board.flags if flag.plant_status == 'failed'),
            plant_stale_count=sum(1 for flag in board.flags if flag.plant_status == 'stale'),
        )

    def delete(self, ctf_id: str, user: AgogeUser) -> None:
        """Admin only, DRAFT or ARCHIVED only. Deletes the rate-limit, digest and board documents,
        then the event. Submissions and the event log are kept.

        The event goes last: if a commit fails it is still there in a deletable state, and a retry
        finds whatever is left because every document is located by query or by derived id.
        """
        if not user.is_admin:
            raise Unauthorized(message=UNAUTHORIZED_MESSAGE)
        event = self._load(ctf_id)
        if event.state not in (CtfStates.DRAFT.value, CtfStates.ARCHIVED.value):
            raise Conflict(
                message=f"CTF event is {self._state_name(event.state)}; only DRAFT or ARCHIVED events can be deleted"
            )
        # A later event on the same workout overwrites these digest ids (the digest does not depend on
        # the event), so only digests still owned by this event are deleted.
        digests = self.db.query(
            collection_name=DbCollections.CTF_DIGEST,
            filters=[('ctf_id', DbOperators.EQUAL, ctf_id)],
        ) or []
        docs = [
            *((DbCollections.CTF_RATE_LIMIT, doc_id) for doc_id in self._rate_limit_ids(ctf_id)),
            *((DbCollections.CTF_DIGEST, digest['digest']) for digest in digests),
            *((DbCollections.CTF_BOARD, f"{ctf_id}-{workout_id}") for workout_id in event.board_ids),
            (DbCollections.CTF, ctf_id),
        ]
        for start in range(0, len(docs), self.MAX_WRITES_PER_COMMIT):
            self.db.batch_write([
                self._operation(collection, doc_id, DbOperationTypes.DELETE)
                for collection, doc_id in docs[start:start + self.MAX_WRITES_PER_COMMIT]
            ])
        self.logger.info(
            f"{self.class_name}:{ctf_id} - Deleted CTF event",
            boards=len(event.board_ids), digests=len(digests), documents=len(docs),
        )

    def _rate_limit_ids(self, ctf_id: str) -> List[str]:
        """Rate-limit documents carry no ctf_id field; their ids are `{ctf_id}-{workout_id}-{bucket}`
        with an arbitrary submitted bucket, so they are found by document-id range. '.' is the
        character after '-', which makes [ctf_id + '-', ctf_id + '.') exactly this event's ids."""
        collection = self.db.db.collection(DbCollections.CTF_RATE_LIMIT.value)
        query = collection.where(
            filter=FieldFilter(FieldPath.document_id(), '>=', collection.document(f"{ctf_id}-"))
        ).where(
            filter=FieldFilter(FieldPath.document_id(), '<', collection.document(f"{ctf_id}."))
        )
        return [snapshot.id for snapshot in query.stream()]

    def _load(self, ctf_id: str) -> CtfEventModel:
        doc = self.db.get(collection_name=DbCollections.CTF, doc_id=ctf_id)
        if not doc:
            raise NotFound(message="CTF event not found")
        return ModelValidator(CtfEventModel, log_location=self.log_name).load(doc)

    @staticmethod
    def _authorize(instructor_ids: List[str], user: AgogeUser) -> None:
        if not user.is_admin and user.email not in instructor_ids:
            raise Unauthorized(message=UNAUTHORIZED_MESSAGE)

    @classmethod
    def _summary(cls, event: CtfEventModel) -> CtfEventSummary:
        return CtfEventSummary(
            id=event.id,
            name=event.spec.name,
            unit_id=event.unit_id,
            state=event.state,
            state_name=cls._state_name(event.state),
            board_count=len(event.board_ids),
            creation_timestamp=event.creation_timestamp,
            starts_at=event.starts_at,
            ends_at=event.ends_at,
        )

    @staticmethod
    def _state_name(state: int) -> str:
        return CtfStates(state).name if state in CtfStates._value2member_map_ else str(state)

    def _new_board(self, event: CtfEventModel, workout: dict, seed: str):
        workout_id = workout['id']
        flags, digests = [], []
        for flag in event.spec.flags:
            digest = flag_digest(derive_flag_value(
                seed, workout_id, flag.id, event.seed_version, event.spec.scoring.flag_prefix
            ))
            flags.append(CtfFlagStateModel(flag_id=flag.id, digest=digest))
            digests.append(CtfDigestModel(digest=digest, ctf_id=event.id, workout_id=workout_id, flag_id=flag.id))
        board = CtfBoardModel(
            id=f"{event.id}-{workout_id}",
            workout_id=workout_id,
            ctf_id=event.id,
            team_name=workout.get('team_name') or workout.get('student_email') or workout_id,
            flags=flags,
        )
        return board, digests

    def _unit_workouts(self, unit_id: str) -> List[dict]:
        workouts = self.db.query(
            collection_name=DbCollections.WORKOUT,
            filters=[('parent_id', DbOperators.EQUAL, unit_id)],
        ) or []
        return [
            w for w in workouts
            if w.get('id') and w.get('state') not in self.EXCLUDED_WORKOUT_STATES
        ]

    def _max_boards(self) -> int:
        env_dict = self.env_dict if self.env_dict is not None else self.env.get_env()
        value = (env_dict or {}).get('ctf_max_boards')
        try:
            # bool is an int subclass; a stray `true` must not become a limit of 1.
            if isinstance(value, bool) or int(value) < 1:
                raise ValueError
            return int(value)
        except (TypeError, ValueError):
            return self.DEFAULT_MAX_BOARDS

    def _workouts_on_active_boards(self, workout_ids: List[str]) -> List[str]:
        busy = set()
        for start in range(0, len(workout_ids), self.MAX_IN_VALUES):
            chunk = workout_ids[start:start + self.MAX_IN_VALUES]
            boards = self.db.query(
                collection_name=DbCollections.CTF_BOARD,
                filters=[
                    ('workout_id', DbOperators.IN, chunk),
                    ('active', DbOperators.EQUAL, True),
                ],
            ) or []
            busy.update(board['workout_id'] for board in boards)
        return [workout_id for workout_id in workout_ids if workout_id in busy]

    def _commit(self, ctf_id: str, docs: List[tuple]) -> None:
        """Set every (collection, doc_id, data) in commits of at most MAX_WRITES_PER_COMMIT.
        If a commit fails, the documents already committed are deleted (best effort) so an
        orphaned active board cannot block the next attempt with a Conflict."""
        committed = 0
        try:
            for start in range(0, len(docs), self.MAX_WRITES_PER_COMMIT):
                chunk = docs[start:start + self.MAX_WRITES_PER_COMMIT]
                self.db.batch_write([
                    self._operation(collection, doc_id, DbOperationTypes.SET, data)
                    for collection, doc_id, data in chunk
                ])
                committed += len(chunk)
        except Exception as e:
            self.logger.error(
                f"{self.class_name}:{ctf_id} - Event creation failed; removing partial writes",
                error_type=type(e).__name__, committed=committed,
            )
            self._rollback(ctf_id, docs[:committed])
            raise

    def _rollback(self, ctf_id: str, docs: List[tuple]) -> None:
        for start in range(0, len(docs), self.MAX_WRITES_PER_COMMIT):
            chunk = docs[start:start + self.MAX_WRITES_PER_COMMIT]
            try:
                self.db.batch_write([
                    self._operation(collection, doc_id, DbOperationTypes.DELETE)
                    for collection, doc_id, _ in chunk
                ])
            except Exception as e:
                # Never mask the original failure; the leftovers are logged by count only.
                self.logger.error(
                    f"{self.class_name}:{ctf_id} - Rollback of partial writes failed",
                    error_type=type(e).__name__, remaining=len(docs) - start,
                )
                return

    def _operation(self, collection: DbCollections, doc_id: str, operation_type: DbOperationTypes, data=None):
        return self.db.operation(
            collection_name=collection.value,
            doc_id=doc_id,
            operation_type=operation_type,
            data=data,
        )
