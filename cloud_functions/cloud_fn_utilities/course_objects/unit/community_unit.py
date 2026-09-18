import time

from common.constants.build_constants import BuildConstants
from common.constants.database import DbCollections
from common.constants.pub_sub import PubSub
from common.constants.states import ServerStates
from common.models.agoge import UnitModel, ServerModel
from common.services.wireguard_endpoint import WireGuardEndpointRegistry
from common.utilities.wireguard_firewall import has_public_wireguard_ingress

from ...gcp.vpc_manager import VpcManager
from ..compute.factory import ComputeManagerFactory
from ...gcp.firewall_rule_manager import FirewallManager
from ...server_specific.firewall_server import FirewallServer
from ...gcp.packet_mirroring.packet_mirror_factory import PacketMirrorFactory
from ..workout.factory_workout import WorkoutFactory
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
        # Build deliveries are at-least-once. A delayed delivery must not rewind a
        # Unit that has already entered its runtime or teardown lifecycle.
        if current_state >= self.s.RUNNING.value:
            return

        # Re-run an incomplete phase. The GCP managers treat already-created
        # networks/firewall rules as success, which makes a phase safe to resume
        # after a process crash between resource creation and its COMPLETED state.
        if current_state < self.s.COMPLETED_NETWORKS.value:
            if current_state != self.s.BUILDING_NETWORKS.value:
                self.state_manager.state_transition(self.s.BUILDING_NETWORKS)
            for network in self.unit_model.networks:
                self.__set_promiscuous_mode(network=network)
                self.vpc_manager.build(network=network)
            self.state_manager.state_transition(self.s.COMPLETED_NETWORKS)

        # Servers are built asynchronously and kicked off through pubsub messages.
        current_state = self.state_manager.get_state()
        if current_state < self.s.COMPLETED_SERVERS.value:
            if current_state != self.s.BUILDING_SERVERS.value:
                self.state_manager.state_transition(self.s.BUILDING_SERVERS)
            for server in self.unit_model.servers or []:
                if server.community_server:
                    self.__send_server_build_msg(server)
            if not self.state_manager.are_server_builds_finished():
                # Leave the Unit in BUILDING_SERVERS. Raising makes the Pub/Sub
                # delivery retryable and the next delivery reuses server records.
                raise TimeoutError(
                    f"Timed out waiting for community servers for Unit {self.unit_id}"
                )
            self.state_manager.state_transition(self.s.COMPLETED_SERVERS)

        current_state = self.state_manager.get_state()
        if current_state < self.s.COMPLETED_FIREWALL_RULES.value:
            if current_state != self.s.BUILDING_FIREWALL_RULES.value:
                self.state_manager.state_transition(self.s.BUILDING_FIREWALL_RULES)
            if self.unit_model.firewall_rules:
                self.firewall_manager.build(self.unit_id, self.unit_model.firewall_rules)
            self.state_manager.state_transition(self.s.COMPLETED_FIREWALL_RULES)

        # A retry may begin after the network phase, so reconstruct this derived
        # flag from the Unit model before deciding whether to create mirroring.
        self.__set_promiscuous_mode()
        # If needed, build packet mirror resource using previously created firewall rules
        if self.promiscuous_mode:
            self.packet_mirroring.create()

        self._activate_wireguard_endpoint()
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
        if self.state_manager.get_state() == self.s.DELETED.value:
            return
        self.logger.info(f"{self.class_name}:{self.unit_id} - Beginning to delete community unit")
        self.state_manager.state_transition(self.s.DELETING_SERVERS)

        # Workouts own student-specific servers and DHCP reservations. Let each
        # workout clean those up and mark itself deleted before tearing down the
        # shared network.
        workouts = self.db_queries.get_children(
            parent_id=self.unit_id,
            child_collection=DbCollections.WORKOUT
        )
        for workout_record in workouts:
            workout_id = str(workout_record['id'])
            if self.debug:
                workout = WorkoutFactory.create_workout_object(
                    workout_id=workout_id,
                    debug=self.debug,
                    env_dict=self.env_dict
                )
                workout.delete()
            else:
                self.pubsub_manager.msg(
                    handler=str(PubSub.Handlers.CONTROL.value),
                    action=str(PubSub.Actions.DELETE.value),
                    build_id=workout_id,
                    course_object=str(PubSub.CourseObjects.WORKOUT.value)
                )

        all_servers_to_wait_for = self.__get_servers()
        servers_to_delete = self.__get_community_servers()

        # Delete any packet mirror resources
        self.__set_promiscuous_mode()
        if self.promiscuous_mode:
            self.packet_mirroring.delete()

        # Check if we need to delete any firewall servers.
        firewall_names = []
        if self.unit_model.firewalls:
            firewalls = self.unit_model.firewalls
            firewall_names = [f'{self.unit_id}-{fw.name}' for fw in firewalls]
            FirewallServer(
                initial_build_id=self.unit_id,
                full_build_model=self.unit_model,
                env_dict=self.env_dict,
                debug=self.debug
            ).delete()
            all_servers_to_wait_for.extend(firewall_names)

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

        workouts_deleted = self.state_manager.are_workouts_deleted()
        servers_deleted = self.__are_servers_deleted(all_servers_to_wait_for)
        if workouts_deleted and servers_deleted:
            # Firewall rules must be removed before their VPC networks.
            if not self.firewall_manager.delete(self.unit_id):
                self.state_manager.state_transition(self.s.BROKEN)
                raise ConnectionError(
                    f'Firewall deletion was not confirmed for community Unit {self.unit_id}'
                )
            try:
                for network in self.unit_model.networks:
                    if not self.vpc_manager.delete(network=network):
                        raise ConnectionError(
                            f'VPC deletion was not confirmed for community Unit {self.unit_id}'
                        )
            except Exception:
                self.state_manager.state_transition(self.s.BROKEN)
                raise
            self.state_manager.state_transition(self.s.DELETED)
            self.logger.info(f"{self.class_name}:{self.unit_id} - Finished deleting the community unit")
        else:
            self.state_manager.state_transition(self.s.BROKEN)
            self.logger.error(
                f"{self.class_name}:{self.unit_id} - Timed out waiting for workout or shared-server "
                f"deletions to complete for community unit"
            )

    def nuke(self):
        """
        Nukes the unit
        """
        self.logger.error(f"{self.class_name}:{self.unit_id} - Error nuking community unit. Nuking is not "
                          f"implemented yet for community units!")
        pass

    def _activate_wireguard_endpoint(self) -> None:
        """Publish the locator only after the Unit's firewall phase succeeds."""
        endpoint = getattr(self.unit_model, 'wireguard_endpoint', None)
        if not endpoint:
            return
        if not has_public_wireguard_ingress(self.unit_model, endpoint.port):
            raise ValueError(
                f'Refusing to activate WireGuard endpoint {endpoint.id}: the Unit '
                f'does not allow public UDP/{endpoint.port} ingress to its gateway.'
            )
        WireGuardEndpointRegistry(
            env_dict=self.env_dict,
            db=self.db,
        ).activate(endpoint.id, unit_id=self.unit_id)

    def __send_server_build_msg(self, server: ServerModel):
        """
        Sends a build message for a specified server.

        Args:
            server (ServerModel): The server configuration.

        This private method is responsible for configuring and sending a build message for a given server.
        It sets the server's parent information and internal IP, then either builds the server directly
        or sends a build message through PubSub.
        """
        # Each build receives its own copy. Mutating the UnitModel template can leak
        # generated hostnames and addresses into later student workouts.
        server = server.model_copy(deep=True)
        server_name = f"{self.unit_id}-{server.name}"
        server.parent_id = self.unit_id
        server.parent_build_type = self.unit_model.build_type

        if server.wireguard_gateway:
            endpoint = self.unit_model.wireguard_endpoint
            if endpoint is None:
                raise ValueError(
                    f"WireGuard gateway {server_name} does not have an allocated endpoint."
                )
            if endpoint.server_name != server_name:
                raise ValueError(
                    f"WireGuard endpoint {endpoint.id} belongs to {endpoint.server_name}, not {server_name}."
                )
            server.hostname = endpoint.hostname
            server.wireguard_endpoint_id = endpoint.id
            public_nic = next(
                (nic for nic in server.nics or [] if nic.external_nat),
                None
            )
            if public_nic is None:
                raise ValueError(f"WireGuard gateway {server_name} requires an external NAT interface.")
            if endpoint.external_ip_name:
                public_nic.external_ip_name = endpoint.external_ip_name


        # Static routes are created by the next-hop server's build after that VM
        # exists. This applies to every shared router, not only WireGuard gateways.
        if server.community_server:
            unit_routes = [
                route.model_copy(deep=True)
                for route in getattr(self.unit_model, 'routes', None) or []
                if route.next_hop_instance in {server.name, server_name}
            ]
            routes_by_name = {
                route.name: route
                for route in [*(server.routes or []), *unit_routes]
            }
            server.routes = list(routes_by_name.values())

        if any(bool(nic.direct_connect) for nic in server.nics or []):
            if not server.hostname:
                server.hostname = f"{server_name}{self.env.parent_dns_suffix}"
            server.tags = list(server.tags or [])
            direct_connect_tag = f'{self.unit_id}-direct-connect'
            if direct_connect_tag not in server.tags:
                server.tags.append(direct_connect_tag)

        existing_server = self.db.get(
            collection_name=DbCollections.SERVER,
            doc_id=server_name,
        )
        if existing_server.get('state') == ServerStates.RUNNING.value:
            # A redelivery after the asynchronous build finished is already
            # satisfied; do not overwrite its runtime state or publish again.
            return

        # Omit template nulls so a retry cannot erase state written by the
        # asynchronous LabServer build. Firestore update() merges these fields.
        server_data = server.model_dump(exclude_none=True)
        for runtime_field in ('state', 'state_timestamp', 'shutoff_timestamp'):
            if runtime_field in existing_server:
                server_data[runtime_field] = existing_server[runtime_field]
        if self.validator(ServerModel, log_location=self.log_name).load(data=server_data):
            self.db.update(collection_name=DbCollections.SERVER, doc_id=server_name, data=server_data)
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
        for server in self.unit_model.servers or []:
            if server.community_server:
                server_name = f"{self.unit_id}-{server.name}"
                servers.append(server_name)
            else:
                for workout_id in self.workout_ids:
                    server_name = f"{workout_id}-{server.name}"
                    servers.append(server_name)
        return servers

    def __get_community_servers(self):
        return [
            f"{self.unit_id}-{server.name}"
            for server in self.unit_model.servers or []
            if server.community_server
        ]

    def __are_servers_deleted(self, server_names):
        """Wait for every named server, including workout-owned servers, to be deleted."""
        wait_time = 0
        deleted_states = {
            self.state_manager.server_states.DELETED.value,
        }

        while wait_time < self.state_manager.MAX_WAIT_TIME:
            all_deleted = True
            for server_name in server_names:
                server = self.db.get(collection_name=DbCollections.SERVER, doc_id=server_name)
                if server and server.get('state') not in deleted_states:
                    all_deleted = False
                    break
            if all_deleted:
                return True
            time.sleep(self.state_manager.SLEEP_TIME)
            wait_time += self.state_manager.SLEEP_TIME
        return False

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
