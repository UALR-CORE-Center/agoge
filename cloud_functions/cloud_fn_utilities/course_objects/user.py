from typing import List, Union
from google.cloud.exceptions import NotFound

from common.constants.database import (
    DatabaseTypes,
    DbCollections,
    DATABASE_NAME,
    DbOperationTypes,
    DbOperators
)
from common.constants.users import LMSConnection
from common.document_database.factory import DocumentDatabaseFactory
from common.models.users import AgogeUser, APISettings, UserPermissions
from common.utilities.gcp.cloud_env import CloudEnv
from common.utilities.id_generator import IdGenerator


class Users:
    def __init__(
        self,
        env_dict: dict
    ) -> None:
        self.user = None
        self.collection_name = DbCollections.USERS
        self.env = CloudEnv(env_dict=env_dict)
        self.env_dict = self.env.get_env()
        self.db = DocumentDatabaseFactory.create_db_object(
            DatabaseTypes.firestore,
            database_name=DATABASE_NAME
        )

    def get(
        self,
        user_id: str = None,
        user_email: str = None,
        as_dict: bool = False
    ) -> Union[AgogeUser, dict]:
        if not user_id and not user_email:
            raise ValueError("Missing or invalid user identifiers")

        if not self.user:
            if user_email:
                user_data = self.db.query(
                    collection_name=self.collection_name,
                    filters=[('email', DbOperators.EQUAL, user_email)]
                )
                if user_data:
                    user_data = user_data[0]
            else:
                user_data = self.db.get(collection_name=self.collection_name, doc_id=user_email)

            if not user_data:
                raise NotFound("Requested user not found!")
            self.user = AgogeUser(**user_data)
        return self.user.model_dump() if as_dict else self.user

    def list(self) -> List[dict]:
        return self.db.query(collection_name=self.collection_name)

    def list_instructors(self) -> List:
        return self.db.query(
            collection_name=self.collection_name,
            filters=[('permissions.instructor', DbOperators.EQUAL, True)]
        )

    def create(
        self,
        user_email: str,
        permissions: dict,
    ) -> AgogeUser:
        uid = IdGenerator.uuid()
        api_settings = APISettings(api=None, url=None, secret=None).model_dump()
        user = AgogeUser(
            uid=uid,
            email=user_email.lower(),
            permissions=permissions,
            settings={LMSConnection.CANVAS.value.lower(): api_settings},
            timezone=self.env.timezone
        )
        self.db.update(
            collection_name=self.collection_name,
            doc_id=uid,
            data=user.model_dump()
        )
        return user

    def create_teachers(
        self,
        emails: List[str]
    ) -> None:
        operations = []
        api_settings = APISettings(api=None, url=None, secret=None).model_dump()
        permissions = UserPermissions(instructor=True, student=False).model_dump()
        for addr in emails:
            uid = IdGenerator.uuid()
            user = AgogeUser(
                uid=uid,
                email=addr,
                permissions=permissions,
                timezone=self.env.timezone,
                settings={LMSConnection.CANVAS.value.lower(): api_settings}
            )
            operation = self.db.operation(
                collection_name=self.collection_name,
                doc_id=uid,
                operation_type=DbOperationTypes.SET,
                data=user.model_dump()
            )
            operations.append(operation)
        self.db.batch_write(operations)

    def delete(
        self,
        user_id: str,
    ) -> None:
        self.db.delete(collection_name=self.collection_name, doc_id=user_id)
