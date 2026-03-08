import time
from abc import ABC, abstractmethod
from googleapiclient import discovery
from googleapiclient.errors import HttpError
from socket import timeout

from common.constants.database import DbCollections, DATABASE_NAME, DatabaseTypes
from common.constants.build_constants import BuildConstants
from common.document_database import DocumentDatabaseFactory
from common.utilities.gcp.cloud_env import CloudEnv
from common.utilities.gcp.cloud_logger import Logger, LoggerNames

from .constants import StartupScripts, MirroredResource, Scopes


class BasePacketMirror(ABC):
    """
    Base class for managing various operations required for establishing a packet mirror system
    within a training environment

    This abstract class defines the fundamental functionalities for packet mirroring in a cloud environment.

    This class provides functionalities to create and manage network resources
    necessary for packet mirroring, including collector instances, backend services,
    internal load balancers, and firewall rules.

    This class must be called last in the workout build process to ensure successful operation.

    Attributes:
        build_id (str): The unique identifier for the build.
        debug (bool): Flag to enable verbose logging. Useful for debugging.
        cloud_env (CloudEnv): Configuration and environment variables container.
        logger (Logger): Logger instance for logging activities.
        compute (Resource): Google Compute Engine API resource API


    Args:
        build_id (str): Unique identifier for the build.
        env_dict (dict, optional): Dictionary of environment variables. Defaults to None.
    """
    def __init__(
        self,
        build_id: str,
        build: dict = None,
        debug: bool = False,
        env_dict: dict = None
    ) -> None:
        """Initializes the PacketMirrorManager with necessary attributes.

        Args:
            build_id (str): Unique identifier for the build.
            env_dict (dict, optional): Dictionary containing environment configurations.
                Defaults to None.
            debug (bool, optional): Flag to enable debug mode. Defaults to False.
        """
        self.class_name = self.__class__.__name__
        self.build_id = build_id
        self.build = build
        self.debug = debug
        self.mig_size = 1
        self.mirror_tag = 'promiscuity'
        self.db = DocumentDatabaseFactory.create_db_object(
            db_type=DatabaseTypes.firestore,
            database_name=DATABASE_NAME
        )
        self.cloud_env = CloudEnv(env_dict=env_dict) if env_dict else CloudEnv()
        self.compute = discovery.build('compute', 'v1', cache_discovery=False)
        self.compute_beta = discovery.build('compute', 'beta', cache_discovery=False)
        self.logger = Logger(LoggerNames.CLOUD_FN, class_name=self.class_name)

    @staticmethod
    def api_url(prefix: str, resource: str) -> str:
        """Generates valid GoogleAPIs URL given a prefix and resource path

        Args:
            prefix (str): Expects string of type [global, region, zone]_url
            resource (str): Path to resource without beginning forward slash.

        Example:
            prefix='projects/PROJECT/zones/ZONE'
            resource='instanceGroups/MIG_NAME'
        """
        return f"https://www.googleapis.com/compute/v1/{prefix}/{resource}"

    @property
    def global_url(self) -> str:
        return f"projects/{self.cloud_env.project}/{Scopes.GLOBAL}"

    @property
    def region_url(self) -> str:
        return f"projects/{self.cloud_env.project}/regions/{self.cloud_env.region}"

    @property
    def zone_url(self) -> str:
        return f"projects/{self.cloud_env.project}/zones/{self.cloud_env.zone}"

    @property
    def managed_instance_group_name(self):
        """Generates the name for the managed instance group based on the build ID.

        Returns:
            str: Name of the collector instance.
        """
        return f'{self.build_id}-collector-mig'

    @property
    def load_balancer_name(self):
        """Generates the name for the load balancer based on the build ID.

        Returns:
            str: Name of the load balancer.
        """
        return f'{self.build_id}-lb'

    @property
    def backend_service_name(self):
        """Generates the name for the backend service based on the load balancer name.

        Returns:
            str: Name of the backend service.
        """
        return f"{self.load_balancer_name}-backend-service"

    @property
    def network_name(self):
        """Gets name of network to attach MiG and LB to"""
        for network in self.build.get('networks', []):
            network_name = network.get('name')
            if 'external' in network_name:
                return f'{self.build_id}-{network_name}'
        return None

    @property
    def network_path(self):
        """Generates full path for network based on network_name.

        Returns:
            str: URL of VPC network.
        """
        return f'{self.global_url}/networks/{self.network_name}'

    def subnetwork_path(self, subnet_name=None):
        """Generates full path for subnetwork based on subnet_name.

        Returns:
            str: URL of VPC subnetwork.
        """
        if subnet_name:
            return f'{self.region_url}/subnetworks/{self.network_name}-{subnet_name}'
        else:
            return f'{self.region_url}/subnetworks/{self.network_name}-default'

    @property
    def packet_mirror_name(self):
        """Generates the name for packet mirror policy based on network name

        Returns:
            str: Name of packet mirror policy.
        """
        return f"{self.network_name}-packet-mirror"

    @abstractmethod
    def _load_build(self) -> dict:
        """Checks for existence of build Datastore object in class. If
        it doesn't exist, it will request latest version

        Returns:
            build (dict)
        """
        pass

    def start(self):
        """Starts MIG instances and creates new forwarding rule for load balancer"""
        # Resize MIG
        self._start_managed_instances()

        # Enable packet mirror policy
        self._update_packet_mirroring_policy(enabled=True)

    def stop(self):
        """Stops MIG instances and deletes load balancer forwarding rule to preserve cost"""
        # Disable packet mirror policy
        self._update_packet_mirroring_policy(enabled=False)

        # Resize MIG
        self._stop_managed_instances()

    def create(self) -> None:
        """Enables packet mirroring by tag for networks and network resources.
        Creation must be implemented in the following order:
            - instance template
            - managed instance group
            - backend service
            - forwarding rules
            - packet mirroring policy
        """
        # Create instance template
        instance_template_url = self._create_instance_template()

        # Create Manged instance group
        mig_url = self._create_managed_instance_group(instance_template_url)

        # Create backend service
        backend_service_url = self._create_backend_service(mig_url)

        # Create forwarding rules
        forwarding_rule_url = self._create_forwarding_rule(backend_service_url)

        # Create packet mirroring policy
        _ = self._create_packet_mirroring(forwarding_rule_url)

        self.logger.info(f"{self.class_name}:{self.build_id} - Finished setting up packet "
                         f"mirroring for build.")

    def delete(self) -> None:
        """Deletes all packet mirroring resources for target network
        Deletion must be implemented in the following order:
            - packet mirroring policy
            - forwarding rules
            - backend service
            - managed instance group
            - instance template
        """
        # Delete packet mirror policy
        self._delete_packet_mirroring()

        # Delete forwarding rules
        self._delete_forwarding_rule()

        # Delete backend service
        self._delete_backend_service()

        # Delete managed instance group
        self._delete_managed_instance_group()

        # Delete instance template
        self._delete_instance_template()

        self.logger.info(f"{self.class_name}:{self.build_id} - Finished deleting packet "
                         f"mirroring for build.")

    def _create_instance_template(self) -> str:
        """Creates instance template using self.managed_instance_group_name

        Returns (str): instance template url
        """
        config = self._get_instance_template()

        # create the instance template
        template_body = {
            'name': f'{self.managed_instance_group_name}-template',
            'properties': config
        }
        try:
            response = (
                self.compute.instanceTemplates()
                .insert(project=self.cloud_env.project, body=template_body)
                .execute()
            )
            self._wait_to_finish(response_id=response['name'], scope=Scopes.GLOBAL, name=template_body['name'])
        except KeyError:
            self.logger.error(f'{self.class_name}:{self.build_id} - Missing URL '
                              f'in template creation response. Does it exist?')
            raise
        except HttpError as e:
            self.logger.error(f'{self.class_name}:{self.build_id} - '
                              f'Failed creating instance template with reason {e.reason}')
            if e.status_code in [409]:
                pass
            else:
                raise e
        return f"{self.global_url}/instanceTemplates/{template_body['name']}"

    def _create_managed_instance_group(self, instance_template_url) -> str:
        """Creates managed instance group for packet mirroring"""
        mig_body = {
            'name': self.managed_instance_group_name,
            'instanceTemplate': instance_template_url,
            'targetSize': 1,
        }
        try:
            mig_response = (
                self.compute.instanceGroupManagers()
                .insert(project=self.cloud_env.project, zone=self.cloud_env.zone, body=mig_body)
                .execute()
            )
            self._wait_to_finish(response_id=mig_response['name'], scope=Scopes.ZONE, name=mig_body['name'])
        except HttpError as e:
            self.logger.error(f'{self.class_name}:{self.managed_instance_group_name} - Failed '
                              f'creating MIG with reason {e.reason}')
            if e.status_code in [409]:
                pass
            else:
                raise e
        except KeyError:
            self.logger.error('Missing URL in MIG creation response. Does it exist?')
            raise

        return self.api_url(self.zone_url, f'instanceGroups/{self.managed_instance_group_name}')

    def _create_backend_service(self, mig_group_url: str) -> str:
        """Creates a backend service for the internal load balancer.

        Args:
            mig_group_url (str): URL of the instance group to be used as a backend.

        Returns:
            str: The URL link to the created backend service.

        Raises:
            HttpError: If an error occurs during backend service creation.
        """
        health_check_url = self.api_url(self.global_url, 'healthChecks/packet-mirror-hc')
        body = {
            "name": self.backend_service_name,
            "region": self.cloud_env.region,
            "backends": [{'group': mig_group_url}],
            "loadBalancingScheme": "INTERNAL",
            "healthChecks": [health_check_url],
            "network": self.network_path
        }

        # Create the backend service
        try:
            backend_service = (
                self.compute.regionBackendServices()
                .insert(project=self.cloud_env.project, region=self.cloud_env.region, body=body)
                .execute()
            )
            self._wait_to_finish(response_id=backend_service['name'], scope=Scopes.REGION, name=body['name'])
        except HttpError as e:
            self.logger.error(f'{self.class_name}:{self.build_id} - Error creating backend '
                              f'service for build {self.build_id}: {e.reason}')
            if e.status_code in [409]:
                pass
            else:
                raise e
        # return f"{self.region_url}/backendServices/{self.backend_service_name}"
        return self.api_url(self.region_url, f"backendServices/{self.backend_service_name}")

    def _create_forwarding_rule(self, backend_service_url: str) -> str:
        """Creates a forwarding rule for internal load balancer and attaches
        it to the specified backend service.

        Args:
            backend_service_url (str): URL of the backend service to attach to the load balancer.

        Returns:
            str: The URL of the newly created internal load balancer.

        Raises:
            HttpError: If an error occurs during load balancer creation.
        """
        try:
            forwarding_rule_body = {
                'name': self.load_balancer_name,
                'network': self.network_path,
                'subnetwork': self.subnetwork_path(),
                'loadBalancingScheme': 'INTERNAL',
                'IPProtocol': 'TCP',
                'ports': ['80', '8080', '443'],
                'backendService': backend_service_url,
                'isMirroringCollector': True,
            }

            # Create the forwarding rule
            forwarding_rule = (
                self.compute.forwardingRules()
                .insert(project=self.cloud_env.project, region=self.cloud_env.region, body=forwarding_rule_body)
                .execute()
            )
            self._wait_to_finish(response_id=forwarding_rule['name'], scope=Scopes.REGION,
                                 name=forwarding_rule_body['name'])
        except HttpError as e:
            self.logger.error(f'{self.class_name}:{self.load_balancer_name} - Error creating '
                              f'load balancer: {e.reason}')
            if e.status_code in [409]:
                pass
            else:
                raise e

        return self.api_url(self.region_url, f"forwardingRules/{self.load_balancer_name}")

    def _create_packet_mirroring(self, forwarding_rule_url) -> str:
        """Enables packet mirroring in the network using the created collector load balancer.

        Args:
            forwarding_rule_url (str): URL of the collector load balancer forwarding rule to use
                                       for packet mirroring.
        Returns:
            str: The response or status of the packet mirroring creation.

        Raises:
            HttpError: If an error occurs during the packet mirroring setup.
        """
        # Serialize mirrored resources for the packet mirroring configuration
        mirrored_resources = self._get_mirrored_resources()
        serialized_resources = self.serialize(mirrored_resources)

        # Create the packet mirroring
        packet_mirror_body = {
            "name": self.packet_mirror_name,
            "network": {'url': self.network_path},
            "collectorIlb": {
                "url": forwarding_rule_url,
            },
            "mirroredResources": serialized_resources,
            'filter': {
                'direction': 'BOTH'
            },
        }
        try:
            request = (
                self.compute.packetMirrorings()
                .insert(project=self.cloud_env.project, region=self.cloud_env.region, body=packet_mirror_body)
                .execute()
            )
            self._wait_to_finish(request['name'], scope=Scopes.REGION, name=packet_mirror_body['name'])
            return request['targetLink']
        except HttpError as e:
            self.logger.error(f"{self.class_name}:{self.packet_mirror_name} - An error occurred "
                              f"creating packet mirror: {e.reason}")
            raise e

    def _update_packet_mirroring_policy(self, enabled: bool = False):
        """Enables or disables packet mirroring policy based on input `enabled` value"""
        response = (
            self.compute.packetMirrorings()
            .patch(
                project=self.cloud_env.project,
                region=self.cloud_env.region,
                packetMirroring=self.packet_mirror_name,
                body={'enable': str(bool(enabled)).upper()}
            )
            .execute()
        )
        self._wait_to_finish(response['name'], scope=Scopes.REGION, name=self.packet_mirror_name)
        return response

    def _start_managed_instances(self) -> None:
        """Starts all instances that are part of the managed instance group"""
        instances = self._list_managed_instances()
        if instances:
            request_body = {
                'instances': instances
            }
            try:
                # TODO: startInstances is a beta command. Consider alternatives
                response = (
                    self.compute_beta.instanceGroupManagers()
                    .startInstances(
                        project=self.cloud_env.project,
                        zone=self.cloud_env.zone,
                        instanceGroupManager=self.managed_instance_group_name,
                        body=request_body
                    ).execute()
                )
                self._wait_to_finish(response['name'], scope=Scopes.ZONE, name=self.managed_instance_group_name)
            except HttpError as e:
                self.logger.error(f'{self.class_name}:{self.build_id} - Failed starting MIG instances. {e.reason}')
        else:
            self.logger.warning(f'{self.class_name}:{self.build_id} - No MIG instances found. '
                                f'Ignoring start request!')

    def _stop_managed_instances(self) -> None:
        """Stops all instances that are part of the managed instance group"""
        instances = self._list_managed_instances()
        if instances:
            request_body = {
                'instances': instances
            }
            try:
                # TODO: stopInstances is a beta command. Consider alternatives
                response = (
                    self.compute_beta.instanceGroupManagers()
                    .stopInstances(
                        project=self.cloud_env.project,
                        zone=self.cloud_env.zone,
                        instanceGroupManager=self.managed_instance_group_name,
                        body=request_body
                    ).execute()
                )
                self._wait_to_finish(response['name'], scope=Scopes.ZONE, name=self.managed_instance_group_name)
            except HttpError as e:
                self.logger.error(f'{self.class_name}:{self.build_id} - Failed stopping MIG instances. {e.reason}')
        else:
            self.logger.warning(f'{self.class_name}:{self.build_id} - No MIG instances found. '
                                f'Ignoring stop request!')

    def _list_managed_instances(self) -> list:
        """Lists all instances in managed instance group"""
        instance_urls = []
        try:
            response = (
                self.compute.instanceGroupManagers()
                .listManagedInstances(
                    project=self.cloud_env.project,
                    zone=self.cloud_env.zone,
                    instanceGroupManager=self.managed_instance_group_name
                ).execute()
            )
        except HttpError as e:
            self.logger.error(f'{self.class_name}:{self.build_id} - Error listing MIG instances. {e.reason}')
            return []
        if instances := response.get('managedInstances', []):
            instance_urls = [instance['instance'] for instance in instances]
        return instance_urls

    def _delete_instance_template(self) -> bool:
        """Handles deletion process for Compute instance templates"""
        try:
            self.compute.instanceTemplates().delete(
                project=self.cloud_env.project,
                instanceTemplate=f'{self.managed_instance_group_name}-template'
            ).execute()
        except HttpError as e:
            if e.status_code in [404]:
                self.logger.warning(f"{self.class_name}:{self.build_id} - No instance template "
                                    f"found for build_id. Maybe it is already deleted?")
                pass
            else:
                self.logger.error(f"{self.class_name}:{self.build_id} - Error deleting instance template."
                                  f"{e.reason}")
                raise e
        self.logger.info(f'{self.class_name}:{self.build_id} - Instance template deleted successfully.')
        return True

    def _delete_managed_instance_group(self) -> bool:
        """Handles deletion process for managed instance groups"""
        try:
            operation = self.compute.instanceGroupManagers().delete(
                project=self.cloud_env.project,
                zone=self.cloud_env.zone,
                instanceGroupManager=self.managed_instance_group_name
            ).execute()
            self._wait_to_finish(operation['name'], scope=Scopes.ZONE, name=self.managed_instance_group_name)
        except HttpError as e:
            if e.status_code in [404]:
                self.logger.warning(f"{self.class_name}:{self.build_id} - No instance group "
                                    f"found for build_id. Maybe it is already deleted?")
                pass
            else:
                self.logger.error(f'{self.class_name}:{self.build_id} - Error '
                                  f'deleting instance group: {e.reason}')
                raise e
        self.logger.info(f'{self.class_name}:{self.build_id} - Managed Instance Group '
                         f'deleted successfully.')
        return True

    def _delete_backend_service(self):
        """Handles deletion process for backend services"""
        backend_service_name = self.backend_service_name
        try:
            operation = (
                self.compute.regionBackendServices()
                .delete(
                    project=self.cloud_env.project,
                    region=self.cloud_env.region,
                    backendService=backend_service_name
                )
                .execute()
            )
            self._wait_to_finish(operation['name'], scope=Scopes.REGION, name=backend_service_name)
        except HttpError as e:
            if e.status_code in [404]:
                self.logger.warning(f"{self.class_name}:{self.build_id} - No backend service "
                                    f"found for build_id. Maybe it is already deleted?")
                pass
            else:
                self.logger.error(f"{self.class_name}:{self.build_id} - Error deleting backend service."
                                  f"{e.reason}")
                raise e
        return True

    def _delete_forwarding_rule(self) -> bool:
        """Handles deletion process for forwarding rules"""
        internal_lb = self.load_balancer_name

        # Delete the forwarding rule
        try:
            operation = self.compute.forwardingRules().delete(
                project=self.cloud_env.project,
                region=self.cloud_env.region,
                forwardingRule=internal_lb
            ).execute()
            self._wait_to_finish(operation['name'], scope=Scopes.REGION, name=internal_lb)
        except HttpError as e:
            if e.status_code in [404]:
                self.logger.warning(f"{self.class_name}:{self.build_id} - No forwarding rule found "
                                    f"for build_id. Maybe it is already deleted?")
                pass
            else:
                self.logger.error(f"{self.class_name}:{self.build_id} - Error deleting forwarding rule."
                                  f"{e.reason}")
                raise e
        self.logger.info(f"{self.class_name}:{self.build_id} - Load balancer forwarding rule deleted successfully.")
        return True

    def _delete_packet_mirroring(self) -> bool:
        """Handles deletion process for packet mirroring policies"""
        packet_mirror_name = self.packet_mirror_name
        try:
            operation = (
                self.compute.packetMirrorings()
                .delete(
                    project=self.cloud_env.project,
                    region=self.cloud_env.region,
                    packetMirroring=packet_mirror_name
                )
                .execute()
            )
            self._wait_to_finish(response_id=operation['name'], scope=Scopes.REGION, name=packet_mirror_name)
        except HttpError as e:
            if e.status_code in [404]:
                self.logger.warning(f"{self.class_name}:{self.build_id} - No packet mirroring policy "
                                    f"found for build_id. Maybe it is already deleted?")
                pass
            else:
                self.logger.error(f"{self.class_name}:{self.build_id} - Error deleting packet mirroring policy."
                                  f"{e.reason}")
                raise e
        return True

    def _get_mirrored_resources(self) -> dict:
        """Extracts mirrored resource objects from build Datastore object"""
        subnets = [
            subnet['name']
            for network in self.build.get('networks', [])
            for subnet in network.get('subnets', [])
            if subnet.get('promiscuous_mode', False)
        ]

        servers = [
            server['name']
            for server in self.build.get('servers', [])
            if server.get('promiscuous_mode', False)
        ]

        # TODO: Determine best approach to extracting promiscuous_mode from network tags
        tags = []

        return {
            MirroredResource.SUBNETWORK: subnets,
            MirroredResource.INSTANCE: servers,
            MirroredResource.TAGS: tags
        }

    def _get_instance_template(self) -> dict:
        """Creates config to use as MIG instance template.

        Returns:
            dict: config used in MIG instance template
        """
        config = {
            'machineType': "e2-micro",
            'properties': {
                'tags': {
                    "items": ['lb-health-check']
                },
            },
            'disks': [
                {
                    'boot': True,
                    'autoDelete': True,
                    'initializeParams': {
                        'sourceImage': f"{self.global_url}/images/image-collector-instance",
                    },
                    'diskSizeGb': 20
                }
            ],
            'networkInterfaces': [{
                'network': self.network_path,
                'subnetwork': self.subnetwork_path(),
                'accessConfigs': [{'type': 'ONE_TO_ONE_NAT', 'name': 'External NAT'}],
                'internalIP': BuildConstants.Networks.Reservations.PACKET_MIRROR_DESTINATION
            }],
            'serviceAccounts': [{
                'email': 'default',
                'scopes': [
                    'https://www.googleapis.com/auth/devstorage.read_write',
                    'https://www.googleapis.com/auth/logging.write'
                ]
            }],
            'labels': {'http-server': '', 'https-server': '', 'allow-ssh': True},
            'metadata': {
                'items': [{
                    'key': 'startup-script',
                    'value': StartupScripts.UNIX.format(BUILD_ID=self.build_id)
                }]
            }
        }
        return config

    def serialize(self, resources):
        """Serializes the given resources for packet mirroring.

        Args:
            resources (dict): Resources to be serialized.

        Returns:
            dict: Serialized resources.

        Raises:
            ValueError: If invalid resource type is found.
            ValueError: If no resources marked for mirroring in resources object.
                i.e {instances: [], subnetworks: [], tags: []}
        """
        serialized = {}
        for key, resource in resources.items():
            if key == MirroredResource.INSTANCE:
                serialized[key] = self._serialize_instances(resource)
            elif key == MirroredResource.SUBNETWORK:
                serialized[key] = self._serialize_subnetworks(resource)
            elif key == MirroredResource.TAGS:
                serialized[key] = resource
            else:
                self.logger.warning(f'{self.class_name}:{self.build_id} - Unrecognized mirror '
                                    f'resource of type {key}. Ignoring ...')

        # Verify at least one resource type exists for mirroring
        if not any(serialized.values()):
            raise ValueError(f'{self.class_name}:{self.build_id} - No resources found to mirror. '
                             f'Is `promiscuous_mode` set in specification?')
        return serialized

    def _serialize_subnetworks(self, subnets: list) -> list:
        """Serializes the subnetworks for packet mirroring.

        Args:
            subnets (list): List of subnetwork names to be serialized.

        Returns:
            list: List of serialized subnetwork names.

        Raises:
            ValueError: If subnets is not a list.
        """
        serialized = []
        if not isinstance(subnets, list):
            raise ValueError(f"Invalid type {type(subnets)} for mirrored_resources.subnetworks")
        for subnet in subnets:
            subnet_str = self.subnetwork_path(subnet_name=subnet)
            serialized.append({'url': subnet_str})
        return serialized

    def _serialize_instances(self, instances: list) -> list:
        """Serializes the instances for packet mirroring.

        Args:
            instances (list): List of instance names to be serialized.

        Returns:
            list: List of serialized instance names.

        Raises:
            ValueError: If instances is not a list.
        """
        serialized = []
        if not isinstance(instances, list):
            raise ValueError(f"Invalid type {type(instances)} for mirrored_resources.instances")
        for name in instances:
            instance_str = f"{self.zone_url}/instances/{name}"
            serialized.append({'url': instance_str})
        return serialized

    def _wait_to_finish(
        self,
        response_id: str,
        scope: str,
        name: str
    ) -> None:
        # Define operation scopes and corresponding method calls
        operations_map = {
            Scopes.GLOBAL: self.compute.globalOperations().wait,
            Scopes.REGION: self.compute.regionOperations().wait,
            Scopes.ZONE: self.compute.zoneOperations().wait,
        }

        # Prepare common parameters
        params = {'project': self.cloud_env.project, 'operation': response_id}

        # Add specific parameters based on scope
        if scope in operations_map:
            if scope == Scopes.REGION:
                params[Scopes.REGION] = self.cloud_env.region
            elif scope == Scopes.ZONE:
                params[Scopes.ZONE] = self.cloud_env.zone

            operation = operations_map[scope](**params)
        else:
            raise ValueError(f'{self.class_name}:{name} - Invalid operation scope {scope}')

        # Follow operation until completion or timeout
        for _ in range(5):
            if self.debug:
                print(f"{self.class_name}:{name} - Waiting for operation {response_id} with scope {scope}")
            try:
                wait = operation.execute()
                if wait.get('error'):
                    if isinstance(wait['error'], list) and len(wait['error']) > 0:
                        error_obj = wait['error'][0]
                        self.logger.warning(f"{self.class_name}:{name} - Error ({error_obj.get('code')}) when "
                                            f"waiting for operation: {error_obj.get('message')}")
                else:
                    return
            except timeout:
                self.logger.warning(f'{self.class_name}:{name} - Response timeout for operation. '
                                    f'Trying again')
                time.sleep(3)
                continue

        self.logger.error(f'{self.class_name}:{name} - Timeout in operation on resource')
        raise ConnectionError

# [ eof ]
