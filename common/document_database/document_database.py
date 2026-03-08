from abc import ABC, abstractmethod
from enum import Enum
from typing import List, Callable, Any, Union, Optional, Tuple

from ..utilities.gcp.cloud_logger import Logger, LoggerNames
from ..constants.database import DbCollections, DATABASE_NAME, DbOperators


class DocumentDatabase(ABC):

    def __init__(
        self,
        project_id: str = None,
        database_name: str = None,
        log_name: str = LoggerNames.CLOUD_FN,
    ) -> None:
        """
        Initialize the DocumentDatabase with the Pydantic model, optional database name, and optional project ID.

        Args:
            project_id (str, optional): Cloud project ID. Defaults to None.
            database_name (str, optional): Name of the database. Defaults to None.
            log_name (str, optional): The name of the Firestore log. Defaults to 'cloud-fn'.
        """
        self.class_name = self.__class__.__name__
        self.database_name = database_name or DATABASE_NAME
        self.project_id = project_id
        self.logger = Logger(
            log_name=log_name,
            class_name=self.class_name
        )
        self.db = None

    def insert(
        self,
        collection_name: DbCollections,
        data: dict,
        use_transaction: bool = False,
        id_field: str = "id"
    ) -> str:
        """
        Insert a document into the database and return the document ID.

        Args:
            id_field (str): Name of field that holds the document ID
            collection_name (str): Name of the collection.
            data (dict): serialized data instance to insert.
            use_transaction (bool): Run operation as a transaction

        Returns:
            str: Document ID of the inserted document.
        """
        doc_id = self._insert(collection_name, data, id_field=id_field, use_transaction=use_transaction)
        self.logger.info(
            f"Inserted document into '{collection_name.value}' with ID: {doc_id}", document_id=doc_id
        )
        return doc_id

    @abstractmethod
    def _insert(
        self,
        collection_name: DbCollections,
        data: dict,
        id_field: str = "id",
        use_transaction: bool = False,
    ) -> str:
        """
        Internal method to insert data into the database.

        Args:
            collection_name (str): Name of the collection.
            data (dict): Serialized data to insert.
            use_transaction (bool): Run operation as a transaction

        Returns:
            str: Document ID of the inserted document.
        """
        pass

    @abstractmethod
    def get(
        self,
        collection_name: DbCollections,
        doc_id: str,
        use_transaction: bool = False
    ) -> dict:
        """
        Retrieve a document by its ID.

        Args:
            doc_id (str): Document ID.
            collection_name (str): Name of the collection.
            use_transaction (bool): Run operation as a transaction

        Returns:
            T: Pydantic model instance with the retrieved data.
        """
        pass

    def update(
        self,
        collection_name: DbCollections,
        doc_id: str,
        data: dict,
        use_transaction: bool = False
    ) -> None:
        """
        Update a document in the database.

        Args:
            collection_name (str): Name of the collection.
            doc_id (str): Document ID.
            data (dict: Pydantic model instance with updated data.
            use_transaction (bool): Run operation as a transaction
        """
        self._update(collection_name, doc_id, data, use_transaction)
        self.logger.info(
            f"Updated document in '{collection_name.value}' with ID: {doc_id}", document_id=doc_id
        )

    @abstractmethod
    def _update(
        self,
        collection_name: DbCollections,
        doc_id: str,
        data: dict,
        use_transaction: bool = False
    ) -> None:
        """
        Internal method to update data in the database.

        Args:
            collection_name (str): Name of the collection.
            doc_id (str): Document ID.
            data (dict): Serialized data for updating.
            use_transaction (bool): Run operation as a transaction
        """
        raise NotImplementedError("update is not implemented for this class.")

    @abstractmethod
    def delete(
        self,
        collection_name: DbCollections,
        doc_id: str,
        use_transaction: bool = False
    ) -> None:
        """
        Delete a document from the database.

        Args:
            collection_name (str): Name of the collection.
            doc_id (str): Document ID.
            use_transaction (bool): Run operation as a transaction
        """
        raise NotImplementedError("delete is not implemented for this class.")

    @abstractmethod
    def query(
        self,
        collection_name: DbCollections,
        filters: Optional[List[Tuple[str, DbOperators, Any]]] = None,
        limit: Optional[int] = None
    ) -> List[dict]:
        """
        Query documents with specified filters.

        Args:
            collection_name (str): Name of the collection.
            filters (list[tuple]): List of tuples (field, DbOperator, value) to filter the documents.
            limit (int): Limit the number of documents returned in query

        Returns:
            List[T]: List of Pydantic model instances matching the query.
        """
        raise NotImplementedError("query is not implemented for this class.")

    def batch_write(
        self,
        operations: List[Callable]
    ) -> None:
        """
        Issue multiple document operations in a single request.

        Args:
             operations (list): List of supported operations to run

        Returns:
            None
        """
        self._handle_batch_splitting(operations)
        self.logger.info(f"executed {len(operations)} operations")

    @abstractmethod
    def _batch_write(
        self,
        operations: List[Callable[[Any], None]]
    ) -> None:
        """
        Issue multiple document operations in a single request.

        Args:
             operations (list): List of supported operations to run

        Returns:
            None
        """
        raise NotImplemented("_batch is not implemented for this class.")

    def _handle_batch_splitting(
        self,
        operations: List[Callable[[Any], None]]
    ) -> None:
        """
        Handles cases where total operations would exceed operations quota for select databases.
        Does not prevent exceeding operations / minute quotas
        """
        batch_size = 500
        total_operations = len(operations)
        exceeds_limit = total_operations > batch_size

        if not exceeds_limit:
            self._batch_write(operations)
        else:
            total_batches = (total_operations + batch_size - 1) // batch_size
            for batch_number in range(total_batches):
                start_index = batch_number * batch_size
                end_index = min(start_index + batch_size, total_operations)
                operations_batch = operations[start_index:end_index]

                try:
                    self._batch_write(operations_batch)
                    self.logger.debug(
                        f'Batch {batch_number + 1}/{total_batches} completed: '
                        f'operations {start_index} to {end_index - 1}'
                    )
                except Exception as e:
                    self.logger.warning(f'Error writing batch {batch_number + 1}: {e}')

    @abstractmethod
    def operation(
        self,
        collection_name: str,
        doc_id: str,
        operation_type: Union[str, Enum],
        data: Any = None
    ) -> Callable:
        """
        Create an operation func based on input operation type

        Args:
            collection_name (str): Name of collection
            doc_id (str): ID of document to run operation on
            operation_type (DbOperationType): Enum of valid operation types
            data (any): Optional updated document
        """
        raise NotImplemented("operation is not implemented for this class.")

    @abstractmethod
    def transaction(
        self,
        operation_func: Callable,
        *args,
        **kwargs
    ) -> Any:
        """
        Executes a database operation within a transaction.

        Args:
            operation_func (Callable): The function that performs the database operation.
            *args: Positional arguments for the operation function.
            **kwargs: Keyword arguments for the operation function.

        Returns:
            Any: The result of the operation function.
        """
        raise NotImplemented("transaction is not implemented for this class.")
