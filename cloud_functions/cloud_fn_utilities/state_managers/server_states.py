from datetime import datetime
from zoneinfo import ZoneInfo

from common.models.agoge import ServerModel
from common.constants.database import DbCollections

from .base_state_manager import BaseStateManager


class ServerStateManager(BaseStateManager):
    def __init__(self):
        super().__init__(model=ServerModel)
        self.s = self.server_states
        self.collection = DbCollections.SERVER

    def _set_build_record(self) -> None:
        pass

    def _is_valid_transition(self, existing_state, new_state):
        return True
