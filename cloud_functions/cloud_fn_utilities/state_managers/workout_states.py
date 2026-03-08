from datetime import datetime
from zoneinfo import ZoneInfo

from common.constants.database import DbCollections
from common.constants.states import WorkoutStates
from common.models.agoge import WorkoutModel

from .base_state_manager import BaseStateManager


class WorkoutStatesManager(BaseStateManager):
    MAX_WAIT_TIME = 300
    COMPLETION_STATES = [
        WorkoutStates.COMPLETED_DELETING_SERVERS.value, WorkoutStates.COMPLETED_FIREWALL.value,
        WorkoutStates.COMPLETED_NETWORKS.value, WorkoutStates.COMPLETED_ROUTES.value,
        WorkoutStates.COMPLETED_SERVERS.value, WorkoutStates.COMPLETED_STUDENT_ENTRY.value
    ]
    OTHER_VALID_TRANSITIONS = [
        (WorkoutStates.DELETED.value, WorkoutStates.START.value),
        (WorkoutStates.READY.value, WorkoutStates.START.value),
        (WorkoutStates.READY.value, WorkoutStates.STARTING.value),
        (WorkoutStates.START.value, WorkoutStates.DELETING_SERVERS.value),
        (WorkoutStates.START.value, WorkoutStates.BUILDING_NETWORKS.value),
        (WorkoutStates.START.value, WorkoutStates.STARTING.value),
        (WorkoutStates.STARTING.value, WorkoutStates.RUNNING.value),
        (WorkoutStates.COMPLETED_NETWORKS.value, WorkoutStates.BUILDING_SERVERS.value),
        (WorkoutStates.BUILDING_SERVERS.value, WorkoutStates.BUILDING_FIREWALL_RULES.value),
        (WorkoutStates.BUILDING_FIREWALL_RULES.value, WorkoutStates.COMPLETED_FIREWALL_RULES.value),
        (WorkoutStates.COMPLETED_FIREWALL_RULES.value, WorkoutStates.RUNNING.value),
        (WorkoutStates.RUNNING.value, WorkoutStates.STOPPING.value),
        (WorkoutStates.STOPPING.value, WorkoutStates.READY.value),
        (WorkoutStates.NOT_BUILT.value, WorkoutStates.BUILDING_SERVERS.value)
    ]

    def __init__(
        self,
        initial_build_id: str = None
    ) -> None:
        super().__init__(model=WorkoutModel, initial_build_id=initial_build_id)
        self.class_name = self.__class__.__name__
        self.s = self.workout_states
        self.collection = DbCollections.WORKOUT
        self.update_masks = [
            "state",
            "state_timestamp",
            "active"
        ]
        if initial_build_id:
            self.build = self.db.get(collection_name=self.collection, doc_id=initial_build_id)
            if self.build.get('state') is None:
                self.build['state'] = self.s.START.value
                self.build['prev_state'] = self.s.START.value
                self.build['state_timestamp'] = datetime.now(tz=ZoneInfo("UTC")).isoformat()

                update_mask = ['prev_state', *self.update_masks]
                self.update_record(
                    build_id=initial_build_id,
                    model=self.model,
                    data=self.build,
                    update_masks=update_mask
                )
            self.build_id = initial_build_id

    def _set_build_record(self) -> None:
        self.build['prev_state'] = self.s.START.value

    def state_transition(self, new_state):
        self.build = self.build_record
        new_state = new_state.value if not isinstance(new_state, int) else new_state
        existing_state = self.get_state()
        self.build['state'] = new_state
        self.build['state_timestamp'] = datetime.now(tz=ZoneInfo("UTC")).isoformat()

        update_mask = ['prev_state', *self.update_masks]
        if existing_state != WorkoutStates.BROKEN.value:
            self.build['prev_state'] = existing_state
        else:
            self.build['prev_state'] = new_state

        if self._is_valid_transition(existing_state, new_state):
            if new_state == WorkoutStates.DELETED.value:
                self.build['active'] = False
            elif new_state == WorkoutStates.READY.value:
                self.build['active'] = True
            self.logger.info(f"{self.class_name}:{self.build_id} - State Transition from "
                             f"{self.s(existing_state).name} to {self.s(new_state).name}")

            self.update_record(build_id=self.build_id, model=self.model, data=self.build, update_masks=update_mask)
            return True
        else:
            self.update_record(build_id=self.build_id, model=self.model, data=self.build, update_masks=update_mask)
            return False

    def _is_valid_transition(
        self,
        existing_state: int,
        new_state: int
    ) -> bool:
        if new_state in [self.s.START.value, self.s.NOT_BUILT.value, self.s.DELETING_SERVERS.value]:
            return True
        elif self._is_valid_state(existing_state, new_state):
            return True
        elif (new_state in self.COMPLETION_STATES
              and existing_state not in [self.s.DELETED.value, self.s.BROKEN.value]):
            return True
        elif (existing_state, new_state) in self.OTHER_VALID_TRANSITIONS:
            return True
        else:
            self.logger.warning(f"{self.class_name}:{self.build_id} - Invalid build state transition! "
                                f"Attempting to move to {self.s(new_state).name}, "
                                f"but the build is currently in the state "
                                f"{self.s(existing_state).name}")
            return False

    def _is_valid_state(
        self,
        existing_state: int,
        new_state: int
    ) -> bool:
        valid_states = {
            self.s.BUILDING_NETWORKS.value: [
                self.s.NOT_BUILT,
                self.s.START.value,
                self.s.BROKEN.value,
                self.s.BUILDING_NETWORKS.value
            ],
            self.s.BUILDING_SERVERS.value: [
                self.s.COMPLETED_NETWORKS.value,
                self.s.BUILDING_SERVERS.value
            ],
            self.s.BUILDING_ROUTES.value: [
                self.s.COMPLETED_SERVERS.value,
                self.s.BUILDING_ROUTES.value
            ],
            self.s.BUILDING_FIREWALL.value: [
                self.s.COMPLETED_ROUTES.value,
                self.s.COMPLETED_SERVERS.value,
                self.s.COMPLETED_NETWORKS.value,
                self.s.BUILDING_FIREWALL.value
            ],
            self.s.READY.value: [
                self.s.COMPLETED_SERVERS.value,
                self.s.BUILDING_SERVERS.value,
                self.s.COMPLETED_FIREWALL_RULES.value
            ],
        }
        return existing_state in valid_states.get(new_state, [])
