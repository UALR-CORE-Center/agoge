from typing import List, Dict, Any

from common.utilities.gcp.cloud_logger import Logger


class DatabaseMask:
    """Document database UPDATE field mask generator"""
    def __init__(self, logger: Logger) -> None:
        self.logger = logger

    def get(
        self,
        document: Dict,
        keys: List[str]
    ) -> Dict:
        """Generates a field mask for a document update event.

        This method creates a field mask dictionary based on the provided document
        and list of keys. For each key, it attempts to fetch the corresponding value
        from the document using nested key access. If the key is not found or an error
        occurs during retrieval, a warning is logged and that key is skipped.

        Args:
            document (dict): The document from which to generate the field mask.
            keys (list[str]): A list of keys to use for field mask generation. Nested keys
                should be specified using dot notation. Examples:
                    - ["creation_timestamp", "state", "id"]
                    - ["workspace_settings.expires", "lms_connection.assessment", "parent_id"]

        Returns:
            dict: A dictionary mapping each key (as provided) to its corresponding value
                from the document.
        """
        mask = {}
        for key in keys:
            split_key = key.split('.')
            try:
                value = self._get_nested_value(document, split_key)
                mask[key] = value
            except (KeyError, TypeError, ValueError) as e:
                self.logger.warning(f'Error generating update mask on {split_key}: {e}. Ignoring ...')
        return mask

    def _get_nested_value(
        self,
        data: dict,
        keys: List[str]
    ) -> Any:
        """Retrieves a nested value from a dictionary using a list of keys.

        This helper method traverses the input dictionary using the provided list of keys
        to extract a nested value. If any key in the sequence is not found or an error occurs
        during traversal, the method logs an error and returns None.

        Args:
            data (dict): The dictionary from which to retrieve the value.
            keys (list[str]): A list of keys that define the path to the desired nested value.

        Returns:
            Any: The nested value if all keys are found; otherwise, None.
        """
        value = data
        try:
            for k in keys:
                value = value[k]
        except (KeyError, TypeError) as e:
            self.logger.error(f"Error accessing nested keys {keys}: {e}")
            return None
        return value
