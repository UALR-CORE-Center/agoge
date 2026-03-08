import json
import datetime
from enum import Enum
from json import JSONDecodeError
from fastapi import Request
from pydantic import ValidationError
from typing import List, Union
from collections import namedtuple

from common.constants.build_constants import BuildConstants
from common.constants.database import (
    DATABASE_NAME,
    DatabaseTypes,
    DbCollections,
    DbOperationTypes,
    DbOperators
)
from common.constants.pub_sub import PubSub
from common.constants.states import WorkoutStates
from common.document_database.factory import DocumentDatabaseFactory
from common.exceptions import BadRequest, NotFound, Forbidden, Unauthorized
from common.models.agoge import WorkoutModel
from common.models.model_validators.model_validator import ModelValidator
from common.models.response import ServerResponse
from common.models.users import AgogeUser, AnonymousAppUser
from common.utilities.gcp.cloud_env import CloudEnv
from common.utilities.gcp.cloud_logger import Logger, LoggerNames
from common.utilities.gcp.pubsub_manager import PubSubManager
from common.utilities.id_generator import IdGenerator
from common.utilities.timestamps import Timestamps

from utilities.lms.lms_canvas import LMSCanvas


class Workout:
    def __init__(
        self,
        env_dict: dict = None
    ) -> None:
        self.class_name = self.__class__.__name__
        self.log_name = LoggerNames.API
        self.collection = DbCollections.WORKOUT
        self.env = CloudEnv(log_name=self.log_name, env_dict=env_dict)
        self.env_dict = self.env.get_env()
        self.db = DocumentDatabaseFactory.create_db_object(
            db_type=DatabaseTypes.firestore,
            database_name=DATABASE_NAME,
            log_name=self.log_name
        )
        self.pubsub_manager = PubSubManager(
            topic=PubSub.Topics.AGOGE,
            log_name=self.log_name,
            env_dict=self.env.get_env()
        )
        self.handler = PubSub.Handlers
        self.pubsub_keys = PubSub.EventAttributes
        self.workout: dict = {}
        self.logger = Logger(self.log_name, class_name=self.class_name)
        self.workout_validator = ModelValidator(model=WorkoutModel)

    def get(
        self,
        build_id: str,
        as_dict: bool = False
    ) -> Union[WorkoutModel, dict]:
        if workout := self.db.get(collection_name=self.collection, doc_id=build_id):
            if as_dict:
                return workout
            else:
                cleaned = self._clean_object(workout)
                try:
                    return self.workout_validator.load(cleaned)
                except ValidationError:
                    raise BadRequest
        raise NotFound

    def get_all_data(
        self,
        build_id: str
    ) -> dict:
        workout = self.get(build_id)
        servers = self._get_servers(build_id)
        return {'workout': workout, 'servers': servers}

    def list(
        self,
        requester: AgogeUser | AnonymousAppUser,
        active: bool,
        days: int,
        student: bool
    ) -> List[WorkoutModel]:
        if requester.is_admin:
            workouts = []
            if not active and not days and not student:
                raise BadRequest(message="Workout list called but no filter given")

            if student:
                filters = [('student_email', DbOperators.EQUAL, requester.email)]
                workouts = self.db.query(collection_name=self.collection, filters=filters)
            elif active:
                current_t = Timestamps.get_current_timestamp_utc()
                query = self.db.query(collection_name=self.collection)
                for workout in query:
                    if (
                        int(workout.get('expires', 0)) > current_t
                        and workout.get('state') not in [WorkoutStates.DELETED.value]
                    ):
                        workouts.append(workout)
            elif days:
                days_ago = Timestamps.get_historic_utc_timestamp(days)
                query = self.db.query(collection_name=self.collection)
                for workout in query:
                    if int(workout.get('creation_timestamp')) > days_ago:
                        workouts.append(workout)

            if workouts:
                return self.workout_validator.load(workouts, halt_on_error=False)
            else:
                raise NotFound(message="No builds found for given filter")
        else:
            if requester.is_authorized:
                filters = [('student_email', DbOperators.EQUAL, requester.email)]
                if workouts := self.db.query(
                        collection_name=self.collection, filters=filters):
                    cleaned = self._clean_object(workouts)
                    return self.workout_validator.load(cleaned, halt_on_error=False)
                raise NotFound(message="No builds found for given filter")
            raise BadRequest(message="Workout list request called but no filter given")

    def get_state(
        self,
        build_id: str
    ) -> dict:
        if workout := self.db.get(collection_name=self.collection, doc_id=build_id):
            return {"build_id": build_id, "state": workout.get('state')}
        raise NotFound

    def build(
        self,
        data: dict
    ) -> tuple[str, bool]:
        email = data.get('input_email')
        join_code = data.get('join_code')
        accessibility_features = data.get('accessibility_features', False)
        debug_mode = data.get('debug', False)

        if join_code and email:
            email = "".join(email.split()).lower()
            join_code = "".join(join_code.split())
            filters = [('join_code', DbOperators.EQUAL, join_code)]
            unit_results = self.db.query(collection_name=DbCollections.UNIT, filters=filters)
            if not unit_results:
                raise NotFound(f"Invalid join code, {join_code}. No Unit found")
            else:
                unit = unit_results[0]

            workout_id, exists = self._find_existing_workout(unit, email, accessibility_features, debug_mode)
            if workout_id:
                return workout_id, exists
            else:
                self.logger.unit_id = unit['id']
                self.logger.error(f"Exceeded max allowed builds for unit with join code {join_code}",
                                  join_code=join_code, student=email)
                raise Forbidden(message=f"Already exceeded max allowed builds for "
                                        f"Unit lab with join_code, {join_code}.")
        else:
            raise BadRequest(message=f"Missing data for required fields, email and join_code. "
                                     f"Received {join_code}, {email}")

    def delete(
        self,
        requester: AgogeUser,
        build_id: str
    ) -> None:
        is_admin = requester.is_admin
        if self.db.get(collection_name=self.collection, doc_id=build_id):
            if is_admin:
                self.pubsub_manager.msg(
                    handler=str(self.handler.CONTROL.value),
                    build_id=str(build_id),
                    action=str(PubSub.Actions.DELETE.value),
                    course_object=str(PubSub.CourseObjects.WORKOUT.value)
                )
                return
            raise Unauthorized(message="Requesting user is not authorized to make this request")
        raise NotFound(message=f"Requested Workout was not found")

    async def process_action(
        self,
        build_id: str,
        request: Request,
    ) -> dict:
        valid_actions = [
            PubSub.Actions.START.value,
            PubSub.Actions.STOP.value,
            PubSub.Actions.NUKE.value,
            PubSub.Actions.EXTEND_RUNTIME.value,
            PubSub.Actions.BUILD.value,
            PubSub.Actions.DELETE.value
        ]
        json_data = await request.json()
        action = json_data.get('action')
        debug_mode = json_data.get('debug', False)

        # For logging
        log_args = {
            'action': action,
            'origin': request.client.host,
            'workout_id': build_id
        }

        # Validate and cast action
        if int(action) not in valid_actions:
            raise BadRequest(message=f"Invalid action given: {action}")
        action = int(action)

        workout = self.get(build_id, as_dict=True)
        if not workout:
            raise NotFound(message=f"Requested workout with id {build_id} not found")

        # Make sure the action is safe to do
        if not self._safe_to_perform_action(action, workout):
            raise BadRequest(f"Not safe to perform action: {action}")

        # Build a base message attributes dictionary
        message_attrs = {
            self.pubsub_keys.HANDLER: None,
            self.pubsub_keys.ACTION: str(action),
            self.pubsub_keys.BUILD_ID: str(build_id),
            self.pubsub_keys.COURSE_OBJECT: str(PubSub.CourseObjects.WORKOUT.value),
        }

        # Action-specific logic & logging
        if action in [PubSub.Actions.START.value, PubSub.Actions.EXTEND_RUNTIME.value]:
            # Compute duration
            duration_hours = 1
            if action == PubSub.Actions.START.value:
                duration_hours = json_data.get('duration', 2)
                try:
                    duration_hours = min(int(duration_hours), 10)
                except (TypeError, ValueError):
                    duration_hours = 2

            self.logger.info(
                f'received request to {PubSub.Actions(action).name} workout with id {build_id}',
                duration_hours=duration_hours,
                **log_args
            )
            # Fill message attributes
            message_attrs[self.pubsub_keys.HANDLER] = str(PubSub.Handlers.CONTROL.value)
            message_attrs[self.pubsub_keys.DURATION] = str(duration_hours)

        elif action in [
            PubSub.Actions.STOP.value,
            PubSub.Actions.NUKE.value,
            PubSub.Actions.DELETE.value
        ]:
            self.logger.info(
                f'received request to {PubSub.Actions(action).name} workout with id {build_id}',
                **log_args
            )
            message_attrs[self.pubsub_keys.HANDLER] = str(PubSub.Handlers.CONTROL.value)

        elif action == PubSub.Actions.BUILD.value:
            self.logger.info(
                f'received request to {PubSub.Actions.BUILD.name} workout with id {build_id}',
                **log_args
            )
            # For BUILD, we might need a different handler or extra attributes
            message_attrs[self.pubsub_keys.HANDLER] = str(PubSub.Handlers.BUILD.value)
            message_attrs[self.pubsub_keys.KEY_TYPE] = str(DbCollections.WORKOUT.value)

        # After building the message_attrs, call a single function that decides
        # whether to invoke directly or via Pub/Sub.
        self._send_or_debug(message_attrs, debug_mode)

        return {"build_id": build_id, "state": workout.get('state')}

    async def process_question_response(
        self,
        build_id: str,
        question_key: [str, int],
        request: Request
    ) -> dict | None:
        self.workout = self.get(build_id, as_dict=True)
        log_args = {
            'workout_id': build_id,
            'question_key': question_key,
            'origin': request.client.host
        }

        if self.workout and self.workout.get('lms_integration') is not None:
            unit = self.db.get(collection_name=DbCollections.UNIT, doc_id=self.workout['parent_id'])
            workout = self._submit_lms_question(unit, self.workout, str(question_key))
            self._validate(workout, DbOperationTypes.UPDATE)
            self.db.update(collection_name=self.collection, doc_id=build_id, data=workout)
        elif self.workout and self.workout.get('assessment') is not None:
            try:
                json_data = await request.json()
                check_auto = json_data.get('check_auto', False)
                response = json_data.get('response', None)
                correct, update = self._evaluate_question(question_key, check_auto, response)
                if correct and update:
                    self.db.update(collection_name=self.collection, doc_id=build_id, data=self.workout)
            except (JSONDecodeError, AttributeError):
                self.logger.warning(
                    f'{self.class_name}:{build_id} - '
                    f'Attempted to validate question {question_key} but request did '
                    f'not contain a valid JSON object. Ignoring ...',
                    **log_args
                )
            return self.workout['assessment']
        else:
            self.logger.error(
                f"{self.class_name}:{build_id} - Auto assessment error for workout. "
                f"Either the workout is invalid or the workout has no associated assessment",
                **log_args
            )
            raise NotFound(message="Either the workout is invalid or the workout has no associated assessment")

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
            Unauthorized: User is not an admin
        """
        if not requester.is_admin:
            raise Unauthorized(message="User is not authorized to make this request")

        json_data = await request.json()
        if not json_data:
            raise BadRequest(message="PATCH request made but no data was found")

        student_email = json_data.get('student_email')
        if not student_email:
            raise BadRequest(message="Unsupported item for PATCH request")

        workout = self.get(build_id, as_dict=True)
        workout['student_email'] = student_email.lower()
        self._validate(workout, DbOperationTypes.UPDATE)
        self.logger.info(f'update workout with id {build_id} from user with id {requester.uid}',
                         workout_id=build_id, user=requester.uid)
        self.db.update(collection_name=self.collection, doc_id=build_id, data=workout)

    def _find_existing_workout(
        self,
        unit: dict,
        student_email: str,
        accessibility_features: bool,
        debug_mode: bool = False
    ) -> tuple[str, bool] | tuple[None, None]:
        """
        Looks for an existing workout in the unit with the given student email address.
        If the workout has not been built, then build at this time
        Args:
            unit (Datastore): The datastore record of the unit
            student_email (str): email address to look for
            accessibility_features (bool): Enables VM accessibility features
            debug_mode (bool): Whether to call the functions directly. If false, the build command is sent to PubSub

        Returns: workout_id:str or None, Bool (True iff record doesn't need to be created)
        """
        filters = [('parent_id', DbOperators.EQUAL, unit['id'])]
        workout_list = self.db.query(collection_name=self.collection, filters=filters)
        for workout in workout_list:
            if workout.get('student_email', '').lower() == student_email:
                workout_id = workout['id']
                if workout.get('state', WorkoutStates.NOT_BUILT.value) == WorkoutStates.NOT_BUILT.value:
                    message_attrs = {
                        self.pubsub_keys.HANDLER: str(PubSub.Handlers.BUILD.value),
                        self.pubsub_keys.ACTION: str(PubSub.Actions.BUILD.value),
                        self.pubsub_keys.COURSE_OBJECT: str(PubSub.CourseObjects.WORKOUT.value),
                        self.pubsub_keys.KEY_TYPE: str(DbCollections.WORKOUT.value),
                        self.pubsub_keys.BUILD_ID: str(workout_id)
                    }
                    self._send_or_debug(message_attrs, debug_mode=debug_mode)
                return workout_id, True

        # No workout found. Determine if a new one should be built. If not, return None.
        max_builds = min(int(self.env.max_workspaces), int(unit['workspace_settings'].get('count', 10000)))
        lms_build = bool(unit.get("lms_integration"))
        if len(workout_list) < max_builds and not lms_build:
            claimed_by = json.dumps({
                'student_email': student_email.lower(),
                'accessibility_features': accessibility_features
            })
            workout_id = IdGenerator.build_id()
            message_attrs = {
                self.pubsub_keys.HANDLER: str(PubSub.Handlers.BUILD.value),
                self.pubsub_keys.ACTION: str(PubSub.Actions.BUILD.value),
                self.pubsub_keys.COURSE_OBJECT: str(PubSub.CourseObjects.UNIT.value),
                self.pubsub_keys.BUILD_ID: str(unit['id']),
                self.pubsub_keys.CHILD_ID: workout_id,
                self.pubsub_keys.CLAIMED_BY: claimed_by
            }
            self._send_or_debug(message_attrs, debug_mode=debug_mode)
            return workout_id, False
        else:
            return None, None

    def _get_servers(
        self,
        build_id: str,
    ) -> List[ServerResponse]:
        servers = self.db.query(
            collection_name=DbCollections.SERVER,
            filters=[('parent_id', DbOperators.EQUAL, build_id)]
        )
        if not servers:
            return []

        servers_resp = []
        for server in servers:
            # Only passes through servers that are hidden and have a human_interaction
            if not server.get('hidden', False) and server.get('human_interaction'):
                servers_resp.append(ServerResponse(**server))
        return servers_resp

    def _evaluate_question(
        self,
        question_key: int,
        check_auto: bool,
        response: str = None,
    ) -> tuple[bool, bool]:
        """
        Loop through the class questions object for the correct question and
        determine if the response is correct.
        Args:
            question_key (int):
            response (str):

        Returns: Correct (bool), Update Obj(bool)
        """
        for question in self.workout['assessment']['questions']:
            if question['id'] != question_key:
                continue

            if question['type'] == 'auto':
                if check_auto:
                    return question['complete'], False
                question['complete'] = True
                return True, True

            if response and not question['complete']:
                question.setdefault('responses', []).append(response)
                if question['answer'] == response:
                    question['complete'] = True
                    return True, True
        return False, True

    def _submit_lms_question(
        self,
        unit: dict,
        workout: dict,
        question_key: str
    ) -> dict:
        """
        Auto assess a question for the LMS based on the unit and question passed in.
        The workout is an object variable.

        Args:
            unit (Any): Datastore entity
            question_key (str): A unique identifier of the question being auto assessed
        Returns: None
        """
        course_code = unit['lms_integration']['lms_connection']['course_code']
        student_email = self.workout.get('student_email')
        if not student_email:
            raise BadRequest("Missing or invalid student email")

        log_args = {
            'student': student_email,
            'workout_id': workout['id']
        }

        lms_type = unit['lms_integration']['lms_connection']['lms_type']
        if lms_type == BuildConstants.LMS.CANVAS:
            url = unit['lms_integration']['lms_connection'].get('url')
            api_key = unit['lms_integration']['lms_connection'].get('api_key')
            lms = LMSCanvas(url=url, api_key=api_key, course_code=course_code)
        else:
            self.logger.error(
                f"{self.class_name}:{workout['id']} - Unsupported LMS found for workout  "
                f"when attempting to auto grade for {student_email}",
                lms_type=lms_type,
                **log_args
            )
            raise ValueError("Unsupported LMS unit")

        quiz_key = workout['lms_integration'].get('quiz_key', None)
        questions = workout['lms_integration'].get('questions', None)
        answered = False
        for question in questions:
            if str(question['question_key']) == question_key and not question.get('complete', False):
                added_points = question['points_possible']
                question['complete'] = True
                self.logger.info(
                    f"{self.class_name}:{unit['id']} - Automated assessment submitted "
                    f"for\nUnit\n Question {question['question_text']}\n"
                    f"Student: {student_email}",
                    **log_args
                )
                lms.mark_question_correct(
                    quiz_id=quiz_key,
                    student_email=student_email,
                    added_points=added_points
                )
                answered = True
                break
            elif question['question_key'] == question_key and question.get('complete', False):
                answered = True
                break

        if not answered:
            self.logger.warning(
                f"{self.class_name}:{unit['id']} - Auto assessment submitted for quiz: "
                f"{quiz_key} and student {student_email}, but "
                f"the question id {question_key} could not be found in the quiz!",
                **log_args
            )
        return workout

    def _clean_object(
        self,
        workouts: dict | List
    ) -> dict | List:
        """Remove any assessment keys and answers from student response object"""
        if isinstance(workouts, list):
            return [self._clean_object(i) for i in workouts]
        else:
            if assessment := workouts.get('assessment'):
                if questions := assessment.get('questions', []):
                    for question in questions:
                        question['answer'] = ''
            elif lms := workouts.get('lms_integration'):
                if questions := lms.get('questions', []):
                    for question in questions:
                        question['answers']['answer_text'] = ""
        return workouts

    def _validate(
        self,
        workout: dict,
        action: Enum
    ) -> None:
        try:
            WorkoutModel(**workout)
        except ValidationError as e:
            msg = f"{self.collection.name} {action.value} failed with validation errors: {e}"
            self.logger.error(msg, action=action.value, workout_id=workout['id'])
            raise BadRequest(msg)

    def _send_or_debug(
        self,
        message_attrs: dict,
        debug_mode: bool
    ) -> None:
        """
        Either publish to Pub/Sub or directly invoke the Cloud Function,
        depending on debug_mode.
        """
        if debug_mode:
            self.logger.info(
                f"Debug mode active. Invoking Cloud Function locally with attributes: {message_attrs}"
            )
            self._invoke_cloud_function_debug(message_attrs)
        else:
            self.pubsub_manager.msg(**message_attrs)

    def _invoke_cloud_function_debug(
        self,
        message_attrs: dict
    ) -> None:
        """
        Bypass Pub/Sub and directly invoke the cloud function.
        Constructs a mock event/context similar to what Cloud Functions receive.
        """
        FakeContext = namedtuple("FakeContext", ["event_id", "timestamp"])
        context = FakeContext(
            event_id="debug-event-id",
            timestamp=datetime.datetime.utcnow().isoformat()
        )
        # The main Cloud Function expects event["attributes"], so build that structure
        event = {"attributes": message_attrs}

        # agoge_cloud_function(event, context, debug_mode=True)

    @staticmethod
    def _safe_to_perform_action(
        action: int,
        workout: dict
    ) -> bool:
        """Validate the incoming PubSub action is safe to perform"""
        s = WorkoutStates
        state = workout.get('state')
        if action == PubSub.Actions.NUKE.value:
            return state in [s.READY.value, s.RUNNING.value, s.READY.BROKEN.value]
        elif action == PubSub.Actions.DELETE.value:
            return state in [s.READY.value, s.NOT_BUILT.value, s.BROKEN.value, s.RUNNING.value]
        elif action == PubSub.Actions.STOP.value:
            return state in [s.RUNNING.value, s.BROKEN.value]
        elif action == PubSub.Actions.START.value:
            return state in [s.READY.value, s.BROKEN.value]
        return True
