import google.auth
from google.cloud import firestore
from google.cloud.firestore_v1 import FieldFilter
from google.api_core.exceptions import GoogleAPIError, NotFound, PermissionDenied
from typing import Type, List, Callable, Any, Optional, Tuple
import logging

from .document_database import DocumentDatabase
from ..constants.database import DbCollections, DbOperationTypes, DbOperators
from ..utilities.gcp.cloud_logger import LoggerNames


class FirestoreDatabase(DocumentDatabase):
    def __init__(
        self,
        project_id: str = None,
        database_name: str = None,
        log_name: str = LoggerNames.CLOUD_FN,
        test_read_access: bool = False
    ) -> None:
        """
        Initialize the FirestoreDatabase with the model and project ID.

        Args:
            project_id (str, optional): GCP project ID. Defaults to None.
            database_name (str, optional): The name of the Firestore database to use.
            log_name (str, optional): The name of the Firestore log. Defaults to 'cloud-fn'.
        """
        # Try connecting to Firestore
        try:
            super().__init__(project_id=project_id, database_name=database_name, log_name=log_name)
            self.db = firestore.Client(database=self.database_name, project=self.project_id)
        except (NotFound, PermissionDenied) as e:
            raise RuntimeError("Firestore database does not exist or cannot be accessed.") from e
        except GoogleAPIError as e:
            self.logger.error(f"General Firestore error using database {database_name}: {e}")
            self.db = None

    def _insert(
        self,
        collection_name: DbCollections,
        data: dict,
        id_field: str = "id",
        use_transaction: bool = False
    ) -> str:
        """
        Internal method to insert data into Firestore.

        Args:
            collection_name (DbCollections): Name of the Firestore collection.
            data (dict): Serialized data to insert.
            id_field (str): The ID to use for the document instead of the default arbitrary ID assigned for new
                documents.

        Returns:
            str: Document ID of the inserted document.
        """
        custom_id = None
        try:
            if id_field not in data:
                raise ValueError(f"The specified ID field '{id_field}' is missing from the data.")

            custom_id = data[id_field]
            doc_ref = self.db.collection(collection_name.value).document(custom_id)
            doc_ref.set(data)
            self.logger.debug(f"Inserted document with ID: {custom_id}", custom_id=custom_id)
            return custom_id
        except Exception as e:
            self.logger.error(f"Error inserting document: {e}", custom_id=custom_id)
            raise

    def get(
        self,
        collection_name: DbCollections,
        doc_id: str,
        use_transaction: bool = False
    ) -> dict:
        """
        Retrieve a document by its ID.

        Args:
            collection_name (DbCollections): Name of the Firestore collection.
            doc_id (str): Document ID in Firestore.
            use_transaction (bool): Whether to run operation as a transaction.

        Returns:
            T: Pydantic model instance with the retrieved data.
        """
        doc_ref = self.db.collection(collection_name.value).document(doc_id)
        try:
            if use_transaction:
                return self.transaction(
                    operation_func=self._transaction_operation,
                    doc_ref=doc_ref,
                    operation=DbOperationTypes.GET
                )
            else:
                doc = doc_ref.get()
                if doc.exists:
                    data = doc.to_dict()
                    # Image documents can contain startup scripts with embedded
                    # credentials. Log identifiers, never document payloads.
                    self.logger.debug(f"Retrieved document with ID: {doc_id}", custom_id=doc_id)
                    return data
                else:
                    self.logger.error(f"Document with ID {doc_id} does not exist.")
                    return {}
        except Exception as e:
            self.logger.error(f"Error getting document: {e}")
            raise

    def _update(
        self,
        collection_name: DbCollections,
        doc_id: str,
        data: dict,
        use_transaction: bool = False
    ) -> None:
        """
        Internal method to update data in Firestore.

        Args:
            collection_name (DbCollections): Name of the Firestore collection.
            doc_id (str): Document ID to update.
            data (dict): Serialized data for updating.
            use_transaction (bool): Run operation as a transaction
        """
        try:
            doc_ref = self.db.collection(collection_name.value).document(doc_id)
            if use_transaction:
                self.transaction(
                    operation_func=self._transaction_operation,
                    doc_ref=doc_ref,
                    operation=DbOperationTypes.SET,
                    data=data,
                    merge=True
                )
            else:
                doc_ref.set(data, merge=True)
            self.logger.debug(f"Updated document with ID: {doc_id}", custom_id=doc_id)
        except Exception as e:
            logging.error(f"Error updating document: {e}")
            raise

    def delete(
        self,
        collection_name: DbCollections,
        doc_id: str,
        use_transaction: bool = False
    ) -> None:
        """
        Delete a document from Firestore.

        Args:
            collection_name (DbCollections): Name of the Firestore collection.
            doc_id (str): Document ID to delete.
            use_transaction (bool): Run operation as a transaction
        """
        try:
            doc_ref = self.db.collection(collection_name.value).document(doc_id)
            if use_transaction:
                self.transaction(
                    operation_func=self._transaction_operation,
                    doc_ref=doc_ref,
                    operation=DbOperationTypes.DELETE
                )
            else:
                self.db.collection(collection_name.value).document(doc_id).delete()
            self.logger.info(f"Deleted document with ID: {doc_id}", custom_id=doc_id)
        except Exception as e:
            self.logger.error(f"Error deleting document: {e}", custom_id=doc_id)
            raise

    def query(
        self,
        collection_name: DbCollections,
        filters: Optional[List[Tuple[str, DbOperators, Any]]] = None,
        limit: Optional[int] = None
    ) -> List[dict]:
        """
        Query documents with specified filters.

        Args:
            collection_name (DbCollections): Name of the Firestore collection.
            filters: Optional list of Tuple (field, DbOperator, value) to filter the documents.
            limit (int): Limit the number of documents returned in query


        Returns:
            List[T]: List of Pydantic model instances matching the query.
        """
        try:
            collection_ref = self.db.collection(collection_name.value)
            query_ref = collection_ref

            if filters:
                for field, op_string, value in filters:
                    query_ref = query_ref.where(filter=FieldFilter(field, op_string.value, value))

            if limit:
                query_ref = query_ref.limit(limit)

            results = query_ref.stream()

            models = [doc.to_dict() for doc in results]
            self.logger.debug(f"Queried {len(models)} documents from '{collection_name.value}' with filters {filters}")
            return models
        except Exception as e:
            self.logger.error(f"Error querying documents: {e}")
            raise

    def listen_to_collection(
        self,
        collection_name: DbCollections,
        callback: Callable[[List[dict]], None],
        model: Type[dict]
    ) -> None:
        collection_ref = self.db.collection(collection_name.value)

        def on_snapshot(col_snapshot, changes, read_time):
            # TODO: Since this method doesn't exist, this might break
            docs = [self.deserialize(doc.to_dict(), model) for doc in col_snapshot]
            callback(docs)

        collection_ref.on_snapshot(on_snapshot)

    def listen_to_document(
            self,
            collection_name: DbCollections,
            doc_id: str,
            callback: Callable[[dict], None]
    ) -> Any:
        doc_ref = self.db.collection(collection_name.value).document(doc_id)
        logging.debug(f"Setting up listener for document {doc_id} in collection {collection_name}")

        def on_snapshot(doc_snapshot, changes, read_time):
            logging.debug(f"Snapshot triggered for document {doc_id}")
            for doc in doc_snapshot:
                if doc.exists:
                    logging.debug(f"Document {doc.id} data: {doc.to_dict()}")
                    callback(doc.to_dict())
                else:
                    logging.warning(f"Document {doc.id} no longer exists.")

        return doc_ref.on_snapshot(on_snapshot)

    def run_transaction(
        self,
        transaction_callable: Callable[[firestore.Transaction], Any]
    ) -> Any:
        transaction = self.db.transaction()
        return transaction_callable(transaction)

    def _batch_write(
        self,
        operations: List[Callable[[Any], None]]
    ) -> None:
        batch = self.db.batch()
        for operation in operations:
            operation(batch)
        batch.commit()

    def operation(
        self,
        collection_name: str,
        doc_id: str,
        operation_type: DbOperationTypes,
        data: Any = None
    ) -> Callable:
        def op(batch: firestore.WriteBatch) -> None:
            doc_ref = self.db.collection(collection_name).document(doc_id)
            if operation_type == DbOperationTypes.DELETE:
                batch.delete(doc_ref)
            else:
                if not data:
                    raise ValueError(f"{operation_type} operation was called, but no data given")

                if operation_type == DbOperationTypes.SET:
                    batch.set(doc_ref, data)
                elif operation_type == DbOperationTypes.UPDATE:
                    batch.update(doc_ref, data)
                else:
                    raise ValueError(f"Invalid or unrecognized operation type {operation_type}")

        return op

    def transaction(
        self,
        operation_func: Callable,
        *args,
        **kwargs
    ) -> Any:
        """
        Executes a Firestore operation within a transaction.

        Args:
            operation_func (Callable): The function that performs the database operation.
            *args: Positional arguments for the operation function.
            **kwargs: Keyword arguments for the operation function.

        Returns:
            Any: The result of the operation function.
        """
        transaction = self.db.transaction()

        try:
            # ``Transaction`` does not expose a run method. The transactional
            # wrapper executes the callback and retries it when Firestore detects
            # a concurrent write conflict.
            transaction_callable = firestore.transactional(operation_func)
            return transaction_callable(transaction, *args, **kwargs)
        except Exception as e:
            self.logger.error(f"Transaction failed: {e}")
            raise

    def _transaction_operation(
        self,
        transaction: firestore.Transaction,
        doc_ref: firestore.DocumentReference,
        operation: DbOperationTypes,
        data: Optional[dict] = None,
        merge: bool = False,
    ) -> Any:
        """
        Performs a Firestore operation within a transaction.

        Args:
            transaction (firestore.Transaction): The transaction object.
            doc_ref (firestore.DocumentReference): Reference to the Firestore document.
            operation (str): The operation to perform ('get', 'set', 'update', 'delete').
            data (dict, optional): Data to set or update.
            merge (bool): Whether to merge data when setting.

        Returns:
            Any: The result of the operation.
        """
        try:
            if operation == DbOperationTypes.GET:
                doc = doc_ref.get(transaction=transaction)
                if doc.exists:
                    data = doc.to_dict()
                    self.logger.debug(
                        f"Retrieved document within transaction: {doc_ref.id}",
                        custom_id=doc_ref.id
                    )
                    return data
                else:
                    self.logger.error(
                        f"Document with ID {doc_ref.id} does not exist.",
                        custom_id=doc_ref.id
                    )
                    return {}
            elif operation == DbOperationTypes.SET:
                transaction.set(doc_ref, data, merge=merge)
                self.logger.debug(
                    f"Set data for document {doc_ref.id} within transaction.",
                    custom_id=doc_ref.id
                )
                return True
            elif operation == DbOperationTypes.UPDATE:
                transaction.update(doc_ref, data)
                self.logger.debug(
                    f"Updated document {doc_ref.id} within transaction.",
                    custom_id=doc_ref.id
                )
                return True
            elif operation == DbOperationTypes.DELETE:
                transaction.delete(doc_ref)
                self.logger.debug(
                    f"Deleted document {doc_ref.id} within transaction.",
                    custom_id=doc_ref.id
                )
                return True
            else:
                self.logger.error(
                    f"Unsupported operation '{operation}' in transaction.",
                    custom_id=doc_ref.id
                )
                raise ValueError(f"Unsupported operation '{operation}'")
        except Exception as e:
            self.logger.error(
                f"Error performing '{operation}' within transaction: {e}",
                custom_id=doc_ref.id
            )
            raise
