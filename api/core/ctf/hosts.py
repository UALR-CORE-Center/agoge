import time
from typing import List, Optional

from common.constants.pub_sub import PubSub
from common.constants.states import CtfStates
from common.exceptions.agoge import BadRequest, Conflict
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
