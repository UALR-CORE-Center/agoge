import time
from abc import abstractmethod
from datetime import datetime, timezone
from enum import Enum
from typing import List, Union, Type
from zoneinfo import ZoneInfo

from pydantic import BaseModel

from common.constants.database import DbCollections, DatabaseTypes, DATABASE_NAME
from common.constants.states import ServerStates, WorkoutStates, UnitStates
from common.document_database import DocumentDatabaseFactory, DatabaseQueries, DatabaseMask
from common.models.model_validators.model_validator import ModelValidator
from common.utilities.gcp.cloud_logger import Logger, LoggerNames


class BaseStateManager:
    MAX_WAIT_TIME = 500
    SLEEP_TIME = 10

    def __init__(
        self,
        model,
        initial_build_id: str = None,
        build_id: str = None
    ) -> None:
        self.class_name = self.__class__.__name__
        self.log_name = LoggerNames.CLOUD_FN
        self.logger = Logger(self.log_name, class_name=self.class_name)
        self.model = model
        self.initial_build_id = initial_build_id
        self.build_id = build_id
        self.unit_states = UnitStates
        self.server_states = ServerStates
        self.workout_states = WorkoutStates
        self.db = DocumentDatabaseFactory.create_db_object(
            db_type=DatabaseTypes.firestore,
            database_name=DATABASE_NAME,
            log_name=self.log_name
        )
        self.db_queries = DatabaseQueries(db=self.db)
        self.validator = ModelValidator
        self.collection = None
        self.s = None
        self.build = None
        self.event_logs = None
        self.db_mask = DatabaseMask(logger=self.logger)
        self.update_masks = [
            "state",
            "state_timestamp",
        ]

    def set_build_record(self, build_id: str) -> None:
        self.build_id = build_id

        self.build = self.build_record
        if self.build.get('state') is None:
            self.build['state'] = self.s.START.value
            self.build['state_timestamp'] = datetime.now(tz=ZoneInfo("UTC")).isoformat()
            self._set_build_record()
            self.update_record(
                build_id=build_id,
                model=self.model,
                data=self.build,
                update_masks=self.update_masks
            )

    @abstractmethod
    def _set_build_record(self) -> None:
        pass

    @abstractmethod
    def _is_valid_transition(
        self,
        existing_state: Union[Type[Enum], int],
        new_state: Union[Type[Enum], int]
    ) -> bool:
        pass

    @property
    def build_record(self) -> dict:
        return self.db.get(collection_name=self.collection, doc_id=self.build_id)

    def get_running(self) -> List:
        """
        This function returns a list of fixed_arena classes which have expired.
        @return: List of IDs for retired classes
        @rtype: list
        """
        return self.db_queries.get_running(collection_name=DbCollections.SERVER)

    def get_expired(self) -> List:
        """
        This function returns builds which have expired.
        @return: List of IDs for retired classes
        @rtype: list
        """
        return self.db_queries.get_expired(collection_name=self.collection)

    def get_state(self) -> int:
        return self.build['state']

    def get_state_timestamp(self) -> Union[str, float, int]:
        return self.build['state_timestamp']

    def state_transition(
        self,
        new_state: Union[Enum, int]
    ) -> None:
        """
        Consistently changes a datastore entity with the necessary state checks.
        :param new_state: The new state for the server
        :return: Boolean on success. If the state transition is valid, then return True. Otherwise, return False
        """
        self.build = self.build_record
        existing_state = self.build['state']
        new_state = new_state.value if not isinstance(new_state, int) else new_state
        self.build['state'] = new_state
        self.build['state_timestamp'] = datetime.now(timezone.utc).isoformat()
        self.logger.info(
            f"{self.class_name}:{self.build_id} - State Transition from "
            f"{self.s(existing_state).name} to {self.s(new_state).name}",
            existing_state=self.s(existing_state).name,
            new_state=self.s(new_state).name
        )
        if build := self.validator(model=self.model, log_location=self.log_name).load(data=self.build, as_dict=True):
            self.update_record(
                build_id=self.build_id,
                model=self.model,
                data=self.build,
                update_masks=self.update_masks
            )
            self.build = build

    def are_server_builds_finished(self) -> bool:
        max_wait_time = 300
        sleep_time = 10
        wait_time = 0
        servers_finished = False
        while not servers_finished and wait_time < max_wait_time:
            servers_finished = True
            servers = self.db_queries.get_servers(parent_id=self.build_id)
            for server in servers:
                if server.get('state', None) != self.server_states.RUNNING.value:
                    servers_finished = False
            if not servers_finished:
                time.sleep(sleep_time)
                wait_time += sleep_time
        if servers_finished:
            return True
        else:
            return False

    def are_servers_started(self) -> bool:
        return self._server_state_check(server_states=[self.server_states.RUNNING.value])

    def are_servers_stopped(self) -> bool:
        return self._server_state_check(server_states=[self.server_states.STOPPED.value,
                                                       self.server_states.BROKEN.value])

    def are_servers_deleted(self) -> bool:
        return self._server_state_check(server_states=[self.server_states.DELETED.value,
                                                       self.server_states.BROKEN.value])

    def update_record(
        self,
        build_id: str,
        model: Type[BaseModel],
        data: dict,
        update_masks: List[str] = None
    ) -> None:
        """
        Validate and update record based on input model. If successful, sets self.build to
        validated model dict
        """
        if self.validator(model=model, log_location=self.log_name).load(data=data):
            if update_masks:
                update_mask = self.db_mask.get(document=data, keys=update_masks)
                self.db.update(collection_name=self.collection, doc_id=build_id, data=update_mask)
            else:
                self.db.update(collection_name=self.collection, doc_id=build_id, data=data)
            self.build = data

    def _server_state_check(
        self,
        server_states: List
    ) -> bool:
        wait_time = 0
        check_complete = False
        while not check_complete and wait_time < self.MAX_WAIT_TIME:
            check_complete = True
            servers = self.db_queries.get_servers(parent_id=self.build_id)
            for server in servers:
                if server.get('state', None) not in server_states:
                    check_complete = False
                    continue
            if not check_complete:
                time.sleep(self.SLEEP_TIME)
                wait_time += self.SLEEP_TIME
        if check_complete:
            return True
        else:
            return False
