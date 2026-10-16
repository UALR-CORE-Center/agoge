from typing import Optional

from common.constants.database import DATABASE_NAME, DatabaseTypes, DbCollections
from common.exceptions import NotFound
from common.models.agoge import CtfBoardModel, CtfEventModel
from common.models.model_validators.model_validator import ModelValidator
from common.utilities.gcp.cloud_logger import Logger, LoggerNames

from cloud_fn_utilities.course_objects.compute.factory import ComputeManagerFactory
from cloud_fn_utilities.course_objects.ctf.flag_planter import FlagPlanter


class HostReset:
    """
    Resets one server of one team board (one CTF_HOST_RESET message) in a ResetMode (Host Reset Modes, PRD):
    `replant` plants that server's flags again, `restart` stops then starts the instance, and `rebuild`
    nukes it and marks its flags `stale`. Every read, write and compute call names only this board and
    its `{workout_id}-{server}` instance, so other teams are never touched (SC-9).
    """
    MSG_WIREGUARD_REBUILD = "rebuild is not allowed on a WireGuard server"

    def __init__(
        self,
        env_dict: dict = None,
        db=None
    ) -> None:
        self.class_name = self.__class__.__name__
        self.logger = Logger(LoggerNames.CLOUD_FN, class_name=self.class_name)
        self.env_dict = env_dict
        if db is None:
            from common.document_database.factory import DocumentDatabaseFactory
            db = DocumentDatabaseFactory.create_db_object(
                db_type=DatabaseTypes.firestore, database_name=DATABASE_NAME, log_name=LoggerNames.CLOUD_FN
            )
        self.db = db
        self.mode_map = {
            'replant': self._replant,
            'restart': self._restart,
            'rebuild': self._rebuild,
        }

    def run(self, ctf_id: str, workout_id: str, server: str, mode: str) -> Optional[str]:
        """
        Returns the mode that ran, or None when the board is inactive (archived or deleted event). Raises
        ValueError for an unknown mode or a missing server name before any read, and NotFound for a missing
        event, board or server document.
        """
        method = self.mode_map.get(mode)
        if method is None:
            self.logger.error(f"{self.class_name}:{ctf_id} - unsupported reset mode", mode=mode)
            raise ValueError(f"Unsupported CTF host reset mode: {mode}")
        if not server:
            raise ValueError("CTF host reset requires a server name.")

        event = self._load(DbCollections.CTF, ctf_id, CtfEventModel)
        board = self._load(DbCollections.CTF_BOARD, f"{ctf_id}-{workout_id}", CtfBoardModel)
        if not board.active:
            self.logger.warning(f"{self.class_name}:{ctf_id} - board {board.id} is not active; {mode} skipped")
            return None

        self.logger.info(f"{self.class_name}:{ctf_id} - {mode} of {server} on board {board.id}")
        method(event, board, server)
        return mode

    def _replant(self, event: CtfEventModel, board: CtfBoardModel, server: str) -> None:
        FlagPlanter(event, env_dict=self.env_dict, db=self.db).plant(board, [server])

    def _restart(self, event: CtfEventModel, board: CtfBoardModel, server: str) -> None:
        # Flags stay on disk: the plant key was removed after the last plant, so the loader does nothing at boot
        manager = self._server_manager(board, server)
        manager.stop()
        manager.start()

    def _rebuild(self, event: CtfEventModel, board: CtfBoardModel, server: str) -> None:
        server_doc = self._server_doc(board, server)
        if server_doc.get('wireguard_endpoint_id'):
            # The API refuses this too; LabServerManager.nuke() would leave a WireGuard server deleted
            raise ValueError(self.MSG_WIREGUARD_REBUILD)
        manager = self._server_manager(board, server, server_doc=server_doc)
        planter = FlagPlanter(event, env_dict=self.env_dict, db=self.db)
        try:
            manager.nuke()
        except Exception:
            # A failed nuke may already have deleted the instance, so its flags can't be trusted either way
            try:
                planter.mark_stale(board, server)
            except Exception as e:
                self.logger.error(f"{self.class_name}:{board.id} - could not mark {server} flags stale",
                                  error=type(e).__name__)
            raise
        planter.mark_stale(board, server)

    def _server_manager(self, board: CtfBoardModel, server: str, server_doc: dict = None):
        server_doc = server_doc or self._server_doc(board, server)
        manager = ComputeManagerFactory.create_manager_object(env_dict=self.env_dict)
        manager.load(server_name=self._instance_name(board, server), server_spec=server_doc)
        return manager

    def _server_doc(self, board: CtfBoardModel, server: str) -> dict:
        instance_name = self._instance_name(board, server)
        data = self.db.get(DbCollections.SERVER, instance_name)
        if not data:
            self.logger.error(f"{self.class_name}:{board.id} - server {instance_name} not found")
            raise NotFound(f"Server {instance_name} not found")
        return data

    @staticmethod
    def _instance_name(board: CtfBoardModel, server: str) -> str:
        # Same naming as SoloWorkout and FlagPlanter: f"{workout_id}-{server.name}"
        return f"{board.workout_id}-{server}"

    def _load(self, collection: DbCollections, doc_id: str, model):
        data = self.db.get(collection, doc_id)
        if not data:
            self.logger.error(f"{self.class_name}:{doc_id} - {collection.value} document not found")
            raise NotFound(f"{collection.value} {doc_id} not found")
        return ModelValidator(model=model, log_location=LoggerNames.CLOUD_FN).load(data=data)
