from .google_classroom_object import GoogleClassroomObject
from .constants import CourseWorkEnums
from .course_work_object import CourseWorkObject


class CourseWork(GoogleClassroomObject):
    """Manages course work in Google Classroom.

    Provides functionalities to create, retrieve, list, update, and delete
    course work items in Google Classroom.

    Attributes:
        _client: The Google Classroom service client.
        course_id: The ID of the course to interact with.
        class_name: The name of the current class.
    """
    def __init__(self, client):
        super().__init__(client)
        """Initializes the CourseWork object with a service client.

        Args:
            client: The Google Classroom service client.
        """
        self.class_name = self.__class__.__name__
        self.course_id = None

    def create(self, course_id: str, title: str, description: str, due_timestamp: float, **kwargs) -> dict:
        """Creates a new course work item.

        Args:
            course_id (str): The ID of the course.
            title (str): The title of the course work.
            description (str): The description of the course work.
            due_timestamp (float): The due timestamp of the course work.
            **kwargs: Additional parameters for the course work.

        Returns:
            dict: The created course work item object.

        Raises:
            Unauthorized: If the user is not authorized.
            ResourceNotFound: If the course is not found.
            GoogleClassroomException: For other exceptions during creation.
        """
        course_work_obj = (
            CourseWorkObject(course_id=course_id)
            .create(title, description, due_timestamp, **kwargs)
        )
        request = (
            self._client.courses()
            .courseWork()
            .create(courseId=course_id, body=course_work_obj)
        )
        created_cw = self._make_request(request, 'create')
        log_msg = f'{self.class_name}:{created_cw.get("id")} - Created CourseWork object for course {course_id}'
        self.logger.info(log_msg)
        return created_cw

    def update(self):
        """Updates an existing course work item.

        Raises:
            NotImplemented: Indicates that the method is not implemented.
        """
        raise NotImplemented(f'{self.class_name}:update - Method not implemented!')

    def delete(self, course_id: str, course_work_id: str) -> None:
        """Deletes a specific course work item.

        Args:
            course_id (str): The ID of the course.
            course_work_id (str): The ID of the course work item to delete.

        Raises:
            Unauthorized: If the user is not authorized.
            ResourceNotFound: If the course or course work item is not found.
            GoogleClassroomException: For other exceptions during deletion.
        """
        request = self._client.courses().courseWork().delete(courseId=str(course_id), id=str(course_work_id))
        self._make_request(request, 'delete')
        log_msg = f'{self.class_name}:{course_work_id} - Deleted CourseWork object for course {course_id}'
        self.logger.info(log_msg)

    def get(self, course_id: str, course_work_id: str) -> dict:
        """Retrieves a specific course work item by its ID.

        Args:
            course_id (str): The ID of the course.
            course_work_id (str): The ID of the course work item.

        Returns:
            dict: The course work item object.

        Raises:
            Unauthorized: If the user is not authorized.
            ResourceNotFound: If the course or course work item is not found.
            GoogleClassroomException: For other exceptions during retrieval.
        """
        request = (
            self._client.courses()
            .courseWork()
            .get(courseId=str(course_id), id=str(course_work_id))
        )
        course_work = self._make_request(request, 'get')
        log_msg = f'{self.class_name}:{course_work_id} - Retrieved CourseWork object for course {course_id}'
        self.logger.debug(log_msg)
        return course_work

    def list(self, course_id: str) -> list:
        """Lists all course work items for a specific course.

        Args:
            course_id (str): The ID of the course.

        Returns:
            list: A list of course work item objects.

        Raises:
            Unauthorized: If the user is not authorized.
            ResourceNotFound: If the course is not found.
            GoogleClassroomException: For other exceptions during listing.
        """
        request = self._client.courses().courseWork().list(courseId=course_id)
        course_works = self._make_request(request, 'list')
        return course_works.get('courseWork', [])

# [ eof ]
