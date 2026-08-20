from common.utilities.gcp.cloud_logger import LoggerNames, Logger
from .courses import Courses
from .course_work import CourseWork
from .invitations import Invitations
from .submission import Submission
from .students import Students
from .service import Service
from .teachers import Teacher
from .constants import CourseWorkEnums, Scopes, CourseScopes


class GoogleClassroom:
    """
    Main interface for interacting with Google Classroom API.

    This class provides methods to interact with various aspects of Google Classroom
    including courses, teachers, and coursework. It is designed to be used by users
    with an administrative level of access.

    Note: Most automation requests require a user authorization level of workspace
    admin or higher.

    Attributes:
        project: The GCP project id associated with the Classroom
        scope: The scope of access for the API.
        user_email: The email address of the user.
        course_id: The ID of the course to interact with.
        _client: The Google Classroom service client.
        logger: Logging client.
    """

    def __init__(self, project, scope=Scopes.FULL, user_email=None, course_id=None):

        """Initializes the GoogleClassroom object with given parameters.

        Args:
            project: The GCP project associated with Classroom
            scope: The scope of access for the API. Defaults to Scopes.PARTIAL.
            user_email: The email address of the user. Defaults to None.
            course_id: The ID of the course to interact with. Defaults to None.
        """
        self.class_name = self.__class__.__name__
        self.project = project
        self.scope = scope
        self.user_email = user_email
        self.course_id = course_id
        self._client = Service.get_instance(
            project=self.project, scope=self.scope,
            user=self.user_email).get_client()
        self.logger = Logger(LoggerNames.CLOUD_FN, class_name=self.__class__.__name__)

    def get_course(self, course_id: str) -> dict:
        """Retrieves the specified course.

        Returns:
            The course object retrieved from the Google Classroom API.
        """
        return self.courses().get(course_id)

    def get_courses(self, teacher_email: str = None):
        """Retrieves courses associated with the specified teacher.

        Args:
            teacher_email (str): Optional email to use for teacherId instead

        Returns:
            A list of course objects taught by the specified teacher.
        """
        teacher_id = teacher_email if teacher_email else self.user_email
        return self.courses().list(user_id=teacher_id)

    def get_all_courses(self):
        return self.courses().list(scope=CourseScopes.WORKSPACE)

    def get_teachers(self, course_id=None) -> dict:
        """Retrieves a dictionary of all teachers in the workspace.

        Returns:
            dict: A dictionary of all teachers in the workspace.
        """
        return self.courses().get_teachers(course_id=course_id)

    def get_roster(self, course_id: str) -> list:
        """Retrieves student roster for a single course

        Returns:
            List of student emails in a course
        """
        return self.courses().get_roster(course_id)

    # Methods for returning class instances
    def courses(self) -> Courses:
        """Creates an instance of the Courses class.

        Returns:
            An instance of the Courses class.
        """
        return Courses(self._client)

    def course_work(self) -> CourseWork:
        """Creates an instance of the CourseWork class.

        Returns:
            An instance of the CourseWork class.
        """
        return CourseWork(self._client)

    def teacher(self) -> Teacher:
        """Creates an instance of the Teacher class.

        Returns:
            An instance of the Teacher class.
        """
        return Teacher(self._client)

    def student(self) -> Students:
        """Creates an instance of the Student class

        Returns:
            An instance of the Student class.
        """
        return Students(self._client)

    def invitations(self) -> Invitations:
        """Creates an instance of the Invitations class

        Returns:
            An instance of the Invitations class.
        """
        return Invitations(self._client)

# [ eof ]
