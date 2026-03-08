from common.utilities.gcp.cloud_logger import LoggerNames, Logger
from .courses import Courses
from .course_work import CourseWork
from .submission import Submission
from .teachers import Teacher
from .students import Students
from .service import Service
from .invitations import Invitations
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
        scope: The scope of access for the API.
        user_email: The email address of the user.
        course_id: The ID of the course to interact with.
        _client: The Google Classroom service client.
        logger: Logging client.
    """

    def __init__(
        self,
        project: str,
        scope: Scopes = Scopes.FULL,
        user_email: str = None,
        course_id: str = None,
        service_account_path: str = None,
        debug: bool = False
    ) -> None:

        """Initializes the GoogleClassroom object with given parameters.

        Args:
            scope: The scope of access for the API. Defaults to Scopes.PARTIAL.
            user_email: The email address of the user. Defaults to None.
            course_id: The ID of the course to interact with. Defaults to None.
        """
        self.class_name = self.__class__.__name__
        self.project = project
        self.scope = scope
        self.user_email = user_email
        self.course_id = course_id
        self.service_account_path = service_account_path
        self.debug = debug
        self._client = Service.get_instance(
            project=self.project, scope=self.scope,
            user=self.user_email,
            service_account_path=self.service_account_path,
            debug=self.debug).get_client()
        self.logger = Logger(LoggerNames.API, class_name=self.class_name)

    def get_course(
        self,
        course_id: str
    ) -> dict:
        """Retrieves the specified course.

        Returns:
            The course object retrieved from the Google Classroom API.
        """
        return self.courses().get(course_id)

    def get_courses(
        self,
        scope: str = CourseScopes.TEACHER,
        user_email: str = None
    ) -> list:
        """Retrieves courses associated with the specified teacher.

        Args:
            scope (str): What scope to apply list on (student, teacher, or workspace).
            user_email (str): Optional email to use for (teacher/student)Id instead

        Returns:
            A list of course objects taught by the specified user.
        """
        user_id = user_email if user_email else self.user_email
        if scope == CourseScopes.TEACHER:
            return self.courses().list(scope=scope, user_id=user_id)
        elif scope == CourseScopes.STUDENT:
            return self.courses().list(scope=scope, user_id=user_id)
        elif scope == CourseScopes.WORKSPACE:
            return self.courses().list(scope=CourseScopes.WORKSPACE)
        return []

    def get_all_teachers(self) -> dict:
        """Retrieves a dictionary of all teachers in the workspace.

        Returns:
            dict: A dictionary of all teachers in the workspace.
        """
        return self.courses().get_all_teachers()

    def get_teachers(
        self,
        course_id: str
    ) -> dict:
        """Retrieves all instructors for a single course

        Returns:
            dict: All teachers in a course
        """
        return self.courses().get_teachers(course_id)

    def get_roster(
        self,
        course_id: str
    ) -> list:
        """Retrieves student roster for a single course

        Returns:
            List of student objects in a course
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
        return Invitations(self._client)

# [ eof ]
