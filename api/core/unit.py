from datetime import datetime, timedelta
from enum import Enum
import re

from fastapi import Request
from pydantic import ValidationError
from typing import List, Union

from common.constants.build_constants import BuildConstants
from common.constants.database import (
    DbCollections,
    DATABASE_NAME,
    DatabaseTypes,
    DbOperationTypes,
    DbOperators,
)
from common.constants.pub_sub import PubSub
from common.constants.states import WorkoutStates, UnitStates
from common.document_database.database_filter import DatabaseFilter
from common.document_database.factory import DocumentDatabaseFactory
from common.exceptions import BadRequest, NotFound, Unauthorized, AgogeValidationError
from common.models.agoge import UnitModel, WorkoutModel, WorkspaceSettingsModel
from common.models.model_validators.model_validator import ModelValidator
from common.models.users import AgogeUser
from common.utilities.gcp.bucket_manager import BucketManager
from common.utilities.gcp.cloud_env import CloudEnv
from common.utilities.gcp.cloud_logger import Logger, LoggerNames
from common.utilities.gcp.pubsub_manager import PubSubManager
from common.utilities.id_generator import IdGenerator
from common.services.wireguard_endpoint import WireGuardEndpointRegistry
from common.utilities.timestamps import Timestamps

from utilities.lms.lms_canvas import LMSSpecCanvas
from utilities.lms.lms_google_classroom import LMSSpecGoogleClassroom, LMSGoogleClassroom


