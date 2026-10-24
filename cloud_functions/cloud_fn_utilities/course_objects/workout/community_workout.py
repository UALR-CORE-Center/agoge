import time
from datetime import datetime, timezone
from uuid import uuid4

from google.cloud.firestore_v1.base_query import FieldFilter

from common.constants.build_constants import BuildConstants
from common.constants.database import DbCollections
from common.constants.pub_sub import PubSub
from common.constants.states import ServerStates, WorkoutStates
from common.utilities.timestamps import Timestamps
from common.models.agoge import WorkoutModel, UnitModel, ServerModel

from ..unit.unit_dhcp_service import UnitDHCP
from ...server_specific.guacamole.display_proxy import DisplayProxy
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
    SHARED_START_CLAIM_SECONDS = 300
    MANAGED_GATEWAY_WAIT_SECONDS = 300
    MANAGED_GATEWAY_POLL_SECONDS = 5

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
                build_type=BuildConstants.UnitType.COMMUNITY.value,
                env_dict=self.env_dict,
                debug=self.debug
            )
        )

    def build(self):
        # Build the servers for each student workout that are not designated for the entire unit
        self.logger.info(f"{self.class_name}:{self.workout_id} - Beginning to build servers for workout ID")
        current_state = self.state_manager.get_state()
        if current_state >= self.s.RUNNING.value:
            return

        server_build_count = 0
        if current_state < self.s.COMPLETED_SERVERS.value:
            if current_state != self.s.BUILDING_SERVERS.value:
                self.state_manager.state_transition(self.s.BUILDING_SERVERS)
            servers = self.unit_model.servers or []
            for server in servers:
                if not server.community_server:
                    server_build_count += 1
                    self.__send_server_build_msg(server)
            if not self.state_manager.are_server_builds_finished():
                # Preserve BUILDING_SERVERS so a Pub/Sub redelivery can resume
                # provisioning instead of stranding the Workout in BROKEN.
                raise TimeoutError(
                    f"Timed out waiting for servers for Workout {self.workout_id}"
                )
            self.state_manager.state_transition(self.s.COMPLETED_SERVERS)

        if getattr(self.unit_model, 'wireguard_lease', None):
            if current_state < self.s.COMPLETED_STUDENT_ENTRY.value:
                self._build_managed_display_proxy()
                # Keep a durable checkpoint before parking. A stop may fail
                # after another VM is already stopped; redelivery must retry
                # stops without trying to rebuild that existing proxy.
                self.state_manager.state_transition(self.s.COMPLETED_STUDENT_ENTRY)
            self._stop_initial_managed_servers()

        self.state_manager.state_transition(self.s.READY)
        self.logger.info(f"{self.class_name}:{self.workout_id} - Finished building {server_build_count} for "
                         f"workout ID")

    def _stop_initial_managed_servers(self):
        """Park only this newly claimed student's VMs before exposing READY."""
        names = {f'{self.workout_id}-{server.name}' for server in self.unit_model.servers or []
                 if not server.community_server}
        names.add(f'{self.workout_id}-display-guacamole-server')
        # Include dynamically created student-owned resources, never the shared
        # Unit gateway. Check parent ownership before sending any control RPC.
        for record in self.db_queries.get_servers(parent_id=self.workout_id):
            short_name = record.get('name')
            if short_name:
                names.add(short_name if short_name.startswith(f'{self.workout_id}-')
                          else f'{self.workout_id}-{short_name}')
        records = {name: self.db.get(collection_name=DbCollections.SERVER, doc_id=name) or {}
                   for name in names}
        if any(record.get('parent_id') != self.workout_id for record in records.values()):
            raise LookupError(f'Student server ownership is missing for Workout {self.workout_id}')
        for name, record in records.items():
            if self.state_manager.get_state() != self.s.COMPLETED_STUDENT_ENTRY.value:
                raise RuntimeError(f'Workout {self.workout_id} left its initial build; refusing to stop its servers')
            if record.get('state') == ServerStates.STOPPED.value:
                continue
            if record.get('state') not in (ServerStates.RUNNING.value, ServerStates.STOPPING.value,
                                           ServerStates.BROKEN.value):
                raise RuntimeError(f'Student server {name} has not finished building')
            if self.debug:
                self.compute_manager.load(server_name=name, network_prefix=self.unit_id)
                self.compute_manager.stop()
            else:
                self.pubsub_manager.msg(
                    handler=str(PubSub.Handlers.CONTROL.value),
                    action=str(PubSub.Actions.STOP.value), build_id=name,
                    course_object=str(PubSub.CourseObjects.LAB_SERVER.value))
        deadline = time.monotonic() + self.MANAGED_GATEWAY_WAIT_SECONDS
        while True:
            current = [self.db.get(collection_name=DbCollections.SERVER, doc_id=name) or {}
                       for name in names]
            if all(record.get('parent_id') == self.workout_id
                   and record.get('state') == ServerStates.STOPPED.value for record in current):
                break
            if (any(record.get('state') in (ServerStates.BROKEN.value, ServerStates.DELETED.value)
                    for record in current) or time.monotonic() >= deadline):
                raise TimeoutError(f'Could not confirm initial student servers stopped for Workout {self.workout_id}')
            time.sleep(self.MANAGED_GATEWAY_POLL_SECONDS)
        # The normal stop path persists STOPPED after its GCP operation. Verify
        # the provider too before declaring the initial student build ready.
        for name in sorted(names):
            self.compute_manager.load(server_name=name, network_prefix=self.unit_id)
            if self.compute_manager._get_instance_status() != 'TERMINATED':
                raise TimeoutError(f'GCP has not confirmed student server {name} stopped')
        self.logger.info(f'Parked initial student servers for Workout {self.workout_id}')

    def _build_managed_display_proxy(self) -> None:
        """Give each student a proxy to only that Workout's assigned machines."""
        students = []
        for template in self.unit_model.servers or []:
            if template.community_server:
                continue
            server_name = f'{self.workout_id}-{template.name}'
            record = self.db.get(collection_name=DbCollections.SERVER, doc_id=server_name)
            if not record:
                raise LookupError(f'Student server {server_name} is missing its provisioned record')
            students.append(ServerModel(**record))
        self.workout.servers = students
        # Guacamole API and the browser need the actual DHCP addresses, rather
        # than the address-less templates copied from the Community Unit.
        self.update_record(doc_id=self.workout_id, data=self.workout, update_keys=['servers'])
        DisplayProxy(
            build_id=self.workout_id,
            build_spec=self.workout,
            collection=DbCollections.WORKOUT,
            env_dict=self.env_dict,
        ).build()

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
        servers_to_start = self.__claim_shared_servers_for_start(servers_to_start)

        if first_in:
            self.packet_mirroring.start()

        for server_name in servers_to_start:
            claim = self._community_start_claims.get(server_name)
            if self.debug:
                self.compute_manager.load(server_name=server_name)
                self.compute_manager.start(**({'community_start_claim': claim} if claim else {}))
            else:
                self.pubsub_manager.msg(
                    handler=str(PubSub.Handlers.CONTROL.value),
                    action=str(PubSub.Actions.START.value),
                    build_id=server_name,
                    course_object=str(PubSub.CourseObjects.LAB_SERVER.value),
                    **({'community_start_claim': claim} if claim else {})
                )
        # Wait for server completion state
        if not self.state_manager.are_servers_started() or not self._managed_gateways_reached(ServerStates.RUNNING):
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
        # Persist STOPPING before counting siblings. If two Workouts stop at
        # nearly the same time, at least the later observer sees the other as
        # non-running and includes the shared gateway in its stop set.
        self.state_manager.state_transition(self.s.STOPPING)
        servers_to_stop, last_one_out = self.__get_servers_for_action(action=PubSub.Actions.STOP)

        self.logger.info(f"Workout {self.workout_id}: Stopping {len(servers_to_stop)} servers.")
        if servers_to_stop:
            if last_one_out:
                self.packet_mirroring.stop()

            for server_name in servers_to_stop:
                claim = None
                if self._is_managed_gateway(server_name):
                    claim = self.__claim_shared_server_stop(server_name)
                    if not claim:
                        # A sibling may have begun starting since the boundary
                        # query, or another stop already owns this transition.
                        if self._has_active_sibling():
                            last_one_out = False
                        continue
                if self.debug:
                    self.compute_manager.load(server_name=server_name)
                    self.compute_manager.stop(**({'community_stop_claim': claim} if claim else {}))
                else:
                    self.pubsub_manager.msg(
                        handler=str(PubSub.Handlers.CONTROL.value),
                        action=str(PubSub.Actions.STOP.value),
                        build_id=server_name,
                        course_object=str(PubSub.CourseObjects.LAB_SERVER.value),
                        **({'community_stop_claim': claim} if claim else {})
                    )
            if (not self.state_manager.are_servers_stopped()
                    or (last_one_out and not self._managed_gateways_reached(ServerStates.STOPPED))):
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
            self.state_manager.state_transition(self.s.READY)
            self.logger.info(f'No compute resources found for workout: {self.workout_id}. Ignoring stop request...')

    def delete(self):
        """Delete only the student-owned servers and release their Unit IP reservations."""
        if self.state_manager.get_state() == self.s.DELETED.value:
            return
        self._add_build_action(PubSub.Actions.DELETE.value, True)
        self.state_manager.state_transition(self.s.DELETING_SERVERS)
        servers_to_delete = self.db_queries.get_servers(parent_id=self.workout_id)

        for server in servers_to_delete:
            server_name = f'{server["parent_id"]}-{server["name"]}'
            if self.debug:
                try:
                    self.compute_manager.load(server_name=server_name)
                    self.compute_manager.delete()
                except LookupError:
                    self.logger.warning(
                        f"{self.class_name}:{self.workout_id} - Could not find server record "
                        f"for {server_name}; treating it as already deleted."
                    )
            else:
                self.pubsub_manager.msg(
                    handler=str(PubSub.Handlers.CONTROL.value),
                    action=str(PubSub.Actions.DELETE.value),
                    build_id=server_name,
                    course_object=str(PubSub.CourseObjects.LAB_SERVER.value)
                )

        server_names = [
            f'{server["parent_id"]}-{server["name"]}'
            for server in servers_to_delete
        ]
        if self.__are_servers_deleted(server_names):
            for server, server_name in zip(servers_to_delete, server_names):
                self.unit_dhcp.release_server_leases(
                    server_name,
                    claim_id=server.get(UnitDHCP.LEASE_CLAIM_FIELD),
                )
            self.state_manager.state_transition(self.s.DELETED)
            self.logger.info(f"{self.class_name}:{self.workout_id} - Finished deleting the Workout!")
        else:
            self.state_manager.state_transition(self.s.BROKEN)
            self.logger.error(
                f"{self.class_name}:{self.workout_id} - Timed out waiting for server deletions to complete!"
            )

    def nuke(self) -> bool:
        """Rebuild only the servers owned by this student workout."""
        return self._nuke_servers(network_prefix=self.unit_id)

    def __are_servers_deleted(self, server_names):
        """Do not recycle an address while a broken or deleting VM might still use it."""
        wait_time = 0
        deleted_state = self.state_manager.server_states.DELETED.value
        while wait_time < self.state_manager.MAX_WAIT_TIME:
            if all(
                not (server := self.db.get(
                    collection_name=DbCollections.SERVER,
                    doc_id=server_name
                )) or server.get('state') == deleted_state
                for server_name in server_names
            ):
                return True
            time.sleep(self.state_manager.SLEEP_TIME)
            wait_time += self.state_manager.SLEEP_TIME
        return False

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
        # Work from a copy of the Unit template so one student's DHCP address,
        # hostname, or parent metadata cannot leak into another workout.
        server = server.model_copy(deep=True)
        server_name = f"{self.workout_id}-{server.name}"
        server.parent_id = self.workout_id
        server.parent_build_type = self.workout.build_type
        existing_server = self.db.get(
            collection_name=DbCollections.SERVER,
            doc_id=server_name,
        )
        if existing_server.get('state') == ServerStates.RUNNING.value:
            return

        for nic in server.nics or []:
            # If direct connect is true, create the hostname that will be used to access this machine
            if nic.direct_connect:
                if not server.hostname:
                    server.hostname = f'{server_name}{self.env.parent_dns_suffix}'
                server.tags = list(server.tags or [])
                direct_connect_tag = f"{self.workout_id}-direct-connect"
                if direct_connect_tag not in server.tags:
                    server.tags.append(direct_connect_tag)

        # The reservation and server-record writes share one transaction. This
        # closes the duplicate-delivery window where two workers could allocate
        # distinct addresses and overwrite the same server document.
        server_data = self.unit_dhcp.claim_server_leases(
            server_name=server_name,
            server_data=server.model_dump(exclude_none=True),
        )
        for nic in server_data.get('nics') or []:
            self.logger.info(
                f"Unit {self.unit_id} DHCP server returning claimed IP address "
                f"{nic.get('internal_ip')} for Workout {self.workout_id}"
            )

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
        if action not in (PubSub.Actions.START, PubSub.Actions.STOP):
            raise ValueError(f'Unsupported Community Workout server action: {action}')

        # Shared resources start with the first running Workout and stop with
        # the last one. Firestore stores the state as the Enum's integer value.
        workouts = self.db_queries.get_children(
            child_collection=DbCollections.WORKOUT,
            parent_id=self.workout.parent_id
        )
        active_states = {WorkoutStates.RUNNING.value}
        if action == PubSub.Actions.STOP:
            # A student currently starting still needs the shared gateway.
            # Stopping another student must not interrupt that pending start.
            active_states.add(WorkoutStates.STARTING.value)
        boundary_workout = not any(
            workout.get('id') != self.workout_id
            and workout.get('state') in active_states
            for workout in workouts
        )

        servers = []
        unit_servers = self.unit_model.servers or []
        for server in unit_servers:
            server_name = f"{self.workout_id}-{server.name}"
            is_community_server = bool(server.community_server)
            if is_community_server:
                server_name = f"{self.unit_id}-{server.name}"

            # Student servers always follow their Workout. Shared servers are
            # touched only on the first start or the last stop.
            if not is_community_server or (is_community_server and boundary_workout):
                servers.append(server_name)

        if getattr(self.unit_model, 'wireguard_lease', None):
            servers.append(f'{self.workout_id}-display-guacamole-server')

        return servers, boundary_workout

    def _managed_gateways_reached(self, expected):
        names = [f'{self.unit_id}-{server.name}' for server in self.unit_model.servers or []
                 if getattr(server, 'community_server', False)
                 and getattr(server, 'wireguard_gateway', False)
                 and getattr(server, 'wireguard_managed', False)]
        if not names:
            return True
        deadline = time.monotonic() + self.MANAGED_GATEWAY_WAIT_SECONDS
        while True:
            if expected == ServerStates.STOPPED and self._has_active_sibling():
                # Another student can legitimately start again after the idle
                # stop claim. Their start waits for that stop, then reopens the
                # gateway; the departing student need only finish its own VMs.
                return True
            records = [self.db.get(collection_name=DbCollections.SERVER, doc_id=name) or {}
                       for name in names]
            if all(record.get('state') == expected.value
                   and (expected != ServerStates.STOPPED
                        or not (record.get('community_stop_claim') or {}).get('token')
                        or (record.get('community_stop_claim') or {}).get('completed') is True)
                   for record in records):
                return True
            if any(record.get('state') in (ServerStates.BROKEN.value, ServerStates.DELETED.value)
                   for record in records) or time.monotonic() >= deadline:
                return False
            time.sleep(self.MANAGED_GATEWAY_POLL_SECONDS)

    def __claim_shared_servers_for_start(self, server_names: list[str]) -> list[str]:
        """Atomically select one publisher for each shared-server START action.

        Two Workouts can both become STARTING before either becomes RUNNING, so
        the sibling query alone cannot safely identify the first one. The
        server document is the shared point of coordination: only the Workout
        that owns its unexpired claim publishes the shared START message.
        Student-owned servers are never filtered here.
        """
        shared_server_names = {
            f'{self.unit_id}-{server.name}'
            for server in (self.unit_model.servers or [])
            if server.community_server
        }
        self._community_start_claims = {}
        selected = []
        for server_name in server_names:
            if server_name in shared_server_names:
                claim = self.__claim_shared_server_start(server_name)
                if not claim:
                    continue
                self._community_start_claims[server_name] = claim
            selected.append(server_name)
        return selected

    def __claim_shared_server_start(self, server_name: str):
        deadline = time.monotonic() + self.MANAGED_GATEWAY_WAIT_SECONDS
        while True:
            claim = self.db.transaction(
                operation_func=self.__claim_shared_server_start_transaction,
                server_name=server_name, now=Timestamps.get_current_timestamp_utc(),
            )
            if claim != 'await_automatic_stop':
                return claim
            if time.monotonic() >= deadline:
                raise TimeoutError(f'Shared server {server_name} did not finish its automatic stop')
            time.sleep(self.MANAGED_GATEWAY_POLL_SECONDS)

    def __claim_shared_server_start_transaction(
        self,
        transaction,
        server_name: str,
        now: float,
    ):
        doc_ref = self.db.db.collection(DbCollections.SERVER.value).document(server_name)
        snapshot = doc_ref.get(transaction=transaction)
        if not snapshot.exists:
            raise LookupError(f'Shared server {server_name} does not exist.')

        server = snapshot.to_dict()
        state = server.get('state')
        if state == ServerStates.RUNNING.value:
            return False
        stop = server.get('community_stop_claim') or {}
        if (state == ServerStates.STOPPED.value and stop.get('token')
                and stop.get('completed') is not True):
            return 'await_automatic_stop'
        if state == ServerStates.STOPPING.value and (server.get('community_stop_claim') or {}).get('token'):
            return 'await_automatic_stop'
        if state in (
            ServerStates.STOPPING.value,
            ServerStates.EXPIRED.value,
            ServerStates.MISFIT.value,
            ServerStates.DELETING.value,
            ServerStates.DELETED.value,
        ):
            raise RuntimeError(
                f'Shared server {server_name} cannot be claimed from '
                f'{ServerStates(state).name}.'
            )

        claim = server.get('community_start_claim') or {}
        if state == ServerStates.STARTING.value:
            claim_owner = claim.get('owner')
            claim_expires = float(claim.get('expires') or 0)
            # A STARTING server without this claim predates the coordinator or
            # was started by another lifecycle path. Let that operation finish.
            if not claim_owner:
                return False
            if claim_owner != self.workout_id and claim_expires > now:
                return False

        token = claim.get('token') if claim.get('owner') == self.workout_id else None
        token = token or uuid4().hex

        transaction.set(
            doc_ref,
            {
                'state': ServerStates.STARTING.value,
                'state_timestamp': datetime.now(timezone.utc).isoformat(),
                'community_start_claim': {
                    'owner': self.workout_id,
                    'expires': now + self.SHARED_START_CLAIM_SECONDS,
                    'token': token,
                },
                'community_stop_claim': None,
            },
            merge=True,
        )
        return token

    def _is_managed_gateway(self, server_name):
        return any(f'{self.unit_id}-{server.name}' == server_name
                   and getattr(server, 'community_server', False)
                   and getattr(server, 'wireguard_gateway', False)
                   and getattr(server, 'wireguard_managed', False)
                   for server in self.unit_model.servers or [])

    def _has_active_sibling(self):
        return any(workout.get('id') != self.workout_id
                   and workout.get('state') in (WorkoutStates.RUNNING.value, WorkoutStates.STARTING.value)
                   for workout in self.db_queries.get_children(
                       child_collection=DbCollections.WORKOUT, parent_id=self.unit_id))

    def __claim_shared_server_stop(self, server_name):
        deadline = time.monotonic() + self.MANAGED_GATEWAY_WAIT_SECONDS
        while True:
            claim = self.db.transaction(
                operation_func=self.__claim_shared_server_stop_transaction,
                server_name=server_name, now=Timestamps.get_current_timestamp_utc())
            if claim != 'await_shared_start':
                return claim
            if time.monotonic() >= deadline:
                raise TimeoutError(f'Shared server {server_name} did not finish its current start')
            time.sleep(self.MANAGED_GATEWAY_POLL_SECONDS)

    def __claim_shared_server_stop_transaction(self, transaction, server_name, now):
        reference = self.db.db.collection(DbCollections.SERVER.value).document(server_name)
        snapshot = reference.get(transaction=transaction)
        if not snapshot.exists:
            raise LookupError(f'Shared server {server_name} does not exist.')
        server = snapshot.to_dict()
        # Firestore tracks these query reads in the same transaction as the
        # STOPPING claim. A concurrent student STARTING write retries the claim
        # rather than allowing an obsolete last-student decision to commit.
        query = self.db.db.collection(DbCollections.WORKOUT.value).where(
            filter=FieldFilter('parent_id', '==', self.unit_id))
        if any(item.to_dict().get('state') in (WorkoutStates.RUNNING.value, WorkoutStates.STARTING.value)
               for item in query.get(transaction=transaction)):
            return None
        if server.get('state') == ServerStates.STARTING.value:
            return 'await_shared_start'
        if server.get('state') == ServerStates.STOPPED.value:
            return None
        existing = server.get('community_stop_claim') or {}
        if server.get('state') == ServerStates.STOPPING.value:
            return existing.get('token') if existing.get('owner') == self.workout_id else None
        if server.get('state') not in (ServerStates.RUNNING.value, ServerStates.STARTING.value):
            raise RuntimeError(f'Shared server {server_name} cannot be automatically stopped from its current state')
        token = uuid4().hex
        transaction.set(reference, {
            'state': ServerStates.STOPPING.value,
            'state_timestamp': datetime.now(timezone.utc).isoformat(),
            'community_stop_claim': {'owner': self.workout_id, 'token': token,
                                     'expires': now + self.SHARED_START_CLAIM_SECONDS, 'completed': False},
            'community_start_claim': None,
        }, merge=True)
        return token
