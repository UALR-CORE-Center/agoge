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
    _INSERT_IN_PROGRESS_INSTANCE_STATES = frozenset({'PROVISIONING', 'STAGING'})
    # One initial observation plus 30 five-second polls. The follower therefore
    # waits the complete 150-second Compute operation window, starting after the
    # worker that owns the insert, before it can classify the build as failed.
    _INSERT_CONFLICT_WAIT_ATTEMPTS = 31
    _INSERT_CONFLICT_WAIT_SECONDS = 5
    _START_IN_PROGRESS_INSTANCE_STATES = frozenset({
        'PROVISIONING',
        'STAGING',
        'REPAIRING',
        'STOPPING',
        'SUSPENDING',
    })

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
        startup_scripts: Optional[list[str]] = None
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
        routes: Optional[list] = None
        wireguard_endpoint_id: Optional[str] = None

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
        self.primary_external_ip = None

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
        self.server_spec.startup_scripts = server_spec.get('startup_scripts') or []
        self.server_spec.startup_script = server_spec.get('startup_script', None)
        if not self.server_spec.startup_script and self.server_spec.startup_scripts:
            self.server_spec.startup_script = '\n'.join(self.server_spec.startup_scripts)
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
        self.server_spec.routes = server_spec.get('routes') or []
        self.server_spec.wireguard_endpoint_id = server_spec.get('wireguard_endpoint_id')

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
        self.server_spec.startup_scripts = server_spec.get('startup_scripts') or []
        self.server_spec.startup_script = server_spec.get('startup_script', None)
        if not self.server_spec.startup_script and self.server_spec.startup_scripts:
            self.server_spec.startup_script = '\n'.join(self.server_spec.startup_scripts)
        self.server_spec.routes = server_spec.get('routes') or []
        self.server_spec.wireguard_endpoint_id = server_spec.get('wireguard_endpoint_id')

    def _build_server(self, finalize_state: bool = True) -> None:
        """Build a server, optionally deferring RUNNING until caller dependencies finish."""
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
        except Conflict as error:
            self.logger.warning(f'{self.class_name}:{self.server_name} - Server already exists!')
            # A create may have succeeded before a delivery was acknowledged.
            # Continue only when the existing instance is the one this build
            # requested. Concurrent Pub/Sub deliveries can observe the first
            # insert in PROVISIONING/STAGING, so wait for that exact VM to reach
            # RUNNING. A delayed BUILD must never relabel a stopped or
            # differently configured VM as RUNNING.
            existing = self.compute_instance.get(resource_name=self.server_spec.name)
            if not self._reconcile_existing_build(existing, instance):
                raise Conflict(
                    f"Existing instance {self.server_spec.name} does not match the requested build"
                ) from error
            created = True

        if created:
            self.logger.info(f'{self.class_name}:{self.server_name} - Successfully built server!')
            if finalize_state:
                self.state_manager.state_transition(self.s.RUNNING)
        else:
            msg = f'{self.class_name}:{self.server_name} - Timeout in trying to build server.'
            self.logger.error(msg)
            self.state_manager.state_transition(self.s.BROKEN)
            raise TimeoutError(msg)

        # WireGuard DNS is published by LabServerManager only after an
        # ownership-checked endpoint stage. Publishing here would let a delayed
        # build for a recycled five-digit ID overwrite its new owner's record.
        if not self.server_spec.wireguard_endpoint_id and (dns_record := self._dns_record()):
            self.dns_manager.add_dns_record(
                dns_record,
                self.server_name,
                ip_address=self.primary_external_ip,
            )

    @classmethod
    def _existing_instance_matches(cls, existing, desired) -> bool:
        """Compare immutable/routing-critical fields after a create conflict."""
        if str(cls._resource_field(existing, 'status', '')).upper() != 'RUNNING':
            return False
        return cls._existing_instance_configuration_matches(existing, desired)

    @classmethod
    def _existing_instance_configuration_matches(cls, existing, desired) -> bool:
        """Compare fields that identify the intended VM independent of status."""
        if bool(cls._resource_field(existing, 'can_ip_forward', False)) != bool(
            cls._resource_field(desired, 'can_ip_forward', False)
        ):
            return False
        if cls._resource_tail(cls._resource_field(existing, 'machine_type')) != cls._resource_tail(
            cls._resource_field(desired, 'machine_type')
        ):
            return False

        desired_tags = set(
            cls._resource_field(cls._resource_field(desired, 'tags', {}), 'items', []) or []
        )
        existing_tags = set(
            cls._resource_field(cls._resource_field(existing, 'tags', {}), 'items', []) or []
        )
        if not desired_tags.issubset(existing_tags):
            return False

        existing_nics = list(cls._resource_field(existing, 'network_interfaces', []) or [])
        desired_nics = list(cls._resource_field(desired, 'network_interfaces', []) or [])
        if len(existing_nics) != len(desired_nics):
            return False
        for current_nic, requested_nic in zip(existing_nics, desired_nics):
            for path_field in ('network', 'subnetwork'):
                if cls._resource_tail(cls._resource_field(current_nic, path_field)) != cls._resource_tail(
                    cls._resource_field(requested_nic, path_field)
                ):
                    return False
            requested_internal_ip = cls._resource_field(requested_nic, 'network_i_p')
            if requested_internal_ip and (
                requested_internal_ip != cls._resource_field(current_nic, 'network_i_p')
            ):
                return False

            current_access = list(cls._resource_field(current_nic, 'access_configs', []) or [])
            requested_access = list(cls._resource_field(requested_nic, 'access_configs', []) or [])
            if len(current_access) != len(requested_access):
                return False
            for current_config, requested_config in zip(current_access, requested_access):
                requested_ip = cls._resource_field(requested_config, 'nat_i_p')
                if requested_ip and requested_ip != cls._resource_field(current_config, 'nat_i_p'):
                    return False
        return True

    def _reconcile_existing_build(self, existing, desired) -> bool:
        """Accept a matching retry, waiting only for an insert already in flight."""
        for attempt in range(self._INSERT_CONFLICT_WAIT_ATTEMPTS):
            status = str(self._resource_field(existing, 'status', '')).upper()
            if status == 'RUNNING':
                return self._existing_instance_configuration_matches(existing, desired)
            if (
                status not in self._INSERT_IN_PROGRESS_INSTANCE_STATES
                or not self._existing_instance_configuration_matches(existing, desired)
            ):
                return False
            if attempt == self._INSERT_CONFLICT_WAIT_ATTEMPTS - 1:
                return False
            time.sleep(self._INSERT_CONFLICT_WAIT_SECONDS)
            existing = self.compute_instance.get(resource_name=self.server_spec.name)
        return False

    @staticmethod
    def _resource_field(resource, name: str, default=None):
        if isinstance(resource, dict):
            return resource.get(name, default)
        return getattr(resource, name, default)

    @staticmethod
    def _resource_tail(value) -> str:
        return str(value or '').rstrip('/').rsplit('/', 1)[-1]

    def _start_server(self) -> None:
        """
        Starts a server based on the specification in the database document with name server_name.
        A guacamole server is also registered with DNS.
        """
        if not self.compute_instance:
            return

        existing_state = self.state_manager.get_state()
        if existing_state == self.s.RUNNING.value:
            return

        self.state_manager.state_transition(self.s.STARTING)
        i = 0
        start_success = False
        start_in_progress = existing_state == self.s.STARTING.value
        while not start_success and i < 5:
            if start_in_progress:
                instance_status = self._get_instance_status()
                if instance_status == 'RUNNING':
                    start_success = True
                    break
                if instance_status in self._START_IN_PROGRESS_INSTANCE_STATES:
                    i += 1
                    if i < 5:
                        time.sleep(self.state_manager.SLEEP_TIME)
                    continue
                # The publisher may have claimed STARTING before its server
                # handler ran. A TERMINATED instance still needs the API call.
                start_in_progress = False

            try:
                if self.server_spec.delayed_start:
                    time.sleep(30)

                if self.compute_instance.start(resource_name=self.server_name, wait=True):
                    start_success = True
                else:
                    i += 1
            except (BadRequest, Conflict) as error:
                # Pub/Sub is at-least-once and simultaneous Community starts
                # can overlap at this exact API boundary. Reconcile with the
                # VM instead of treating "already starting/running" as a
                # broken gateway.
                instance_status = self._get_instance_status()
                if instance_status == 'RUNNING':
                    start_success = True
                    break
                if instance_status in self._START_IN_PROGRESS_INSTANCE_STATES:
                    start_in_progress = True
                    i += 1
                    if i < 5:
                        time.sleep(self.state_manager.SLEEP_TIME)
                    continue
                if not instance_status:
                    # The action may have been accepted even though the
                    # follow-up read failed. Preserve STARTING for redelivery
                    # instead of asserting a broken state without evidence.
                    start_in_progress = True
                self.logger.error(
                    f'{self.class_name}:{self.server_name} - Start request failed in '
                    f'instance state {instance_status or "UNKNOWN"}: {error}'
                )
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
            # WireGuard DNS is handled after an ownership-checked endpoint stage
            # in LabServerManager.start().
            if not self.server_spec.wireguard_endpoint_id and (dns_record := self._dns_record()):
                self.dns_manager.add_dns_record(dns_record, self.server_name)
                if self.server_name == f'{self.parent_build_id}-display':
                    self._wait_for_guacamole(dns_record[:-1])

            self.state_manager.state_transition(self.s.RUNNING)
            self.logger.info(f"{self.class_name}:{self.server_name} - Finished starting server")
        else:
            if start_in_progress:
                # Keep the operation retryable. Another delivery owns the
                # in-flight Compute Engine start and may still complete it.
                raise TimeoutError(
                    f'{self.class_name}:{self.server_name} - Timed out waiting for an in-progress start'
                )
            self.state_manager.state_transition(self.s.BROKEN)
            self.logger.error(f"{self.class_name}:{self.server_name} - Timeout or other error trying to start server")

    def _get_instance_status(self) -> str:
        try:
            instance = self.compute_instance.get(resource_name=self.server_name)
        except Exception as error:
            self.logger.warning(
                f'{self.class_name}:{self.server_name} - Could not reconcile server state: {error}'
            )
            return ''
        return str(self._resource_field(instance, 'status', '') or '').upper()

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
                    # LabServerManager owns the WireGuard DNS lifecycle and
                    # performs an ownership/IP-checked deletion. Never fall
                    # back to a name-only delete here, including for legacy
                    # gateway records that predate reserved address names.
                    if (
                        not getattr(self.server_spec, 'wireguard_endpoint_id', None)
                        and not self._uses_reserved_external_ip()
                    ):
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

        # A dotted hostname is already externally qualified. This is required
        # when WireGuard endpoints use a delegated suffix other than the
        # application's parent DNS suffix.
        if hostname.endswith('.'):
            return hostname
        if '.' in hostname:
            return f'{hostname}.'

        dns_suffix = self.env.parent_dns_suffix.strip('.')
        return f"{hostname}.{dns_suffix}."

    def _uses_reserved_external_ip(self) -> bool:
        return any(
            nic.get('external_ip_name')
            for nic in (getattr(self.server_spec, 'nics', None) or [])
            if isinstance(nic, dict)
        )

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
