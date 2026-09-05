from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from typing import List

from common.constants.build_constants import BuildConstants
from common.constants.database import (
    DbCollections,
    DATABASE_NAME,
    DatabaseTypes,
)
from common.constants.pub_sub import PubSub
from common.constants.states import ServerStates, UnitStates, WorkoutStates
from common.document_database import DocumentDatabaseFactory, DatabaseQueries, DatabaseMask
from common.models.agoge import WorkoutModel, UnitModel
from common.utilities.timestamps import Timestamps
from common.utilities.gcp.cloud_env import CloudEnv
from common.utilities.gcp.pubsub_manager import PubSubManager
from common.utilities.gcp.cloud_logger import Logger, LoggerNames
from ..compute.factory import ComputeManagerFactory
from ...gcp.vpc_manager import VpcManager
from ...gcp.firewall_rule_manager import FirewallManager
from ...state_managers.workout_states import WorkoutStatesManager


class BaseWorkout(ABC):
    REBUILD_PUBLISH_TIMEOUT_SECONDS = 30
    REBUILDABLE_STATES = frozenset(
        {
            WorkoutStates.READY.value,
            WorkoutStates.RUNNING.value,
            WorkoutStates.BROKEN.value,
        }
    )
    REBUILDABLE_UNIT_STATES = frozenset(
        {
            UnitStates.READY.value,
            UnitStates.RUNNING.value,
            UnitStates.BROKEN.value,
        }
    )

    def __init__(
        self,
        workout_id: str,
        workout_model: WorkoutModel,
        unit_model: UnitModel,
        duration_hours: int = 2,
        debug: bool = False,
        env_dict: dict = None
    ) -> None:
        self.log_name = LoggerNames.CLOUD_FN
        self.workout_id = workout_id
        self.workout = workout_model
        self.unit_model = unit_model
        self.duration_seconds = self._shutoff_timestamp(duration_hours)
        self.debug = debug
        self.env = CloudEnv(env_dict=env_dict) if env_dict else CloudEnv()
        self.env_dict = self.env.get_env()
        self.logger = Logger(self.log_name)
        self.s = WorkoutStates
        self.collection = DbCollections.WORKOUT
        self.pubsub_manager = PubSubManager(PubSub.Topics.AGOGE, env_dict=self.env_dict)
        self.state_manager = WorkoutStatesManager(initial_build_id=self.workout_id)
        self.compute_manager = ComputeManagerFactory.create_manager_object(env_dict=self.env_dict)
        self.vpc_manager = VpcManager(build_id=self.workout_id, env_dict=self.env_dict)
        self.firewall_manager = FirewallManager(env_dict=self.env_dict)
        self.db = DocumentDatabaseFactory.create_db_object(
            db_type=DatabaseTypes.firestore,
            database_name=DATABASE_NAME
        )
        self.db_queries = DatabaseQueries(db=self.db)
        self.db_mask = DatabaseMask(logger=self.logger)
        if not self.workout:
            self.logger.error(f"The datastore record for {self.workout_id} no longer exists!")
            raise LookupError
        self.promiscuous_mode = False

    @staticmethod
    def _shutoff_timestamp(
        duration_hours: int
    ) -> int:
        try:
            duration_seconds = min(int(duration_hours) * 3600, 36000) if duration_hours else 7200
        except ValueError:
            duration_seconds = 7200
        return duration_seconds

    @abstractmethod
    def build(self):
        pass

    @abstractmethod
    def start(self):
        pass

    @abstractmethod
    def stop(self):
        pass

    @abstractmethod
    def delete(self):
        pass

    @abstractmethod
    def nuke(self) -> bool:
        pass

    def get_record(self) -> WorkoutModel:
        workout = self.db.get(collection_name=self.collection, doc_id=self.workout_id)
        return WorkoutModel(**workout)

    def update_record(
        self,
        doc_id: str,
        data: WorkoutModel,
        update_keys: List[str] = None
    ) -> WorkoutModel:
        update_data = data.model_dump(exclude_unset=True)

        if update_keys:
            update_mask = self.db_mask.get(document=update_data, keys=update_keys)
            self.db.update(
                collection_name=DbCollections.WORKOUT,
                doc_id=doc_id,
                data=update_mask
            )
        else:
            self.db.update(
                collection_name=DbCollections.WORKOUT,
                doc_id=doc_id,
                data=update_data
            )
        return data

    def extend_runtime(self) -> None:
        shutoff_ts = self.workout.shutoff_timestamp
        if shutoff_ts is not None:
            new_shutoff_ts = (
                    shutoff_ts + timedelta(seconds=self.duration_seconds).total_seconds()
            )
            self.workout.shutoff_timestamp = Timestamps.round_to_next_quarter(new_shutoff_ts)
            self.update_record(doc_id=self.workout_id, data=self.workout, update_keys=['shutoff_timestamp'])

    def _add_build_action(
        self,
        action,
        update: bool = False
    ) -> None:
        self.workout.action = action
        if update:
            self.update_record(doc_id=self.workout_id, data=self.workout, update_keys=["action"])

    def _reset_expiration(self) -> None:
        workout_duration_days = self.unit_model.workout_duration_days
        if workout_duration_days is not None:
            self.workout.expires = Timestamps.get_current_timestamp_utc(add_seconds=86400 * workout_duration_days)
            self._add_build_action(PubSub.Actions.BUILD.value)
            self.update_record(doc_id=self.workout_id, data=self.workout, update_keys=["expires", "action"])

    def _nuke_servers(self, network_prefix: str = None) -> bool:
        """Rebuild this Workout's servers and wait for the rebuild cycle.

        Server records are moved to RESETTING before child rebuilds start. This
        prevents the completion check from accepting their old RUNNING state
        before a rebuild has actually started.
        """
        unit_state = getattr(self.unit_model, "state", None)
        unit_type = getattr(self.unit_model, "unit_type", None)
        if not self._unit_is_rebuildable(unit_state, unit_type):
            self.logger.warning(
                f"{self.class_name}:{self.workout_id} - Refusing to rebuild while "
                f"Unit {self.unit_model.id} is in state {unit_state}."
            )
            return False

        workout_state = self.state_manager.get_state()
        if workout_state not in self.REBUILDABLE_STATES:
            self.logger.warning(
                f"{self.class_name}:{self.workout_id} - A rebuild cannot start "
                f"from Workout state {workout_state}."
            )
            return False

        servers_to_nuke = self.db_queries.get_servers(parent_id=self.workout_id)
        if not servers_to_nuke:
            servers_to_nuke = self._recover_server_records()
        if not servers_to_nuke:
            self.logger.warning(
                f"{self.class_name}:{self.workout_id} - No server records were "
                "found and none could be recovered from the Workout specification; "
                "there is nothing to rebuild."
            )
            return False

        server_names = [
            f'{server["parent_id"]}-{server["name"]}'
            for server in servers_to_nuke
        ]
        claimed = False
        try:
            claimed = self.db.transaction(
                operation_func=self._claim_workout_rebuild_transaction,
            )
            if not claimed:
                self.logger.warning(
                    f"{self.class_name}:{self.workout_id} - Another action "
                    "claimed the Workout before the rebuild could start."
                )
                return False

            self._prepare_rebuild_infrastructure()

            reset_timestamp = datetime.now(timezone.utc).isoformat()
            for server_name in server_names:
                self.db.update(
                    collection_name=DbCollections.SERVER,
                    doc_id=server_name,
                    data={
                        "state": ServerStates.RESETTING.value,
                        "state_timestamp": reset_timestamp,
                    },
                )

            for server_name in server_names:
                if self.debug:
                    self.compute_manager.load(
                        server_name=server_name,
                        network_prefix=network_prefix,
                    )
                    self.compute_manager.nuke()
                else:
                    message_attrs = {
                        "handler": str(PubSub.Handlers.CONTROL.value),
                        "action": str(PubSub.Actions.NUKE.value),
                        "build_id": server_name,
                        "course_object": str(PubSub.CourseObjects.LAB_SERVER.value),
                    }
                    if network_prefix:
                        message_attrs["network_prefix"] = network_prefix
                    publish_future = self.pubsub_manager.msg(**message_attrs)
                    if publish_future is not None:
                        publish_future.result(
                            timeout=self.REBUILD_PUBLISH_TIMEOUT_SECONDS
                        )

            if not self.state_manager.are_server_builds_finished():
                raise TimeoutError(
                    f"Timed out waiting for server rebuilds for Workout {self.workout_id}."
                )

            self.db.update(
                collection_name=DbCollections.WORKOUT,
                doc_id=self.workout_id,
                data={
                    "active": True,
                    "shutoff_timestamp": Timestamps.get_current_timestamp_utc(
                        add_seconds=self.duration_seconds
                    )
                },
            )
            self.state_manager.state_transition(self.s.RUNNING)
        except Exception:
            if claimed:
                self.state_manager.state_transition(self.s.BROKEN)
            self.logger.error(
                f"{self.class_name}:{self.workout_id} - Workout rebuild failed."
            )
            raise

        self.logger.info(
            f"{self.class_name}:{self.workout_id} - Finished rebuilding "
            f"{len(server_names)} server(s)."
        )
        return True

    def _recover_server_records(self) -> list[dict]:
        """Recover missing child server records when a subclass can do so safely."""
        return []

    def _prepare_rebuild_infrastructure(self) -> None:
        """Ensure subclass-specific prerequisites exist before rebuilding servers."""

    def _claim_workout_rebuild_transaction(self, transaction) -> bool:
        """Atomically validate the Unit and claim the Workout."""
        unit_id = self.unit_model.id
        unit_ref = self.db.db.collection(DbCollections.UNIT.value).document(unit_id)
        unit_snapshot = unit_ref.get(transaction=transaction)
        if not unit_snapshot.exists:
            return False

        unit = unit_snapshot.to_dict()
        if not self._unit_is_rebuildable(
            unit.get("state"),
            unit.get("unit_type"),
        ):
            return False

        doc_ref = self.db.db.collection(DbCollections.WORKOUT.value).document(
            self.workout_id
        )
        snapshot = doc_ref.get(transaction=transaction)
        if not snapshot.exists:
            return False

        workout = snapshot.to_dict()
        existing_state = workout.get("state")
        if (
            str(workout.get("parent_id")) != str(unit_id)
            or existing_state not in self.REBUILDABLE_STATES
        ):
            return False

        transaction.set(
            doc_ref,
            {
                "action": PubSub.Actions.NUKE.value,
                "prev_state": existing_state,
                "state": WorkoutStates.BUILDING_SERVERS.value,
                "state_timestamp": datetime.now(timezone.utc).isoformat(),
            },
            merge=True,
        )
        return True

    @classmethod
    def _unit_is_rebuildable(cls, state, unit_type) -> bool:
        if state in cls.REBUILDABLE_UNIT_STATES:
            return True

        unit_type_value = getattr(unit_type, "value", unit_type)
        return state == UnitStates.START.value and unit_type_value in {
            None,
            BuildConstants.UnitType.SOLO.value,
        }
