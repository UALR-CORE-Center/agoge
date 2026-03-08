from abc import ABC, abstractmethod
from datetime import timedelta
from typing import List

from common.constants.database import (
    DbCollections,
    DATABASE_NAME,
    DatabaseTypes,
)
from common.constants.pub_sub import PubSub
from common.constants.states import WorkoutStates
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
    def nuke(self):
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
