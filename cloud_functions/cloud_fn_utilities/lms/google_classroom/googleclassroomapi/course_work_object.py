import copy
from datetime import datetime

from common.utilities.gcp.cloud_logger import LoggerNames, Logger
from .constants import CourseWorkEnums
from .exceptions import InvalidCourseWorkObject


class CourseWorkObject:
    def __init__(self, course_id: str):
        self.course_id = course_id
        self.logger = Logger(LoggerNames.CLOUD_FN, class_name=self.__class__.__name__)

    def create(self, title: str, description: str, due_ts: float, **kwargs) -> dict:
        """
        Creates a CourseWork object compatible with the Google Classroom API.

        This method prepares and serializes a CourseWork object with given attributes,
        ensuring it is safe and formatted correctly for transmission through the API.
        Optional parameters can be provided through kwargs, which allow for further
        customization of the CourseWork object.

        Args:
            title (str): The title of the coursework.
            description (str): A detailed description of the coursework.
            due_ts (float): The due timestamp for the coursework.
            **kwargs: Additional keyword arguments for more properties. Supported kwargs include:
                - materials (optional): Supplementary materials for the coursework. Defaults to None.
                - work_type (optional): The type of coursework (e.g., ASSIGNMENT, QUIZ). Defaults to ASSIGNMENT.
                - state (optional): The publication state of the coursework (e.g., PUBLISHED, DRAFT). Defaults to
                PUBLISHED.

        Returns:
            dict: A serialized dictionary of the CourseWork object, ready for API transmission.

        Examples:
            >>> create("Math Assignment", "Complete the problems on page 23", 1616161616.0)
            {'title': 'Math Assignment', 'description': 'Complete the problems on page 23', ...}

            >>> create("Science Quiz", "Quiz on Chapter 5", 1616161616.0, work_type=CourseWorkEnums.CourseWorkType.QUIZ)
            {'title': 'Science Quiz', 'description': 'Quiz on Chapter 5', 'workType': 'QUIZ', ...}
        """
        # Set defaults for any additional arguments
        materials = kwargs.get('materials', None)
        work_type = kwargs.get('work_type', CourseWorkEnums.CourseWorkType.ASSIGNMENT)
        state = kwargs.get('state', CourseWorkEnums.CourseWorkState.PUBLISHED)

        # Create and serialize course work object
        course_work_obj = {
            "title": title,
            "description": description,
            "materials": materials,
            "workType": work_type,
            "state": state,
            "due_ts": due_ts
        }
        serialized = (
            self.Serializer(course_work_obj=course_work_obj)
            .serialize()
        )
        return serialized

    class Serializer:
        """Serializes course work objects for Google Classroom.

        This class is responsible for converting course work objects into a format
        that is compatible with the Google Classroom API, including validation and
        transformation of fields.

        Attributes:
            course_work_obj: The course work object to be serialized.
            valid: A boolean indicating if the course work object is valid.
            work_type: Enum for valid course work types.
            state: Enum for valid course work states.
            submission_mode: Enum for valid submission modification modes.
        """

        def __init__(self, course_work_obj):
            """Initializes the Serializer with a course work object.

            Args:
                course_work_obj: The course work object to be serialized.
            """
            self.course_work_obj = course_work_obj
            self.valid = False
            self.work_type = CourseWorkEnums.CourseWorkType
            self.state = CourseWorkEnums.CourseWorkState
            self.submission_mode = CourseWorkEnums.SubmissionModificationMode

        def serialize(self) -> dict:
            """Serializes the course work object.

            Validates and transforms the course work object into a format compatible
            with the Google Classroom API.

            Returns:
                dict: The serialized course work object.

            Raises:
                InvalidCourseWorkObject: If any validations fail.
            """
            course_work_obj = copy.deepcopy(self.course_work_obj)

            # Validate and serialize materials
            if materials := course_work_obj.setdefault('materials', []):
                course_work_obj['materials'] = self._materials(materials)

            # Validate state and work type
            if not self._state(course_work_obj['state']):
                raise InvalidCourseWorkObject(f"Invalid state: {course_work_obj['state']}")
            if not self._work_type(course_work_obj['workType']):
                raise InvalidCourseWorkObject(f"Invalid workType: {course_work_obj['workType']}")

            # Parse due timestamp
            due_date, due_time = self._due_timestamp(course_work_obj['due_ts'])
            course_work_obj['due_date'] = due_date
            course_work_obj['due_time'] = due_time
            del course_work_obj['due_ts']

            return course_work_obj

        def _work_type(self, work_type: str) -> bool:
            """Validates the work type against known types.

            Args:
                work_type (str): The work type to validate.

            Returns:
                bool: True if valid, False otherwise.
            """
            types = [value for key, value in self.work_type.__dict__.items() if not key.startswith('__')]
            return work_type in types

        def _submission_modification_mode(self, submission_mode):
            """Check if submission mode is in gathered class attributes"""
            modes = [value for key, value in self.submission_mode.__dict__.items() if not key.startswith('__')]
            return submission_mode in modes

        def _state(self, state: str) -> bool:
            """Validates the state against known states.

            Args:
                state (str): The state to validate.

            Returns:
                bool: True if valid, False otherwise.
            """
            states = [value for key, value in self.state.__dict__.items() if not key.startswith('__')]
            return state in states

        @staticmethod
        def _due_timestamp(due_ts: float) -> tuple:
            """Converts a timestamp into a date and time dictionary.

            Args:
                due_ts (float): The UNIX timestamp for the due date and time.

            Returns:
                tuple: A tuple containing dictionaries for the due date and due time.

            Raises:
                InvalidCourseWorkObject: If the timestamp is invalid.
            """
            try:
                due_datetime = datetime.fromtimestamp(due_ts)
            except (OverflowError, OSError, ValueError):
                raise InvalidCourseWorkObject("Invalid `due_ts` value.")

            due_date = {'year': due_datetime.year, 'month': due_datetime.month, 'day': due_datetime.day}
            due_time = {'hours': due_datetime.hour, 'minutes': due_datetime.minute}
            return due_date, due_time

        @staticmethod
        def _materials(materials: list) -> list:
            """Validates and processes materials within the course work object.

            Args:
                materials (list): The list of materials to validate and process.

            Returns:
                list: The processed list of materials.

            Raises:
                InvalidCourseWorkObject: If any material is missing required keys.
            """
            for material in materials:
                if 'link' not in material or 'url' not in material.get('link', {}):
                    raise InvalidCourseWorkObject(f"Invalid material: {material}")
            return materials

# [ eof ]
