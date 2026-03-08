"""

"""
import random
import string
from bbrest import BbRest

from common.utilities.id_generator import IdGenerator
from ..lms.lms import LMS, LMSSpec, LMSSpecIncompleteInstructorSettingsError, \
    LMSUserNotFound, LMSExceptionWithHttpStatus
from ..lms.exceptions.blackboard import BlackboardException, InvalidAccessToken


class BlackboardConstants:
    class Questions:
        class Types:
            SHORT_ANSWER = 'short_answer_question'
            ESSAY_QUESTION = 'essay_question'
            FILE_UPLOAD_QUESTION = 'file_upload_question'
            FILL_IN_MULTIPLE_BLANKS = 'fill_in_multiple_blanks_question'
            MULTIPLE_ANSWERS = 'multiple_answers_question'
            MULTIPLE_CHOICE = 'multiple_choice_question'
            BOOLEAN = 'true_false_question'


class LMSBlackboard(LMS):
    def __init__(self, url, api_key, secret_key, courseId=None):
        super().__init__(url, api_key, secret_key, courseId)
        self.blackboard = BbRest(self.url, self.api_key, self.secret_key)
        self.course = self.blackboard.GetCourse(self.courseId) if courseId else None

    def get_class_list(self):
        self.students = self.course.GetUsers(courseId=self.course.courseId, enrollment_type=['student'])
        return self.students

    def get_courses(self):
        courses = self.blackboard.GetCourses()
        return {x.id: x.name for x in courses}

    def mark_question_correct(self, quiz_id, student_email, added_points):
        submission = self._get_submission(student_email, quiz_id)
        score = submission.score + added_points if submission.score else added_points
        submission.edit(submission={'posted_grade': score})

    def validate_connection(self):
        """
        Validates the input API key is associated with a registered Blackboard user
        returns: True if connection is valid
        raises: LMS exception with associated HTTP status code if connection fails
        """
        try:
            user = self.blackboard.GetUser()
            if user:
                return True
            else:
                raise LMSExceptionWithHttpStatus(LMSUserNotFound, http_status_code=404)
        except InvalidAccessToken as e:
            raise LMSExceptionWithHttpStatus(message=str(e), http_status_code=401) from e
        except BlackboardException as e:
            raise LMSExceptionWithHttpStatus(message=str(e), http_status_code=400) from e

    def _get_submission(self, student_email, quiz_id):
        selected_assignment = None
        assignments = list(self.course.get_assignments())
        for assignment in assignments:
            if assignment.quiz_id == quiz_id:
                selected_assignment = assignment
                break
        if not selected_assignment:
            raise
        users = list(self.course.get_users(search_term=student_email))
        user_id = users[0].id if len(users) > 0 else None
        submission = selected_assignment.get_submission(user_id)
        return submission


class LMSSpecBlackboard(LMSSpec):
    def __init__(self, build_spec, course_code, lms_type, due_at=None, time_limit=None, allowed_attempts=None):
        super().__init__(build_spec, course_code, lms_type, due_at, time_limit, allowed_attempts)

    def _get_connection(self):
        try:
            api_key = self.settings[self.lms_type]['api']
            secret_key = self.settings[self.lms_type]['secret']
            url = self.settings[self.lms_type]['url']
        except ValueError:
            raise LMSSpecIncompleteInstructorSettingsError(f"Missing instructor settings for the LMS {self.lms_type}")

        blackboard = BbRest(url, api_key, secret_key)
        blackboard.GetCourse(self.course_code)
        connection = {
            'lms_type': self.lms_type,
            'api_key': api_key,
            'secret_key': secret_key,
            'url': url,
            'course_code': self.course_code
        }
        return connection

    def _decorate_questions(self, questions):
        """
        Modify the questions and replace script_assessment questions with those that can be inserted by the quiz.
        Args:
            questions (list): A list of questions

        Returns:

        """
        for question in questions:
            if 'name' in question:
                question['question_name'] = question.pop('name')
            if 'script_assessment' in question and question['script_assessment']:
                random_answer = IdGenerator.build_id(12)
                question.update({
                    'question_type': 'short_answer_question',
                    'answers': [{'answer_text': random_answer, 'weight': '100'}]
                })
        return questions






