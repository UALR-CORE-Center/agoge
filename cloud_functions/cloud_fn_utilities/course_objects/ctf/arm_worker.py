from typing import Optional, Tuple

from common.constants.database import DATABASE_NAME, DatabaseTypes, DbCollections
from common.constants.states import CtfStates, WorkoutStates
from common.exceptions import NotFound
from common.models.agoge import CtfBoardModel, CtfEventModel
from common.models.model_validators.model_validator import ModelValidator
from common.utilities.ctf_state_manager import CtfStateManager
from common.utilities.gcp.cloud_logger import Logger, LoggerNames

from cloud_fn_utilities.course_objects.ctf.flag_planter import FlagPlanter, board_servers


class ArmWorker:
    """
    Arms one team board of a CTF event (one CTF_ARM_BOARD message): checks the workout is running, plants
    every flag-bearing server, then aggregates. The aggregation is one transaction that records the board's
    arm_status, decrements the event's boards_pending, and, when this was the last board, moves the event
    ARMING -> ARMED if any board armed, else ARMING -> BROKEN.
    """
    TERMINAL_STATUSES = ('armed', 'failed')
    MSG_WORKOUT_NOT_RUNNING = "Workout is not running"
    MSG_WORKOUT_NOT_FOUND = "Workout not found"
    MSG_BOARD_INACTIVE = "Board is not active"
    MSG_NO_FLAGS_PLANTED = "No flags planted"
    MSG_ABORTED = "Arm aborted by an internal error"

    def __init__(
        self,
        env_dict: dict = None,
        db=None,
        compute_api=None
    ) -> None:
        self.class_name = self.__class__.__name__
        self.logger = Logger(LoggerNames.CLOUD_FN, class_name=self.class_name)
        self.env_dict = env_dict
        self.compute_api = compute_api
        if db is None:
            from common.document_database.factory import DocumentDatabaseFactory
            db = DocumentDatabaseFactory.create_db_object(
                db_type=DatabaseTypes.firestore, database_name=DATABASE_NAME, log_name=LoggerNames.CLOUD_FN
            )
        self.db = db
        self.state_manager = CtfStateManager(db=self.db, log_name=LoggerNames.CLOUD_FN)

    def run(self, ctf_id: str, workout_id: str) -> Optional[str]:
        """
        Returns the board's final arm_status, or None when the message is stale (event no longer ARMING).
        Raises NotFound for a missing event or board. Any other error still aggregates the board as failed
        before re-raising, so one crashed worker cannot leave the event in ARMING forever.
        """
        board_id = f"{ctf_id}-{workout_id}"
        event = self._load(DbCollections.CTF, ctf_id, CtfEventModel)
        if event.state != CtfStates.ARMING.value:
            # Pub/Sub can redeliver after the event moved on; planting then would reset servers mid-game
            self.logger.warning(f"{self.class_name}:{ctf_id} - event is not ARMING; arm of {board_id} skipped")
            return None
        board = self._load(DbCollections.CTF_BOARD, board_id, CtfBoardModel)
        if board.arm_status in self.TERMINAL_STATUSES:
            self.logger.warning(f"{self.class_name}:{ctf_id} - board {board_id} already {board.arm_status}; skipped")
            return board.arm_status

        try:
            self._mark_arming(board_id)
            arm_status, arm_error = self._arm(event, board, workout_id)
        except Exception as e:
            self.logger.error(f"{self.class_name}:{ctf_id} - arm of {board_id} aborted", error=type(e).__name__)
            try:
                self._aggregate(ctf_id, board_id, 'failed', self.MSG_ABORTED)
            except Exception as aggregate_error:
                self.logger.error(
                    f"{self.class_name}:{ctf_id} - could not aggregate aborted board {board_id}",
                    error=type(aggregate_error).__name__
                )
            raise
        return self._aggregate(ctf_id, board_id, arm_status, arm_error)

    def _arm(self, event: CtfEventModel, board: CtfBoardModel, workout_id: str) -> Tuple[str, Optional[str]]:
        """Plants the board and returns (arm_status, arm_error) for it."""
        if not board.active:
            return 'failed', self.MSG_BOARD_INACTIVE
        workout = self.db.get(DbCollections.WORKOUT, workout_id)
        if not workout:
            return 'failed', self.MSG_WORKOUT_NOT_FOUND
        if workout.get('state') != WorkoutStates.RUNNING.value:
            return 'failed', self.MSG_WORKOUT_NOT_RUNNING

        servers = board_servers(event, board)
        if not servers:
            return 'failed', self.MSG_NO_FLAGS_PLANTED
        planter = FlagPlanter(event, env_dict=self.env_dict, compute_api=self.compute_api, db=self.db)
        board = planter.plant(board, servers)
        return self.arm_result(board)

    @classmethod
    def arm_result(cls, board: CtfBoardModel) -> Tuple[str, Optional[str]]:
        """
        A board is `armed` when at least one of its flags planted: it is playable, its failed flags stay
        visible per flag and can be replanted, and BROKEN is reserved for an arm where nothing is playable.
        Plant errors never contain a flag value, so they are safe to copy into arm_error.
        """
        total = len(board.flags)
        planted = sum(1 for flag in board.flags if flag.plant_status == 'planted')
        if planted == 0:
            first_error = next((flag.plant_error for flag in board.flags if flag.plant_error), None)
            return 'failed', f"{cls.MSG_NO_FLAGS_PLANTED}: {first_error}" if first_error else cls.MSG_NO_FLAGS_PLANTED
        if planted < total:
            return 'armed', f"{total - planted} of {total} flags failed to plant"
        return 'armed', None

    def _mark_arming(self, board_id: str) -> None:
        board_ref = self._ref(DbCollections.CTF_BOARD, board_id)

        def operation(transaction):
            if not board_ref.get(transaction=transaction).exists:
                raise NotFound(f"CTF board {board_id} not found")
            transaction.update(board_ref, {'arm_status': 'arming', 'arm_error': None})

        self.db.transaction(operation)

    def _aggregate(self, ctf_id: str, board_id: str, arm_status: str, arm_error: Optional[str]) -> str:
        """
        One transaction: board arm_status, boards_pending - 1, and the ARMED/BROKEN transition at 0. Every read
        comes before the first write, as Firestore requires, so the event read here is passed to the state
        manager. A board already in a terminal status was aggregated by an earlier delivery and is not counted
        twice.
        """
        event_ref = self._ref(DbCollections.CTF, ctf_id)
        board_ref = self._ref(DbCollections.CTF_BOARD, board_id)

        def operation(transaction):
            event_snapshot = event_ref.get(transaction=transaction)
            board_snapshot = board_ref.get(transaction=transaction)
            if not event_snapshot.exists:
                raise NotFound(f"CTF event {ctf_id} not found")
            if not board_snapshot.exists:
                raise NotFound(f"CTF board {board_id} not found")
            event = event_snapshot.to_dict()
            stored_status = board_snapshot.to_dict().get('arm_status')
            if stored_status in self.TERMINAL_STATUSES:
                self.logger.warning(f"{self.class_name}:{ctf_id} - board {board_id} already aggregated as {stored_status}")
                return stored_status
            if event.get('state') != CtfStates.ARMING.value:
                # Nothing left to count down; record the board so the dashboard still shows its outcome
                transaction.update(board_ref, {'arm_status': arm_status, 'arm_error': arm_error})
                self.logger.warning(f"{self.class_name}:{ctf_id} - event left ARMING before {board_id} finished")
                return arm_status

            boards_pending = max(int(event.get('boards_pending', 0)) - 1, 0)
            any_armed = arm_status == 'armed'
            if boards_pending == 0 and not any_armed:
                other_ids = [bid for bid in event.get('board_ids', []) if f"{ctf_id}-{bid}" != board_id]
                for other_id in other_ids:
                    snapshot = self._ref(DbCollections.CTF_BOARD, f"{ctf_id}-{other_id}").get(transaction=transaction)
                    if snapshot.exists and snapshot.to_dict().get('arm_status') == 'armed':
                        any_armed = True
                        break

            transaction.update(board_ref, {'arm_status': arm_status, 'arm_error': arm_error})
            if boards_pending > 0:
                transaction.update(event_ref, {'boards_pending': boards_pending})
            else:
                new_state = CtfStates.ARMED if any_armed else CtfStates.BROKEN
                self.state_manager.transition_in_transaction(
                    transaction, ctf_id, new_state, event=event, boards_pending=0
                )
            return arm_status

        result = self.db.transaction(operation)
        self.logger.info(f"{self.class_name}:{ctf_id} - board {board_id} arm finished", arm_status=result)
        return result

    def _ref(self, collection: DbCollections, doc_id: str):
        return self.db.db.collection(collection.value).document(doc_id)

    def _load(self, collection: DbCollections, doc_id: str, model):
        data = self.db.get(collection, doc_id)
        if not data:
            self.logger.error(f"{self.class_name}:{doc_id} - {collection.value} document not found")
            raise NotFound(f"{collection.value} document {doc_id} not found")
        return ModelValidator(model=model, log_location=LoggerNames.CLOUD_FN).load(data=data)
