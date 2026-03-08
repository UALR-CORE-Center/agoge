import requests
import time
from abc import abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Union, List, Any, Type, TypeVar

from common.constants.build_constants import BuildConstants
from common.constants.database import DatabaseTypes, DATABASE_NAME, DbCollections
from common.constants.google import ImageSource
from common.constants.pub_sub import PubSub
from common.constants.states import ServerStates
from common.document_database import DocumentDatabaseFactory
from common.exceptions.agoge import (
    NotFound,
    BadRequest,
    BaseAgogeException,
    Conflict
)
from common.models.model_validators.model_validator import ModelValidator
from common.utilities.gcp.cloud_env import CloudEnv
from common.utilities.gcp.cloud_logger import Logger, LoggerNames
from common.utilities.gcp.compute.compute_image import ComputeImageAPI, BaseComputeAPI
from common.utilities.gcp.compute.compute_instance import ComputeInstanceAPI
from common.utilities.gcp.compute.compute_disk import ComputeDiskAPI
from common.utilities.gcp.compute.compute_machine_type import ComputeMachineTypesAPI
from common.utilities.gcp.compute.compute_snapshot import ComputeSnapshotAPI
from common.utilities.gcp.compute.resources.attached_disk_resource import AttachedDiskResource
from common.utilities.gcp.compute.resources.instance_resource import InstanceResource
from common.utilities.gcp.pubsub_manager import PubSubManager

from cloud_fn_utilities.gcp.dns_manager import DnsManager


ComputeApiClient = TypeVar('ComputeApiClient', bound=BaseComputeAPI)


