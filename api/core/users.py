from typing import Union

from pydantic import ValidationError
from uuid import UUID

from common.constants.users import LMSConnection, UserGroups
from common.constants.database import (
    DatabaseTypes,
    DbCollections,
    DATABASE_NAME,
    DbOperators
)
from common.document_database.factory import DocumentDatabaseFactory
from common.exceptions import BadRequest, NotFound, Unauthorized, Conflict
from common.models.lms_courses import Courses, LMSCourse
from common.models.model_validators.agoge_user import SafeAgogeUserValidator
from common.models.users import AgogeUser, SafeAgogeUser, APISettings
from common.utilities.gcp.cloud_env import CloudEnv
from common.utilities.gcp.cloud_logger import LoggerNames
from common.utilities.id_generator import IdGenerator

from utilities.lms.lms_canvas import LMSCanvas
from utilities.lms.lms_canvas import exceptions as CanvasExceptions
from utilities.lms.lms_google_classroom import LMSGoogleClassroom


class Users:
    def __init__(self) -> None:
        self.class_name = self.__class__.__name__
        self.log_name = LoggerNames.API
        self.user = None
        self.collection_name = DbCollections.USERS
        self.env = CloudEnv(log_name=self.log_name)
        self.env_dict = self.env.get_env()
        self.db = DocumentDatabaseFactory.create_db_object(
            DatabaseTypes.firestore,
            database_name=DATABASE_NAME,
            log_name=self.log_name
        )

    def get_user(
        self,
        user_id: str = None,
        user_email: str = None,
        as_dict: bool = False
    ) -> AgogeUser | dict:
        if not user_id and not user_email:
            raise BadRequest(message="Missing or invalid user identifiers in request")

        if not self.user:
            if user_email:
                user_data = self.db.query(
                    collection_name=self.collection_name,
                    filters=[('email', DbOperators.EQUAL, user_email)]
                )
                if user_data:
                    user_data = user_data[0]
            else:
                user_data = self.db.get(collection_name=self.collection_name, doc_id=user_id)

            if not user_data:
                raise NotFound(message="Requested user not found!")
            self.user = AgogeUser(**user_data)
        return self.user.model_dump() if as_dict else self.user

    def get_user_from_request(
        self,
        requester: AgogeUser,
        user_id: UUID.hex
    ) -> AgogeUser:
        self.user = self.get_user(user_id=user_id)
        if requester.is_admin or requester.uid == self.user.uid:
            return self.user
        raise Unauthorized("Requesting user has insufficient permissions")

    def list_users(self) -> list[SafeAgogeUser]:
        users = self.db.query(collection_name=self.collection_name)
        return SafeAgogeUserValidator().load(users, halt_on_error=False)

    def create(
        self,
        json_data: dict,
        env_dict: dict
    ) -> SafeAgogeUser:
        email = json_data.get('email')
        submitted_permissions = json_data.get('permissions')
        permissions = UserGroups.BASE.value
        uid = IdGenerator.uuid()

        if not email:
            raise BadRequest(message="User creation failed. Missing or invalid data for `email`")

        email = email.lower()
        duplicate = self.db.query(self.collection_name, filters=[('email', DbOperators.EQUAL, email)])
        if duplicate and len(duplicate) > 0:
            raise Conflict(message="Account already exists!")

        if submitted_permissions:
            for group, value in submitted_permissions.items():
                if group in permissions:
                    permissions[group] = value

        user = {
            'uid': uid,
            'email': email,
            'permissions': permissions,
            'settings': {
                LMSConnection.CANVAS.value.lower(): APISettings(api=None, url=None, secret=None).model_dump()
            },
            'timezone': env_dict.get('timezone', 'America/Chicago')
        }
        self.db.update(
            collection_name=self.collection_name,
            doc_id=uid,
            data=user
        )
        return SafeAgogeUser.from_dict(user)

    def delete(
        self,
        user_id: str,
        requester: AgogeUser
    ) -> None:
        if user_id == requester.uid:
            raise BadRequest(message="Invalid request. Cannot delete yourself!")

        self.db.delete(collection_name=self.collection_name, doc_id=user_id)
        return

    def update(
        self,
        requester: AgogeUser,
        user_id: str,
        data: dict
    ) -> SafeAgogeUser:
        """
        Updates current user based on provided JSON data
        Args:
            requester (AgogeUser): User making update request
            user_id (str): UID of user to update
            data (dict): JSON data to update user with

        Returns: updated SafeAgogeUser
        """
        self.user = self.get_user(user_id=user_id)

        for key, value in data.items():
            if hasattr(self.user, key) and key not in ["settings", "permissions"]:
                setattr(self.user, key, value)
            elif key == "settings":
                try:
                    self.update_settings(requester, user_id, data={'settings': value}, update=False)
                except Unauthorized:
                    # Requesting user can only modify their own settings
                    pass
            elif key == "permissions":
                if requester.is_admin and requester.uid == self.user.uid:
                    if not value.get('admin'):
                        raise BadRequest(message="Invalid request. Nice try, but you cannot demote yourself!")
                self.user.permissions.update(value)

        permissions = self.user.permissions
        if any(permissions.get(role) for role in ['admin', 'instructor', 'student']):
            self.user.permissions['pending'] = False
        else:
            self.user.permissions['pending'] = True

        return self._update_user(self.user, cleaned=True)

    def update_settings(
        self,
        requester: AgogeUser,
        user_id: str,
        data: dict = None,
        update: bool = True
    ) -> Union[AgogeUser, None]:
        if requester.uid != user_id:
            raise Unauthorized("Requesting user does not have the correct permissions to modify this account")

        user = self.get_user(user_id=user_id)

        if data and 'settings' in data:
            new_settings = data['settings']
            try:
                # Validate the entire new settings dictionary
                for lms_key, settings_values in new_settings.items():
                    if not LMSConnection.has_value(lms_key):
                        raise BadRequest(message=f"Invalid LMS in settings: {lms_key}")
                APISettings(**new_settings)
            except ValidationError as e:
                raise BadRequest(message=f"Invalid input: {e}")

            # If validation passes, update the user settings
            for lms_key, settings_values in new_settings.items():
                if isinstance(settings_values, dict):
                    lms_enum_key = LMSConnection(lms_key).value
                    if lms_enum_key in user.settings:
                        # Update only the provided fields in the existing settings
                        existing_settings = user.settings[lms_enum_key]
                        for key, value in settings_values.items():
                            if value not in (None, ""):
                                setattr(existing_settings, key, value)
                    else:
                        user.settings[lms_enum_key] = APISettings(**{lms_key: settings_values})

            if update:
                return self._update_user(user, cleaned=False)

            self.user = user
            return
        else:
            raise BadRequest(message="Invalid or missing `settings` obj in request to update")

    def reset_user_settings(
        self,
        requester: AgogeUser,
        user_id: str,
        data: dict = None
    ) -> SafeAgogeUser | AgogeUser:
        authorized = requester.is_admin
        is_owner = requester.uid == user_id
        if is_owner or authorized:
            user = self.get_user(user_id)

            for lms in LMSConnection:
                if lms.value in data:
                    user.settings[lms.value] = APISettings()
            self._update_user(user)
            if not is_owner:
                return SafeAgogeUser.from_agoge_user(user)
            return user
        raise Unauthorized("Requesting user does not have the correct permissions to modify this account")

    def _update_user(
        self,
        user: AgogeUser,
        cleaned: bool = True
    ) -> SafeAgogeUser | AgogeUser:
        """
        Updates user Datastore record based on input AgogeUser object
        Args:
            user (AgogeUser): user to update
            cleaned (bool): Whether to return SafeAgogeUser or AgogeUser

        Returns: SafeAgogeUser (default) or AgogeUser
        """
        self.db.update(
            collection_name=self.collection_name,
            doc_id=user.uid,
            data=user.model_dump()
        )

        return SafeAgogeUser.from_agoge_user(user) if cleaned else user

    def get_user_courses(
        self,
        requester: AgogeUser,
    ) -> Courses:
        overview = requester.get_settings_overview()
        courses = Courses()

        if overview.get('canvas'):
            api_key = requester.settings['canvas'].api
            url = requester.settings['canvas'].url
            try:
                canvas = LMSCanvas(url=url, api_key=api_key).get_courses()
                courses.canvas = [LMSCourse(**i) for i in canvas]
            except CanvasExceptions.InvalidAccessToken as e:
                # self.reset_user_settings(requester, user_id=requester.uid, data={LMS.CANVAS.value: True})
                print(e)
        if self.env_dict.get('classroom_user'):
            classroom = (
                LMSGoogleClassroom(env_dict=self.env_dict)
                .get_courses_from_db(requester.email)
            )
            courses.classroom = [LMSCourse(**i) for i in classroom]
        return courses
