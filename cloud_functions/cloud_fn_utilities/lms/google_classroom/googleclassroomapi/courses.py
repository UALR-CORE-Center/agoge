from .constants import CourseScopes
from .google_classroom_object import GoogleClassroomObject
from .exceptions import InvalidRequest
from .teachers import Teacher
from .students import Students


class Courses(GoogleClassroomObject):
    """Manages courses in Google Classroom.

    Provides functionalities to create, retrieve, update, delete, and manage
    courses and their rosters in Google Classroom.

    Attributes:
        _client: The Google Classroom service client.
        course: The current course object.
        teacher_id: The ID of the teacher.
        logger: Logger client
    """

    def __init__(self, client):
        super().__init__(client)
        """Initializes the Courses object with a service client.

        Args:
            client: The Google Classroom service client.
        """
        self.class_name = self.__class__.__name__
        self.course = None
        self.teacher_id = None

    def create(self, name, section, description, room, state, heading=None, owner='me'):
        """Creates a new course in Google Classroom.

        Args:
            name (str): Name of the course.
            section (str): Section of the course.
            description (str): Description of the course.
            room (str): Room where the course is held.
            state (str): State of the course.
            heading (str, optional): Heading for the course description. Defaults to None.
            owner (str, optional): Owner ID of the course. Defaults to 'me'.

        Returns:
            A dict representing the created course.

        Raises:
            Unauthorized: If the user is not authorized.
            ResourceNotFound: If the course is not found.
            Conflict: If there is a conflict in course creation.
            GoogleClassroomException: For other exceptions during course creation.
        """
        if not heading:
            heading = f'Welcome to {name}'
        course = {
            'name': name,
            'section': section,
            'descriptionHeading': heading,
            'description': description,
            'room': room,
            'ownerId': owner,
            'courseState': state
        }
        request = self._client.courses().create(body=course)
        course = self._make_request(request, 'create')
        log_msg = f'{self.class_name}:{course.get("id")} - Course created: {(course.get("name"))}'
        self.logger.info(log_msg)
        return course

    def get(self, course_id) -> dict:
        """Retrieves a specific course by its ID.

        Args:
            course_id (str): The ID of the course to retrieve.

        Returns:
            dict: The course object from the Google Classroom API.

        Raises:
            Unauthorized: If the user is not authorized.
            ResourceNotFound: If the course is not found.
            GoogleClassroomException: For other exceptions during course retrieval.
        """
        course = None
        request = self._client.courses().get(id=str(course_id))
        course = self._make_request(request, 'get')
        return course

    def delete(self, course_id) -> None:
        """Deletes a specific course by its ID.

        Args:
            course_id (str): The ID of the course to delete.

        Raises:
            Unauthorized: If the user is not authorized.
            ResourceNotFound: If the course is not found.
            GoogleClassroomException: For other exceptions during course deletion.
        """
        request = self._client.courses().delete(id=str(course_id))
        self._make_request(request, 'delete')
        log_msg = f'{self.class_name}:{course_id} - Deleted course'
        self.logger.info(log_msg)

    def update(self, course_id: str, **kwargs) -> dict:
        """Updates an existing course with specified properties.

        Args:
            course_id (str): The ID of the course to update.
            **kwargs: Arbitrary keyword arguments for course properties.

        Returns:
            dict: The updated course object.

        Raises:
            Unauthorized: If the user is not authorized.
            GoogleClassroomException: For other exceptions during course update.
        """
        course = self.get(course_id=course_id)
        for key, val in kwargs.items():
            if key == 'courseOwner':
                continue
            elif key in course:
                course[key] = val

        request = self._client.courses().update(id=str(course_id), body=course)
        updated = self._make_request(request, 'update')
        log_msg = f'{self.class_name}:{course_id} - Updated course.'
        self.logger.info(log_msg)
        return updated

    def list(self, scope=CourseScopes.TEACHER, user_id=None) -> list:
        """Retrieves all courses for a specific teacher or student.

        Args:
            scope (str): The scope to list courses. If set to user, look for input user_id,
                otherwise pull project wide
            user_id (str, optional): The ID of the user whose courses to retrieve. Defaults to None.

        Returns:
            list: A list of course objects.

        Raises:
            Unauthorized: If the user is not authorized.
            ResourceNotFound: If the course is not found.
            GoogleClassroomException: For other exceptions during course retrieval.
        """
        if scope == CourseScopes.TEACHER:
            if user_id:
                request = self._client.courses().list(teacherId=user_id)
            else:
                raise InvalidRequest('Request to list courses by user failed. Missing value for `user_id`')
        elif scope == CourseScopes.STUDENT:
            if user_id:
                request = self._client.courses().list(studentId=user_id)
            else:
                raise InvalidRequest('Request to list courses by user failed. Missing value for `user_id`')
        elif scope == CourseScopes.WORKSPACE:
            request = self._client.courses().list()
        else:
            raise InvalidRequest(f'Request to list courses with invalid or missing scope: {scope}')
        response = self._make_request(request, 'list')
        return response.get('courses', [])

    def get_teachers(self, course_id=None) -> dict:
        """
        Retrieves a dictionary of all current teachers in the workspace

        Returns:
             list: All unique teachers in workspace in the format [{id: emailAddress},...]
        """
        teacher = Teacher(self._client)
        teachers = {}
        if course_id:
            teachers.update(teacher.list(course_id, teachers))
        else:
            courses = self.list(scope=CourseScopes.WORKSPACE)
            for course in courses:
                teachers.update(teacher.list(course['id'], teachers))
        return teachers

    def get_roster(self, course_id) -> list:
        """Retrieves the roster of students for a specific course.

        Args:
            course_id (str): The ID of the course.

        Returns:
            list: A list of student emails registered to the course.

        Raises:
            Unauthorized: If the user is not authorized.
            ResourceNotFound: If the course is not found.
            GoogleClassroomException: For other exceptions during roster retrieval.
        """
        return Students(self._client).list(course_id)

    def transfer_ownership(self, course_id: str, teacher_email: str) -> dict:
        """Transfers ownership of a course to a new teacher.

        Args:
            course_id (str): The ID of the course.
            teacher_email (str): The email of the new teacher.

        Returns:
            dict: The updated course object with the new owner.

        Raises:
            Unauthorized: If the user is not authorized.
            ResourceNotFound: If the course is not found.
            BadRequest: If the request is bad.
            GoogleClassroomException: For other exceptions during ownership transfer.
        """
        # Create a new teacher with the input email. Returns object if successful or teacher already exists
        Teacher(client=self._client).create(course_id=course_id, user_email=teacher_email)

        # Create ownership transfer request
        request = (
            self._client.courses()
            .patch(id=course_id, updateMask='ownerId', body={'ownerId': teacher_email})
        )
        course = self._make_request(request, 'transfer_ownership')
        log_msg = f'{self.class_name}:{course_id} - Updated course with new owner {teacher_email}'
        self.logger.info(log_msg)
        return course

# [ eof ]
