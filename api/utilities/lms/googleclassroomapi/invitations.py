from .google_classroom_object import GoogleClassroomObject
from .constants import CourseRole


__author__ = "Andrew Bomberger"
__copyright__ = "Copyright 2024, Bastazo, Inc."
__credits__ = ["Andrew Bomberger"]
__license__ = "MIT"
__version__ = "0.0.1"
__maintainer__ = "Andrew Bomberger"
__email__ = "andrew@bastazo.com"
__status__ = "Testing"


class Invitations(GoogleClassroomObject):
    """Manages Invitations in Google Classroom.

    Provides functionalities to create, retrieve, list, and manage
    invitations in Google Classroom.

    Attributes:
        _client: The Google Classroom client.
        course_id: ID of course to interact with.
        user_id: The ID of the user.
        logger: Logging client.
    """
    def __init__(self, client):
        super().__init__(client)
        """Initializes the Invitations object with a Classroom client.

        Args:
            client: The Google Classroom client.
        """
        self.class_name = self.__class__.__name__
        self.course_id = None
        self.user_id = None

    def accept(
            self,
            invitation_id: str
    ) -> None:
        """Accepts an invitation to a class on behalf of a user.

        Args:
            invitation_id (str): ID of the invitation to accept.

        Raises:
            Unauthorized: If the user is not authorized.
            ResourceNotFound: If the invitation is not found.
            GoogleClassroomException: For other exceptions during invitation acceptance.
        """
        request = self._client.invitations().accept(id=str(invitation_id))
        self._make_request(request, 'accept')

    def accept_all_invitations(
            self,
            user_id: str
    ) -> None:
        """
        Accepts all existing course invitations on behalf of a user

        Args:
            user_id (str): User ID or email of user to accept on behalf of
        """
        invitations = self.list(user_id)
        if invitations:
            self.logger.info(f'{self.class_name}:{user_id} - Found {len(invitations)} course '
                             f'invitations waiting acceptance ...')
            for invitation in invitations:
                self.accept(invitation['id'])

    def create(
            self,
            course_id: str,
            user_email: str,
            role: str = CourseRole.TEACHER
    ) -> dict:
        """Generates an invitation to a course.

        Args:
            course_id (str): ID of the course.
            user_email (str): Email of the user to be invited.
            role (str): Role of user to be invited as.

        Returns:
            dict: The invitation object.

        Raises:
            Unauthorized: If the user is not authorized.
            Conflict: If there is a conflict in the invitation.
            GoogleClassroomException: For other exceptions during the invitation process.
        """
        user = {
            'courseId': course_id,
            'role': role,
            'userId': str(user_email).lower()
        }

        # Create user invitation
        request = self._client.invitations().create(body=user)
        invitation = self._make_request(request, 'invite_to_class')
        log_msg = (f"{self.class_name}:{course_id} - User {invitation.get('userId')}"
                   f"was invited as a {role} to course with ID {course_id}")
        self.logger.info(log_msg)
        return invitation

    def delete(
            self,
            invitation_id: str
    ) -> None:
        """
        Deletes an existing course invitation on behalf of a user.

        Args:
            invitation_id (str): ID of invitation to delete

        Returns:
            None
        """
        request = self._client.invitations().delete(id=invitation_id)
        self._make_request(request, 'delete')

    def update(self, *args, **kwargs):
        pass

    def get(
            self,
            invitation_id: str
    ):
        """
        Gets an existing course invitation for a user.

        Args:
            invitation_id (str): ID of invitation to get

        Returns:
            Invitation
        """
        request = self._client.invitations().get(id=invitation_id)
        return self._make_request(request, 'get')

    def list(
            self,
            user_id: str
    ):
        """
        Lists all existing course invitations for a user.

        Args:
            user_id (str): ID of user to retrieve invitations for

        Returns:
            list: Course invitations list
        """
        request = self._client.invitations().list(userId=str(user_id))
        invitations = self._make_request(request, 'list')
        return invitations.get('invitations', [])

# [ eof ]
