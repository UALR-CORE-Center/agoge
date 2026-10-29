import time
from datetime import datetime, timezone
from typing import List, Optional

from pydantic import ValidationError

from common.constants.build_constants import BuildConstants
from common.constants.database import DbCollections, DbOperationTypes, DbOperators
from common.constants.pub_sub import PubSub
from common.constants.states import CtfStates, WorkoutStates
from common.exceptions.agoge import BadRequest, Conflict, NotFound, ServiceUnavailable
from common.models.agoge import (
    CtfCreateRequest,
    CtfEventModel,
    CtfSpecModel,
    CtfTeamMembersRequest,
    CtfTeamRequest,
    UnitModel,
)
from common.models.model_validators.model_validator import ModelValidator
from common.models.response import CtfTeamRow, CtfTemplateRow, CtfTemplateServer
from common.models.users import AgogeUser
from common.utilities.gcp.cloud_logger import Logger, LoggerNames
from common.utilities.id_generator import IdGenerator
from common.utilities.workout_record import build_workout_record
from core.ctf.event import NOT_PROVISIONED_MESSAGE, CtfEvent
from core.ctf.hosts import CtfHosts
from core.unit import Unit
from utilities.infrastructure_as_code.object_validators import CtfValidator


class CtfSetup:
    """Pre-event setup: create an event and its lab from a template, manage the team roster,
    edit the event's flags, and build/start/stop every team's VMs ahead of Arm.

    A team is a board plus the workout it plays on. Its workout is written NOT_BUILT when the team is
    added, so no VM starts until the instructor builds the servers or a member first joins.
    """
    S = CtfStates
    # The board list and the flags are fixed once arming starts: arm workers plant exactly them.
    SETUP_STATES = {S.DRAFT}
    # Late students can still be added to a team until the exercise is over.
    MEMBER_STATES = {S.DRAFT, S.ARMING, S.ARMED, S.RUNNING, S.PAUSED, S.BROKEN}
    # Workouts that have servers: neither unbuilt nor being torn down.
    UNBUILT_STATES = {WorkoutStates.NOT_BUILT.value}
    GONE_STATES = {
        WorkoutStates.DELETING_SERVERS.value,
        WorkoutStates.COMPLETED_DELETING_SERVERS.value,
        WorkoutStates.DELETED.value,
    }
    # action -> (states it may run in, handler, PubSub action, whether it targets unbuilt workouts)
    SERVER_ACTIONS = {
        'build': (
            {S.DRAFT, S.ARMED, S.BROKEN, S.RUNNING, S.PAUSED},
            PubSub.Handlers.BUILD, PubSub.Actions.BUILD, True,
        ),
        'start': (
            {S.DRAFT, S.ARMED, S.BROKEN, S.RUNNING, S.PAUSED},
            PubSub.Handlers.CONTROL, PubSub.Actions.START, False,
        ),
        # Never while RUNNING: stopping a team's VMs mid-exercise is a host reset, not setup.
        # ARCHIVED is allowed so leftover VMs can still be shut down after the event is filed away.
        'stop': (
            {S.DRAFT, S.ARMED, S.BROKEN, S.PAUSED, S.ENDED, S.ARCHIVED},
            PubSub.Handlers.CONTROL, PubSub.Actions.STOP, False,
        ),
    }

    def __init__(self, env_dict: dict = None, db=None, pubsub=None, env=None) -> None:
        self.class_name = self.__class__.__name__
        self.log_name = LoggerNames.API
        self.logger = Logger(self.log_name, class_name=self.class_name)
        # CtfEvent owns event loading, authorization, boards and the lazy db/PubSub/env clients.
        self.events = CtfEvent(env_dict=env_dict, db=db, pubsub=pubsub, env=env)
        # Reused for its publish-and-wait helper.
        self.hosts = CtfHosts(env_dict=env_dict, db=self.events.db, pubsub=pubsub)
        self.db = self.events.db

    def templates(self) -> List[CtfTemplateRow]:
        """Catalog templates a CTF can be created from: solo labs whose `ctf` block validates."""
        docs = self.db.query(collection_name=DbCollections.CATALOG) or []
        rows = []
        for doc in docs:
            if not doc.get('ctf') or not self._is_solo(doc):
                continue
            try:
                spec = ModelValidator(CtfSpecModel, log_location=self.log_name).load(doc['ctf'])
            except ValidationError:
                self.logger.warning(f"{self.class_name}:{doc.get('id')} - Skipping template with an invalid ctf block")
                continue
            summary = doc.get('summary') or {}
            rows.append(CtfTemplateRow(
                id=doc['id'],
                name=summary.get('name') or doc['id'],
                description=summary.get('description'),
                ctf_name=spec.name,
                flag_count=sum(1 for flag in spec.flags if not flag.decoy),
                servers=[
                    CtfTemplateServer(
                        name=server.get('name'),
                        os=(server.get('details') or {}).get('os'),
                        machine_type=server.get('machine_type'),
                    )
                    for server in doc.get('servers') or [] if server.get('name')
                ],
            ))
        return sorted(rows, key=lambda row: row.name.lower())

    def _get_image_record(self, image_id: str):
        """CtfValidator's image loader: a parent built from a nested lab host image needs no ip_aliases."""
        return self.db.get(collection_name=DbCollections.IMAGE, doc_id=image_id)

    def create(self, request: CtfCreateRequest, user: AgogeUser, ctf_id: str) -> str:
        """Create the event's own lab from a catalog template, then the event in DRAFT with no teams.

        The lab is a solo unit marked with `ctf_event_id` and `registration_required`, so its join
        page admits only rostered emails. Nothing is published: no VM exists until servers are built.
        """
        spec_doc = self.db.get(collection_name=DbCollections.CATALOG, doc_id=request.spec_id)
        if not spec_doc:
            raise NotFound(message="Template not found")
        if not spec_doc.get('ctf'):
            raise BadRequest(message="Template has no ctf specification")
        if not self._is_solo(spec_doc):
            raise BadRequest(message="A CTF template must be a solo lab")
        try:
            spec = ModelValidator(CtfSpecModel, log_location=self.log_name).load(spec_doc['ctf'])
        except ValidationError as e:
            raise BadRequest(message=f"Template ctf specification is invalid: {e.error_count()} error(s)")
        # The checks a catalog save runs, so a stale template fails here rather than at Arm.
        CtfValidator(
            {'servers': spec_doc.get('servers') or [], 'ctf': spec.model_dump()}, image_loader=self._get_image_record,
        ).load()
        if request.name:
            spec.name = request.name
        if request.expires <= time.time():
            raise BadRequest(message="expires must be in the future")
        if not self.events.env.ctf_flag_seed:
            raise ServiceUnavailable(message=NOT_PROVISIONED_MESSAGE)

        try:
            # count 0: CtfSetup sets it to the number of teams as they are added.
            unit = Unit.new_unit_model(
                build_spec=spec_doc,
                requester=user,
                expires=int(request.expires),
                build_count=0,
                registration_required=True,
            )
        except ValidationError as e:
            raise BadRequest(message=f"Template is not a valid lab: {e.error_count()} error(s)")
        unit.ctf = spec
        unit.ctf_event_id = ctf_id
        event = CtfEventModel(
            id=ctf_id,
            unit_id=unit.id,
            instructor_id=[user.email],
            spec=spec,
            creation_timestamp=time.time(),
            board_ids=[],
            join_code=unit.join_code,
            state=CtfStates.DRAFT.value,
            state_timestamp=datetime.now(timezone.utc).isoformat(),
        )
        self.db.update(collection_name=DbCollections.UNIT, doc_id=unit.id, data=unit.model_dump())
        try:
            self.db.update(collection_name=DbCollections.CTF, doc_id=ctf_id, data=event.model_dump(mode='json'))
        except Exception:
            # The unit is only reachable through its event, so it goes too.
            self.db.delete(collection_name=DbCollections.UNIT, doc_id=unit.id)
            raise
        self.logger.info(f"{self.class_name}:{ctf_id} - Created CTF event", unit_id=unit.id, spec_id=request.spec_id)
        return ctf_id

    def teams(self, ctf_id: str, user: AgogeUser) -> List[CtfTeamRow]:
        event = self.events.get(ctf_id, user)
        boards = self.events._boards(event)
        workouts = self._workouts([board.workout_id for board in boards])
        return [
            self._team_row(board.workout_id, board.team_name, board.members, board.arm_status,
                           workouts.get(board.workout_id))
            for board in boards
        ]

    def add_team(self, ctf_id: str, request: CtfTeamRequest, user: AgogeUser) -> CtfTeamRow:
        """Write the team's NOT_BUILT workout, its board and its digests, then add it to the event."""
        event = self._event_in(ctf_id, user, self.SETUP_STATES, "add a team to")
        boards = self.events._boards(event)
        if any(board.team_name.lower() == request.team_name.lower() for board in boards):
            raise Conflict(message=f"A team named {request.team_name} already exists")
        max_boards = self.events._max_boards()
        if len(event.board_ids) >= max_boards:
            raise BadRequest(message=f"A CTF event allows at most {max_boards} teams")
        # Not atomic with the commit below: two instructors adding the same email at the same moment
        # could both pass. The join then resolves the email to the first board found.
        self._require_free_members(request.members)
        seed = self.events.env.ctf_flag_seed
        if not seed:
            raise ServiceUnavailable(message=NOT_PROVISIONED_MESSAGE)
        unit = self._unit(event)

        workout_id = IdGenerator.build_id()
        workout = build_workout_record(
            unit, workout_id, log_name=self.log_name,
            student_email=request.members[0], team_name=request.team_name,
        )
        board, digests = self.events._new_board(event, workout, seed)
        board.members = request.members
        docs = [
            (DbCollections.WORKOUT, workout_id, workout),
            *((DbCollections.CTF_DIGEST, d.digest, d.model_dump()) for d in digests),
            (DbCollections.CTF_BOARD, board.id, board.model_dump()),
        ]
        self.events._commit(ctf_id, docs)
        try:
            count = self.db.transaction(lambda transaction: self._change_board_ids(transaction, ctf_id, add=workout_id))
        except Exception:
            self.events._rollback(ctf_id, docs)
            raise
        self._set_unit_count(event.unit_id, count)
        self.logger.info(f"{self.class_name}:{ctf_id} - Added team", workout_id=workout_id, members=len(request.members))
        return self._team_row(workout_id, board.team_name, board.members, board.arm_status, workout)

    def remove_team(self, ctf_id: str, workout_id: str, user: AgogeUser) -> None:
        """Delete a team whose servers were never built: its digests, board and workout record."""
        event = self._event_in(ctf_id, user, self.SETUP_STATES, "remove a team from")
        if workout_id not in event.board_ids:
            raise NotFound(message="Team not found")
        board_id = f"{ctf_id}-{workout_id}"
        if not self._is_unbuilt(workout_id):
            raise Conflict(message="This team's servers are already built; only an unbuilt team can be removed")
        # Deactivate first: from here a member's join is refused (NotOnRoster), so no BUILD can race the
        # delete, and an inactive board never blocks its emails from joining another team.
        self.db.update(collection_name=DbCollections.CTF_BOARD, doc_id=board_id, data={'active': False})
        if not self._is_unbuilt(workout_id):
            # A member joined between the check and the deactivation; the team stays.
            self.db.update(collection_name=DbCollections.CTF_BOARD, doc_id=board_id, data={'active': True})
            raise Conflict(message="A member just joined and started this team's servers; it can no longer be removed")
        digests = self.db.query(
            collection_name=DbCollections.CTF_DIGEST,
            filters=[('ctf_id', DbOperators.EQUAL, ctf_id), ('workout_id', DbOperators.EQUAL, workout_id)],
        ) or []
        docs = [
            *((DbCollections.CTF_DIGEST, digest['digest']) for digest in digests),
            (DbCollections.CTF_BOARD, board_id),
            (DbCollections.WORKOUT, workout_id),
        ]
        self.db.batch_write([
            self.events._operation(collection, doc_id, DbOperationTypes.DELETE) for collection, doc_id in docs
        ])
        count = self.db.transaction(lambda transaction: self._change_board_ids(transaction, ctf_id, remove=workout_id))
        self._set_unit_count(event.unit_id, count)
        self.logger.info(f"{self.class_name}:{ctf_id} - Removed team", workout_id=workout_id)

    def set_members(self, ctf_id: str, workout_id: str, request: CtfTeamMembersRequest, user: AgogeUser) -> CtfTeamRow:
        """Replace a team's roster. The workout's student_email follows the first member."""
        event = self._event_in(ctf_id, user, self.MEMBER_STATES, "change the roster of")
        if workout_id not in event.board_ids:
            raise NotFound(message="Team not found")
        board_id = f"{ctf_id}-{workout_id}"
        board = self.db.get(collection_name=DbCollections.CTF_BOARD, doc_id=board_id)
        if not board:
            raise NotFound(message="Team not found")
        self._require_free_members(request.members, exclude_board_id=board_id)
        self.db.update(collection_name=DbCollections.CTF_BOARD, doc_id=board_id, data={'members': request.members})
        workout = self.db.get(collection_name=DbCollections.WORKOUT, doc_id=workout_id)
        if workout:
            self.db.update(
                collection_name=DbCollections.WORKOUT, doc_id=workout_id,
                data={'student_email': request.members[0]},
            )
        self.logger.info(f"{self.class_name}:{ctf_id} - Updated team roster", workout_id=workout_id, members=len(request.members))
        return self._team_row(workout_id, board['team_name'], request.members, board.get('arm_status', 'pending'), workout)

    def update_spec(self, ctf_id: str, ctf: CtfSpecModel, user: AgogeUser) -> CtfEventModel:
        """Replace the event's flags and scoring. Every board's flag states and digests are rebuilt,
        because a flag id or the prefix changes the derived values. Allowed only in DRAFT, before
        anything is planted."""
        event = self._event_in(ctf_id, user, self.SETUP_STATES, "edit the flags of")
        unit = self.db.get(collection_name=DbCollections.UNIT, doc_id=event.unit_id) or {}
        # The same pair edit_manager runs on a catalog save: path patterns, servers, slots, unlocks.
        CtfValidator(
            {'servers': unit.get('servers') or [], 'ctf': ctf.model_dump()}, image_loader=self._get_image_record,
        ).load()
        seed = self.events.env.ctf_flag_seed
        if not seed:
            raise ServiceUnavailable(message=NOT_PROVISIONED_MESSAGE)

        updated = ModelValidator(CtfEventModel, log_location=self.log_name).load({**event.model_dump(), 'spec': ctf.model_dump()})
        old_ids = {
            d.get('digest') for d in self.db.query(
                collection_name=DbCollections.CTF_DIGEST, filters=[('ctf_id', DbOperators.EQUAL, ctf_id)],
            ) or []
        }
        boards, new_digests = [], []
        for board in self.events._boards(event):
            new_board, digests = self.events._new_board(
                updated, {'id': board.workout_id, 'team_name': board.team_name}, seed
            )
            new_board.members = board.members
            boards.append(new_board)
            new_digests.extend(digests)
        new_ids = {d.digest for d in new_digests}

        # 1. Digests that did not exist yet: the old boards never point at them, so a failure here
        #    leaves the event as it was (and _commit removes the partial writes).
        added = [(DbCollections.CTF_DIGEST, d.digest, d.model_dump()) for d in new_digests if d.digest not in old_ids]
        self.events._commit(ctf_id, added)
        # 2. The spec and every board together, in one transaction that re-checks DRAFT, so submissions
        #    and Arm see either the old flags or the new ones, never a mix.
        try:
            self.db.transaction(lambda transaction: self._replace_spec(transaction, ctf_id, updated, boards))
        except Exception:
            self.events._rollback(ctf_id, added)
            raise
        # 3. Only now nothing refers to the old digests.
        stale = sorted(old_ids - new_ids - {None})
        for start in range(0, len(stale), CtfEvent.MAX_WRITES_PER_COMMIT):
            self.db.batch_write([
                self.events._operation(DbCollections.CTF_DIGEST, digest, DbOperationTypes.DELETE)
                for digest in stale[start:start + CtfEvent.MAX_WRITES_PER_COMMIT]
            ])
        self.db.update(collection_name=DbCollections.UNIT, doc_id=event.unit_id, data={'ctf': ctf.model_dump()})
        self.logger.info(f"{self.class_name}:{ctf_id} - Updated CTF flags", flags=len(ctf.flags))
        return updated

    def servers(self, ctf_id: str, action: str, user: AgogeUser) -> int:
        """Publish one workout BUILD, START or STOP per team; return the message count. These are the
        same messages the unit page sends, so the Cloud Function needs nothing new."""
        states, handler, pubsub_action, unbuilt_only = self.SERVER_ACTIONS[action]
        event = self._event_in(ctf_id, user, states, f"{action} the servers of")
        if not event.board_ids:
            raise BadRequest(message="Add at least one team first")
        workouts = self._workouts(event.board_ids)
        attrs = PubSub.EventAttributes
        messages = [{
            attrs.HANDLER: str(handler.value),
            attrs.ACTION: str(pubsub_action.value),
            attrs.COURSE_OBJECT: str(PubSub.CourseObjects.WORKOUT.value),
            attrs.BUILD_ID: workout_id,
        } for workout_id in event.board_ids
            if workout_id in workouts and self._targets(workouts[workout_id].get('state'), unbuilt_only)]
        if messages:
            self.hosts._publish(ctf_id, messages)
        self.logger.info(f"{self.class_name}:{ctf_id} - Published server {action}", messages=len(messages))
        return len(messages)

    def _targets(self, state, unbuilt_only: bool) -> bool:
        """BUILD goes only to unbuilt workouts; START and STOP only to workouts that have servers."""
        if unbuilt_only:
            return state in self.UNBUILT_STATES
        return state not in self.UNBUILT_STATES and state not in self.GONE_STATES

    def _event_in(self, ctf_id: str, user: AgogeUser, states: set, verb: str) -> CtfEventModel:
        event = self.events.get(ctf_id, user)
        if event.state not in {state.value for state in states}:
            raise Conflict(message=f"Cannot {verb} a CTF event that is {CtfEvent._state_name(event.state)}")
        return event

    def _unit(self, event: CtfEventModel) -> UnitModel:
        doc = self.db.get(collection_name=DbCollections.UNIT, doc_id=event.unit_id)
        if not doc:
            raise NotFound(message="The CTF event's lab no longer exists")
        return ModelValidator(UnitModel, log_location=self.log_name).load(doc)

    def _is_unbuilt(self, workout_id: str) -> bool:
        workout = self.db.get(collection_name=DbCollections.WORKOUT, doc_id=workout_id)
        return not workout or workout.get('state') in self.UNBUILT_STATES

    def _change_board_ids(self, transaction, ctf_id: str, add: Optional[str] = None, remove: Optional[str] = None) -> int:
        """Add or remove one board id, re-checking DRAFT inside the transaction so a concurrent Arm
        never starts with a board list that changes under it. Returns the new number of boards."""
        doc_ref = self.db.db.collection(DbCollections.CTF.value).document(ctf_id)
        snapshot = doc_ref.get(transaction=transaction)
        if not snapshot.exists:
            raise NotFound(message="CTF event not found")
        stored = snapshot.to_dict()
        if stored.get('state') != CtfStates.DRAFT.value:
            raise Conflict(message=f"Cannot change the teams of a CTF event that is {CtfEvent._state_name(stored.get('state'))}")
        board_ids = [workout_id for workout_id in stored.get('board_ids', []) if workout_id != remove]
        if add and add not in board_ids:
            board_ids.append(add)
        transaction.update(doc_ref, {'board_ids': board_ids})
        return len(board_ids)

    def _replace_spec(self, transaction, ctf_id: str, updated: CtfEventModel, boards: list) -> None:
        """Write the new spec and rewritten boards in one transaction. Boards are capped at
        ctf_max_boards (default 100), well inside a transaction's write limit."""
        doc_ref = self.db.db.collection(DbCollections.CTF.value).document(ctf_id)
        snapshot = doc_ref.get(transaction=transaction)
        if not snapshot.exists:
            raise NotFound(message="CTF event not found")
        state = snapshot.to_dict().get('state')
        if state != CtfStates.DRAFT.value:
            raise Conflict(message=f"Cannot edit the flags of a CTF event that is {CtfEvent._state_name(state)}")
        board_ref = self.db.db.collection(DbCollections.CTF_BOARD.value)
        for board in boards:
            transaction.set(board_ref.document(board.id), board.model_dump())
        transaction.update(doc_ref, {'spec': updated.model_dump(mode='json')['spec']})

    def _set_unit_count(self, unit_id: str, count: int) -> None:
        self.db.update(collection_name=DbCollections.UNIT, doc_id=unit_id, data={'workspace_settings': {'count': count}})

    def _require_free_members(self, members: List[str], exclude_board_id: Optional[str] = None) -> None:
        """An email may be on at most one active board, so the join page can resolve it to one workout."""
        for start in range(0, len(members), CtfEvent.MAX_IN_VALUES):
            # One array filter only: combining it with an equality filter can need a composite index.
            boards = self.db.query(
                collection_name=DbCollections.CTF_BOARD,
                filters=[('members', DbOperators.ARRAY_CONTAINS_ANY, members[start:start + CtfEvent.MAX_IN_VALUES])],
            ) or []
            for board in boards:
                if board.get('id') == exclude_board_id or not board.get('active', True):
                    continue
                taken = sorted(set(members) & set(board.get('members') or []))
                if taken:
                    raise Conflict(message=f"{taken[0]} is already on team {board.get('team_name')} in an active CTF event")

    def _workouts(self, workout_ids: List[str]) -> dict:
        """{workout_id: workout document}, read with `id in` queries of at most MAX_IN_VALUES."""
        found = {}
        for start in range(0, len(workout_ids), CtfEvent.MAX_IN_VALUES):
            chunk = workout_ids[start:start + CtfEvent.MAX_IN_VALUES]
            docs = self.db.query(collection_name=DbCollections.WORKOUT, filters=[('id', DbOperators.IN, chunk)]) or []
            found.update({doc['id']: doc for doc in docs if doc.get('id') in chunk})
        return found

    @staticmethod
    def _team_row(workout_id: str, team_name: str, members: List[str], arm_status: str, workout: Optional[dict]) -> CtfTeamRow:
        state = workout.get('state') if workout else None
        return CtfTeamRow(
            workout_id=workout_id,
            team_name=team_name,
            members=members,
            workout_state=state,
            workout_state_name=(
                WorkoutStates(state).name if state in WorkoutStates._value2member_map_
                else (None if state is None else str(state))
            ),
            arm_status=arm_status,
        )

    @staticmethod
    def _is_solo(doc: dict) -> bool:
        return doc.get('unit_type', BuildConstants.UnitType.SOLO.value) == BuildConstants.UnitType.SOLO.value
