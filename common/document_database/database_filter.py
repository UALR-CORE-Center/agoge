import operator
from typing import List, Tuple, Union, Any

from common.utilities.gcp.cloud_logger import Logger, LoggerNames


class DatabaseFilter:
    """
    Manually filter queries returned from Document database.
    Useful for cases where required filters are more complex than API allows
    """
    class Operators:
        EQUAL = operator.eq
        NOT_EQUAL = operator.ne
        LESS_THAN = operator.lt
        LESS_THAN_EQUAL = operator.le
        GREATER_THAN = operator.gt
        GREATER_THAN_EQUAL = operator.ge

    def __init__(
        self,
        query: List,
        log_name: str = LoggerNames.CLOUD_FN
    ) -> None:
        self.class_name = self.__class__.__name__
        self.query = query
        self.filters = []
        self.filtered = []
        self.logger = Logger(log_name, class_name=self.class_name)

    def filter(self) -> List:
        if not self.filters:
            return []

        for item in self.query:
            try:
                if self._apply_filters(item):
                    self.filtered.append(item)
            except ValueError as e:
                self.logger.warning(f"Error applying filter: {e}")

        return self.filtered

    def get(self) -> Union[List[Tuple], List]:
        """Returns list of filters"""
        return self.filters

    def add(
        self,
        key: str,
        op: Operators,
        compare_value: Any
    ) -> None:
        """
        Args:
            key (str): Key in dictionary where base value is stored. Nested keys should be dot delimited
            op (str): Operation to apply to list
            compare_value (Any): value to compare to base value

        Returns: None

        Examples:
            add_filter(
                key="parent_id",
                op=DataStoreFilter.Operators.EQUAL,
                "ajdkuekjdasd"
            )

            add_filter(
                key="workspace_settings.expires",
                op=DataStoreFilter.Operators.LESS_THAN,
                17209238290823
            )
        """
        split_key = key.split(".")
        self.filters.append((split_key, op, compare_value))

    def _add_filters(self, filters: List[Tuple]) -> None:
        for filter_args in filters:
            self.add(*filter_args)

    def _apply_filters(
        self,
        item: Any
    ) -> bool:
        for item_filter in self.filters:
            split_key, operation, compare = item_filter
            try:
                value = self._get_nested_value(item, split_key)
                if value is None or not operation(value, compare):
                    return False
            except (KeyError, TypeError, ValueError) as e:
                self.logger.warning(f"Error applying filter on {split_key}: {e}")
                return False
        return True

    def _get_nested_value(
        self,
        data: dict,
        keys: str
    ) -> Any:
        """Helper method to fetch value from a nested dictionary using a pre-split list of keys."""
        value = data

        try:
            for k in keys:
                value = value[k]
        except (KeyError, TypeError) as e:
            self.logger.warning(f"Error accessing nested keys {keys}: {e}")
            return None
        return value
