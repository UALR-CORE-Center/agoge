import time
from datetime import datetime
from typing import List
from zoneinfo import ZoneInfo

from common.models.agoge import UnitModel
from common.constants.database import DbCollections

from .base_state_manager import BaseStateManager


class UnitStateManager(BaseStateManager):
    def __init__(
        self,
        build_id: str = None
    ) -> None:
        super().__init__(model=UnitModel)
        self.s = self.unit_states
        self.collection = DbCollections.UNIT
        if build_id:
            self.build_id = build_id
            self.build = self.db.get(collection_name=self.collection, doc_id=self.build_id)
            if self.build.get('state') is None:
                self.build['state'] = self.s.START.value
                self.build['state_timestamp'] = datetime.now(tz=ZoneInfo("UTC")).isoformat()
                self.update_record(
                    build_id=self.build_id,
                    model=self.model,
                    data=self.build,
                    update_masks=self.update_masks
                )

    def _set_build_record(self) -> None:
        pass

    def _is_valid_transition(self, existing_state, new_state):
        pass

    def are_workouts_deleted(self):
        return self._workout_state_check(
            workout_states=[self.workout_states.DELETED.value, self.workout_states.BROKEN.value]
        )

    def _workout_state_check(
        self,
        workout_states: List
    ) -> bool:
        wait_time = 0
        check_complete = False
        while not check_complete and wait_time < self.MAX_WAIT_TIME:
            check_complete = True
            workouts = self.db_queries.get_children(
                parent_id=self.build_id,
                child_collection=DbCollections.WORKOUT,
            )
            for workout in workouts:
                if workout.get('state') not in workout_states:
                    check_complete = False
                    continue
            if not check_complete:
                time.sleep(self.SLEEP_TIME)
                wait_time += self.SLEEP_TIME
        if check_complete:
            return True
        else:
            return False



