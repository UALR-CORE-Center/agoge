# Model Validators

Model validators use the underlying Pydantic class to validate input data with a selected model. The classes will then
catch any errors thrown and depending on attribute values either:
- Create an 'error' log event and raise the appropriate error
- Create a 'warning' log event and ignore the input object
- If no errors are thrown, return either the associated Pydantic model or validated model dictionary.

The accepted input data types is either a `dict` or a `List[dict]`.

## Extending the Validator Class
For most use cases, the default functionality provided in `ModelValidator` is sufficient. However, some use cases will
require additional data processing on addition to the base logic. In this case, simply inherit
from `ModelValidator` class and add any additional logic in the `load` method prior to calling `_safe_load`.

```python
# Example of simple ModelValidator extension
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

```
