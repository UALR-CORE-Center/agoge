import time

from common.constants.build_constants import BuildConstants
from common.constants.database import DbCollections, DbOperationTypes, DbOperators
from common.constants.pub_sub import PubSub
from common.models.agoge import UnitModel, ServerModel

from ...gcp.vpc_manager import VpcManager
from ..compute.factory import ComputeManagerFactory
from ...gcp.firewall_rule_manager import FirewallManager
from ...server_specific.firewall_server import FirewallServer
from ...gcp.packet_mirroring.packet_mirror_factory import PacketMirrorFactory
from .base_unit import BaseUnit


class CommunityUnit(BaseUnit):
    def __init__(self, unit_model: UnitModel, workout_id=None, form_data=None, debug=False, force=False,
                 env_dict=None):
        super().__init__(unit_model=unit_model, workout_id=workout_id, form_data=form_data, debug=debug, force=force,
                         env_dict=env_dict)
        """
        Manages the lifecycle and operations of a community unit in a cyber training environment.

        This class extends BaseUnit to handle specific functionalities related to community units,
        including building, starting, stopping, deleting, and nuking units and their associated
        servers and network resources.

        Args:
            unit_entity (Entity): The datastore entity representing the unit.
            workout_id (str, optional): Identifier for a specific workout within the unit. Defaults to None.
            form_data (dict, optional): Data associated with web forms, including student and team information.
                                        Defaults to None.
            debug (bool, optional): If True, enables debug mode which may change operational behaviors like
                                    avoiding PubSub messages and synchronous builds. Defaults to False.
            force (bool, optional): Unused parameter, reserved for future use. Defaults to False.
            env_dict (dict, optional): Dictionary of environment variables and configurations. Defaults to None.

        Attributes:
            vpc_manager (VpcManager): Manager for handling VPC operations.
            firewall_manager (FirewallManager): Manager for handling firewall rules.
            promiscuous_mode (Bool): Enables/Disables packet mirroring for environment
            packet_mirroring (PacketMirrorFactory): Factory class for managing packet mirroring resources

        Note:
            The class interacts with multiple GCP services and custom managers for specific operations.
            It is designed to be used within a larger system that manages cyber training environments.
        """
        self.vpc_manager = VpcManager(build_id=self.unit_id, env_dict=self.env_dict)
        self.firewall_manager = FirewallManager(env_dict=self.env_dict)
        self.promiscuous_mode = False
        self.packet_mirroring = (
            PacketMirrorFactory.create_packet_mirror_object(
                build_id=self.unit_id,
                build_type=BuildConstants.UnitType.COMMUNITY.value,
                build=self.unit_model.model_dump(),
                env_dict=self.env_dict,
                debug=self.debug
            )
        )
        self.compute_manager = ComputeManagerFactory.create_manager_object(env_dict=self.env_dict)
        self.__get_workouts()

    def _build_unit(self):
        """
        Initiates the building process of the unit.

        This method manages the state transition of the unit and triggers the building of networks,
        servers, and firewall rules associated with the unit. It handles each stage of the building
        process and transitions the unit's state accordingly.
        """
        self.logger.info(f"{self.class_name}:{self.unit_id} - Beginning a community unit build for unit ID")
        current_state = self.state_manager.get_state()
        if not current_state:
            self.state_manager.state_transition(self.s.START)
        elif current_state < self.s.READY.value:
            # The unit components are either already built or in the process of being built.
            return

        if self.state_manager.get_state() < self.s.BUILDING_NETWORKS.value:
            self.state_manager.state_transition(self.s.BUILDING_NETWORKS)
            for network in self.unit_model.networks:
                self.__set_promiscuous_mode(network=network)
                self.vpc_manager.build(network=network)
            self.state_manager.state_transition(self.s.COMPLETED_NETWORKS)

        # Servers are built asynchronously and kicked off through pubsub messages.
        if self.state_manager.get_state() < self.s.BUILDING_SERVERS.value:
            self.state_manager.state_transition(self.s.BUILDING_SERVERS)
            for server in self.unit_model.servers:
                if server.get.community_server:
                    self.__send_server_build_msg(server)

        if self.state_manager.get_state() < self.s.BUILDING_FIREWALL_RULES.value:
            self.state_manager.state_transition(self.s.BUILDING_FIREWALL_RULES)
            self.firewall_manager.build(self.unit_id, self.unit_model.firewall_rules)
            self.state_manager.state_transition(self.s.COMPLETED_FIREWALL_RULES)

        # If needed, build packet mirror resource using previously created firewall rules
        if self.promiscuous_mode:
            self.packet_mirroring.create()

        self.state_manager.state_transition(self.s.READY)
        self.logger.info(f"Finished community unit build for {self.unit_id}!")

    def start(self):
        """
        Starts the unit by initiating its servers.

        This method transitions the unit's state to START and sends messages to start all associated
        servers. It checks the state of the servers and logs the status.
        """
        self.logger.info(f"{self.class_name}:{self.unit_id} - Beginning to start servers for a community unit")
        self.state_manager.state_transition(self.s.START)
        servers_to_start = self.__get_servers()

        # Start any packet mirror resources
        self.__set_promiscuous_mode()
        if self.promiscuous_mode:
            self.packet_mirroring.start()

        # Start remaining servers
        for server in servers_to_start:
            if self.debug:
                self.compute_manager.load(server_name=server)
                self.compute_manager.start()
            else:
                self.pubsub_manager.msg(
                    handler=str(PubSub.Handlers.CONTROL.value),
                    action=str(PubSub.Actions.START.value),
                    build_id=server,
                    course_object=str(PubSub.CourseObjects.LAB_SERVER.value)
                )

        if not self.state_manager.are_servers_started():
            self.state_manager.state_transition(self.s.BROKEN)
            self.logger.error(f"{self.class_name}:{self.unit_id} - Unit timed out waiting for "
                              f"server builds to complete!")
        else:
            self.state_manager.state_transition(self.s.RUNNING)
            self.logger.info(f"{self.class_name}:{self.unit_id} - Finished starting the Unit")
        self.logger.info(f"{self.class_name}:{self.unit_id} - Finished starting servers for community unit")

    def stop(self):
        """
        Stops the unit by shutting down its servers.

        This method transitions the unit's state to STOPPING and sends messages to stop all associated
        servers. It checks the state of the servers and logs the status.
        """
        self.logger.info(f"{self.class_name}:{self.unit_id} - Beginning to stop servers for a community unit")
        self.state_manager.state_transition(self.s.STOPPING)
        servers_to_stop = self.__get_servers()

        # Stop any packet mirror resources
        self.__set_promiscuous_mode()
        if self.promiscuous_mode:
            self.packet_mirroring.stop()

        # Stop remaining servers
        for server in servers_to_stop:
            if self.debug:
                self.compute_manager.load(server_name=server)
                self.compute_manager.stop()
            else:
                self.pubsub_manager.msg(
                    handler=str(PubSub.Handlers.CONTROL.value),
                    action=str(PubSub.Actions.STOP.value),
                    build_id=server,
                    course_object=str(PubSub.CourseObjects.LAB_SERVER.value)
                )

        if not self.state_manager.are_servers_stopped():
            self.state_manager.state_transition(self.s.BROKEN)
            self.logger.error(f"{self.class_name}:{self.unit_id} - Unit timed out waiting for server "
                              f"builds to complete!")
        else:
            self.state_manager.state_transition(self.s.READY)
            self.logger.info(f"{self.class_name}:{self.unit_id} - Finished stopping servers for the unit!")

    def delete(self):
        """
        Deletes the unit by deleting all servers, including workout servers, and then deleting the network objects
        """
        self.logger.info(f"{self.class_name}:{self.unit_id} - Beginning to delete community unit")
        self.state_manager.state_transition(self.s.DELETING_SERVERS)
        servers_to_delete = self.__get_servers()

        # Delete any packet mirror resources
        self.__set_promiscuous_mode()
        if self.promiscuous_mode:
            self.packet_mirroring.delete()

        # Check if we need to delete any firewall servers
        firewall_names = []
        if self.unit_model.firewalls is not None:
            firewalls = self.unit_model.firewalls
            firewall_names = [f'{self.workout_id}-{fw["name"]}' for fw in firewalls]
            FirewallServer(initial_build_id=self.unit_id, full_build_model=self.unit_model).delete()

        # Delete remaining servers
        for server_name in servers_to_delete:
            if server_name not in firewall_names:
                if self.debug:
                    try:
                        self.compute_manager.load(server_name=server_name)
                        self.compute_manager.delete()
                    except LookupError:
                        self.logger.error(f"{self.class_name}:{self.workout_id} - Could not find workout "
                                          f"server record for {server_name}. Marking Workout record as "
                                          f"broken.")
                else:
                    self.pubsub_manager.msg(
                        handler=str(PubSub.Handlers.CONTROL.value),
                        action=str(PubSub.Actions.DELETE.value),
                        build_id=server_name,
                        course_object=str(PubSub.CourseObjects.LAB_SERVER.value)
                    )

        if self.state_manager.are_servers_deleted():
            for network in self.unit_model.networks:
                self.vpc_manager.delete(network=network)
            self.state_manager.state_transition(self.s.DELETED)
            self.logger.info(f"{self.class_name}:{self.unit_id} - Finished deleting the community unit")
        else:
            self.state_manager.state_transition(self.s.BROKEN)
            self.logger.error(f"{self.class_name}:{self.unit_id} - Timed out waiting for server deletions to "
                              f"complete for community unit")

    def nuke(self):
        """
        Nukes the unit
        """
        self.logger.error(f"{self.class_name}:{self.unit_id} - Error nuking community unit. Nuking is not "
                          f"implemented yet for community units!")
        pass

    def __send_server_build_msg(self, server):
        """
        Sends a build message for a specified server.

        Args:
            server (dict): A dictionary containing the server's configuration.

        This private method is responsible for configuring and sending a build message for a given server.
        It sets the server's parent information and internal IP, then either builds the server directly
        or sends a build message through PubSub.
        """
        server_name = f"{self.unit_id}-{server['name']}"
        server['parent_id'] = self.unit_id
        server['parent_build_type'] = self.unit_model.build_type
        if server['nics'][0].get('direct_connect', False):
            server['hostname'] = f"{server_name}{self.env.parent_dns_suffix}"
            if 'tags' in server:
                server.get('tags', []).append(f'{self.unit_id}-direct-connect')
            else:
                server['tags'] = [f'{self.unit_id}-direct-connect']

        if server := self.validator(ServerModel, data=server, as_dict=True):
            self.db.update(collection_name=DbCollections.SERVER, doc_id=server_name, data=server)
        if self.debug:
            self.compute_manager.load(server_name=server_name)
            self.compute_manager.build()
        else:
            self.pubsub_manager.msg(
                handler=str(PubSub.Handlers.BUILD.value),
                action=str(PubSub.Actions.BUILD.value),
                server_name=str(server_name),
                course_object=str(PubSub.CourseObjects.LAB_SERVER.value)
            )

    def __get_servers(self):
        """
        Retrieves a list of servers associated with the unit.

        Returns:
            List[str]: A list of server names associated with the unit.

        This private method compiles a list of server names based on the unit's configuration and
        the current workout IDs. It includes both community and individual workout servers.
        """
        self.workout_ids = self.__get_workouts()
        servers = []
        for server in self.unit_model.servers:
            if server.community_server:
                server_name = f"{self.unit_id}-{server.get('name')}"
                servers.append(server_name)
            else:
                for workout_id in self.workout_ids:
                    server_name = f"{workout_id}-{server.get('name')}"
                    servers.append(server_name)
        return servers

    def __get_workouts(self):
        workouts = self.db_queries.get_children(parent_id=self.unit_id, child_collection=DbCollections.WORKOUT)
        workout_ids = []
        for workout in workouts:
            workout_ids.append(workout['id'])
        return workout_ids

    def __set_promiscuous_mode(self, network=None):
        """Checks if promiscuous mode is enabled in network"""
        if network:
            if not self.promiscuous_mode:
                self.promiscuous_mode = any(subnet.promiscuous_mode for subnet in network.subnets)
        else:
            if networks := self.unit_model.networks or []:
                for network in networks:
                    if not self.promiscuous_mode:
                        self.promiscuous_mode = any(
                            subnet.promiscuous_mode
                            for subnet in network.subnets
                        )

    def _wait_until_unit_is_ready_for_servers(self):
        wait_time = 5
        max_iterations = 20
        for i in range(max_iterations):
            if self.state_manager.get_state() >= self.s.COMPLETED_NETWORKS.value:
                return
            else:
                time.sleep(wait_time)
        self.logger.error(f"{self.class_name}:{self.unit_id} - Timed out waiting for Unit "
                          f"to finish building networks!")

