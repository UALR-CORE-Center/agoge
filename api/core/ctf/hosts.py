import time
from typing import List, Optional, get_args

from common.constants.database import DbCollections, DbOperators
from common.constants.pub_sub import PubSub
from common.constants.states import CtfStates, ServerStates
from common.exceptions.agoge import BadRequest, Conflict, NotFound
from common.models.agoge import ResetMode
from common.models.response import CtfHostRow
from common.models.users import AgogeUser
from common.utilities.gcp.cloud_logger import Logger, LoggerNames
from core.ctf.event import CtfEvent


class CtfHosts:
    """Host operations on a CTF event's boards: replant and reset publish, host rows."""
    # Endpoint table: PUT /ctf/{ctf_id}/flags/ is allowed only while boards exist and are planted or plantable.
    REPLANT_STATES = (CtfStates.ARMED, CtfStates.RUNNING, CtfStates.PAUSED, CtfStates.BROKEN)
    # Shared deadline for every publish future of one request; the request is waiting on it.
    PUBLISH_TIMEOUT_SECONDS = 30

    def __init__(self, env_dict: dict = None, db=None, pubsub=None) -> None:
        self.class_name = self.__class__.__name__
        self.log_name = LoggerNames.API
        self.logger = Logger(self.log_name, class_name=self.class_name)
        self.env_dict = env_dict
        # CtfEvent owns event loading, authorization and the lazy db/PubSub clients; reuse them.
        self.events = CtfEvent(env_dict=env_dict, db=db, pubsub=pubsub)
        self.db = self.events.db

    def replant(
        self, ctf_id: str, workout_ids: Optional[List[str]], servers: Optional[List[str]], user: AgogeUser
    ) -> int:
        """Publish one CTF_PLANT per selected board and flag-bearing server; return the message count.

        `None` selects every board (or every flag-bearing server). Every board carries every spec
        flag, so the flag-bearing servers are the spec's servers. The planter marks the flags
        `planting` itself, so nothing is written here: a replant that is never delivered leaves the
        flags as they were, and the instructor can simply replant again.
        """
        event = self.events.get(ctf_id, user)
        if event.state not in {s.value for s in self.REPLANT_STATES}:
            raise Conflict(message=f"Cannot replant flags of a CTF event that is {CtfEvent._state_name(event.state)}")
        boards = self._select(event.board_ids, workout_ids, "board")
        targets = self._select(list(dict.fromkeys(f.server for f in event.spec.flags)), servers, "server")

        attrs = PubSub.EventAttributes
        messages = [{
            attrs.HANDLER: PubSub.Handlers.CTF.value,
            attrs.ACTION: str(PubSub.Actions.CTF_PLANT.value),
            attrs.CTF_ID: ctf_id,
            attrs.WORKOUT_ID: workout_id,
            attrs.SERVER_NAME: server,
        } for workout_id in boards for server in targets]
        self._publish(ctf_id, messages)
        self.logger.info(
            f"{self.class_name}:{ctf_id} - Published replant",
            boards=len(boards), servers=len(targets), messages=len(messages),
        )
        return len(messages)

    def reset(
        self, ctf_id: str, workout_id: str, server: str, mode: str, user: AgogeUser, guest: Optional[str] = None
    ) -> None:
        """Publish one CTF_HOST_RESET for one server of one board (Host Reset Modes), or for one nested
        guest of that server when `guest` is set (Nested Guest Contract).

        Every check runs before the publish, so a refused reset sends nothing. Resets share the replant
        states: before ARMED there is nothing planted to restore (and ARMING would race the arm
        worker), and after RUNNING/PAUSED the exercise is over. Nothing is written here; the Cloud
        Function marks progress on the board as it works.
        """
        if mode not in get_args(ResetMode):
            raise BadRequest(message=f"Unknown reset mode: {mode}")
        event = self.events.get(ctf_id, user)
        if event.state not in {s.value for s in self.REPLANT_STATES}:
            raise Conflict(message=f"Cannot reset a host of a CTF event that is {CtfEvent._state_name(event.state)}")
        if workout_id not in event.board_ids:
            raise NotFound(message=f"Workout {workout_id} is not a board of this CTF event")
        # Server docs are keyed workout_id-name; a team's own servers are the only ones it may reset.
        doc = self.db.get(DbCollections.SERVER, f"{workout_id}-{server}")
        if not doc:
            raise NotFound(message=f"Server {server} does not exist on workout {workout_id}")
        if guest is not None:
            # Guest names are unique per server, not per spec, so the pair is what must be declared.
            if not any(g.name == guest and g.server == server for g in event.spec.nested_guests):
                raise NotFound(message=f"Guest {guest} is not declared on server {server}")
            if mode == 'replant' and not any(f.server == server and f.guest == guest for f in event.spec.flags):
                raise BadRequest(message=f"Guest {guest} carries no flags, so there is nothing to replant")
        elif mode == 'replant' and server not in {flag.server for flag in event.spec.flags}:
            raise BadRequest(message=f"Server {server} carries no flags, so there is nothing to replant")
        # A guest rebuild reverts a libvirt snapshot inside the parent and never touches its instance.
        if guest is None and mode == 'rebuild' and doc.get('wireguard_endpoint_id'):
            # LabServerManager.nuke() deletes WireGuard servers without rebuilding them.
            raise BadRequest(message=f"Server {server} has a WireGuard endpoint and cannot be rebuilt")

        attrs = PubSub.EventAttributes
        message = {
            attrs.HANDLER: PubSub.Handlers.CTF.value,
            attrs.ACTION: str(PubSub.Actions.CTF_HOST_RESET.value),
            attrs.CTF_ID: ctf_id,
            attrs.WORKOUT_ID: workout_id,
            attrs.SERVER_NAME: server,
            attrs.RESET_MODE: mode,
        }
        if guest is not None:
            # Omitted, not empty, for the server itself: Pub/Sub attributes are strings, so "" would
            # have to be read back as None by the handler.
            message[attrs.GUEST] = guest
        self._publish(ctf_id, [message])
        self.logger.info(
            f"{self.class_name}:{ctf_id} - Published host reset",
            workout_id=workout_id, server=server, mode=mode, guest=guest,
        )

    def hosts(self, ctf_id: str, user: AgogeUser) -> List[CtfHostRow]:
        """One row per board per server: the flag-bearing spec servers first (spec order), then the
        workout's other servers by name, so restart and rebuild reach every host a team owns. Each
        server row is followed by one row per nested guest declared on it (spec order).

        Server documents are read with `parent_id in` queries of at most MAX_IN_VALUES boards, never
        one read per board. A flag-bearing server with no document yet (unbuilt or deleted) still gets
        a row with no state, so the panel shows the gap instead of hiding the host. Shared community
        servers are parented to the unit, not a workout, so they belong to no single team and are
        not listed.
        """
        event = self.events.get(ctf_id, user)
        boards = self.events._boards(event)
        # (server, guest) per flag id; guest None is the server itself, so a guest's flags count on the
        # guest's row and not again on its parent's.
        flag_hosts = {flag.id: (flag.server, flag.guest) for flag in event.spec.flags}
        spec_servers = list(dict.fromkeys(server for server, _ in flag_hosts.values()))
        guests = {}
        for nested in event.spec.nested_guests:
            guests.setdefault(nested.server, []).append(nested.name)
        docs = self._server_docs([board.workout_id for board in boards])

        rows = []
        for board in boards:
            servers = docs.get(board.workout_id, {})
            flag_counts = {}
            for flag in board.flags:
                host = flag_hosts.get(flag.flag_id)
                if host is not None:
                    flag_counts[host] = flag_counts.get(host, 0) + 1
            names = spec_servers + sorted(name for name in servers if name not in spec_servers)
            for name in names:
                doc = servers.get(name)
                state = doc.get('state') if doc else None
                rows.append(CtfHostRow(
                    workout_id=board.workout_id,
                    team_name=board.team_name,
                    server=name,
                    server_state=state,
                    server_state_name=self._server_state_name(state),
                    flag_count=flag_counts.get((name, None), 0),
                    # Host Reset Modes: LabServerManager.nuke() leaves WireGuard servers deleted, and a
                    # server with no document has nothing to rebuild.
                    rebuild_allowed=doc is not None and not doc.get('wireguard_endpoint_id'),
                ))
                for guest in guests.get(name, []):
                    # A guest shows its parent's state: the parent is the only instance there is.
                    rows.append(CtfHostRow(
                        workout_id=board.workout_id,
                        team_name=board.team_name,
                        server=name,
                        guest=guest,
                        server_state=state,
                        server_state_name=self._server_state_name(state),
                        flag_count=flag_counts.get((name, guest), 0),
                        # A guest rebuild is a snapshot revert inside the parent, never an instance nuke.
                        rebuild_allowed=True,
                    ))
        return rows

    def _server_docs(self, workout_ids: List[str]) -> dict:
        """{workout_id: {server name: server document}} for the given workouts' own servers."""
        by_workout = {}
        for start in range(0, len(workout_ids), CtfEvent.MAX_IN_VALUES):
            chunk = workout_ids[start:start + CtfEvent.MAX_IN_VALUES]
            docs = self.db.query(
                collection_name=DbCollections.SERVER,
                filters=[('parent_id', DbOperators.IN, chunk)],
            ) or []
            for doc in docs:
                if doc.get('parent_id') in chunk and doc.get('name'):
                    by_workout.setdefault(doc['parent_id'], {})[doc['name']] = doc
        return by_workout

    @staticmethod
    def _server_state_name(state) -> Optional[str]:
        if state is None:
            return None
        return ServerStates(state).name if state in ServerStates._value2member_map_ else str(state)

    @staticmethod
    def _select(available: List[str], requested: Optional[List[str]], kind: str) -> List[str]:
        """`available` when nothing was requested, else the requested subset in `available` order.
        An empty or unknown selection is the caller's mistake, so it is refused before any publish."""
        if requested is None:
            return list(available)
        if not requested:
            raise BadRequest(message=f"Select at least one {kind}, or omit the field for every {kind}")
        unknown = [name for name in dict.fromkeys(requested) if name not in available]
        if unknown:
            raise BadRequest(message=f"Unknown {kind} for this CTF event: {', '.join(unknown)}")
        wanted = set(requested)
        return [name for name in available if name in wanted]

    def _publish(self, ctf_id: str, messages: List[dict]) -> None:
        """Publish every message, then resolve each future against one shared deadline.

        `PubSubManager.msg` returns the client's publish future, and the client reports real failures
        (network, permission, a missing topic, a timeout) only through that future, so a request that
        returns without error had every message accepted. The first failure is raised after the rest
        resolve, so the log shows how many went out.
        """
        futures, errors = [], []
        for message in messages:
            try:
                futures.append(self.events.pubsub.msg(**message))
            except Exception as e:
                # A synchronous raise means the client itself is unusable, so the rest are not tried.
                errors.append(e)
                break
        deadline = time.monotonic() + self.PUBLISH_TIMEOUT_SECONDS
        for future in futures:
            try:
                future.result(timeout=max(deadline - time.monotonic(), 0))
            except Exception as e:
                errors.append(e)
        if errors:
            self.logger.error(
                f"{self.class_name}:{ctf_id} - Publish failed",
                error_type=type(errors[0]).__name__, errors=len(errors), handed_to_client=len(futures),
                messages=len(messages),
            )
            raise errors[0]
