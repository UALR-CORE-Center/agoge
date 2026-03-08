from typing import List, Any

from ..constants.database import DbCollections, DbOperators
from ..constants.states import ServerStates, UnitStates, WorkoutStates
from ..utilities.timestamps import Timestamps
from ..utilities.gcp.cloud_logger import LoggerNames, Logger
from .document_database import DocumentDatabase


class DatabaseQueries:
    def __init__(
        self,
        db: DocumentDatabase,
        log_name: str = LoggerNames.CLOUD_FN
    ) -> None:
        self.db = db
        self.class_name = self.__class__.__name__
        self.logger = Logger(log_name=log_name, class_name=self.class_name)

    def get_active(
        self,
        collection_name: DbCollections
    ) -> List[dict]:
        if collection_name == DbCollections.UNIT:
            filters = [('state', DbOperators.NOT_EQUAL, UnitStates.DELETED.value)]
        else:
            filters = [
                ('state', DbOperators.GREATER_THAN, WorkoutStates.NOT_BUILT.value),
                ('state', DbOperators.LESS_THAN, WorkoutStates.DELETING_SERVERS.value),
            ]
        return self.db.query(collection_name=collection_name, filters=filters)

    def get_children(
        self,
        parent_id: str,
        child_collection: DbCollections
    ) -> List[dict]:
        filters = [('parent_id', DbOperators.EQUAL, parent_id)]
        return self.db.query(collection_name=child_collection, filters=filters)

    def get_expired(
        self,
        collection_name: DbCollections,
        add_seconds: int = 0
    ) -> List[dict]:
        """
            Get expired or expiring objects based on current collection and current timestamp.

            Args:
                collection_name (DbCollections): Name of collection to query
                add_seconds (int): Number of seconds to add to current timestamp
        """
        current_ts = Timestamps.get_current_timestamp_utc(add_seconds=add_seconds)
        expired = []
        if collection_name == DbCollections.UNIT:
            filters = [
                ('state', DbOperators.NOT_IN, [WorkoutStates.DELETED.value]),
            ]
            units = self.db.query(collection_name=DbCollections.UNIT, filters=filters)
            expired = self._less_than_ts('workspace_settings.expires', current_ts, units)
        elif collection_name == DbCollections.WORKOUT:
            filters = [('state', DbOperators.NOT_EQUAL, WorkoutStates.DELETED.value),]
            workouts = self.db.query(collection_name=collection_name, filters=filters)
            expired = self._less_than_ts('expires', current_ts, workouts)
        elif collection_name == DbCollections.SERVER:
            filters = [('shutoff_timestamp', DbOperators.LESS_THAN, current_ts)]
            expired = self.db.query(collection_name=collection_name, filters=filters)
        elif collection_name == DbCollections.SNAPSHOTS:
            filters = [('expiration_date', DbOperators.LESS_THAN, current_ts)]
            expired = self.db.query(collection_name=DbCollections.SNAPSHOTS, filters=filters)
        else:
            raise NotImplemented(f"`get_expiration` not implemented for collection type {collection_name}")

        return expired

    def get_expiring_units(self) -> List[dict]:
        two_days = 172800
        return self.get_expired(collection_name=DbCollections.UNIT, add_seconds=two_days)

    def get_ready_for_shutoff(
        self,
        collection_name: DbCollections
    ) -> List[dict]:
        """Return list of non-deleted objects that are safe to stop"""
        if collection_name in [DbCollections.WORKOUT]:
            current_ts = Timestamps.get_current_timestamp_utc()
            filters = [('shutoff_timestamp', DbOperators.LESS_THAN, current_ts)]
            results = self.db.query(collection_name=collection_name, filters=filters)
            return [
                workout for workout in results
                if int(workout['state']) != WorkoutStates.DELETED.value
            ]
        else:
            self.logger.warning(
                f"{self.class_name}:{collection_name} - "
                f"on an unsupported collection type: {collection_name}"
            )

    def get_running(
        self,
        collection_name: DbCollections
    ) -> List[dict]:
        if collection_name == DbCollections.SERVER:
            query_filters = [('state', DbOperators.EQUAL, ServerStates.RUNNING.value)]
        elif collection_name == DbCollections.WORKOUT:
            query_filters = [('state', DbOperators.EQUAL, WorkoutStates.RUNNING.value)]
        elif collection_name == DbCollections.IMAGE:
            query_filters = [('state', DbOperators.EQUAL, ServerStates.RUNNING.value)]
        else:
            raise NotImplemented(f"`get_running` not implemented for collection type {collection_name}")
        return self.db.query(collection_name=collection_name, filters=query_filters)

    def get_servers(
        self,
        parent_id: str
    ) -> List[dict]:
        filters = [('parent_id', DbOperators.EQUAL, parent_id)]
        return self.db.query(collection_name=DbCollections.SERVER, filters=filters)

    def _less_than_ts(
        self,
        key: str,
        current_ts: float,
        data: List
    ) -> List:
        filtered = []
        split_key = key.split(".")
        for item in data:
            if key_value := self._get_nested_value(data=item, keys=split_key):
                if int(key_value) < current_ts:
                    filtered.append(item)
        return filtered

    def _get_nested_value(
        self,
        data: dict,
        keys: List[str]
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
