from datetime import datetime
from zoneinfo import ZoneInfo

from common.constants.database import DbCollections
from common.models.agoge import AgogeImageModel

from .base_state_manager import BaseStateManager


class ImageStateManager(BaseStateManager):
    def __init__(self):
        super().__init__(model=AgogeImageModel)
        self.collection = DbCollections.IMAGE
        self.s = self.server_states

    def _set_build_record(self) -> None:
        pass

    def set_build_record(self, build_id: str) -> None:
        self.build_id = build_id
        self.build = self.build_record
        if self.build.get('state') is None:
            self.build['state'] = self.s.START.value
            self.build['state_timestamp'] = datetime.now(tz=ZoneInfo("UTC")).isoformat()
            self.update_record(
                build_id=build_id,
                model=self.model,
                data=self.build,
                update_masks=self.update_masks
            )

    def get_status(self):
        return self.build['status']

    def _is_valid_transition(self, existing_state, new_state):
        return True
