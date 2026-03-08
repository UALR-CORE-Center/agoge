"""
Module to synchronize default server images from a source Google Cloud project to the current environment's project.

This module defines the DefaultServerImage class, which uses the ComputerImageSync utility to synchronize
server images from the specified source project to the project defined in the environment.
"""

from googleapiclient import discovery

from common.utilities.gcp.cloud_env import CloudEnv
from common.document_database.factory import DocumentDatabaseFactory
from common.constants.database import DatabaseTypes, DATABASE_NAME, DbCollections

from cloud_deployment.operations.images_and_specs.computer_image_sync import ComputerImageSync
from cloud_deployment.utilities.globals import DefaultServerImages
from cloud_deployment.input_data.default_server_images import DEFAULT_SERVER_IMAGES


class DefaultServerImage:
    """
    A class to handle the synchronization of default server images from a source Google Cloud project
    to the current environment's project.
    """

    SOURCE_IMAGE_PROJECT = "ualr-cybersecurity"

    def __init__(
        self,
        suppress: bool = True
    ) -> None:
        """
        Initialize the DefaultServerImage class.

        Args:
            suppress (bool): If True, suppresses the output of the ComputerImageSync operations.
        """
        self.suppress = suppress
        self.env = CloudEnv()
        self.service = discovery.build('compute', 'v1')
        self.computer_image_sync = ComputerImageSync(
            suppress=self.suppress, env_dict=self.env.get_env()
        )
        self.db = DocumentDatabaseFactory.create_db_object(
            db_type=DatabaseTypes.firestore,
            database_name=DATABASE_NAME
        )

    def run(self) -> None:
        """
        Execute the synchronization process for the default server images.
        """
        print(
            f"Starting synchronization of default server images from '{self.SOURCE_IMAGE_PROJECT}' "
            f"to '{self.env.project}'."
        )
        for server in DefaultServerImages:
            print(f"Starting import of server image '{server.value}'.")
            self.computer_image_sync.sync(
                server.value, source_project=self.SOURCE_IMAGE_PROJECT
            )
            server_record = DEFAULT_SERVER_IMAGES.get(server, None)
            if not server_record:
                print(f"Warning: Server record not found in the DEFAULT_SERVER_IMAGES dict for '{server.value}'.")
                continue
            server_disks = server_record["disks"]
            for disk in server_disks:
                disk["initializeParams"]["sourceImage"] = \
                    disk["initializeParams"]["sourceImage"].format(project=self.env.project)
                disk["initializeParams"]["type"] = \
                    disk["initializeParams"]["type"].format(project=self.env.project, zone=self.env.zone)
            self.db.insert(collection_name=DbCollections.IMAGE, data=server_record, id_field="name")
            print(f"Successfully imported server image '{server.value}'.")
        print("Synchronization of default server images completed.")
