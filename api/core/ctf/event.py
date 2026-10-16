import time
from datetime import datetime, timezone
from typing import List

from pydantic import ValidationError

from common.constants.database import DATABASE_NAME, DatabaseTypes, DbCollections, DbOperationTypes, DbOperators
from common.constants.states import CtfStates, WorkoutStates
from common.exceptions.agoge import BadRequest, Conflict, NotFound, ServiceUnavailable, Unauthorized
from common.models.agoge import (
    CtfBoardModel,
    CtfDigestModel,
    CtfEventModel,
    CtfFlagStateModel,
    CtfSpecModel,
)
from common.models.model_validators.model_validator import ModelValidator
from common.models.users import AgogeUser
from common.utilities.ctf_flags import derive_flag_value, flag_digest
from common.utilities.gcp.cloud_logger import Logger, LoggerNames
from common.utilities.id_generator import IdGenerator

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
    # A workout being torn down gets no board: it can never be armed.
    EXCLUDED_WORKOUT_STATES = {
        WorkoutStates.DELETING_SERVERS.value,
        WorkoutStates.COMPLETED_DELETING_SERVERS.value,
        WorkoutStates.DELETED.value,
    }

    def __init__(self, env_dict: dict = None, db=None, env=None) -> None:
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
        if not user.is_admin and user.email not in instructor_ids:
            raise Unauthorized(message=UNAUTHORIZED_MESSAGE)

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

    def _commit(self, ctf_id: str, docs: list) -> None:
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

    def _rollback(self, ctf_id: str, docs: list) -> None:
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
