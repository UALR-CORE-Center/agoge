from abc import ABC, abstractmethod
import json

from common.document_database import DocumentDatabaseFactory, DatabaseQueries
from common.utilities.gcp.cloud_env import CloudEnv
from common.utilities.gcp.pubsub_manager import PubSubManager
from common.utilities.gcp.cloud_logger import Logger, LoggerNames
from common.constants.database import (
    DatabaseTypes,
    DATABASE_NAME,
    DbCollections
)
from common.constants.pub_sub import PubSub
from common.constants.build_constants import BuildConstants
from common.constants.states import UnitStates, WorkoutStates
from common.models.agoge import UnitModel, WorkoutModel, WebApplicationModel, AgogeWorkoutSummaryModel
from common.models.model_validators.model_validator import ModelValidator
from common.utilities.id_generator import IdGenerator
from common.utilities.timestamps import Timestamps

from ...lms.canvas.lms_canvas import LMSCanvas
from ...lms.google_classroom.lms_google_classroom import LMSGoogleClassroom
from ...state_managers.unit_states import UnitStateManager
from ..workout.factory_workout import WorkoutFactory


class BaseUnit(ABC):
    """
    Base class for managing various operations of a unit in a cyber training environment.

    This abstract class defines the fundamental functionalities for unit management, such as building,
    starting, stopping, deleting, and nuking units. It also supports marking units as broken and
    adding student workout records for LMS integration.

    Attributes:
        unit_id (str): The unique identifier for the unit.
        debug (bool): Flag to enable verbose logging. Useful for debugging.
        force (bool): Flag to force operations, bypassing certain checks or states.
        env (CloudEnv): Configuration and environment variables container.
        logger (Logger): Logger instance for logging activities.
        s (UnitStates): Enumeration of possible states of the unit.
        pubsub_manager (PubSubManager): Manager for handling Pub/Sub operations.
        unit_model (dict): Data structure containing the unit's configuration and state.
        lms_integration (bool): Flag indicating if the unit is integrated with an LMS.
        lms_quiz (bool): Flag indicating if a quiz is associated with the unit in the LMS.
        workout_id (str, optional): Identifier for a specific workout within the unit.
        form_data (dict, optional): Data associated with web forms, including student and team information.
        state_manager (UnitStateManager): Manager for handling state transitions of the unit.

    Args:
        unit_model (UnitModel, dict): The Database document representing the unit.
        workout_id (str, optional): Identifier for the child workout. Defaults to None.
        form_data (str): JSON string associated with web form submissions. Defaults to None.
        debug (bool, optional): Flag to enable verbose logging. Defaults to False.
        force (bool, optional): Flag to force operations. Defaults to False.
        env_dict (dict, optional): Dictionary of environment variables. Defaults to None.

    The class provides abstract methods for building, starting, stopping, deleting, and nuking
    units which must be implemented in subclasses. Additional helper methods are provided for
    managing unit state and interacting with external systems like LMS or GCP services.
    """
    def __init__(
        self,
        unit_model: UnitModel,
        workout_id: str = None,
        form_data: str = None,
        debug: bool = False,
        force: bool = False,
        env_dict: dict = None
    ) -> None:
        self.class_name = self.__class__.__name__
        self.log_name = LoggerNames.CLOUD_FN
        self.unit_type = None
        self.unit_id = unit_model.id
        self.debug = debug
        self.force = force
        self.env = CloudEnv(env_dict=env_dict) if env_dict else CloudEnv()
        self.env_dict = self.env.get_env()
        self.logger = Logger(
            log_name=self.log_name,
            class_name=self.class_name,
            unit_id=self.unit_id
        )
        self.s = UnitStates
        self.pubsub_manager = PubSubManager(topic=PubSub.Topics.AGOGE, env_dict=self.env_dict)
        self.validator = ModelValidator
        self.unit_model = unit_model
        self.model_fields_set = unit_model.model_fields_set
        self.db = DocumentDatabaseFactory.create_db_object(
            db_type=DatabaseTypes.firestore,
            database_name=DATABASE_NAME
        )
        self.db_queries = DatabaseQueries(db=self.db)
        if not self.unit_model:
            self.logger.error(f"{self.class_name}:{self.unit_id} - The Unit datastore record no longer exists!")
            raise LookupError
        self.lms_integration = self._lms_integration
        self.lms_quiz = False
        if self.lms_integration:
            self.course_work = self.unit_model.lms_integration.course_work
            if self.course_work == BuildConstants.LMSCourseWork.QUIZ:
                self.lms_quiz = True

        # Pass in these values to build a single workout associated with the unit
        self.workout_id = workout_id
        self.form_data = json.loads(form_data) if form_data else None

        self.state_manager = UnitStateManager(build_id=self.unit_id)
        self.workout_ids = []

    @property
    def _lms_integration(self):
        if 'lms_integration' in self.model_fields_set:
            return self.unit_model.lms_integration is not None
        return False

    def build(self) -> None:
        """
        Builds the unit based on the configuration and LMS integration settings.

        This method initiates the build process for the unit. If LMS integration is enabled,
        it delegates the build process to an LMS-specific method. Otherwise, it builds a workout
        based on the provided workout_id and form_data. The method manages the unit's state transitions
        during the build process.

        Raises:
            ValueError: If the necessary conditions for building the workout are not met, or if the
                        unit reaches its maximum capacity.
        """
        self.logger.info(f"Beginning to build unit {self.unit_id}")
        if self.lms_integration:
            self._deploy_unit_to_lms()

        self._build_unit()
        if self.workout_id:
            self._build_workout_in_unit(workout_id=self.workout_id)
        else:
            self.logger.warning(
                f"{self.class_name}:{self.unit_id} - "
                f"No workout id provided for build handler with action "
                f"{self.unit_model.build_type}"
            )
            return

    @abstractmethod
    def _build_unit(self):
        pass

    @abstractmethod
    def start(self):
        """Starts the unit. Must be implemented by subclasses."""
        pass

    @abstractmethod
    def stop(self):
        """Stops the unit. Must be implemented by subclasses."""
        pass

    @abstractmethod
    def delete(self):
        """Deletes the unit. Must be implemented by subclasses."""
        pass

    @abstractmethod
    def nuke(self):
        """Nukes the unit. Must be implemented by subclasses."""
        pass

    def mark_broken(self) -> None:
        """
        Marks the unit as broken by setting its state to BROKEN and updating the record in DataStore.
        """
        self.unit_model.state = self.s.BROKEN
        self.db.update(
            collection_name=DbCollections.UNIT,
            doc_id=self.unit_id,
            data=self.unit_model.model_dump()
        )

    def get_build_id(self) -> str:
        """
        Returns the build id of the unit.
        Returns:
            str: The build id of the unit.
        """
        return self.unit_id

    def add_student_workout_record(
        self,
        student_email: str,
        student_name: str
    ) -> None:
        """
        Adds a workout record for a student to the unit. Initially used for synchronizing with the LMS
        when new students are added to the course.

        Args:
            student_email (str): The email address of the student.
            student_name (str): The name of the student.
        """
        workout_id = IdGenerator.build_id()
        workout_record = self._create_workout_record(
            workout_id=workout_id,
            student_name=student_name,
            student_email=student_email
        )
        self.db.update(collection_name=DbCollections.WORKOUT, doc_id=workout_id, data=workout_record)

    def _deploy_unit_to_lms(self) -> None:
        """
        Deploys the unit to a Learning Management System (LMS) based on the unit's configuration.

        This method initializes a connection to the specified LMS using the configuration details
        from the unit_model. It supports deployment to different types of LMS, such as Canvas.
        Depending on the unit configuration, this method either creates a quiz or an assignment in the LMS.

        After creating the quiz or assignment, the method fetches the class list from the LMS and generates
        workout records for each student. Each workout record is then stored in the Datastore.

        Raises:
            ValueError: If the LMS type specified in the unit_model is not supported.
        """
        lms_type = self.unit_model.lms_integration.lms_connection.lms_type
        url = self.unit_model.lms_integration.lms_connection.url
        api_key = self.unit_model.lms_integration.lms_connection.api_key
        course_code = self.unit_model.lms_integration.lms_connection.course_code
        if lms_type == BuildConstants.LMS.CANVAS:
            lms = LMSCanvas(
                url=url, api_key=api_key,
                course_code=course_code,
                build=self.unit_model.model_dump(),
                env_dict=self.env_dict
            )
        elif lms_type == BuildConstants.LMS.GOOGLE_CLASSROOM:
            lms = LMSGoogleClassroom(
                build=self.unit_model.model_dump(),
                course_code=course_code,
                env_dict=self.env_dict
            )
        else:
            self.logger.error(f"{self.class_name}:{self.unit_id} - Unsupported LMS object")
            raise ValueError

        if self.lms_quiz:
            lms.create_quiz()
        else:
            lms.create_assignment()

        # Prevents overwriting the unit after the quiz has been updated
        updated_unit = lms.get_updated_build()
        self.unit_model = UnitModel(**updated_unit)

        roster = lms.get_class_list()
        self.unit_model.workspace_settings.count = len(roster)
        for student in roster:
            workout_id = IdGenerator.build_id()
            student_email = student.get('email')
            student_name = student.get('name')
            workout_record = self._create_workout_record(
                workout_id=workout_id,
                student_email=student_email,
                student_name=student_name
            )
            self.db.update(
                collection_name=DbCollections.WORKOUT,
                doc_id=workout_id,
                data=workout_record
            )

        self.db.update(
            collection_name=DbCollections.UNIT,
            doc_id=self.unit_id,
            data=self.unit_model.model_dump()
        )

    def _build_workout_in_unit(
        self,
        workout_id: str
    ) -> None:
        """
        Builds a workout within the unit based on provided workout_id and form data.

        This method is responsible for creating a workout record and initiating the build process.
        It first checks if the number of existing workouts has reached the unit's maximum capacity.
        If not, it proceeds to create a workout record based on the provided workout_id, along with
        any additional data such as student email or team name obtained from form_data.

        The workout is then built either directly (in debug mode) or through a PubSub message
        (in normal operation mode).

        Args:
            workout_id (str): The identifier for the workout to be built.

        Raises:
            ValueError: If the unit is at its maximum capacity or if required data is missing or invalid.
        """
        self.logger.info(f"{self.class_name}:{workout_id} -Beginning to prepare workout id for unit {self.unit_id}")
        self._wait_until_unit_is_ready_for_servers()
        count = min(int(self.env.max_workspaces), int(self.unit_model.workspace_settings.count))

        workout_list = self.db_queries.get_children(
            parent_id=self.unit_id,
            child_collection=DbCollections.WORKOUT
        )
        if workout_list:
            if len(workout_list) >= count:
                self.logger.error(
                    f"{self.class_name}:{self.unit_id} - "
                    f"Requested build for Unit failed; Unit is at max capacity"
                )
                raise ValueError
        if not self.form_data:
            self.logger.error(
                f'{self.class_name}:{self.unit_id} - '
                f'Requested workout build for Unit failed; No form_data given.'
            )
            raise ValueError
        student_email = self.form_data.get('student_email', None)
        team_name = self.form_data.get('team_name', None)
        if student_email:
            workout_record = self._create_workout_record(
                workout_id=workout_id,
                student_email=student_email,
                student_name=student_email
            )
        elif team_name:
            workout_record = self._create_workout_record(workout_id=workout_id, team_name=team_name)
        else:
            self.logger.error(
                f'{self.class_name}:{self.unit_id} - '
                f'Invalid or missing claimed_by values given for Unit'
            )
            raise ValueError

        self.db.update(collection_name=DbCollections.WORKOUT, doc_id=workout_id, data=workout_record)

        if self.debug:
            workout = WorkoutFactory.create_workout_object(
                workout_id=workout_id,
                debug=self.debug,
                env_dict=self.env_dict
            )
            workout.build()
        else:
            self.pubsub_manager.msg(
                handler=str(PubSub.Handlers.BUILD.value),
                action=str(PubSub.Actions.BUILD.value),
                key_type=str(DbCollections.WORKOUT.value),
                build_id=str(workout_id),
                course_object=str(PubSub.CourseObjects.WORKOUT.value)
            )

    def _create_workout_record(self, workout_id: str, **kwargs) -> dict:
        """
        Creates and validates a workout record with the given workout_id
        and additional data derived from the unit.

        Args:
            workout_id (str): The identifier for the workout.
            **kwargs (Dict[str, Any]): Additional top-level details to add to record model

        Returns:
            dict: WorkoutModel in dictionary form representing the workout record.
        """
        unit_summary = self.unit_model.summary
        workout_record = {
            'id': workout_id,
            'parent_id': self.unit_id,
            'parent_build_type': BuildConstants.BuildType.UNIT,
            'build_type': BuildConstants.BuildType.WORKOUT,
            'creation_timestamp': Timestamps.get_current_timestamp_utc(),
            'state': WorkoutStates.NOT_BUILT.value,
            'summary': AgogeWorkoutSummaryModel(
                name=unit_summary.name,
                description=unit_summary.description,
                student_instructions_url=unit_summary.student_instructions_url
            )
        }

        if kwargs:
            for key, value in kwargs.items():
                if key == 'student_email':
                    workout_record[key] = str(value).lower()
                else:
                    workout_record[key] = value

        # Expiration based on workout_duration_days
        if (workout_duration_days := self.unit_model.workout_duration_days) is not None:
            workout_record['expires'] = Timestamps.get_current_timestamp_utc(add_seconds=86400*workout_duration_days)
        else:
            workout_record['expires'] = self.unit_model.workspace_settings.expires

        # Networks, servers, and firewall_rules
        for key in ['unit_type', 'networks', 'servers', 'firewall_rules', 'firewalls']:
            try:
                if hasattr(self.unit_model, key):
                    value = getattr(self.unit_model, key)
                    if value:
                        if key == 'servers':
                            workout_record['shutoff_timestamp'] = (
                                Timestamps.get_current_timestamp_utc(add_seconds=7200, round_to_quarter=True)
                            )
                        workout_record[key] = value
            except AttributeError as e:
                self.logger.debug(
                    f"{self.class_name} - Attempted to access field {key}, but it doesn't exist in model!"
                    f"{e}"
                )

        # Optional Fields
        # Process web_applications if they exist
        if (web_applications := self.unit_model.web_applications) is not None:
            processed_web_applications = [
                WebApplicationModel(
                    host_name=app.host_name,
                    name=app.name,
                    starting_directory=app.starting_directory,
                    url=f"https://{app.host_name}/{app.starting_directory}"
                )
                for app in web_applications
            ]
            workout_record['web_applications'] = processed_web_applications

        # Optional escape room, assessment, or lms_quiz
        if (escape_room := self.unit_model.escape_room) is not None:
            workout_record['escape_room'] = escape_room
        elif (assessment := self.unit_model.assessment) is not None:
            workout_record['assessment'] = assessment
        elif (lms_integration := self.unit_model.lms_integration) is not None:
            workout_record['lms_integration'] = lms_integration

        # Debug flag
        if self.debug:
            workout_record['test'] = True

        return self.validator(model=WorkoutModel, log_location=self.log_name).load(workout_record, as_dict=True)

    @abstractmethod
    def _wait_until_unit_is_ready_for_servers(self):
        """Needed to avoid building workouts on community builds before the networks have been deployed"""
        pass
