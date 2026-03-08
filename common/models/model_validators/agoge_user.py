from typing import Union, List

from .model_validator import ModelValidator
from ..users import AgogeUser, SafeAgogeUser
from ...utilities.gcp.cloud_logger import LoggerNames


class SafeAgogeUserValidator(ModelValidator):
    def __init__(self, log_location: str = LoggerNames.API) -> None:
        super().__init__(model=SafeAgogeUser, log_location=log_location)

    def load(
        self,
        data: Union[dict, List[dict]],
        halt_on_error: bool = True,
        as_dict: bool = False,
    ) -> Union[SafeAgogeUser, List[SafeAgogeUser], dict]:
        self.halt_on_error = halt_on_error
        self.as_dict = as_dict

        for user in data:
            user['settings'] = AgogeUser(**user).get_settings_overview()

        return self._safe_load(data)
