from common.constants.database import DATABASE_NAME, DatabaseTypes, DbCollections
from common.constants.pub_sub import PubSub
from common.document_database import DocumentDatabaseFactory
from common.exceptions import NotFound
from common.models.agoge import CtfBoardModel, CtfEventModel
from common.models.model_validators.model_validator import ModelValidator
from common.utilities.gcp.cloud_env import CloudEnv
from common.utilities.gcp.cloud_logger import Logger, LoggerNames

from cloud_fn_utilities.course_objects.ctf.arm_worker import ArmWorker
from cloud_fn_utilities.course_objects.ctf.flag_planter import FlagPlanter, board_servers


class CtfHandler:
    """
    The single Cloud Function entry point for CTF work (Handlers.CTF). Every CTF message names one event
    (CTF_ID) and one team board (WORKOUT_ID); SERVER_NAME and RESET_MODE narrow it further where the
    action needs them.
    """
    def __init__(
        self,
        event_attributes: dict,
        env_dict: dict = None,
        debug: bool = False,
        db=None
    ) -> None:
        self.class_name = self.__class__.__name__
        self.event_attributes = event_attributes
        self.env = CloudEnv(env_dict=env_dict) if env_dict else CloudEnv()
        self.env_dict = self.env.get_env()
        self.debug = debug
        self.logger = Logger(LoggerNames.CLOUD_FN, class_name=self.class_name)
        self.db = db or DocumentDatabaseFactory.create_db_object(
            db_type=DatabaseTypes.firestore,
            database_name=DATABASE_NAME,
            log_name=LoggerNames.CLOUD_FN
        )
        self.event_attr_keys = PubSub.EventAttributes
        self.action = self.event_attributes.get(self.event_attr_keys.ACTION, None)
        self.ctf_id = self.event_attributes.get(self.event_attr_keys.CTF_ID, None)
        self.workout_id = self.event_attributes.get(self.event_attr_keys.WORKOUT_ID, None)
        self.server_name = self.event_attributes.get(self.event_attr_keys.SERVER_NAME, None)
        self.reset_mode = self.event_attributes.get(self.event_attr_keys.RESET_MODE, None)

        if not self.action:
            self.logger.error(f"{self.class_name} - No action provided in cloud function CTF handler")
            raise ValueError("Action missing from CTF event attributes.")

        if not self.ctf_id or not self.workout_id:
            self.logger.error(
                f"{self.class_name}:{self.action} - CTF action requires a ctf id and a workout id",
                ctf_id=self.ctf_id,
                workout_id=self.workout_id
            )
            raise ValueError("CTF id or workout id missing from CTF event attributes.")

        # CTF_HOST_RESET (host_reset, G4) is added when that dispatcher lands
        self.action_map = {
            str(PubSub.Actions.CTF_ARM_BOARD.value): self._arm_board,
            str(PubSub.Actions.CTF_PLANT.value): self._plant,
        }

    def route(self) -> None:
        action_func = self.action_map.get(self.action)
        if action_func is None:
            self.logger.error(
                f"{self.class_name}:{self.action} - Unsupported action supplied to the CTF handler",
                action=self.action
            )
            raise ValueError(f"Unsupported CTF action: {self.action}")

        action_func()

    def _arm_board(self) -> None:
        """
        CTF_ARM_BOARD: arms one team board. ArmWorker loads the event and board itself, because it must
        skip a stale message (event no longer ARMING) before touching anything.
        """
        ArmWorker(env_dict=self.env_dict, db=self.db).run(self.ctf_id, self.workout_id)

    def _plant(self) -> None:
        """
        CTF_PLANT: re-plants one board's flags on SERVER_NAME, or on every server that carries one of the
        board's flags when no server is named. An inactive board (archived or deleted event) is skipped.
        """
        event = self._load_event()
        board = self._load_board()
        if not board.active:
            self.logger.warning(f"{self.class_name}:{self.ctf_id} - board {board.id} is not active; plant skipped")
            return

        servers = [self.server_name] if self.server_name else board_servers(event, board)
        FlagPlanter(event, env_dict=self.env_dict, db=self.db).plant(board, servers)

    def _load_event(self) -> CtfEventModel:
        data = self.db.get(DbCollections.CTF, self.ctf_id)
        if not data:
            self.logger.error(f"{self.class_name}:{self.ctf_id} - CTF event not found")
            raise NotFound(f"CTF event {self.ctf_id} not found")
        return ModelValidator(model=CtfEventModel, log_location=LoggerNames.CLOUD_FN).load(data=data)

    def _load_board(self) -> CtfBoardModel:
        board_id = f"{self.ctf_id}-{self.workout_id}"
        data = self.db.get(DbCollections.CTF_BOARD, board_id)
        if not data:
            self.logger.error(f"{self.class_name}:{self.ctf_id} - CTF board {board_id} not found")
            raise NotFound(f"CTF board {board_id} not found")
        return ModelValidator(model=CtfBoardModel, log_location=LoggerNames.CLOUD_FN).load(data=data)
