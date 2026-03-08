import time
from datetime import datetime
from typing import Union, Any

from common.constants.google import ImageSource
from common.constants.states import ImageStatus, ServerStates
from common.constants.pub_sub import PubSub
from common.constants.database import DbCollections, DATABASE_NAME, DatabaseTypes, DbOperators
from common.document_database import DocumentDatabaseFactory, DatabaseQueries
from common.exceptions import NotFound, BaseAgogeException, BadRequest
from common.models.agoge import AgogeImageModel
from common.models.model_validators.model_validator import ModelValidator
from common.utilities.gcp.cloud_env import CloudEnv
from common.utilities.gcp.cloud_logger import Logger, LoggerNames
from common.utilities.gcp.compute.compute_image import ComputeImageAPI
from common.utilities.gcp.compute.resources.network_interface_resource import NetworkInterfaceResource
from common.utilities.gcp.compute.resources.image_resource import ImageResource

from cloud_fn_utilities.gcp.dns_manager import DnsManager
from cloud_fn_utilities.server_specific.agoge_user_startup_script import AgogeUserStartupScript, MetadataKey

from .base_compute_manager import BaseComputeManager
from .snapshot_manager import SnapshotManager
from ...state_managers import ImageStateManager


class ImageTemplateManager(BaseComputeManager):
    """
    Manages the creation, synchronization, and management of custom images in Google Cloud.

    Attributes:
        image_name (str): Name of the image to manage.
        server_name (str): Derived server name from the image name.
        delete_previous (bool): Whether to delete the previous image before creating a new one.
        class_name (str): Name of this class.
        logger (Logger): Logger for logging information.
        env (CloudEnv): Cloud environment configuration.
        source_image_project (str): Google Cloud project where the source image is located.
        db (DocumentDatabaseFactory): Manager for document database operations
    """

    SOURCE_IMAGE_PROJECT = ComputeImageAPI.SOURCE_IMAGE_PROJECT
    DEFAULT_MAX_SNAPSHOTS = ComputeImageAPI.DEFAULT_MAX_SNAPSHOTS

    def __init__(
        self,
        user: str = None,
        delete_previous: bool = False,
        env_dict: dict = None,
        source_image_project: str = SOURCE_IMAGE_PROJECT,
        debug: bool = False
    ) -> None:
        super().__init__(env_dict=env_dict, images=True, disks=True, snapshots=True)
        """
        Args:
            name (str): Name of the image to manage.
            delete_previous (bool, optional): Whether to delete the previous image before creating a new one. Defaults to False.
            env_dict (dict, optional): Environment configuration dictionary. Defaults to None.
            source_image_project (str, optional): Source project for the image. Defaults to SOURCE_IMAGE_PROJECT.
        """
        self.class_name = self.__class__.__name__
        self.log_name = LoggerNames.CLOUD_FN
        self.debug = debug
        self.user = user
        self.delete_previous = delete_previous
        self.logger = Logger(self.log_name, class_name=self.class_name)
        self.env = CloudEnv(env_dict=env_dict) if env_dict else CloudEnv()
        self.env_dict = self.env.get_env()
        self.course_object = PubSub.CourseObjects.TEMPLATE_SERVER
        self.image_name = None
        self.server_name = None
        self.dns_manager = DnsManager(env_dict=self.env_dict)
        self.snapshot_manager = SnapshotManager(
            server_type=self.course_object,
            env_dict=self.env_dict,
            debug=self.debug
        )
        self.source_image_project = source_image_project
        self.db = DocumentDatabaseFactory.create_db_object(
            db_type=DatabaseTypes.firestore,
            database_name=DATABASE_NAME
        )
        self.db_query = DatabaseQueries(db=self.db)
        self.collection = DbCollections.IMAGE
        self.state_manager = ImageStateManager()

    @property
    def dns_record(self) -> str:
        return self._dns_record()

    def load(
        self,
        server_name: str,
        **kwargs
    ) -> dict:
        """Loads the server specifications from the datastore based on server name.

        Args:
            server_name: A string name of the server.
            **kwargs: Arbitrary keyword arguments.

        Returns:
            A dictionary containing server specifications.

        Raises:
            LookupError: If no record exists for the compute record.
        """
        self.image_name, self.server_name = self._extract_image_and_server_names(server_name)

        if 'image_spec' in kwargs:
            image_spec = kwargs['image_spec']
        else:
            image_spec = self.db.get(collection_name=self.collection, doc_id=self.server_name)

        if not image_spec:
            self.logger.error(
                f"{self.class_name}:{self.server_name} - No record exists for compute image!",
                template_image_id=self.server_name,
                image_name=self.image_name
            )
            raise LookupError

        self.source_image_project = kwargs.get('source_image_project', self.env.project)
        self._load_template_server(server_spec=image_spec)
        self.state_manager.set_build_record(self.server_name)
        self.snapshot_manager.load(
            server_name=self.server_name,
            server_type=self.course_object,
            image_spec=image_spec
        )
        return image_spec

    def build(self) -> None:
        """Builds an individual server based on the image template specifications."""
        self._build_server()

    def check_in(self) -> None:
        """
        For a given compute instance, generates a production image before
        deleting the instance and associated DNS records.
        """
        self.create_production_image()

        if self.debug:
            self.delete_server()
        else:
            self.pubsub_manager.msg(
                handler=str(PubSub.Handlers.CONTROL.value),
                image_name=str(self.image_name),
                course_object=str(PubSub.CourseObjects.TEMPLATE_SERVER.value),
                action=str(PubSub.Actions.DELETE.value)
            )

        self._update_record_status(ImageStatus.CHECKED_IN)

    def check_out(self) -> None:
        """
        Build a compute instance using the given compute image.
        If successful, image is reserved for changes by the requesting user
        until checked-in (released)
        """
        self.build()

        self._update_record_status(ImageStatus.CHECKED_OUT)

    def start_server(self) -> None:
        self._start_server()

    def stop_server(self) -> None:
        self._stop_server()

    def stop_all_running(self) -> None:
        """Stop any running checked out image servers"""
        running_images = self.db_query.get_running(collection_name=DbCollections.IMAGE)
        for image in running_images:
            image_id = str(image['name'])
            if self.debug:
                self.load(server_name=image_id, image_spec=image)
                self.stop_server()
            else:
                self.pubsub_manager.msg(
                    handler=str(PubSub.Handlers.CONTROL.value),
                    action=str(PubSub.Actions.STOP.value),
                    course_object=str(PubSub.CourseObjects.TEMPLATE_SERVER.value),
                    image_name=str(image_id),
                )

    def sync(
        self,
        source_project: str = None
    ) -> Union[bool, None]:
        """
        Synchronizes the image from the source project to the current project. If the image in the current project
        is older than the source image, it triggers a copy of the source image.

        Args:
            source_project (str, optional): The source project to sync the image from. Defaults to the class's
                source_image_project.

        Returns:
            bool: True if sync was successful or not needed, False if any errors occurred.
        """
        source_project = source_project if source_project else self.source_image_project
        if not self.image_name:
            self.logger.error(f"{self.class_name}: - Sync image called but no image name provided!")
            return False

        if not (src_image := self._get_image(self.image_name, source_project)):
            return False

        src_creation_ts = datetime.fromisoformat(src_image.creation_timestamp)

        if not (dst_image := self._get_image(self.image_name)):
            return self._copy_image()

        dst_creation_ts = datetime.fromisoformat(dst_image.creation_timestamp)
        if src_creation_ts > dst_creation_ts:
            return self._copy_image()

        return True

    def create_production_image(
        self,
        latest: bool = True,
        snapshot_name: str = None
    ) -> bool:
        """
        Creates a new production image from a snapshot of a specified disk.

        Args:
            latest (bool): Create a new snapshot of server and use latest to create a new image
            snapshot_name (str, optional): Create an image from existing snapshot
        """
        if latest:
            # latest is supplied, send request to generate a new snapshot from current template server state
            self.logger.info(f"{self.class_name}:{self.server_name} - Stopping the server before snapshotting.")
            self.stop_server()
            self.logger.info(
                f"{self.class_name}:{self.server_name} - Server has stopped. Now beginning to take a snapshot "
                f"before imaging."
            )

            snapshot_name = self.snapshot_manager.create_snapshot()
            self.logger.info(f"{self.class_name}:{self.server_name} - Completed taking the snapshot. "
                             f"Now beginning to image the server from the snapshot.")

        if not snapshot_name:
            raise ValueError("Missing value for `latest` or `snapshot_name`. Must provide one")

        # Wait for previous image to delete first to avoid any insert conflicts
        if not self.delete_image():
            self.logger.warning(f"{self.class_name}:{self.server_name} - "
                                f"Could not delete the existing image for server")

        # It is now safe to send image insert request
        self.logger.info(f"{self.class_name}:{self.server_name} - Beginning to image the server.")
        self._create_image_from_snapshot(snapshot_name)
        self.logger.info(f"{self.class_name}:{self.server_name} - Completed imaging the server.")

    def cancel(self) -> None:
        """
        Deletes instance and cancels image reservation
        """
        self.logger.info(f'canceling image template {self.image_name} changes')
        self.delete_server(state_transition=False)

        self._update_record_status(ImageStatus.CHECKED_IN)

    def delete(self) -> None:
        """
        Delete production image, server, server snapshots, and image database records.
        """
        self.logger.info(f'starting deletion process for image template {self.image_name}')

        # Delete the template server
        self.delete_server()

        # Delete all template snapshots
        self.snapshot_manager.delete_snapshots()

        # Everything is deleted. It is safe to delete the template image
        self.delete_image()

        # Clean up DB records
        self.db.delete(collection_name=self.collection, doc_id=self.server_name)
        self.db.delete(collection_name=DbCollections.SNAPSHOTS, doc_id=self.server_name)

    def delete_server(self, state_transition: bool = True) -> bool:
        """Delete image server and server DNS records"""
        self.logger.info(f'{self.class_name}:{self.server_name} - Deleting server')
        if state_transition:
            self.state_manager.state_transition(self.s.DELETING)

        try:
            self.compute_instance.delete(self.server_name, wait=True)
        except NotFound as e:
            # If the resource can't be found, it was either already deleted or never created
            self.logger.error(f'{self.class_name}:{self.server_name} - Deletion request returned status code 404. '
                              f'Marking {self.parent_build_id} server as deleted!')
            if state_transition:
                self.state_manager.state_transition(self.s.DELETED)
        except (BadRequest, BaseAgogeException) as e:
            if state_transition:
                self.state_manager.state_transition(self.s.BROKEN)
            return False

        if state_transition:
            self.state_manager.state_transition(self.s.DELETED)

        # Check if a dns record exists for deletion
        if dns_record := self._dns_record():
            self.logger.info(f'{self.class_name}:{self.server_name} - Deleting DNS record for server, '
                             f'{self.parent_build_id}')
            self.dns_manager.delete_dns(record_name=dns_record)

        return True

    def delete_image(self) -> bool:
        """Delete image server image"""
        if not self.image_name:
            self.logger.error(f'{self.class_name}: - Delete image called but no image name provided!')
            return False

        try:
            return self.compute_image.delete(self.image_name, wait=True)
        except NotFound as e:
            self.logger.error(f"{self.class_name}:{self.image_name} - "
                              f"Error deleting image {self.image_name}: "
                              f"{e.message}")
            return True
        except (BadRequest, BaseAgogeException) as e:
            self.logger.error(f'{self.class_name}:{self.image_name} - {e.message}')
            raise

    def _copy_image(
        self,
        delete_previous: bool = False
    ) -> None:
        """
        Copies the image from the source project to the current project, optionally deleting the previous image.

        Raises:
            Exception: If the image deletion or copy fails or times out.
        """
        self.logger.info(f"{self.class_name}:{self.server_name} - Beginning to copy image from "
                         f"{self.source_image_project} to {self.env.project}")

        if delete_previous:
            if not self.compute_image.delete(self.image_name):
                msg = f"{self.class_name}:{self.server_name} - Timeout waiting for image to delete."
                self.logger.error(msg)
                raise Exception(msg)

        if image := self._get_image(self.image_name, project=self.source_image_project):
            image_resource = ImageResource(self.env.zone).new(
                name=self.image_name,
                source=image.self_link,
                source_type=ImageSource.IMAGE,
            )
            if not self.compute_image.create(
                resource_name=self.image_name,
                image_resource=image_resource,
                project=self.env.project
            ):
                raise Exception(f"timeout waiting for image {self.image_name} to copy.")

    def _get_image(
        self,
        image_name: str,
        project: str = None
    ) -> Any:
        if not project:
            project = self.env.project

        try:
            return self.compute_image.get(image_name, project=project)
        except NotFound as e:
            self.logger.error(
                f"{self.class_name}:{self.server_name} - The source image {image_name} does not "
                f"exist: {e.message}"
            )
            return False

    def _create_image_from_snapshot(
        self,
        snapshot_name: str
    ) -> bool:
        """Create a new image from a snapshot"""
        description = f'{str(self.env.project).capitalize()} production image.'
        if self.server_spec.description:
            description = f'{description} {self.server_spec.description}'

        snapshot_source = self.compute_snapshot.get(resource_name=snapshot_name, project=self.env.project)
        
        return self.compute_image.create(
            resource_name=self.image_name,
            description=description,
            source_type=ImageSource.SNAPSHOT,
            source=snapshot_source.self_link
        )

    def _add_disks(self):
        image_source = self.server_spec.self_link
        if (add_disk := self.server_spec.add_disk) == 0:
            add_disk = None
        boot_disk = self._get_boot_disk(image_source=image_source, disk_size_gb=add_disk)
        disks = [boot_disk]

        self.server_spec.disks = disks

    def _add_metadata(self) -> None:
        """Generates and adds metadata for the server based on specifications."""
        metadata = {'items': []}
        if self.server_spec.startup_script:
            metadata['items'].append({"key": "startup-script", "value": self.server_spec.startup_script})
        if self.server_spec.ssh_keys:
            metadata['items'].append({"key": "ssh-keys", "value": self._ssh_keys()})
        if connections := self.server_spec.human_interaction:
            if not isinstance(connections, list):
                connections = [connections]

            if startup_script := self._generate_startup_script(connections):
                metadata_key, script = startup_script
                metadata['items'].append({"key": metadata_key, "value": script})
        self.server_spec.metadata = metadata

    def _add_nics(self) -> None:
        """Configures network interfaces for the server."""
        network_interface_resource = NetworkInterfaceResource(region=self.env.region, project=self.env.project)
        access_config = network_interface_resource.access_config(type_='ONE_TO_ONE_NAT', name="External NAT")
        default_network = network_interface_resource.default_network()
        attached_nic = (
            network_interface_resource
            .new(
                network=default_network,
                access_configs=[access_config]
            )
        )
        self.server_spec.network_interfaces = [attached_nic]

    def _dns_record(self) -> str:
        """Generates DNS record for the server.

        Returns:
            A DNS record string.
        """
        return self._template_dns_record()

    def _generate_startup_script(
        self,
        human_interactions: list[dict]
    ) -> bool | tuple[None, str]:
        """Generates startup script based on OS and user interaction settings.

        Returns:
            A startup script string if applicable, otherwise False.
        """
        script = []
        script_key = MetadataKey.__dict__.get(self.server_spec.os.upper(), None)
        if not script_key:
            return False

        if script_key == MetadataKey.LINUX:
            script.append(AgogeUserStartupScript.unix_prefix())

        for interaction in human_interactions:
            username = interaction.get('username')
            password = interaction.get('password')
            ssh_key = interaction.get('ssh_key')
            startup_script = AgogeUserStartupScript(username, password, ssh_key)
            if script_key == MetadataKey.WINDOWS:
                script.extend(startup_script.get_windows_script())
            elif script_key == MetadataKey.LINUX:
                script.extend(startup_script.get_unix_script())

        if script:
            return script_key, "\n".join(script)
        return False

    def _update_record_status(
        self,
        status: ImageStatus = ImageStatus.CHECKED_OUT
    ) -> None:
        """Updates image status and state.
        Resets image record to default state if image is marked as checked-in.

        Args:
            status (ImageStatus): Status of current image
        """
        db_image = self.db.get(collection_name=self.collection, doc_id=self.server_name)

        if status == ImageStatus.CHECKED_OUT:
            db_image['status'] = status.value
            db_image['image'] = self.image_name
            db_image['in_use_by'] = self.user
            db_image['dns_record'] = self.dns_record
        elif status == ImageStatus.CHECKED_IN:
            db_image['status'] = status.value
            db_image['state'] = ServerStates.START.value
            db_image['in_use_by'] = None
            db_image['dns_record'] = None
            db_image['image_exists'] = True

        db_image['self_link'] = self.compute_image.self_link(self.image_name, self.env.project)

        if ModelValidator(AgogeImageModel, log_location=self.log_name).load(db_image):
            self.db.update(collection_name=self.collection, doc_id=self.server_name, data=db_image)
