from .document_database import DocumentDatabase
from .firestore_database import FirestoreDatabase
from ..constants.database import DatabaseTypes
from ..utilities.gcp.cloud_logger import Logger, LoggerNames


class DocumentDatabaseFactory:
    """
    A factory class responsible for creating instances of different DocumentDatabase subclasses
    based on the specified database type. This factory centralizes the logic for instantiating
    the appropriate database object, ensuring that only supported database types are created.

    Attributes:
        _database_classes (dict): A dictionary mapping each supported DatabaseTypes enum to its
                                  corresponding DocumentDatabase subclass.
    """
    _database_classes = {
        DatabaseTypes.firestore: FirestoreDatabase
    }

    @staticmethod
    def create_db_object(
        db_type: DatabaseTypes,
        project_id: str = None,
        database_name: str = None,
        log_name: str = LoggerNames.CLOUD_FN,
    ) -> DocumentDatabase:
        """
        Creates an instance of a DocumentDatabase subclass based on the specified database type.

        This method checks the `db_type` parameter to select the appropriate subclass from the
        `_database_classes` dictionary. If `db_type` is supported, an instance of the corresponding
        database class is created with the provided `database_name` and `project_id`.

        Args:
            log_name ():
            db_type (DatabaseTypes): The type of database to create. Must be a member of the
                                     DatabaseTypes enum.
            database_name (str): The name of the database to connect to.
            project_id (str): The Google Cloud project ID associated with the database.
            log_name (str, optional): The name of the Firestore log. Defaults to 'cloud-fn'.

        Returns:
            DocumentDatabase: An instance of the specified DocumentDatabase subclass.
        """
        db_class = DocumentDatabaseFactory._database_classes.get(db_type)
        if not db_class:
            raise ValueError(f"Unsupported database type: {db_type.value}")

        logger = Logger(log_name)
        logger.debug(f"DocumentDatabaseObject:create_db_object - "
                     f"Creating database instance of type: {db_type.value}")
        return db_class(project_id=project_id, database_name=database_name, log_name=log_name)
