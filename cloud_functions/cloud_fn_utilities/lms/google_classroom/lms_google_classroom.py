"""
Cloud function LMS class to create assignments
"""
import json
from .googleclassroomapi.google_classroom import GoogleClassroom, CourseWorkEnums

from common.utilities.gcp.cloud_env import CloudEnv
from common.utilities.gcp.cloud_logger import Logger, LoggerNames
from ..lms import LMS


class LMSGoogleClassroom(LMS):
    def __init__(self, course_code, build, env_dict=None):
        super().__init__(course_code=course_code, build=build, url=None, api_key=None)
        self.class_name = self.__class__.__name__
        self.cloud_env = CloudEnv(env_dict=env_dict) if env_dict else CloudEnv()
        self.user = self.cloud_env.classroom_user
        self.teacher = None
        if build:
            self.teacher = self.build.get('instructor_id')[0]
        if self.teacher:
            self.classroom = GoogleClassroom(project=self.cloud_env.project, user_email=self.teacher)
        else:
            self.classroom = GoogleClassroom(project=self.cloud_env.project, user_email=self.user)
        self.course_name = self._get_course_name()
        self.course_work = self.classroom.course_work()
        self.invitations = self.classroom.invitations()
        self.students = []

    def _get_course_name(self):
        name = None
        if self.course_code and self.build:
            course = self.classroom.get_course(course_id=self.course_code)
            name = course.get('name')
            self.build['lms_integration']['lms_connection']['name'] = name
        return name

    def get_updated_build(self) -> dict:
        """Returns the updated build details.

        Returns:
            A dictionary containing the updated build details.
        """
        return self.build

    def get_courses(self):
        return self.classroom.get_courses()

    def get_all_courses(self):
        return self.classroom.get_all_courses()

    def get_teachers(self, course_id: str = None):
        return self.classroom.get_teachers(course_id=course_id)

    def get_class_list(self, suppress_logs: bool = True):
        """Fetches the list of students from Google Classroom.

        Args:
            suppress_logs: A boolean indicating whether to suppress logging, default to True.
        """
        roster = []
        for student in self.classroom.get_roster(self.course_code):
            try:
                roster.append(student.summary())
            except AttributeError:
                if hasattr(student, 'name') and not suppress_logs:
                    self.logger.warning(f"{self.class_name}:{self.course_code} - Email does not exist for "
                                        f"{student.name} and a workout will not be created for them!")
                elif not suppress_logs:
                    self.logger.warning(f"{self.class_name}:{self.course_code} - Error when trying to enumerate "
                                        f"class list. Student record has no name!")
        for teacher in self.classroom.get_teachers(self.course_code).values():
            try:
                roster.append(teacher.summary())
            except AttributeError:
                if hasattr(teacher, 'name') and not suppress_logs:
                    self.logger.warning(f"{self.class_name}:{self.course_code} - Email does not exist for "
                                        f"{teacher.name} and a workout will not be created for them!")
                elif not suppress_logs:
                    self.logger.warning(f"{self.class_name}:{self.course_code} - Error when trying to enumerate "
                                        f"class list. Teacher record has no name!")
        return roster

    def create_quiz(self, delete_existing_quizzes: bool = True):
        """Creates a new quiz in the course, optionally deleting existing quizzes.

        Args:
            delete_existing_quizzes: A boolean indicating whether to delete existing quizzes, default to True.
        """
        raise NotImplementedError(f'create_quiz method not implemented for {self.class_name}')

    def create_assignment(self, delete_existing_assignment: bool = True):
        """Creates a new assignment in the course, optionally deleting existing assignments.

        Args:
            delete_existing_assignment: A boolean indicating whether to delete existing assignments, default to True.
        """
        project_name = str(self.cloud_env.project).title().replace('-', " ")
        assignment_name = f"{self.build['summary']['name']}"
        if delete_existing_assignment:
            self.delete_assignment_by_name(assignment_name)

        description = self._get_description()
        materials = self._get_materials(app_name=project_name)
        self.course_work.create(
            course_id=self.course_code,
            title=assignment_name,
            description=description,
            due_timestamp=self.build['lms_integration']['due_at'],
            materials=materials
        )

    def delete_assignment_by_name(self, assignment_name: str) -> bool:
        """Deletes an assignment by name.

        Args:
            assignment_name: The name of the assignment to delete.

        Returns:
            A boolean indicating whether the assignment was successfully deleted.
        """
        assignments = self.course_work.list(self.course_code)
        for assignment in assignments:
            if assignment['title'] == assignment_name:
                self.course_work.delete(course_id=self.course_code, course_work_id=assignment['id'])
                return True
        return False

    def accept_all_invitations(self):
        """
        Accepts all pending invitations for the project user
        """
        self.invitations.accept_all(user_id=self.user)

    def _get_description(self) -> str:
        """Generates a description for the assignment.

        Returns:
            A string containing the description for the assignment.
        """
        return (f"Your lab and lab instructions are available using the links below. "
                f"Use the join code {self.build.get('join_code', None)} and the email used to login "
                f"to this site.")

    def _get_materials(self, app_name: str) -> list:
        """Generates materials links for the assignment.

        Args:
            app_name: The name of the application to include in the materials.

        Returns:
            A list of dictionaries containing materials links for the assignment.
        """
        materials = [{'link': {'url': f'{self.cloud_env.main_app_url}/join', 'title': app_name}}]
        if student_instructions_url := self.build['summary'].get('student_instructions_url', None):
            materials.append({'link': {'url': student_instructions_url, 'title': 'Instructions'}})
        return materials

# [ eof ]
