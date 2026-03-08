from .google_classroom_object import GoogleClassroomObject
from .user_object import UserObject

__author__ = "Andrew Bomberger"
__copyright__ = "Copyright 2024, Bastazo, Inc."
__credits__ = ["Andrew Bomberger"]
__license__ = "MIT"
__version__ = "0.0.1"
__maintainer__ = "Andrew Bomberger"
__email__ = "andrew@bastazo.com"
__status__ = "Testing"


class Students(GoogleClassroomObject):
    def __init__(self, client):
        super().__init__(client)
        self.class_name = self.__class__.__name__

    def create(self, course_id: str, student_email: str) -> dict:
        """Creates a new user with student role in course

        Args:
            course_id (str): The ID of the course
            student_email (str): The email of the student user to create

        Returns:
            dic: The newly created student user

        Raises:
            Unauthorized: If the user is not authorized.
            ResourceNotFound: If the course is not found.
            BadRequest: If the request is bad.
            GoogleClassroomException: For other exceptions during user creation.
        """
        student_body = {
            'userId': str(student_email),
        }
        request = self._client.courses().students().create(courseId=course_id, body=student_body)
        created_student = self._make_request(request, 'create')
        return created_student

    def delete(self, *args, **kwargs):
        raise NotImplementedError(f"{self.class_name}:delete - Method not implemented")

    def update(self, *args, **kwargs):
        raise NotImplementedError(f"{self.class_name}:update - Method not implemented")

    def get(self, *args, **kwargs):
        raise NotImplementedError(f"{self.class_name}:get - Method not implemented")

    def list(self, course_id):
        """Retrieves the roster of students for a specific course.

        Args:
            course_id (str): The ID of the course.

        Returns:
            list: A list of students registered to the course.

        Raises:
            Unauthorized: If the user is not authorized.
            ResourceNotFound: If the course is not found.
            GoogleClassroomException: For other exceptions during roster retrieval.
        """
        student_profiles = []
        students = []
        page_token = None

        while True:
            request = (
                self._client.courses()
                .students()
                .list(
                    courseId=str(course_id),
                    pageToken=page_token,
                    pageSize=100
                )
            )
            response = self._make_request(request, 'get_roster')
            students.extend(response.get("students", []))
            page_token = response.get("nextPageToken", None)
            if not page_token:
                break

        for student in students:
            student_profiles.append(UserObject(student))
        self.logger.info(f'{self.class_name}:{course_id} - Retrieved {len(students)} '
                         f'registered students for course.')
        return student_profiles

# [ eof ]
