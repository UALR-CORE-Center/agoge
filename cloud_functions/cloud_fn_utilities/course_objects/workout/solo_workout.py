from common.constants.database import DbCollections
from common.constants.pub_sub import PubSub
from common.utilities.timestamps import Timestamps
from common.models.agoge import WorkoutModel, UnitModel

from cloud_fn_utilities.server_specific.guacamole.display_proxy import DisplayProxy
from ...server_specific.firewall_server import FirewallServer
from .base_workout import BaseWorkout
from ...gcp.packet_mirroring.packet_mirror_factory import PacketMirrorFactory


class SoloWorkout(BaseWorkout):
    def __init__(
        self,
        workout_id: str,
        workout_model: WorkoutModel,
        unit_model: UnitModel,
        duration_hours: int = 2,
        debug: bool = False,
        env_dict: dict = None
    ) -> None:
        super().__init__(
            workout_id=workout_id,
            workout_model=workout_model,
            unit_model=unit_model,
            duration_hours=duration_hours,
            debug=debug,
            env_dict=env_dict
        )
        self.class_name = self.__class__.__name__
        self.packet_mirroring = (
            PacketMirrorFactory.create_packet_mirror_object(
                build_id=self.workout_id,
                build=self.workout.model_dump(),
                env_dict=self.env_dict,
                debug=self.debug
            )
        )

    def build(self):
        self._reset_expiration()
        if not self.workout.networks:
            if self.workout.web_applications is not None:
                self.state_manager.state_transition(self.s.RUNNING)
                self.logger.info(f"{self.class_name}:{self.workout_id} - No compute assets required for workout.")
                self.logger.info(f"{self.class_name}:{self.workout_id} - Finished building workout.")
            else:
                self.logger.info(f"{self.class_name}:{self.workout_id} - No compute assets to build for workout.")
            return

        if not (state := self.state_manager.get_state()):
            self.state_manager.state_transition(self.s.START)
        elif state == self.s.DELETED.value:
            now = Timestamps.get_current_timestamp_utc()
            if now < self.unit_model.workspace_settings.expires:
                self.state_manager.state_transition(self.s.START)
            else:
                self.logger.error(f"{self.class_name}:{self.workout_id} - Attempt to rebuild workout failed: "
                                  f"Unit is already expired!")
                return

        if self.state_manager.get_state() < self.s.BUILDING_NETWORKS.value:
            self.state_manager.state_transition(self.s.BUILDING_NETWORKS)
            networks = self.workout.networks or []
            for network in networks:
                self.__set_promiscuous_mode(network=network)
                self.vpc_manager.build(network=network)
            self.state_manager.state_transition(self.s.COMPLETED_NETWORKS)

        # Servers are built asynchronously and kicked off through pubsub messages.
        if self.state_manager.get_state() < self.s.BUILDING_SERVERS.value:
            self.state_manager.state_transition(self.s.BUILDING_SERVERS)
            # Build the Guacamole Proxy first, so it will be ready when the students hit the landing page.
            if self.debug:
                DisplayProxy(
                    build_id=self.workout_id,
                    build_spec=self.workout,
                    collection=DbCollections.WORKOUT,
                    env_dict=self.env_dict
                ).build()
            else:
                self.pubsub_manager.msg(
                    handler=str(PubSub.Handlers.BUILD.value),
                    action=str(PubSub.Actions.BUILD.value),
                    key_type=str(DbCollections.WORKOUT.value),
                    build_id=str(self.workout_id),
                    course_object=str(PubSub.CourseObjects.DISPLAY_PROXY.value)
                )

            servers = self.workout.servers or []
            for server in servers:
                server_name = f"{self.workout_id}-{server.name}"
                server.parent_id = self.workout_id
                server.parent_build_type = self.workout.build_type
                server.firewall_rules = self.workout.firewall_rules or []

                # If direct connect is true, create the hostname that will be used to access this machine
                # direct_connect = False
                direct_connect = any(bool(nic.direct_connect) for nic in server.nics)
                if direct_connect:
                    server.hostname = f'{server_name}{self.env.parent_dns_suffix}'
                    if server.tags is None:
                        server.tags = [f"{self.workout_id}-direct-connect"]
                    else:
                        server.tags.append(f"{self.workout_id}-direct-connect")
                    self.update_record(doc_id=self.workout_id, data=self.workout, update_keys=['servers'])

                self.db.update(
                    collection_name=DbCollections.SERVER,
                    doc_id=server_name,
                    data=server.model_dump()
                )

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

            # Check if we need to build a firewall server on network
            if self.workout.firewalls:
                FirewallServer(
                    initial_build_id=self.workout_id,
                    full_build_model=self.workout,
                    env_dict=self.env_dict,
                    debug=self.debug
                ).build()

        if self.state_manager.get_state() < self.s.BUILDING_FIREWALL_RULES.value:
            self.state_manager.state_transition(self.s.BUILDING_FIREWALL_RULES)
            if (firewall_rules := self.workout.firewall_rules) is not None:
                self.firewall_manager.build(self.workout_id, firewall_rules)
            self.state_manager.state_transition(self.s.COMPLETED_FIREWALL_RULES)

        if self.promiscuous_mode:
            self.packet_mirroring.create()

        if not self.state_manager.are_server_builds_finished():
            self.state_manager.state_transition(self.s.BROKEN)
            self.logger.error(f"{self.class_name}:{self.workout_id} - Workout timed out waiting for server "
                              f"builds to complete!")
        else:
            self.state_manager.state_transition(self.s.RUNNING)
            self.logger.info(f"{self.class_name}:{self.workout_id} - Finished building Workout!")

    def start(self):
        self._add_build_action(PubSub.Actions.START.value, True)
        self.state_manager.state_transition(self.s.STARTING)
        servers_to_start = self.db_queries.get_servers(self.workout_id)

        # Packet mirroring resources are managed separately from normal compute instances
        self.__set_promiscuous_mode()
        if self.promiscuous_mode:
            self.packet_mirroring.start()

        # Start remaining servers
        for server in servers_to_start:
            server_name = f'{server["parent_id"]}-{server["name"]}'
            if self.debug:
                self.compute_manager.load(server_name=server_name)
                self.compute_manager.start()
            else:
                self.pubsub_manager.msg(
                    handler=str(PubSub.Handlers.CONTROL.value),
                    action=str(PubSub.Actions.START.value),
                    build_id=server_name,
                    course_object=str(PubSub.CourseObjects.LAB_SERVER.value)
                )

        if not self.state_manager.are_servers_started():
            self.state_manager.state_transition(self.s.BROKEN)
            self.logger.error(f"{self.class_name}:{self.workout_id} - Workout timed out waiting for server builds "
                              f"to complete!")
        else:
            self.state_manager.state_transition(self.s.RUNNING)
            self.logger.info(f"{self.class_name}:{self.workout_id} - Finished starting the Workout!")

        self.workout = self.get_record()
        self.workout.shutoff_timestamp = Timestamps.get_current_timestamp_utc(
            add_seconds=self.duration_seconds
        )
        self.update_record(doc_id=self.workout_id, data=self.workout)

    def stop(self):
        self._add_build_action(PubSub.Actions.STOP.value, True)
        servers_to_stop = self.db_queries.get_servers(parent_id=self.workout_id)

        if servers_to_stop:
            self.state_manager.state_transition(self.s.STOPPING)

            # Packet mirroring resources are handled separately from normal compute instances
            self.__set_promiscuous_mode()
            if self.promiscuous_mode:
                self.packet_mirroring.stop()

            # Stop remaining servers
            for server in servers_to_stop:
                server_name = f'{server["parent_id"]}-{server["name"]}'
                if self.debug:
                    self.compute_manager.load(server_name=server_name)
                    self.compute_manager.stop()
                else:
                    self.pubsub_manager.msg(
                        handler=str(PubSub.Handlers.CONTROL.value),
                        action=str(PubSub.Actions.STOP.value),
                        build_id=server_name,
                        course_object=str(PubSub.CourseObjects.LAB_SERVER.value)
                    )

            if not self.state_manager.are_servers_stopped():
                self.state_manager.state_transition(self.s.BROKEN)
                self.logger.error(f"{self.class_name}:{self.workout_id} - Workout timed out waiting for server "
                                  f"builds to stop!")
            else:
                self.state_manager.state_transition(self.s.READY)
                self.logger.info(f"{self.class_name}:{self.workout_id} - Finished Stopping the Workout!")
                self.workout = self.get_record()
                self.workout.shutoff_timestamp = None
                self.update_record(doc_id=self.workout_id, data=self.workout)
        else:
            self.logger.info(f'{self.class_name}:{self.workout_id} - No compute resources found for workout. '
                             f'Ignoring stop request...')

    def delete(self):
        self._add_build_action(PubSub.Actions.DELETE.value, True)
        self.state_manager.state_transition(self.s.DELETING_SERVERS)
        servers_to_delete = self.db_queries.get_servers(parent_id=self.workout_id)

        # First we need to delete any packet mirroring resources
        self.__set_promiscuous_mode()
        if self.promiscuous_mode:
            self.packet_mirroring.delete()

        # Check if we need to delete any firewall servers
        firewall_names = []
        if self.workout.firewalls is not None:
            firewalls = self.workout.firewalls
            firewall_names = [f'{self.workout_id}-{fw.name}' for fw in firewalls]
            FirewallServer(
                initial_build_id=self.workout_id,
                full_build_model=self.workout
            ).delete()

        # Delete remaining servers
        for server in servers_to_delete:
            server_name = f'{server["parent_id"]}-{server["name"]}'
            if server_name not in firewall_names:
                if self.debug:
                    try:
                        self.compute_manager.load(server_name=server_name)
                        self.compute_manager.delete()
                    except LookupError:
                        self.logger.error(f"{self.class_name}:{self.workout_id} - Could not find server record "
                                          f"for {server_name}. Marking Workout record as broken.")
                else:
                    self.pubsub_manager.msg(
                        handler=str(PubSub.Handlers.CONTROL.value),
                        action=str(PubSub.Actions.DELETE.value),
                        build_id=server_name,
                        course_object=str(PubSub.CourseObjects.LAB_SERVER.value)
                    )

        if self.state_manager.are_servers_deleted():
            self.firewall_manager.delete(self.workout_id)
            if self.workout.networks is not None:
                for network in self.workout.networks:
                    self.vpc_manager.delete(network=network)
            self.state_manager.state_transition(self.s.DELETED)
            self.logger.info(f"{self.class_name}:{self.workout_id} - Finished deleting the Workout!")
        else:
            self.state_manager.state_transition(self.s.BROKEN)
            self.logger.error(f"{self.class_name}:{self.workout_id} - Workout timed out waiting for server deletions "
                              f"to complete!")

    def nuke(self) -> bool:
        """Deletes all existing servers for current workout and rebuilds
        using the specification already stored in the Datastore object
        :return:
        """
        return self._nuke_servers()

    def __set_promiscuous_mode(self, network=None):
        """Checks if promiscuous mode is enabled in network"""
        if network is not None:
            if not self.promiscuous_mode:
                subnets = network.subnets or []
                self.promiscuous_mode = any(subnet.promiscuous_mode for subnet in subnets)
        else:
            networks = self.workout.networks or []
            for network in networks:
                if not self.promiscuous_mode:
                    subnets = network.subnets or []
                    self.promiscuous_mode = any(subnet.promiscuous_mode for subnet in subnets)
