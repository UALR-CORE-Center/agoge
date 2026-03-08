import time
from google.cloud import datastore
from google.cloud.datastore import Entity
from googleapiclient.errors import HttpError
from google.api_core.exceptions import NotFound, Conflict

from common.constants.states import ServerStates, WorkoutStates, UnitStates
from common.utilities.timestamps import Timestamps
from common.utilities.gcp.cloud_logger import Logger, LoggerNames

from ..globals import DatastoreKeyTypes


class DataStoreManager:
    MAX_ATTEMPTS = 20
    WAIT_PERIOD = 3

    def __init__(
        self,
        key_type: DatastoreKeyTypes = None,
        key_id: str = None
    ):
        self.class_name = self.__class__.__name__
        self.logger = Logger(LoggerNames.CLOUD_FN)
        self.key_type = key_type
        self.key_id = key_id
        self.transaction = None
        try:
            self.ds_client = datastore.Client()
        except HttpError as e:
            self.logger.warning(f"{self.class_name} - Error getting datastore client connection. "
                                f"Backing off 5 seconds and trying again")
            time.sleep(5)
            self.ds_client = datastore.Client()
        if self.key_type and self.key_id:
            self.key = self.ds_client.key(self.key_type, self.key_id)
        else:
            self.key = None

    def get(
            self,
            key_type: DatastoreKeyTypes = None,
            key_id: str = None,
            use_transaction: bool = False,
            wait: bool = True
    ) -> Entity:
        """
        Retrieves an entity from Datastore. If not found, retries a specified number of times.
        Args:
            key_type: The kind of the Datastore key.
            key_id: The ID of the Datastore key.
            use_transaction: Flag to indicate if the get should be transactional.
            wait (bool): Flag indicating whether to attempt to grab the key.
        Returns:
            The retrieved Datastore entity or None if not found.
        """
        use_key = self.ds_client.key(key_type, key_id) if key_type else self.key
        entity = self.ds_client.get(use_key) if not use_transaction else self._get_transaction(use_key)

        if not entity and use_key.kind == DatastoreKeyTypes.ADMIN_INFO.value:
            return self._create_new_entity(use_key)

        if wait and not entity:
            for attempt in range(self.MAX_ATTEMPTS):
                time.sleep(self.WAIT_PERIOD)
                entity = self.ds_client.get(use_key) if not use_transaction else self._get_transaction(use_key)
                if entity:
                    break

        return entity

    def put(
            self,
            entity: Entity | dict,
            key_type: DatastoreKeyTypes = None,
            key_id: str = None,
            use_transaction: bool = False
    ) -> None:
        """
        Saves an entity to Datastore.
        Args:
            entity: The entity to be saved.
            key_type: The kind of the Datastore key.
            key_id: The ID of the Datastore key.
            use_transaction: Flag to indicate if the put should be transactional.
        Raises:
            Exception: If a conflict occurs during a transactional put.
        """
        self.key = self.ds_client.key(key_type, key_id) if key_type else self.key
        if isinstance(entity, dict):
            ds_entity = datastore.Entity(self.key)
            ds_entity.update(entity)
        else:
            ds_entity = entity
        ds_entity.key = self.key
        safe_entity = self._create_safe_entity(ds_entity)

        if use_transaction:
            self._put_transaction(safe_entity)
        else:
            self.ds_client.put(safe_entity)

    def put_multi(
            self,
            entities: list[Entity]
    ) -> None:
        self.ds_client.put_multi(entities=entities)

    def delete(
            self,
            key_type: DatastoreKeyTypes = None,
            key_id: str = None
    ) -> None:
        if self.key:
            self.ds_client.delete(self.key)
        else:
            self.set(key_type, key_id)
            self.ds_client.delete(self.key)

    def delete_multi(
            self,
            key_ids: list,
            key_type: DatastoreKeyTypes = None
    ) -> None:
        if not key_type and self.key_type:
            key_type = self.key_type
        else:
            raise ValueError('Missing `key_type` for `delete_multi`')
        keys = []
        for key in key_ids:
            keys.append(self.ds_client.key(key_type, key))
        self.ds_client.delete_multi(keys=keys)

    def query(
            self,
            limit: int = None,
            **kwargs
    ) -> list[Entity]:
        """Returns query object"""
        if limit:
            return list(self.ds_client.query(kind=self.key_type, **kwargs).fetch(limit=limit))
        return list(self.ds_client.query(kind=self.key_type, **kwargs).fetch())

    def set(
            self,
            key_type: DatastoreKeyTypes,
            key_id: str
    ) -> None:
        self.key_id = key_id
        self.key = self.ds_client.key(key_type, self.key_id)

    def entity(
            self,
            obj: dict
    ) -> Entity:
        """Returns Entity object"""
        ds_entity = datastore.Entity(self.key)
        ds_entity.update(obj)
        return self._create_safe_entity(ds_entity)

    def get_servers(self) -> list[Entity]:
        filters = [('parent_id', '=', self.key_id)]
        query_servers = self.ds_client.query(kind=DatastoreKeyTypes.SERVER, filters=filters)
        return list(query_servers.fetch())

    def get_children(
            self,
            child_key_type: DatastoreKeyTypes,
            parent_id: str,
            wait: bool = True
    ) -> list[Entity]:
        filters = [('parent_id', '=', parent_id)]
        query_workspaces = self.ds_client.query(kind=child_key_type, filters=filters)
        children = list(query_workspaces.fetch())
        i = 0
        if wait:
            while not children and i < self.MAX_ATTEMPTS:
                i += 1
                time.sleep(self.WAIT_PERIOD)
                children = list(query_workspaces.fetch())
        return children

    def get_expired(self) -> list[str]:
        expired = []
        query_expired = list(self.ds_client.query(kind=self.key_type).fetch())
        current_timestamp = Timestamps.get_current_timestamp_utc()
        if self.key_type == DatastoreKeyTypes.WORKOUT:
            for obj in query_expired:
                if expiration := obj.get('expires'):
                    if (
                            int(expiration) < current_timestamp
                            and obj.get('state', None) != WorkoutStates.DELETED.value
                    ):
                        expired.append(obj.key.name)
        elif self.key_type == DatastoreKeyTypes.SERVER:
            for server in query_expired:
                if shutoff_ts := server.get('shutoff_timestamp'):
                    if shutoff_ts < current_timestamp:
                        expired.append(server)
        elif self.key_type == DatastoreKeyTypes.UNIT:
            for unit in query_expired:
                if int(unit['workspace_settings']['expires']) < current_timestamp:
                    if unit.get('state', None) not in [UnitStates.DELETED.value]:
                        expired.append(unit.key.name)
        return expired

    def get_expiring_units(self) -> list[str]:
        """
        returns a list of all the units that expire within 48 hours
        @return:
        """
        two_days = 172800
        expire_ts = Timestamps.get_current_timestamp_utc(add_seconds=two_days)
        filters = [('state', '!=', WorkoutStates.DELETED.value)]
        query_expiring = self.ds_client.query(kind=DatastoreKeyTypes.UNIT, filters=filters)
        expiring = []
        for obj in query_expiring.fetch():
            if obj['workspace_settings']['expires'] < expire_ts:
                expiring.append(obj.key.name)
        return expiring

    def get_ready_for_shutoff(self) -> list[str] | list:
        ready_for_shutoff = []
        query_shutoff = self.ds_client.query(kind=self.key_type)
        if self.key_type in [DatastoreKeyTypes.WORKOUT]:
            current_ts = Timestamps.get_current_timestamp_utc()
            for obj in list(query_shutoff.fetch()):
                if shutoff_ts := obj.get('shutoff_timestamp', None):
                    if shutoff_ts < current_ts:
                        ready_for_shutoff.append(obj.key.name)
            return ready_for_shutoff
        else:
            self.logger.warning(f"{self.class_name}:{self.key_type} - "
                                f"Attempting to query labs ready for shutoff "
                                f"on an unsupported key type: {self.key_type}.")
            return []

    def get_running(self) -> list[Entity]:
        """
        returns a list of running entities associated with the key_type
        @return:
        """
        running = []
        query_filters = []
        if self.key_type == DatastoreKeyTypes.SERVER:
            query_filters = [('state', '=', ServerStates.RUNNING.value)]
        elif self.key_type == DatastoreKeyTypes.WORKOUT:
            query_filters = [('state', '=', WorkoutStates.RUNNING.value)]
        elif self.key_type == DatastoreKeyTypes.IMAGE:
            query_filters = [('state', '=', ServerStates.RUNNING.value)]
        query_running = self.ds_client.query(kind=self.key_type, filters=query_filters)
        running += list(query_running.fetch())
        return running

    def get_admins(self) -> list[Entity]:
        """Returns list of emails for admin accounts"""
        users = self.ds_client.query(
            kind=DatastoreKeyTypes.USERS,
            filters=[('permissions.admin', '=', True)]
        )
        return list(users.fetch())

    def _create_new_entity(
            self,
            key
    ) -> Entity:
        new_entity = datastore.Entity(key=key)
        self.ds_client.put(new_entity)
        return new_entity

    @staticmethod
    def _create_safe_entity(
            entity: dict | Entity
    ) -> Entity:
        """
        Creates a safe entity by excluding large strings from indexes.
        Args:
            entity: The entity to be made safe for Datastore.
        Returns:
            The safe entity.
        """
        exclude_from_indexes = [
            k for k, v in entity.items()
            if isinstance(v, str) and len(v) > 1500
        ]
        entity.exclude_from_indexes = exclude_from_indexes
        return entity

    def _get_transaction(
            self,
            key
    ) -> Entity:
        """
        Retrieves an entity within a transaction.
        Args:
            key: The Datastore key of the entity to retrieve.
        Returns:
            The retrieved entity with the transaction attached.
        """
        self.transaction = self.ds_client.transaction()
        self.transaction.begin()
        entity = self.ds_client.get(key)
        return entity

    def _put_transaction(
            self,
            obj: Entity
    ) -> None:
        """
        Saves an entity within a transaction.
        Args:
            obj: The entity to be saved.
        Raises:
            Exception: If the transaction is inactive or not started.
            Conflict: If a conflict occurs during the transaction.
        """
        if not self.transaction:
            self.logger.warning(
                f"{self.class_name} - Datastore put operation is being executed without a "
                f"transaction. This could lead to concurrency issues. Review the necessity of a transaction for this "
                f"operation to ensure data integrity. "
            )
        self.transaction.put(obj)
        try:
            self.transaction.commit()
        except Conflict:
            raise Exception("Record modified while processing datastore transaction.")

