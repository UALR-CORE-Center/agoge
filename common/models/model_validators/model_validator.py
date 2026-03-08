from typing import Dict, Optional, Union, TypeVar, Type, List, Generic, Any
from pydantic import BaseModel, ValidationError

from ...utilities.gcp.cloud_logger import Logger, LoggerNames

M = TypeVar('M', bound=BaseModel)


class ModelValidator(Generic[M]):
    def __init__(
        self,
        model: Type[M],
        log_location: str = LoggerNames.API
    ) -> None:
        self.class_name = self.__class__.__name__
        self.model = model
        self.halt_on_error = True
        self.as_dict = False
        self.logger = Logger(
            log_location,
            class_name=self.class_name,
        )

    def load(
        self,
        data: Union[Dict, List[Dict]],
        halt_on_error: bool = True,
        as_dict: bool = False
    ) -> Optional[Union[List[Union[M, Dict]], M, Dict]]:
        self.halt_on_error = halt_on_error
        self.as_dict = as_dict
        return self._safe_load(data)

    def _safe_load(
        self,
        data: Union[Dict, List[Dict]],
    ) -> Optional[Union[List[Union[M, Dict]], M, Dict]]:
        if isinstance(data, list):
            valid_objects = []
            for item in data:
                try:
                    valid_objects.append(self._safe_load(item))
                except ValidationError as e:
                    self._on_error(item, e)
            return valid_objects
        elif isinstance(data, dict):
            try:
                model_instance: BaseModel = self.model(**data)
                if self.as_dict:
                    return model_instance.model_dump()
                return model_instance
            except ValidationError as e:
                self._on_error(data, e)
        else:
            msg = f"Unsupported object type {type(data)}"
            self.logger.error(msg, data=data, model=self.model.__name__)
            raise ValueError(msg)

    def _on_error(
        self,
        item: Any,
        error: Exception
    ) -> None:
        if self.halt_on_error:
            self.logger.error(f"{self.class_name} - Validation errors occurred while loading "
                              f"the model: {error}", model=self.model.__name__)
            raise error
        else:
            msg = f"{self.class_name} - Skipping invalid object due to validation error: {error}. {item}"
            self.logger.warning(msg, model=self.model.__name__)


# [ eof ]
