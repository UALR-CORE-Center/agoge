import re
from typing import Union

from pydantic import ValidationError

from common.constants.database import DatabaseTypes, DATABASE_NAME, DbCollections, ADMIN_INFO_DOCUMENT
from common.document_database import DocumentDatabaseFactory
from common.exceptions import BadRequest, AgogeValidationError
from common.models.agoge import CloudEnvModel
from common.models.users import AgogeUser
from common.utilities.gcp.cloud_env import CloudEnv
from common.utilities.gcp.cloud_logger import LoggerNames, Logger


class Project:
    def __init__(
        self,
        env_dict: dict
    ) -> None:
        self.log_name = LoggerNames.API
        self.env = CloudEnv(log_name=LoggerNames.API, env_dict=env_dict)
        self.logger = Logger(log_name=self.log_name, class_name=self.__class__.__name__)
        self.db = DocumentDatabaseFactory.create_db_object(
            db_type=DatabaseTypes.firestore,
            database_name=DATABASE_NAME,
            log_name=self.log_name
        )

    def get(
        self,
        as_dict: bool = False
    ) -> Union[CloudEnvModel, dict]:
        env = self.env.get_env()
        if as_dict:
            return env
        return CloudEnvModel(**env)

    def update(
        self,
        requester: AgogeUser,
        data: dict
    ) -> None:
        env_dict = self.get(as_dict=True)

        for key, value in data.items():
            if key in env_dict or key in ['classroom_user', 'student_workout_firewall']:
                if key == 'classroom_user':
                    if not self._validate_email(value):
                        raise AgogeValidationError(f'classroom_user must be a valid email address')
                env_dict[key] = value
            else:
                raise BadRequest(f'Invalid or unrecognized key, `{key}`')

        try:
            CloudEnvModel(**env_dict)
            self.db.update(DbCollections.ADMIN_INFO, doc_id=ADMIN_INFO_DOCUMENT, data=env_dict)
        except ValidationError as e:
            self.logger.error(
                f"Failed updating project settings with validation errors: {e}",
                requester=requester.uid,
                formData=data
            )
            raise AgogeValidationError(message=str(e))

    @staticmethod
    def _validate_email(value: str) -> bool:
        pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
        return re.match(pattern, value) is not None