# TODO: Focus here
class BaseComputeManager:
    """Base manager class for translating Agoge data and actions to
    computing operations on cloud infrastructure.

    Provides methods for taking input Agoge-specific data and delegates tasks to the appropriate cloud
    API classes and class methods
    """
    @dataclass
    class Server:
        """Dataclass for holding server configuration."""
        add_disk: int
        can_ip_forward: bool
        delayed_start: bool
        disk_size: int
        image: str
        metadata: list
        machine_type: str
        min_cpu_platform: str
        nics: list
        parent_build_type: str
        name: str
        tags: list
        disks: Optional[list] = None
        parent_id: Optional[str] = None
        build_type: Optional[str] = None
        dns_hostname: Optional[str] = None
        description: Optional[str] = None
        startup_script: Optional[str] = None
        guacamole_startup_script: Optional[str] = None
        hostname: Optional[str] = None
        human_interaction: Optional[list[dict]] = None
        machine_image: Optional[str] = None
        network_interfaces: Optional[list] = None
        os: Optional[str] = None
        service_accounts: Optional[list] = None
        ssh_keys: List[str] = field(default_factory=list)
        network_prefix: Optional[str] = None
        self_link: Optional[str] = None

    def __init__(
        self,
        env_dict: dict = None,
        instances: bool = True,
        images: bool = False,
        disks: bool = False,
        snapshots: bool = False,
        machine_types: bool = True,
    ) -> None:
        """Initializes the base compute manager with environment settings.

        Args:
            env_dict (dict): Dictionary containing cloud environment configuration
            instances (bool): Enable GCP InstancesClient API in class. Defaults to True
            images (bool): Enable GCP ImagesClient API in class. Defaults to False
            disks (bool): Enable GCP DisksClient API in class. Defaults to False
            snapshots (bool): Enable GCP SnapshotsClient API in class. Defaults to False
            machine_types (bool): Enable GCP MachineTypesClient API in class. Defaults to True
        """
        self.class_name = self.__class__.__name__
        self.log_name = LoggerNames.CLOUD_FN
        self.env = CloudEnv(env_dict=env_dict) if env_dict else CloudEnv()
        self.env_dict = self.env.get_env()
        self.project = self.env.project
        self.dns_manager = DnsManager(env_dict=self.env_dict)
        self.pubsub_manager = PubSubManager(topic=PubSub.Topics.AGOGE, env_dict=self.env_dict)
        self.db = DocumentDatabaseFactory.create_db_object(
            db_type=DatabaseTypes.firestore,
            database_name=DATABASE_NAME
        )

        # Enable select compute API clients
        self.compute_disk = self._enable_compute_api(ComputeDiskAPI, disks)
        self.compute_image = self._enable_compute_api(ComputeImageAPI, images)
        self.compute_instance = self._enable_compute_api(ComputeInstanceAPI, instances)
        self.compute_machine_types = self._enable_compute_api(ComputeMachineTypesAPI, machine_types)
        self.compute_snapshot = self._enable_compute_api(ComputeSnapshotAPI, snapshots)

        # data attributes
        self.s = ServerStates
        self.logger = Logger(self.log_name, class_name=self.class_name)
        self.validate = ModelValidator
        self.server_spec = self.Server
        self.source_image_project = None
        self.server_name = None
        self.image_name = None
        self.build_type = None
        self.parent_build_type = None
        self.parent_build_id = None
        self.network_prefix = None
        self.state_manager = None
        self.assessment = None
        self.ip_aliases = False
        self.collection = DbCollections.SERVER

    @property
    def dns_record(self) -> str:
        return self._dns_record()

    @staticmethod
    def _extract_image_and_server_names(
        name: str
    ) -> tuple[str, str]:
        """Extracts and returns image and server names from the provided name.

        Args:
            name: A string which might be the server name or the image name
                  (begins with 'image-').

        Returns:
            A tuple containing the image name and server name.
        """
        if name.startswith('image'):
            image_name = name
            server_name = name.removeprefix("image-")
        else:
            image_name = f"image-{name}"
            server_name = name
        return image_name, server_name

    def _enable_compute_api(
        self,
        client_cls: Type[ComputeApiClient],
        enable: bool
    ) -> Union[ComputeApiClient, None]:
        if enable:
            return client_cls(
                project=self.env.project,
                region=self.env.region,
                zone=self.env.zone,
                log_name=self.log_name
            )
        return None

    @abstractmethod
    def load(
        self,
        server_name: str,
        **kwargs
    ) -> None:
        """Abstract method to load server data from a database."""
        pass

    def _load_lab_server(
        self,
        server_name: str,
        server_spec: dict,
        network_prefix: str = None,
    ) -> None:
        # Populate server dataclass
        self.server_spec.name = self.server_name = server_name
        self.server_spec.add_disk = server_spec.get('add_disk', 0)
        self.server_spec.build_type = server_spec.get('build_type', None)
        self.server_spec.can_ip_forward = server_spec.get('can_ip_forward', False)
        self.server_spec.delayed_start = server_spec.get('delayed_start', False)
        self.server_spec.dns_hostname = server_spec.get('dns_hostname', None)
        self.server_spec.startup_script = server_spec.get('startup_script', None)
        self.server_spec.guacamole_startup_script = server_spec.get('guacamole_startup_script', None)
        self.server_spec.hostname = server_spec.get('hostname', None)
        self.server_spec.image = server_spec.get('image')
        self.server_spec.machine_image = server_spec.get('machine_image', None)
        self.server_spec.machine_type = server_spec.get(
            'machine_type',
            BuildConstants.GoogleMachineTypes.E2_MEDIUM.value
        )
        self.server_spec.ssh_keys = []  # SSH keys are stripped from the server before being used for the workout
        self.server_spec.metadata = server_spec.get('metadata', None)
        self.server_spec.min_cpu_platform = server_spec.get('min_cpu_platform', None)
        self.server_spec.network_prefix = network_prefix if network_prefix else server_spec['parent_id']
        self.server_spec.nics = server_spec.get('nics', [])
        self.server_spec.parent_build_type = server_spec.get('parent_build_type', None)
        self.server_spec.parent_id = server_spec.get('parent_id', None)
        self.server_spec.service_accounts = server_spec.get('serviceAccounts', None)
        self.server_spec.tags = server_spec.get('tags', [])

        # Set additional class attributes
        self.parent_build_id = server_spec.get('parent_id', None)
        self.parent_build_type = self.server_spec.parent_build_type

    def _load_template_server(
        self,
        server_spec: dict,
    ) -> None:
        self.server_spec.name = self.server_name
        self.server_spec.add_disk = server_spec.get('add_disk', 0)
        self.server_spec.build_type = server_spec.get('build_type', None)
        self.server_spec.can_ip_forward = server_spec.get('can_ip_forward', False)
        self.server_spec.delayed_start = server_spec.get('delayed_start', False)
        self.server_spec.description = server_spec.get('description', None)
        self.server_spec.disks = server_spec.get('disks')
        self.server_spec.human_interaction = server_spec.get('human_interaction', None)
        self.server_spec.self_link = server_spec.get('self_link')
        if self.server_spec.human_interaction:
            ssh_keys = [
                ssh_key
                for conn in self.server_spec.human_interaction
                if (ssh_key := conn.get('ssh_key'))
            ]
            self.server_spec.ssh_keys = ssh_keys
        self.server_spec.image = self.image_name
        self.server_spec.ip_aliases = server_spec.get('ip_aliases', None)
        self.server_spec.machine_image = server_spec.get('machine_image', None)
        self.server_spec.machine_type = (
            server_spec.get('machine_type', BuildConstants.GoogleMachineTypes.E2_MEDIUM.value)
        )
        self.server_spec.metadata = server_spec.get('metadata', None)
        self.server_spec.min_cpu_platform = server_spec.get('min_cpu_platform', None)
        self.server_spec.nics = server_spec.get('nics', [])
        self.server_spec.network_prefix = None
        self.server_spec.os = server_spec.get('os')
        self.server_spec.parent_build_type = None
        self.server_spec.parent_id = None
        self.server_spec.tags = server_spec.get('tags', [])
        self.server_spec.network_interfaces = None
        self.server_spec.ssh_keys = server_spec.get('ssh_keys', [])
        self.server_spec.startup_script = server_spec.get('startup_script', None)

    def _build_server(self) -> None:
        """Builds an individual server based on the server specifications."""
        self.state_manager.state_transition(self.s.BUILDING)
        self._add_disks()
        self._add_metadata()
        self._add_nics()

        advanced_machine_features = None
        min_cpu_platform = None
        machine_type = self._lookup_machine_type(self.server_spec.machine_type)
        service_account = self.server_spec.service_accounts or self.compute_instance.SERVICE_ACCOUNT_CONFIG
        tags = {'items': self.server_spec.tags} if self.server_spec.tags else {'items': []}

        if self.server_spec.min_cpu_platform and self.server_spec.min_cpu_platform != "":
            min_cpu_platform = self.server_spec.min_cpu_platform
        if self.ip_aliases:
            advanced_machine_features = {"enable_nested_virtualization": True}
            if self.server_spec.min_cpu_platform is None:
                machine_type_prefix = self.server_spec.machine_type[:2]
                if machine_type_prefix == 'n1':
                    self.server_spec.min_cpu_platform = "Intel Haswell"
                elif machine_type_prefix == "n2":
                    self.server_spec.min_cpu_platform = "Intel Cascade Lake"

        instance = (
            InstanceResource(zone=self.env.zone)
            .new(
                name=self.server_spec.name,
                machine_type=machine_type,
                tags=tags,
                disks=self.server_spec.disks,
                metadata=self.server_spec.metadata,
                can_ip_forward=self.server_spec.can_ip_forward,
                network_interfaces=self.server_spec.network_interfaces,
                service_accounts=service_account,
                min_cpu_platform=min_cpu_platform,
                advanced_machine_features=advanced_machine_features,
            )
        )

        if self.server_spec.build_type == BuildConstants.ServerBuildType.MACHINE_IMAGE:
            instance.source_machine_image = (
                f"projects/{self.project}/global/machineImages/{self.server_spec.machine_image}"
            )
        else:
            if self.server_spec.delayed_start:
                time.sleep(30)

        try:
            created = (
                self.compute_instance
                .create(resource_name=self.server_spec.name, wait=True, instance_resource=instance)
            )
        except Conflict:
            self.logger.warning(f'{self.class_name}:{self.server_name} - Server already exists!')
            return

        if created:
            self.logger.info(f'{self.class_name}:{self.server_name} - Successfully built server!')
            self.state_manager.state_transition(self.s.RUNNING)
        else:
            msg = f'{self.class_name}:{self.server_name} - Timeout in trying to build server.'
            self.logger.error(msg)
            self.state_manager.state_transition(self.s.BROKEN)
            raise TimeoutError(msg)

        # Register any DNS records if they exist
        if dns_record := self._dns_record():
            self.dns_manager.add_dns_record(dns_record, self.server_name)

    def _start_server(self) -> None:
        """
        Starts a server based on the specification in the database document with name server_name.
        A guacamole server is also registered with DNS.
        """
        if not self.compute_instance:
            return

        self.state_manager.state_transition(self.s.STARTING)
        i = 0
        start_success = False
        while not start_success and i < 5:
            try:
                if self.server_spec.delayed_start:
                    time.sleep(30)

                if self.compute_instance.start(resource_name=self.server_name, wait=True):
                    start_success = True
            except BadRequest:
                self.logger.error(f'{self.class_name}:{self.server_name} - Server is still building.')
                break
            except Conflict:
                self.state_manager.state_transition(self.s.BROKEN)
                self.logger.error(f'{self.class_name}:{self.server_name} - Server does not exist! Exiting function.')
                break
            except BrokenPipeError:
                self.logger.info(f"{self.class_name}:{self.server_name} - Broken pipe error when trying to "
                                 f"start server. Trying again...")
                i += 1
                continue
            except Exception as e:
                error_message = e.args[0] if len(e.args) > 0 else "NO ERROR MESSAGE PROVIDED"
                self.logger.warning(f"{self.class_name}:{self.server_name} - Unknown error occurred: {error_message}. "
                                    f"Continuing to try again.")
                i += 1
                continue

        if start_success:
            # If the server is an external proxy, then register its DNS name
            if dns_record := self._dns_record():
                self.dns_manager.add_dns_record(dns_record, self.server_name)
                if self.server_name == f'{self.parent_build_id}-display':
                    self._wait_for_guacamole(dns_record[:-1])

            self.state_manager.state_transition(self.s.RUNNING)
            self.logger.info(f"{self.class_name}:{self.server_name} - Finished starting server")
        else:
            self.state_manager.state_transition(self.s.BROKEN)
            self.logger.error(f"{self.class_name}:{self.server_name} - Timeout or other error trying to start server")

    def _stop_server(self) -> None:
        """
        Stops a server based on the specification in the database record with name server_name.
        """
        if not self.compute_instance:
            return

        if self.state_manager.get_state() != self.s.STOPPED.value:
            self.state_manager.state_transition(self.s.STOPPING)
            i = 0
            stop_success = False
            while not stop_success and i < 5:
                try:
                    if self.compute_instance.stop(resource_name=self.server_name, wait=True):
                        stop_success = True
                except BadRequest as e:
                    self.logger.info(
                        f'{self.class_name}{self.server_name} - Stop request for server '
                        f'{self.server_name} failed with reason: {e.message}'
                    )
                    stop_success = True
                except (NotFound, BaseAgogeException) as e:
                    self.state_manager.state_transition(self.s.BROKEN)
                    break
                except BrokenPipeError:
                    i += 1
                    continue

            if stop_success:
                if dns_record := self._dns_record():
                    self.logger.info(f'{self.class_name}:{self.server_name} - Deleting DNS record for server, '
                                     f'{self.parent_build_id}')
                    self.dns_manager.delete_dns(record_name=dns_record)

                self.state_manager.state_transition(self.s.STOPPED)
                self.logger.info(f"{self.class_name}:{self.server_name} - Finished stopping server")
            else:
                self.state_manager.state_transition(self.s.BROKEN)
                self.logger.error(f"{self.class_name}:{self.server_name} - Timeout trying to stop server")
        else:
            self.logger.info(f"{self.class_name}:{self.server_name} - Server is not running")

    def _get_boot_disk(
        self,
        image_source: str = None,
        disk_size_gb: int = None
    ) -> Any:
        """Retrieves desired server image and generates a boot disk object
        to send with server instance insert requests

        """
        if not image_source:
            try:
                image_response = self.compute_image.get(resource=self.server_spec.image, project=self.project)
            except NotFound:
                self.logger.error(f'{self.class_name}:{self.server_name} - Error when trying to build server. '
                                  f'Cannot obtain the cloud disk for {self.server_spec.image}')
                raise
            image = image_response.self_link
        else:
            image = image_source

        # Generate boot disk from existing image
        attached_disk_resource = AttachedDiskResource()
        disk_init_params = attached_disk_resource.initialized_params(
            disk_name=f'{self.server_name}-disk',
            source=image,
            source_type=ImageSource.IMAGE,
            disk_size_gb=disk_size_gb,
        )
        boot_disk = attached_disk_resource.new(
            boot=True,
            auto_delete=True,
            initialize_params=disk_init_params
        )
        return boot_disk

    def _add_disks(self) -> None:
        pass

    def _add_metadata(self) -> None:
        pass

    @abstractmethod
    def _add_nics(self) -> None:
        pass

    @abstractmethod
    def _dns_record(self) -> str:
        pass

    def _template_dns_record(self) -> str:
        """Generates DNS record for the template server.

        Returns:
            A DNS record string.
        """
        dns_record = f"{self.server_name}{self.env.parent_dns_suffix}"
        if dns_record[-1] != '.':
            dns_record = f"{dns_record}."
        return dns_record

    def _server_dns_record(self) -> str | bool:
        """Generates DNS record for the lab server.

        Returns:
            A DNS record string.
        """
        hostname = self.server_spec.dns_hostname or self.server_spec.hostname
        if not hostname:
            return False

        # Get dns_suffix without the trailing dot
        dns_suffix = self.env.parent_dns_suffix.rstrip('.')

        if dns_suffix in hostname:
            # Ensure hostname ends with a dot
            return hostname if hostname.endswith('.') else f"{hostname}."
        else:
            return f"{hostname}{dns_suffix}."

    def _ssh_keys(self) -> str:
        if self.server_spec.ssh_keys:
            return "\n".join(self.server_spec.ssh_keys)

    def _wait_for_guacamole(
        self,
        dns: str
    ) -> bool:
        max_attempts = 15
        attempts = 0
        success = False
        while not success and attempts < max_attempts:
            try:
                response = requests.get(f"https://{dns}:8080/guacamole/#", timeout=40)
                return True
            except requests.exceptions.Timeout:
                self.logger.info(f"{self.class_name}:{self.server_name} - Timeout {attempts} of {max_attempts} "
                                 f"waiting for guacamole server connection {dns}.")
                attempts += 1
            except requests.exceptions.ConnectionError:
                self.logger.info(f"{self.class_name}:{self.server_name} - HTTP Connection Error for Guacamole "
                                 f"Server {dns}")
                attempts += 1
        return False

    def _lookup_machine_type(
        self,
        machine_type: Union[int, str]
    ) -> str:
        if self.compute_machine_types and isinstance(machine_type, str):
            m_type_found = self.compute_machine_types.get(resource=machine_type)
            return m_type_found.name

        self.logger.warning(f"Could not find machine type for {machine_type}. Defaulting to SMALL instead")
        return self.compute_instance.GOOGLE_MACHINE_TYPES[BuildConstants.MachineTypes.SMALL.value]
