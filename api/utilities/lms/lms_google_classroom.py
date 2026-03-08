from common.constants.database import DbCollections, DATABASE_NAME, DatabaseTypes, DbOperators
from common.document_database import DocumentDatabaseFactory
from common.models.agoge import LMSQuizQuestionsModel, LMSConnectionModel
from common.utilities.gcp.cloud_env import CloudEnv
from common.utilities.gcp.cloud_logger import LoggerNames

from ..lms.googleclassroomapi.google_classroom import GoogleClassroom, CourseScopes
from ..lms.lms import LMS, LMSSpec


class LMSGoogleClassroom(LMS):
    def __init__(
        self,
        env_dict: dict,
        course_code: str = None
    ) -> None:
        super().__init__(course_code, url=None, api_key=None)
        self.log_name = LoggerNames.API
        self.cloud_env = CloudEnv(log_name=self.log_name, env_dict=env_dict)
        self.db = DocumentDatabaseFactory.create_db_object(
            db_type=DatabaseTypes.firestore,
            database_name=DATABASE_NAME,
            log_name=self.log_name
        )
        self.user = self.cloud_env.classroom_user
        self.classroom = GoogleClassroom(project=self.cloud_env.project, user_email=self.user)
        self.course = self.classroom.get_course(course_id=self.course_code) if self.course_code else None

    def get_class_list(self) -> list:
        self.students = self.classroom.get_roster(self.course_code)
        return self.students

    def get_courses(
        self,
        teacher_email: str = None
    ) -> dict:
        courses = self.classroom.get_courses(user_email=teacher_email)
        return {course['id']: course['name'] for course in courses}

    def get_all_courses(self) -> list:
        return self.classroom.get_courses(scope=CourseScopes.WORKSPACE)

    def get_teachers(
        self,
        course_id: str
    ) -> list[str] | dict:
        instructors = self.classroom.get_teachers(course_id)
        if isinstance(instructors, dict):
            return [i.email for i in instructors.values()]
        return instructors

    def get_courses_from_db(
        self,
        teacher_email: str
    ) -> list[dict]:
        classroom = []
        filters = [('teachers', DbOperators.ARRAY_CONTAINS, str(teacher_email))]
        if classroom_db := self.db.query(
                collection_name=DbCollections.CLASSROOM,
                filters=filters
        ):
            classroom = [
                {'id': i['id'], 'name': i['name']}
                for i in classroom_db
            ]
        return classroom


class LMSSpecGoogleClassroom(LMSSpec):
    def __init__(
        self,
        instructor,
        build_spec,
        course_code,
        lms_type,
        env_dict,
        due_at=None,
        time_limit=None,
        allowed_attempts=None,
        additional_instructors=None
    ) -> None:
        super().__init__(
            instructor, build_spec, course_code, lms_type, env_dict,
            due_at, time_limit, allowed_attempts, additional_instructors
        )

    def _get_connection(self) -> LMSConnectionModel:
        return LMSConnectionModel(
            lms_type=self.lms_type,
            course_code=self.course_code
        )

    def _decorate_questions(
        self,
        questions: list[LMSQuizQuestionsModel]
    ) -> None:
        """
        Modify the questions and replace script_assessment questions with those that can be inserted by the quiz.
        Args:
            questions (list): A list of questions

        Returns:

        """
        # TODO: Update this to meet the google forms standard
        pass


# [ eof ]