class Unit:
    def __init__(
        self,
        env_dict: dict,
        debug: bool = False
    ) -> None:
        self.debug = debug
        self.class_name = self.__class__.__name__
        self.log_name = LoggerNames.API
        self.collection = DbCollections.UNIT
        self.pubsub_actions = PubSub.Actions
        self.handler = PubSub.Handlers
        self.env = CloudEnv(log_name=self.log_name, env_dict=env_dict)
        self.env_dict = self.env.get_env()
        self.db = DocumentDatabaseFactory.create_db_object(
            db_type=DatabaseTypes.firestore,
            database_name=DATABASE_NAME,
            log_name=self.log_name
        )
        self.pubsub_mgr = PubSubManager(
            topic=PubSub.Topics.AGOGE,
            log_name=self.log_name,
            env_dict=self.env_dict
        )
        self.bm = BucketManager(log_name=self.log_name, env_dict=self.env_dict)
        self.logger = Logger(log_name=self.log_name, class_name=self.class_name)
        self.unit_model_validator = ModelValidator(model=UnitModel)
        self.workout_model_validator = ModelValidator(model=WorkoutModel)

    def get(
        self,
        build_id: str,
        as_dict: bool = False
    ) -> Union[UnitModel, dict]:
        if unit := self.db.get(collection_name=self.collection, doc_id=build_id):
            unit = self._hydrate_wireguard_endpoint(unit)
            if as_dict:
                return unit
            else:
                try:
                    return self.unit_model_validator.load(unit)
                except (AgogeValidationError, ValidationError) as e:
                    raise BadRequest(message=f"Unit.get failed with validation errors: {e}")
        raise NotFound(message="No Unit found for given ID")

    def _hydrate_wireguard_endpoint(self, unit: dict) -> dict:
        """Overlay current registry state onto the immutable allocation snapshot."""
        endpoint = unit.get("wireguard_endpoint")
        endpoint_id = endpoint.get("id") if isinstance(endpoint, dict) else None
        if not endpoint_id:
            return unit

        try:
            registration = WireGuardEndpointRegistry(
                env_dict=self.env_dict,
                db=self.db,
                log_name=self.log_name,
            ).get(endpoint_id)
            if registration.unit_id != unit.get("id"):
                self.logger.error(
                    f"WireGuard endpoint {endpoint_id} is linked to the wrong Unit",
                    unit_id=unit.get("id"),
                )
                hydrated = dict(unit)
                hydrated["wireguard_endpoint"] = None
                return hydrated
            hydrated = dict(unit)
            hydrated["wireguard_endpoint"] = registration.public_endpoint().model_dump()
            return hydrated
        except (NotFound, ValidationError) as error:
            self.logger.warning(
                f"Could not hydrate WireGuard endpoint {endpoint_id}: {error}",
                unit_id=unit.get("id"),
            )
            # Never fall back to the immutable allocation snapshot. Once its
            # tombstone is purged, the same five-digit ID may legitimately
            # belong to a different Unit.
            hydrated = dict(unit)
            hydrated["wireguard_endpoint"] = None
            return hydrated

    def get_all_data(
        self,
        build_id: str,
        requester: AgogeUser,
    ) -> dict:
        unit = self.get(build_id)
        self._require_instructor_access(unit, requester)
        try:
            workouts = self.list_workouts(build_id)
        except NotFound:
            workouts = []
        roster = self.get_unit_roster_size(children=workouts)
        return {'unit': unit, 'workouts': workouts, 'roster': roster}

    @staticmethod
    def _require_instructor_access(unit: UnitModel | dict, requester: AgogeUser) -> None:
        """Limit instructor-only Unit details to assigned instructors and admins."""
        if requester.is_admin:
            return
        instructor_ids = (
            unit.get('instructor_id', [])
            if isinstance(unit, dict)
            else unit.instructor_id
        )
        if isinstance(instructor_ids, str):
            instructor_ids = [instructor_ids]
        if requester.email not in (instructor_ids or []):
            raise Unauthorized(
                message="Requesting user is not authorized to view this Unit"
            )

    def list(
        self,
        requester: AgogeUser,
        active: bool,
        expired: bool,
        days: int,
        instructor: bool
    ) -> tuple[List[UnitModel], List[UnitModel]] | List[UnitModel]:
        if instructor and active and expired:
            # Default return object if no query parameters are used
            if units := self._get_instructor_units(requester.email):
                try:
                    active = self.unit_model_validator.load(units.get('active'))
                    expired = self.unit_model_validator.load(units.get('expired'))
                    return active, expired
                except (AgogeValidationError, ValidationError):
                    raise BadRequest(message="Validation errors occurred when processing data")
            raise NotFound
        elif requester.is_admin:
            if instructor:
                unit_query = self._get_instructor_units(instructor_id=requester.email, aggregated=True)
            else:
                unit_query = self.db.query(collection_name=self.collection)

            ds_filter = DatabaseFilter(unit_query)
            ops = ds_filter.Operators

            if active and not expired:
                current_ts = Timestamps.get_current_timestamp_utc()
                ds_filter.add('workspace_settings.expires', ops.GREATER_THAN, current_ts)
            if expired and not active:
                current_ts = Timestamps.get_current_timestamp_utc()
                ds_filter.add('workspace_settings.expires', ops.LESS_THAN, current_ts)
            if days:
                days_back = Timestamps.get_historic_utc_timestamp(days)
                ds_filter.add('creation_timestamp', ops.GREATER_THAN, days_back)

            if not ds_filter.filters:
                self.logger.error(
                    f"{self.class_name} - Invalid or missing filter items for Unit list",
                    user=requester.uid
                )
                raise BadRequest("Invalid or missing filter items")

            filtered_units = ds_filter.filter()
            if filtered_units:
                try:
                    return self.unit_model_validator.load(filtered_units)
                except (AgogeValidationError, ValidationError) as e:
                    raise BadRequest(message=str(e))
            raise NotFound
        else:
            raise Unauthorized(message='Requesting user is not authorized to make this call')

    def build(
        self,
        requester: AgogeUser,
        data: dict
    ) -> str:
        """
        Processes build request for a single Unit

        Args:
            requester (AgogeUser): user requesting build
            data (dict): Form data submitted by user

        Returns: build_id of created Unit
        Raise: NotFound or BadRequest
        """
        # Parse Form Data
        expire_datetime = data.get('expires')
        registration_required = data.get('registration_required', False)
        build_type = data.get('build_file')
        build_count = data.get('build_count', 1)
        test_unit = data.get('test', False)

        if expire_datetime and build_type:
            self.logger.info(
                f"User initiated build request for spec {build_type}",
                spec=build_type,
                user=requester.uid
            )
            # Sends build request for unit; Records are created, but no resources are used
            # until requested by student
            build_spec = self.db.get(collection_name=DbCollections.CATALOG, doc_id=build_type)
            if not build_spec:
                raise NotFound(f'Specification not found. Invalid build type {build_type}')

            # Clean out any unneeded keys
            for key in ['discriminator', 'id', 'creation_timestamp']:
                build_spec.pop(key, None)

            # Generate Unit model from requested Catalog model
            unit_id = IdGenerator.build_id()
            build_count = min(build_count, 100) if build_count != 0 else 1
            workspace_settings = WorkspaceSettingsModel(
                count=build_count,
                expires=int(Timestamps.from_utc_str(expire_datetime)),
                student_emails=[],
                registration_required=registration_required
            )

            unit = UnitModel(
                **build_spec,
                id=unit_id,
                workspace_settings=workspace_settings,
                join_code=IdGenerator.join_code(),
                state=UnitStates.START.value,
                test=test_unit,
                creation_timestamp=int(Timestamps.get_current_timestamp_utc())
            )
            unit.build_type = build_spec.get('build_type', BuildConstants.BuildType.UNIT.value)
            unit.instructor_id = [requester.email]
            endpoint_registry = self._allocate_wireguard_endpoint(unit)

            lms_integration = data.get('lms_integration', None)
            try:
                if lms_integration:
                    build_spec = self._lms_integrate(requester=requester, build_spec=unit, data=data)
                    self.commit(build_spec)
                else:
                    # Solo Units are provisioned lazily with each Workout. A
                    # Community Unit must create its shared VPC and servers now.
                    self.commit(
                        unit,
                        publish=unit.unit_type == BuildConstants.UnitType.COMMUNITY,
                    )
                return unit_id
            except (AgogeValidationError, ValidationError) as e:
                self._cancel_uncommitted_wireguard_endpoint(unit, endpoint_registry)
                self.logger.error(
                    message=str(e),
                    specification_id=unit.id,

                )
                unit_name = unit.summary.name if unit.summary else unit.id
                error_message = (f'Validation errors occurred processing selected specification: '
                                 f'{unit_name}')
                raise BadRequest(error_message)
            except Exception:
                # If commit completed but Pub/Sub failed, the Unit lookup keeps
                # the endpoint. Otherwise remove the orphaned reservation.
                self._cancel_uncommitted_wireguard_endpoint(unit, endpoint_registry)
                raise
        else:
            raise BadRequest('Missing or invalid data')

    def build_all(
        self,
        build_id: str
    ) -> None:
        """
        Processes requests to build all Workouts in a Unit.

        Args:
            build_id (str): ID of unit to initiate build requests for

        Returns: None
        Raises: NotFound
        """
        workouts = self.list_workouts(build_id)
        for workout in workouts:
            workout_id = workout.id
            if workout.state == WorkoutStates.NOT_BUILT.value:
                student_name = workout.student_email
                self.logger.info(
                    message=f"Sending job to build lab for {student_name} with workout ID {workout_id}",
                    workout_id=workout_id,
                    student=student_name
                )
                self.pubsub_mgr.msg(
                    handler=str(PubSub.Handlers.BUILD.value),
                    action=str(self.pubsub_actions.BUILD.value),
                    build_id=workout_id,
                    course_object=str(PubSub.CourseObjects.WORKOUT.value)
                )

    def delete(
        self,
        requester: AgogeUser,
        build_id: str
    ) -> None:
        is_admin = requester.is_admin
        if unit := self.db.get(collection_name=self.collection, doc_id=build_id):
            if is_admin or requester.email in unit.get('instructor_id'):
                self.pubsub_mgr.msg(
                    handler=str(self.handler.CONTROL.value),
                    build_id=str(build_id),
                    action=str(self.pubsub_actions.DELETE.value),
                    course_object=str(PubSub.CourseObjects.UNIT.value)
                )
                return
            raise Unauthorized(message="Requesting user is not authorized to make this request")
        raise NotFound(message=f"Requested Unit was not found")

    async def process_action(
        self,
        build_id: str,
        request: Request
    ) -> None:
        """
        Processes PubSub actions on target Unit
        Args:
            request (Request):
            build_id (str): ID of Unit to interact with

        Returns:
        Raises: BadRequest
        """
        json_data = await request.json()
        action = json_data.get('action', 0)
        workout_ids = json_data.get("workout_ids")
        if int(action) == PubSub.Actions.RESET_EXPIRATION.value:
            days = json_data.get('days', 2)
            self._reset_expiration(build_id=build_id, days=days)
        elif int(action) in [
            PubSub.Actions.START.value,
            PubSub.Actions.STOP.value,
            PubSub.Actions.BUILD.value
        ]:
            if int(action) == PubSub.Actions.BUILD.value:
                handler = self.handler.BUILD.value
            else:
                handler = self.handler.CONTROL.value

            msg_args = {
                PubSub.EventAttributes.HANDLER: handler,
                PubSub.EventAttributes.ACTION: str(action),
                PubSub.EventAttributes.COURSE_OBJECT: str(PubSub.CourseObjects.WORKOUT.value)
            }
            if workout_ids:
                unit_workouts = self.list_workouts(build_id)
                self.logger.info(
                    f'sending {PubSub.Actions(int(action)).name} request for unit workouts list',
                    action=action,
                    unit_id=build_id,
                    workout_ids=str(workout_ids)
                )

                workouts_map = {workout.id: workout for workout in unit_workouts}
                for w_id in workout_ids:
                    # Only process action if ID is a valid unit workout ID and is a valid state
                    if workout := workouts_map.get(w_id):
                        if (int(action) == PubSub.Actions.BUILD.value
                                and workout.state != WorkoutStates.NOT_BUILT.value):
                            self.logger.warning(
                                f'Ignoring BUILD request for workout, {w_id}. Workout is already built!',
                                workout_id=w_id,
                                workout_state=str(workout.state),
                                unit_id=build_id
                            )
                            continue
                        msg_args[PubSub.EventAttributes.BUILD_ID] = w_id

                        self.pubsub_mgr.msg(**msg_args)
            else:
                # TODO: Consider removing this branch as a valid option
                self.logger.info(
                    f'sending {PubSub.Actions(int(action)).name} request for unit with id {build_id}',
                    action=action,
                    unit_id=build_id
                )
                msg_args[PubSub.EventAttributes.COURSE_OBJECT] = str(PubSub.CourseObjects.UNIT.value)
                msg_args[PubSub.EventAttributes.BUILD_ID] = build_id
                self.pubsub_mgr.msg(**msg_args)
        else:
            raise BadRequest(f"Invalid or unsupported action ({action}) for Unit")

    async def update(
        self,
        build_id: str,
        request: Request,
        requester: AgogeUser
    ) -> None:
        """
        Args:
            requester (AgogeUser): User initiating request
            build_id (str): ID of unit to update
            request (Request): Request

        Raises:
            BadRequest: Missing or Invalid Data
            NotFound: Invalid or missing build_id
            Unauthorized: User is not an admin or instructor already assigned to unit
        """
        json_data = await request.json()
        if not json_data:
            raise BadRequest(message="Update request made but no data was found")
        unit = self.get(build_id, as_dict=True)

        is_instructor = requester.is_instructor and requester.email in unit.get('instructor_id')
        if not requester.is_admin and not is_instructor:
            raise Unauthorized(message=f"User is not authorized to make this request. {requester.uid}")

        update = False
        for key, value in json_data.items():
            if key in unit:
                update = True
                if key == 'instructor_id':
                    instructors = value.split(',')
                    unit[key] = [i.lower() for i in instructors]
                else:
                    unit[key] = value

        if update:
            self._validate(unit, collection=self.collection, action=DbOperationTypes.UPDATE)
            self.db.update(collection_name=self.collection, doc_id=build_id, data=unit)
            return

        raise BadRequest(message="Could not process update. Invalid data given")

    def _reset_expiration(
        self,
        build_id: str,
        days: int
    ) -> None:
        unit = self.db.get(collection_name=self.collection, doc_id=build_id)
        if unit:

            ts = unit['workspace_settings']['expires']
            expires_ts = self._extend_by_days(ts, days)
            self.logger.info(
                f'resetting expiration for unit with id {build_id} to {days} days from now',
                unit_id=build_id,
                days=days,
                old_expiration=ts,
                new_expiration=expires_ts
            )

            # Update Unit
            unit['workspace_settings']['expires'] = expires_ts
            self._validate(unit, collection=self.collection, action=DbOperationTypes.UPDATE)
            self.db.update(collection_name=self.collection, doc_id=build_id, data=unit)

            # Update any Unit Workouts
            workouts = self._get_unit_workouts(build_id)
            if workouts:
                operations = []
                for workout in workouts:
                    workout['expires'] = expires_ts
                    self._validate(workout, collection=DbCollections.WORKOUT, action=DbOperationTypes.UPDATE)
                    op = self.db.operation(
                        collection_name=DbCollections.WORKOUT,
                        doc_id=workout['id'],
                        operation_type=DbOperationTypes.UPDATE,
                        data=workout
                    )
                    operations.append(op)
                self.db.batch_write(operations)

            return
        raise NotFound(f'Unit with build_id, {build_id}, does not exist')

    def _get_instructor_units(
        self,
        instructor_id: str,
        aggregated: bool = False
    ) -> Union[dict, List]:
        filters = [('instructor_id', DbOperators.ARRAY_CONTAINS, instructor_id)]
        units = self.db.query(
            collection_name=self.collection,
            filters=filters
        )

        if units and not aggregated:
            instructor_units = {'active': [], 'expired': []}
            current_ts = Timestamps.get_current_timestamp_utc()
            for unit in units:
                if int(unit['workspace_settings']['expires']) > current_ts:
                    instructor_units['active'].append(unit)
                else:
                    instructor_units['expired'].append(unit)
            return instructor_units
        return units

    def get_states(
        self,
        build_id: str,
    ) -> tuple[bool, list]:
        """
        Retrieves states for all workouts in a unit sorted by workout id
        Args:
            build_id (str): ID of Unit

        Returns: exists (bool), states (list)

        """
        workouts = self._get_unit_workouts(build_id)
        if workouts:
            states = [
                {'build_id': i['id'], 'state': WorkoutStates(i['state']).name.lower()}
                for i in workouts
            ]
        else:
            states = []
        return bool(states), states

    def get_unit_roster_size(
        self,
        build_id: str = None,
        children: List = None
    ) -> int:
        if isinstance(children, list):
            return len(children)
        if build_id:
            workouts = self._get_unit_workouts(build_id)

            return len(workouts) if workouts else 0
        return 0

    def list_workouts(
        self,
        build_id: str
    ) -> List[WorkoutModel]:
        if workouts := self._get_unit_workouts(build_id):
            try:
                return self.workout_model_validator.load(workouts)
            except (AgogeValidationError, ValidationError) as e:
                raise BadRequest(message=f"list_workout failed with validation errors {e}")
        raise NotFound(message=f"No Workouts found for Unit ID {build_id}")

    def _get_unit_workouts(self, unit_id: str) -> List:
        filters = [('parent_id', DbOperators.EQUAL, unit_id)]
        workouts = self.db.query(collection_name=DbCollections.WORKOUT, filters=filters)
        return workouts or []

    def _validate(
        self,
        build: dict,
        collection: Enum,
        action: Enum
    ) -> None:
        try:
            if collection == DbCollections.UNIT:
                UnitModel(**build)
            elif collection == DbCollections.WORKOUT:
                WorkoutModel(**build)
            return
        except ValidationError as e:
            msg = f"{collection.name} {action.value} failed with validation errors: {e}"
            self.logger.error(msg, action=action.value)
            raise BadRequest(message=msg)

    def _lms_integrate(
        self,
        requester: AgogeUser,
        build_spec: UnitModel,
        data: dict
    ) -> UnitModel:
        """
        Takes input build specification and decorates it based on select LMS
        Args:
            build_spec (dict): Build specification to process
            data (dict): Form data to process

        Returns: decorated build_spec
        Raises: BadRequest
        """
        lms_course_code = data.get('lms_course_code', None)
        lms_allowed_attempts = data.get('lms_allowed_attempts', None)
        lms_type = data.get('lms_type', BuildConstants.LMS.CANVAS.value)
        lms_due_at_ts = build_spec.workspace_settings.expires

        if lms_type == BuildConstants.LMS.CANVAS.value:
            lms_spec_decorator = LMSSpecCanvas(
                instructor=requester,
                build_spec=build_spec.model_dump(),
                course_code=lms_course_code,
                due_at=lms_due_at_ts,
                allowed_attempts=lms_allowed_attempts,
                lms_type=lms_type,
                env_dict=self.env_dict
            )
        elif lms_type == BuildConstants.LMS.GOOGLE_CLASSROOM.value:
            additional_instructors = []
            if lms_course_code:
                classroom = LMSGoogleClassroom(env_dict=self.env_dict)
                additional_instructors = classroom.get_teachers(lms_course_code)

            lms_spec_decorator = LMSSpecGoogleClassroom(
                instructor=requester,
                build_spec=build_spec.model_dump(),
                course_code=lms_course_code,
                due_at=lms_due_at_ts,
                allowed_attempts=lms_allowed_attempts,
                lms_type=lms_type,
                additional_instructors=additional_instructors,
                env_dict=self.env_dict
            )
        else:
            raise BadRequest(f'Invalid or unsupported LMS type {lms_type}')

        decorated_unit_model = lms_spec_decorator.decorate()
        return decorated_unit_model

    def commit(
        self,
        build_spec: UnitModel,
        publish: bool = True
    ) -> None:
        """
        Save input UnitModel to DB and sends PubSub request for
        build task delegation.
        """
        self.db.update(
            collection_name=self.collection,
            doc_id=build_spec.id,
            data=build_spec.model_dump()
        )
        if not self.debug and publish:
            self.pubsub_mgr.msg(
                handler=str(self.handler.BUILD.value),
                action=str(PubSub.Actions.BUILD.value),
                course_object=str(PubSub.CourseObjects.UNIT.value),
                build_id=(str(build_spec.id))
            )

    def _allocate_wireguard_endpoint(
        self,
        unit: UnitModel,
    ) -> WireGuardEndpointRegistry | None:
        """Decorate a community Unit and its one gateway with runtime endpoint data."""
        if unit.unit_type != BuildConstants.UnitType.COMMUNITY:
            return None

        gateways = [server for server in unit.servers or [] if server.wireguard_gateway]
        if not gateways:
            return None
        if len(gateways) != 1:
            raise BadRequest("A community Unit can have only one WireGuard gateway")

        gateway = gateways[0]
        public_nic = next(
            (nic for nic in gateway.nics or [] if nic.external_nat),
            None,
        )
        if public_nic is None:
            raise BadRequest("The WireGuard gateway requires an external NAT interface")

        # A logical name is portable in Catalog specifications. Compute managers
        # prefix it with the Unit ID to obtain the actual reserved address name.
        if not public_nic.external_ip_name:
            public_nic.external_ip_name = "wireguard-ip"
        external_ip_name = public_nic.external_ip_name
        if not external_ip_name.startswith(f"{unit.id}-"):
            external_ip_name = f"{unit.id}-{external_ip_name}"
        if not re.fullmatch(
            r"[a-z](?:[-a-z0-9]{0,61}[a-z0-9])?",
            external_ip_name,
        ):
            raise BadRequest(
                "The final WireGuard external address name must be a 1-63 character "
                "lowercase Google Compute Engine resource name"
            )

        server_name = f"{unit.id}-{gateway.name}"
        registry = WireGuardEndpointRegistry(
            env_dict=self.env_dict,
            db=self.db,
            log_name=self.log_name,
        )
        endpoint = registry.allocate(
            unit_id=unit.id,
            server_name=server_name,
            external_ip_name=external_ip_name,
            expires=unit.workspace_settings.expires if unit.workspace_settings else None,
        )
        gateway.wireguard_endpoint_id = endpoint.id
        unit.wireguard_endpoint = endpoint
        return registry

    def _cancel_uncommitted_wireguard_endpoint(
        self,
        unit: UnitModel,
        registry: WireGuardEndpointRegistry | None,
    ) -> None:
        """Compensate for validation failures before a Unit document is saved."""
        endpoint = unit.wireguard_endpoint
        if not registry or not endpoint:
            return
        try:
            if self.db.get(collection_name=self.collection, doc_id=unit.id):
                return
            registry.cancel_reservation(endpoint.id, unit_id=unit.id)
        except Exception as error:
            self.logger.warning(
                f"Could not cancel WireGuard endpoint {endpoint.id}: {error}",
                unit_id=unit.id,
            )

    @staticmethod
    def _extend_by_days(
        ts: float,
        days: int
    ) -> int:
        seconds = timedelta(seconds=86400 * int(days))
        return int((datetime.fromtimestamp(ts) + seconds).timestamp())
