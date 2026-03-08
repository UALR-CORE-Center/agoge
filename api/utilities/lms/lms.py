"""
A base parent class for the LMS object in the Cyber Arena
"""
from datetime import datetime, timedelta, UTC
from typing import Union

from common.models.agoge import UnitModel, LMSIntegrationModel
from common.models.users import AgogeUser
from common.constants.database import DatabaseTypes, DATABASE_NAME
from common.constants.build_constants import BuildConstants
from common.utilities.gcp.cloud_env import CloudEnv
from common.document_database import DocumentDatabaseFactory
from common.utilities.gcp.cloud_logger import LoggerNames


class LMS:
    def __init__(
        self,
        course_code: str = None,
        url: str = None,
        api_key: str = None
    ) -> None:
        self.course_code = course_code
        self.url = url
        self.api_key = api_key
        self.students = []
        self.quiz = []
        self.question = []

    def get_class_list(self):
        raise NotImplementedError("get_class_list not implemented for this object.")

    def mark_question_complete(self, quiz_id, student_email, question_id):
        raise NotImplementedError("mark_question_complete not implemented for this object.")

    def validate_connection(self):
        raise NotImplementedError("validate_connection not implemented for this object.")


class LMSSpec:
    def __init__(
        self,
        instructor: AgogeUser,
        build_spec: dict,
        course_code: str,
        lms_type: BuildConstants.LMS,
        env_dict: dict,
        due_at: Union[str, float] = None,
        time_limit: int = None,
        allowed_attempts: int = None,
        additional_instructors: list[str] = None,
    ) -> None:
        self.log_name = LoggerNames.API
        self.build_spec = build_spec
        self.build_spec_model = UnitModel(**self.build_spec)
        self.course_code = course_code
        self.instructor = instructor
        self.instructors = self.build_spec.get('instructor_id', None)
        self.due_at = due_at if due_at else (datetime.now(UTC) + timedelta(days=30)).strftime('%Y-%m-%dT%H:%M:%SZ')
        self.time_limit = time_limit
        self.allowed_attempts = allowed_attempts if allowed_attempts else -1
        self.additional_instructors = additional_instructors
        self.env = CloudEnv(log_name=self.log_name, env_dict=env_dict)
        self.db = DocumentDatabaseFactory.create_db_object(
            db_type=DatabaseTypes.firestore,
            database_name=DATABASE_NAME,
            log_name=self.log_name
        )
        self.settings = None
        self.lms_type = lms_type

    def decorate(self) -> UnitModel:
        if self.instructor.settings is None:
            raise LMSSpecNoInstructorSettingsError
        self.settings = self.instructor.settings

        lms_integration = LMSIntegrationModel(
            description="",
            due_at=str(self.due_at),
            allowed_attempts=self.allowed_attempts,
            lms_connection=self._get_connection()
        )
        if self.build_spec_model.lms_integration is None:
            self.build_spec_model.lms_integration = lms_integration
        if self.build_spec_model.lms_integration.course_work is None:
            self.build_spec_model.lms_integration.course_work = BuildConstants.LMSCourseWork.ASSIGNMENT.value
        if self.build_spec_model.lms_integration.questions is not None:
            self.build_spec_model.lms_integration.questions = self._decorate_questions(lms_integration.questions)
        if self.additional_instructors:
            if self.instructor.email not in self.additional_instructors:
                self.additional_instructors.append(self.instructor.email)
            self.build_spec_model.instructor_id = self.additional_instructors
        else:
            self.build_spec_model.instructor_id = [self.instructor.email]
        return self.build_spec_model

    def _get_connection(self):
        pass

    def _decorate_questions(self, questions):
        pass


class LMSSpecError(Exception):
    pass


class LMSSpecNoInstructorSettingsError(LMSSpecError):
    pass


class LMSSpecIncompleteInstructorSettingsError(LMSSpecError):
    pass


class LMSSpecConnectionError(LMSSpecError):
    pass


class LMSSpecLMSTypeNotSupported(LMSSpecError):
    pass


class LMSExceptionWithHttpStatus(Exception):
    def __init__(self, message, http_status_code=400):
        super().__init__(message)
        self.http_status_code = http_status_code


class LMSUserNotFound(Exception):
    pass
