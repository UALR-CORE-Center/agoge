from .google_classroom_object import GoogleClassroomObject
from .invitations import Invitations
from .constants import CourseRole
from .user_object import UserObject


__author__ = "Andrew Bomberger"
__copyright__ = "Copyright 2024, Bastazo, Inc."
__credits__ = ["Andrew Bomberger"]
__license__ = "MIT"
__version__ = "0.0.1"
__maintainer__ = "Andrew Bomberger"
__email__ = "andrew@bastazo.com"
__status__ = "Testing"


class Teacher(GoogleClassroomObject):
    """Manages teachers in Google Classroom.

    Provides functionalities to create, retrieve, list, and manage
    teachers in Google Classroom.

    Attributes:
        _client: The Google Classroom client client.
        course_id: ID of course to interact with.
        user_id: The ID of the teacher user.
        logger: Logging client.
    """
    def __init__(self, client):
        super().__init__(client)
        """Initializes the Teachers object with a Classroom client.

        Args:
            client: The Google Classroom client.
        """
        self.class_name = self.__class__.__name__
        self.course_id = None
        self.user_id = None

    def create(self, course_id: str, user_email: str) -> dict:
        """Creates a new teacher for a specific course.

        Args:
            course_id (str): ID of the course.
            user_email (str): Email address of user to create as instructor.

        Returns:
            dict: A dictionary representing the created teacher.

        Raises:
            Unauthorized: If the user is not authorized.
            ResourceNotFound: If the course is not found.
            GoogleClassroomException: For other exceptions during teacher creation.
        """
        teacher = {'userId': str(user_email).lower()}
        request = self._client.courses().teachers().create(courseId=str(course_id), body=teacher)
        teacher_resp = self._make_request(request, 'create')
        self.logger.info(f'{self.class_name}:{course_id} - Teacher created for course {course_id}')
        return teacher_resp

    def delete(self, course_id, user_id: str) -> None:
        """Deletes a teacher from a course.

        Args:
            course_id (str): ID of the course.
            user_id (str): ID of the teacher.

        Raises:
            Unauthorized: If the user is not authorized.
            ResourceNotFound: If the course or teacher is not found.
            GoogleClassroomException: For other exceptions during teacher deletion.
        """
        request = self._client.courses().teachers().delete(courseId=course_id, userId=user_id)
        self._make_request(request, 'delete')
        self.logger.info(f'{self.class_name}:{course_id} - Teacher {user_id} removed from course')

    def update(self, *args, **kwargs):
        raise NotImplementedError(f"{self.class_name}: update - Method not implemented.")

    def get(self, *args, **kwargs):
        raise NotImplementedError(f"{self.class_name}:get - Method not implemented.")

    def list(self, course_id: str, known_teachers: dict = None) -> dict:
        """Retrieves all teachers for a specific course.

        Args:
            course_id (str): The ID of the course.
            known_teachers (dict, optional): Current known dictionary of teachers to filter duplicates.

        Returns:
            dict: All teachers from a course in the format {userId: emailAddress, ...}.

        Raises:
            Unauthorized: If the user is not authorized.
            ResourceNotFound: If the course is not found.
            GoogleClassroomException: For other exceptions during teacher listing.
        """
        if known_teachers:
            teachers = known_teachers
        else:
            known_teachers = {}
            teachers = {}

        page_token = None
        while True:
            request = (
                self._client.courses()
                .teachers()
                .list(
                    courseId=course_id,
                    pageToken=page_token,
                    pageSize=100
                )
            )
            response = self._make_request(request, 'list')
            for teacher in response.get("teachers", []):
                if teacher["userId"] not in known_teachers:
                    teachers[teacher["userId"]] = UserObject(teacher)
            page_token = response.get("nextPageToken", None)
            if not page_token:
                break
        return teachers

    def invite_to_class(self, course_id: str, user_email: str) -> dict:
        """Generates an invitation to a course as a co-teacher.

        Args:
            course_id (str): ID of the course.
            user_email (str): Email of the user to be invited.

        Returns:
            dict: The invitation object.

        Raises:
            Unauthorized: If the user is not authorized.
            Conflict: If there is a conflict in the invitation.
            GoogleClassroomException: For other exceptions during the invitation process.
        """
        return (
            Invitations(client=self._client)
            .create(course_id, user_email, CourseRole.TEACHER)
        )

    def accept_invitation_to_class(self, invitation_id: str) -> None:
        """Accepts an invitation to a class on behalf of a user.

        Args:
            invitation_id (str): ID of the invitation to accept.

        Raises:
            Unauthorized: If the user is not authorized.
            ResourceNotFound: If the invitation is not found.
            GoogleClassroomException: For other exceptions during invitation acceptance.
        """
        Invitations(client=self._client).accept(invitation_id)

    def get_user_id_by_email(self, course_id: str, user_email: str) -> str or None:
        """Retrieves the user ID for a given email in a specific course.

        Args:
            course_id (str): The ID of the course.
            user_email (str): The email address of the user.

        Returns:
            str or None: The user ID if found, otherwise None.

        Raises:
            Unauthorized: If the user is not authorized.
            GoogleClassroomException: For other exceptions during the retrieval process.
        """
        request = self._client.courses().teachers().list(courseId=course_id)
        teachers = self._make_request(request, 'get_user_id_by_email')

        for teacher in teachers.get('teachers', []):
            if current_email := teacher['profile'].get('emailAddress', None):
                if current_email.lower() == user_email.lower():
                    return teacher['userId']
        return None

    def is_valid_teacher(self, user_email: str) -> bool:
        """Checks if the given email is associated with a valid teacher account.

        Args:
            user_email (str): The email address to check.

        Returns:
            bool: True if the user is a valid teacher, False otherwise.

        Raises:
            Unauthorized: If the user is not authorized.
            GoogleClassroomException: For other exceptions during the check.
        """
        request = self._client.courses().list(teacherId=str(user_email).lower())
        courses = self._make_request(request, 'is_valid_teacher')
        if courses and 'courses' in courses and len(courses['courses']) > 0:
            return True
        return False

# [ eof ]
