import re

from common.exceptions import AgogeValidationError
from common.models.agoge import AgogeSummaryModel


class SummaryValidator:
    def __init__(
        self,
        config: dict
    ) -> None:
        self.config = config

    def load(self, summary: dict) -> dict:
        AgogeSummaryModel(**summary)
        self._validate()

        return self.config

    def _validate(self) -> None:
        summary = self.config['summary']
        if not self._validate_name(summary['name']):
            raise AgogeValidationError(f'Invalid specification name {summary["name"]}: '
                                       f'Names must meet the following requirements:'
                                       f'\n\t- Start with a letter or number.'
                                       f'\n\t- Followed by up to 100 mixed case letters, numbers, '
                                       f'colons (":"), or spaces'
                                       f'\n\t- Cannot end in a special character')

        if not self._validate_author(summary['author']):
            raise AgogeValidationError(f"Invalid specification author {str(summary['author'])}: "
                                       f"Authors must meet the following requirements:"
                                       f"\n\t- Starts with a letter or number"
                                       f"\n\t- Followed by up to 48 letters, "
                                       f"numbers, and spaces."
                                       f"\n\t- Cannot end in a special character"
                                       f"\n\t- Cannot exceed 50 characters in length")

    @staticmethod
    def _validate_name(
        spec_name: str
    ) -> bool:
        pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9\s\-:.@]{0,98}[a-zA-Z0-9])?$'
        return bool(re.match(pattern, str(spec_name)))

    @staticmethod
    def _validate_author(
        author: str
    ) -> bool:
        pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9\s]{0,48}[a-zA-Z0-9])?$'
        return bool(re.match(pattern, str(author)))

# [ eof ]
