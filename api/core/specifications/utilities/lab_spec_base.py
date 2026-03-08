import re
from abc import ABC, abstractmethod

from common.document_database.factory import DocumentDatabaseFactory
from common.constants.database import DbCollections, DatabaseTypes, DATABASE_NAME
from common.constants.pub_sub import PubSub
from common.utilities.gcp.cloud_env import CloudEnv
from common.utilities.gcp.cloud_logger import Logger, LoggerNames
from common.utilities.gcp.pubsub_manager import PubSubManager
from common.utilities.id_generator import IdGenerator


class LabSpecBase(ABC):
    """
    A base class representing a cyber arena (Agoge) lab specification that syncs to the Datastore.
    Attributes:
        class_name (str): The name of the class.
        logger (Logger): Logger object for logging information.
        spec (dict): The specification data for the laboratory.
        env_dict (dict): Dictionary containing environment variables.
        validated (bool): Indicates whether the spec has been validated.
        db (DocumentDatabaseFactory): Manager for document database operations.
        pub_sub_mgr (PubSubManager): Manager for Google Cloud Pub/Sub operations.
    Methods:
        is_valid(): Validates the laboratory specification.
        save(image_servers=bool): Saves the validated laboratory specification.
        sync_computer_images(create=bool): Synchronizes computer images based on the specification.
    """
    def __init__(self, env_dict: dict) -> None:
        self.class_name = self.__class__.__name__
        self.catalog_collection = DbCollections.CATALOG
        self.edit_collection = DbCollections.SPECIFICATION_EDITS
        self.log_name = LoggerNames.API
        self.spec = None
        env = CloudEnv(env_dict=env_dict, log_name=self.log_name)
        self.env_dict = env.get_env()
        self.validated = False
        self.db = DocumentDatabaseFactory.create_db_object(
            db_type=DatabaseTypes.firestore,
            database_name=DATABASE_NAME,
            log_name=self.log_name
        )
        self.pub_sub_mgr = PubSubManager(topic=PubSub.Topics.AGOGE, log_name=self.log_name, env_dict=self.env_dict)
        self.logger = Logger(self.log_name, class_name=self.class_name)

    @staticmethod
    def _get_id_from_name(
            name: str,
            discriminator: str
    ) -> str:
        name = name.lower()
        name = re.sub(r'[^a-z0-9]+', '-', name).strip('-')
        return "{spec_id}#{discriminator}".format(
            spec_id=name,
            discriminator=discriminator,
        )

    @staticmethod
    def generate_discriminator() -> str:
        return IdGenerator.discriminator()

    @abstractmethod
    def is_valid(self):
        """
        Validates the build spec. This method checks if the spec contains
        all required fields and conforms to the expected schema based on its 'build_type'.
        Returns:
            tuple: A tuple containing a boolean indicating validity (True if valid, False otherwise)
                   and a string message describing the validity status.
        """
        pass

    @abstractmethod
    def save(self):
        """
        Saves the validated laboratory specification. This method persists the spec
        to a datastore and raises an error if the spec is invalid.
        Raises:
            ValidationError: If the laboratory specification is invalid.
        Returns:
            None
        """
        pass

    @abstractmethod
    def _validate_spec(self):
        """
        Private method for the internal validation of the build specification.
        Raises:
            ValidationError: If the specification does not contain a 'build_type' or fails schema validation.
        Returns:
            None
        """
        pass

    def sync_computer_images(self, create: bool = False):
        """
        Synchronizes computer images based on the build specification. This method sends
        messages to a Pub/Sub topic to trigger image synchronization or creation actions.

        Intended to be called as part of final process of saving validated spec to Datastore
        Args:
            create (bool, optional): If True, triggers the creation of new images. Defaults to False.
        Returns:
            None
        """
        self.logger.info(f"Beginning to sync compute images in specification", spec_id=self.spec['id'])
        server_list = []
        if 'servers' in self.spec:
            server_list = self.spec['servers']

        for server_spec in server_list:
            if 'image' in server_spec:
                if create:
                    action = str(PubSub.Actions.BUILD)
                else:
                    action = str(PubSub.Actions.SYNC)
                self.pub_sub_mgr.msg(
                    handler=str(PubSub.Handlers.CONTROL.value),
                    action=action,
                    image_name=server_spec['image'],
                    course_object=str(PubSub.CourseObjects.TEMPLATE_SERVER.value)
                )
# [ eof ]
