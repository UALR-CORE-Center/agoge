from typing import Union

from common.constants.build_constants import BuildConstants
from common.constants.database import DbCollections, DatabaseTypes, DATABASE_NAME
from common.constants.pub_sub import PubSub
from common.document_database import DocumentDatabaseFactory, DatabaseQueries
from common.models.agoge import ServerModel, UnitModel, NicModel, WorkoutModel
from common.utilities.gcp.cloud_env import CloudEnv
from common.utilities.gcp.cloud_logger import Logger, LoggerNames
from common.utilities.gcp.pubsub_manager import PubSubManager
from ..course_objects.compute.factory import ComputeManagerFactory
from ..gcp.route_manager import RouteManager

from netaddr import IPNetwork


class FirewallServer:
    def __init__(
        self,
        initial_build_id: str,
        full_build_model: Union[UnitModel, WorkoutModel],
        env_dict: dict = None,
        debug: bool = False
    ) -> None:
        """
        Creates a firewall server for a given build.
        @param initial_build_id: The build ID used mainly for naming objects in the cloud
        @type initial_build_id: str
        @param full_build_model: The full build spec needed for identifying network configuration information
        @type full_build_model: UnitModel or WorkoutModel
        """
        self.class_name = self.__class__.__name__
        self.debug = debug
        self.env = CloudEnv(env_dict=env_dict) if env_dict else CloudEnv()
        self.env_dict = self.env.get_env()
        self.logger = Logger(LoggerNames.CLOUD_FN, class_name=self.class_name)
        self.pubsub_manager = PubSubManager(PubSub.Topics.AGOGE, env_dict=self.env_dict)
        self.compute_manager = ComputeManagerFactory.create_manager_object(env_dict=self.env_dict)
        self.db = DocumentDatabaseFactory.create_db_object(
            db_type=DatabaseTypes.firestore,
            database_name=DATABASE_NAME
        )
        self.server_spec = None
        self.server_name = None
        self.build_id = initial_build_id
        self.full_build_model = full_build_model
        self.firewall_spec = full_build_model.firewalls or []

        # Add the gateway network here for the firewall configurations
        self.parent_build_type = self.full_build_model.build_type or BuildConstants.BuildType.UNIT.value
        self.gateway_network = BuildConstants.Networks.GATEWAY_NETWORK_NAME
        self._add_network()
        self.firewall_server_spec: Union[ServerModel, dict] = {}

        # Init network routing
        self.dst_ranges = {}
        for network in self.full_build_model.networks:
            self.dst_ranges[network.name] = network.subnets[0].ip_subnet

    def build(self):
        for fw in self.firewall_spec:
            firewall_type = fw.type
            firewall_name = f"{self.build_id}-{fw.name}"
            self.firewall_server_spec = ServerModel(
                name=fw.name,
                can_ip_forward=True,
                machine_type=BuildConstants.GoogleMachineTypes.E2_STANDARD_4.value,
                nics=[],
                parent_id=self.build_id,
                parent_build_type=self.parent_build_type,
                image=self._get_image(firewall_type)
            )

            self._add_nics(fw)

            # Create licensing server
            if firewall_type == BuildConstants.Firewalls.FirewallTypes.VYOS:
                self._add_vyos_features()
            elif firewall_type == BuildConstants.Firewalls.FirewallTypes.FORTINET:
                self._add_fortinet_features()
            else:
                self.logger.error(f"{self.class_name}:{self.build_id} - Unsupported firewall type: {firewall_type}.")
                raise

            # Create firewall server
            self.db.update(
                collection_name=DbCollections.SERVER,
                doc_id=firewall_name,
                data=self.firewall_server_spec.model_dump()
            )

            if self.debug:
                self.compute_manager.load(firewall_name)
                self.compute_manager.build()
            else:
                self.pubsub_manager.msg(
                    handler=str(PubSub.Handlers.BUILD.value),
                    action=str(PubSub.Actions.BUILD.value),
                    course_object=str(PubSub.CourseObjects.LAB_SERVER.value),
                    server_name=str(firewall_name)
                )
            self._add_routes(fw)

    def delete(self):
        self._delete_routes()
        for fw in self.firewall_spec:
            firewall_type = fw.type
            if firewall_type == BuildConstants.Firewalls.FirewallTypes.FORTINET:
                self._delete_fortinet_features()
            firewall_name = f"{self.build_id}-{fw.name}"
            self.___delete(firewall_name)

    def _add_network(self):
        # Standard workouts will have the network added in during initial unit build
        if self.parent_build_type != BuildConstants.BuildType.WORKOUT.value:
            self.full_build_model.networks.append(BuildConstants.Networks.GATEWAY_NETWORK_CONFIG)
            self.firewall_spec[0].networks.append(BuildConstants.Networks.GATEWAY_NETWORK_NAME)

    def _add_nics(self, firewall_spec):
        for network in firewall_spec.networks:
            for network_spec in self.full_build_model.networks:
                if network == network_spec.name:
                    subnet = network_spec.subnets[0]
                    network_ip = self._get_ip_address(subnet.ip_subnet)
                    self.firewall_server_spec.nics.append(
                        NicModel(
                            network=network,
                            internal_ip=network_ip,
                            subnet_name=subnet.name,
                            external_nat=False
                        )
                    )

    def _get_ip_address(self, subnet):
        taken_ip_addresses = []
        for server in self.full_build_model.servers:
            for nic in server.nics:
                taken_ip_addresses.append(nic.internal_ip)
        n = IPNetwork(subnet)
        quads = str(n[0]).split(".")
        i = 10
        candidate_ip = None
        for i in range(10, 250, 10):
            candidate_ip = f"{quads[0]}.{quads[1]}.{quads[2]}.{i}"
            if candidate_ip not in taken_ip_addresses:
                continue
        return candidate_ip

    def _get_image(
        self,
        firewall_type: str
    ) -> str:
        firewall_types = BuildConstants.Firewalls.FirewallTypes
        if firewall_type == firewall_types.VYOS.value:
            return FirewallSettings.Vyos.IMAGE
        else:
            return FirewallSettings.Fortinet.IMAGE

    def _add_vyos_features(self):
        return

    def _add_fortinet_features(self):
        """Builds licensing server for workout"""
        license_server = ServerModel(
            parent_id=self.build_id,
            parent_build_type=self.parent_build_type,
            name=f"{self.build_id}-fortimanager",
            build_type=BuildConstants.ServerBuildType.MACHINE_IMAGE,
            machine_type=BuildConstants.GoogleMachineTypes.E2_MEDIUM.value,
            machine_image=BuildConstants.MachineImages.FORTIMANAGER,
            nics=[
                NicModel(
                    network=self.gateway_network,
                    internal_ip=FirewallSettings.Fortinet.LICENSE_SERVER_IP,
                    subnet_name='default',
                    external_nat=False
                )
            ]
        )
        self.db.update(
            collection_name=DbCollections.SERVER,
            doc_id=license_server.name,
            data=license_server.model_dump()
        )
        if self.debug:
            self.compute_manager.load(license_server.name)
            self.compute_manager.build()
        else:
            self.pubsub_manager.msg(
                handler=str(PubSub.Handlers.BUILD.value),
                action=str(PubSub.Actions.BUILD.value),
                course_object=str(PubSub.CourseObjects.LAB_SERVER.value),
                server_name=str(license_server.name)
            )

    def _delete_fortinet_features(self):
        fortinet_server_name = f"{self.build_id}-fortimanager"
        self.___delete(fortinet_server_name)

    def ___delete(self, server_name: str) -> None:
        if self.debug:
            try:
                self.compute_manager.load(server_name)
                self.compute_manager.delete()
            except LookupError:
                self.logger.error(f" {self.class_name}:{server_name} - Workout {self.build_id}: Could not find server "
                                  f"record. Ignoring deletion request.")
        else:
            self.pubsub_manager.msg(
                handler=str(PubSub.Handlers.CONTROL.value),
                action=str(PubSub.Actions.DELETE.value),
                build_id=str(server_name),
                course_object=str(PubSub.CourseObjects.LAB_SERVER.value)
            )

    def _add_routes(self, firewall_spec):
        routes = []
        for network in firewall_spec.networks:
            if network != self.gateway_network:
                new_route = {
                    'name': f"default-{network}-through-firewall",
                    'network': network,
                    'dest_range': '0.0.0.0/0',
                    'next_hop_instance': self.firewall_server_spec.name
                }
                routes.append(new_route)
            for to_network in firewall_spec.networks:
                if to_network != network:
                    new_route = {
                        'name': f"default-{network}-to-{to_network}",
                        'network': network,
                        'dest_range': self.dst_ranges[to_network],
                        'next_hop_instance': self.firewall_server_spec.name
                    }
                    routes.append(new_route)
        rm = RouteManager(self.build_id, env_dict=self.env_dict)
        rm.build(routes)

    def _delete_routes(self):
        rm = RouteManager(self.build_id, env_dict=self.env_dict)
        rm.delete()


class FirewallSettings:
    class Vyos:
        IMAGE = "image-cyberarena-vyos"

    class Fortinet:
        IMAGE = "image-cybergymfortinet-cybergym-fortinet-fortigate"
        LICENSE_SERVER_IP = '10.1.0.100'
