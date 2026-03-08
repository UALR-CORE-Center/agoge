from common.constants.database import DbCollections
from common.constants.pub_sub import PubSub
from common.constants.states import WorkoutStates
from common.utilities.timestamps import Timestamps
from common.models.agoge import WorkoutModel, UnitModel, ServerModel

from ..unit.unit_dhcp_service import UnitDHCP
from .base_workout import BaseWorkout
from ...gcp.packet_mirroring.packet_mirror_factory import PacketMirrorFactory


class CommunityWorkout(BaseWorkout):
    """
    Manages the lifecycle of a community workout in the cyber arena.

    This class extends BaseWorkout to handle community-specific workout activities,
    including building, starting, stopping, and managing servers. It interacts
    with Google Cloud Platform services and internal DHCP services to manage
    network resources and compute instances for the workout.

    Attributes:
        unit_id (str): Identifier for the unit associated with the workout.
        unit_dhcp (UnitDHCP): An instance of the UnitDHCP class to manage DHCP services.

    Args:
        workout_id (str): Unique identifier for the workout.
        workout_model (WorkoutModel): A dictionary containing workout-specific configuration.
        unit_model (UnitModel): A dictionary containing unit-specific configuration.
        duration_hours (int, optional): Duration of the workout in hours. Defaults to 2.
        debug (bool, optional): Enables debug mode if True. Defaults to False.
        env_dict (dict, optional): Environment variables for compute instances. Defaults to None.
    """
    def __init__(
        self,
        workout_id,
        workout_model: WorkoutModel,
        unit_model: UnitModel,
        duration_hours=2,
        debug=False,
        env_dict=None
    ):
        super().__init__(workout_id=workout_id, workout_model=workout_model, unit_model=unit_model,
                         duration_hours=duration_hours, debug=debug, env_dict=env_dict)
        self.class_name = self.__class__.__name__
        self.unit_id = unit_model.id
        self.unit_dhcp = UnitDHCP(unit_id=self.unit_id)
        self.packet_mirroring = (
            PacketMirrorFactory.create_packet_mirror_object(
                build_id=self.unit_id,
                build=self.unit_model.model_dump(),
                env_dict=self.env_dict,
                debug=self.debug
            )
        )

    def build(self):
        # Build the servers for each student workout that are not designated for the entire unit
        self.logger.info(f"{self.class_name}:{self.workout_id} - Beginning to build servers for workout ID")
        server_build_count = 0
        if self.state_manager.get_state() < self.s.BUILDING_SERVERS.value:
            self.state_manager.state_transition(self.s.BUILDING_SERVERS)
            servers = self.unit_model.servers or []
            for server in servers:
                if not server.community_server:
                    server_build_count += 1
                    self.__send_server_build_msg(server)
        if not self.state_manager.are_server_builds_finished():
            self.state_manager.state_transition(self.s.BROKEN)
            self.logger.error(f"{self.class_name}:{self.workout_id} - Workout timed out waiting for server "
                              f"builds to complete!")
        else:
            self.state_manager.state_transition(self.s.READY)
            self.logger.info(f"{self.class_name}:{self.workout_id} - Finished building {server_build_count} for "
                             f"workout ID")

    def start(self):
        """
        Initiates the start process for the community workout. It also ensures community servers are started with
        the workout

        This method triggers the starting of servers and transitions the workout state accordingly.
        It logs the progress and handles any errors that might occur during the process.

        Raises:
            TimeoutError: If the servers fail to start within the expected timeframe.
        """
        self.logger.info(f"Beginning to start servers for workout ID {self.workout_id}")
        self._add_build_action(PubSub.Actions.START.value, True)
        self.state_manager.state_transition(self.s.STARTING)
        servers_to_start, first_in = self.__get_servers_for_action(action=PubSub.Actions.START)

        if first_in:
            self.packet_mirroring.start()

        for server_name in servers_to_start:
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
        # Wait for server completion state
        if not self.state_manager.are_servers_started():
            self.state_manager.state_transition(self.s.BROKEN)
            self.logger.error(f"Workout {self.workout_id}: Timed out waiting for server builds to complete!")
        else:
            self.state_manager.state_transition(self.s.RUNNING)
            self.logger.info(f"Finished starting the Workout: {self.workout_id}!")
        self.workout = self.get_record()
        self.workout.shutoff_timestamp = Timestamps.get_current_timestamp_utc(add_seconds=self.duration_seconds)
        self.update_record(doc_id=self.workout_id, data=self.workout)
        self.logger.info(f"Finished starting {len(servers_to_start)} servers for workout ID {self.workout_id}")

    def stop(self):
        """
        Initiates the stop process for the community workout and ensures if this is the last workout, then
        the community servers are stopped.

        This method triggers the stopping of servers and transitions the workout state accordingly.
        It logs the progress and handles any errors that might occur during the process.

        Raises:
            TimeoutError: If the servers fail to stop within the expected timeframe.
        """
        self.logger.info(f"Beginning to stop servers for workout ID {self.workout_id}")
        self._add_build_action(PubSub.Actions.STOP.value, True)
        servers_to_stop, last_one_out = self.__get_servers_for_action(action=PubSub.Actions.STOP)

        self.logger.info(f"Workout {self.workout_id}: Stopping {len(servers_to_stop)} servers.")
        if servers_to_stop:
            self.state_manager.state_transition(self.s.STOPPING)
            if last_one_out:
                self.packet_mirroring.stop()

            for server_name in servers_to_stop:
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
                self.logger.error(f"Workout {self.workout_id}: Timed out waiting for server builds to stop!")
            else:
                self.state_manager.state_transition(self.s.READY)
                self.logger.info(f"Finished Stopping the Workout: {self.workout_id}!")
                self.workout = self.get_record()
                self.workout.shutoff_timestamp = None
                self.update_record(doc_id=self.workout_id, data=self.workout)
                self.logger.info(f"Finished stopping {len(servers_to_stop)} servers for workout ID {self.workout_id}")
        else:
            self.logger.info(f'No compute resources found for workout: {self.workout_id}. Ignoring stop request...')

    def delete(self):
        """Community workout deletion takes place at the Unit level"""
        pass

    def nuke(self):
        """Community workout nuking takes place at the Unit level"""
        pass

    def __send_server_build_msg(self, server: ServerModel):
        """
        Sends a message to build a server for the workout with necessary configurations.

        This function generates a server name based on the workout ID and the server's name. It assigns
        the workout ID and the workout entity's build type to the server. It then iterates through the
        network interfaces (NICs) of the server to obtain and assign internal IP addresses from the DHCP
        server. The server configuration is then stored in the datastore. Depending on the debug mode,
        this function either directly builds the server using ComputeManager or sends a message to
        PubSub to trigger the build process.

        Args:
            server (Entity): Datastore entity containing the server's configuration.

        Side Effects:
            - Updates the server's configuration with a parent ID, build type, and internal IP addresses for each NIC.
            - Stores the updated server configuration in the datastore.
            - In debug mode, directly builds the server. Otherwise, sends a message to PubSub for server build.
        """
        server_name = f"{self.workout_id}-{server.name}"
        server.parent_id = self.workout_id
        server.parent_build_type = self.workout.build_type
        for nic in server.nics:
            internal_ip = self.unit_dhcp.get_network_address(nic.network)
            self.logger.info(f"Unit {self.unit_id} DHCP server returning available IP address {internal_ip} for "
                             f"Workout {self.workout_id}")
            nic.internal_ip = internal_ip

            # If direct connect is true, create the hostname that will be used to access this machine
            if nic.direct_connect and not server.hostname:
                server.hostname = f'{server_name}{self.env.parent_dns_suffix}'
                server.tags.append(f"{self.workout_id}-direct-connect")
                # Get the updated workout first before saving it back. Otherwise, this will overwrite the workout state.
                self.workout = self.get_record()
                self.workout = self.update_record(doc_id=self.workout_id, data=self.workout)
        self.db.update(collection_name=DbCollections.SERVER, doc_id=server_name, data=server)
        if self.debug:
            self.compute_manager.load(
                server_name=server_name,
                network_prefix=self.unit_id,
            )
            self.compute_manager.build()
        else:
            self.pubsub_manager.msg(
                handler=str(PubSub.Handlers.BUILD.value),
                action=str(PubSub.Actions.BUILD.value),
                server_name=str(server_name),
                network_prefix=self.unit_id,
                course_object=str(PubSub.CourseObjects.LAB_SERVER.value)
            )

    def __get_servers_for_action(self, action: PubSub.Actions):
        """
        Determine the servers to be affected by a specified action (start or stop).

        Args:
            action (PubSub.Actions): The action to be performed (start or stop).

        Returns:
            List[str]: A list of server names to be acted upon.
        """
        # Determine if this is the last workout to stop in case of a community build.
        last_one_out = True
        if action == PubSub.Actions.STOP:
            workouts = self.db_queries.get_children(
                child_collection=DbCollections.WORKOUT,
                parent_id=self.workout.parent_id
            )
            for workout in workouts:
                if workout['id'] != self.workout_id and workout['state'] == WorkoutStates.RUNNING:
                    last_one_out = False
                    break

        servers = []
        unit_servers = self.unit_model.servers or []
        for server in unit_servers:
            server_name = f"{self.workout_id}-{server.name}"
            is_community_server = bool(server.community_server)
            if is_community_server:
                server_name = f"{self.unit_id}-{server.name}"

            # Add server if it's non-community or if it's a community server and starting or the last workout stopping.
            if not is_community_server or (is_community_server and (
                    action == PubSub.Actions.START or (
                    action == PubSub.Actions.STOP and last_one_out))):
                servers.append(server_name)

        return servers, last_one_out
