from common.constants.database import DbCollections, DbOperationTypes
from common.constants.build_constants import BuildConstants
from ...course_objects.user import Users
from ..google_classroom.lms_google_classroom import LMSGoogleClassroom
from ..lms_synchronizer import LMSSynchronizer


class LMSGoogleClassroomSynchronizer(LMSSynchronizer):
    def __init__(self, env_dict=None):
        super().__init__(env_dict=env_dict)
        self.class_name = self.__class__.__name__
        self.users = Users(env_dict=self.env_dict)
        self.teacher_list_cache = {}
        self.collection = DbCollections.CLASSROOM

    def _filter_active_lms_units(self, active_units):
        active_lms_units = []
        for unit in active_units:
            lms_integration = unit.get('lms_integration')
            if lms_integration is not None:
                if lms_integration['lms_connection']['lms_type'] == BuildConstants.LMS.GOOGLE_CLASSROOM:
                    active_lms_units.append(unit)
        return active_lms_units

    def _get_active_students(self, unit):
        course_code = unit['lms_integration']['lms_connection']['course_code']
        course_key = f"https://classroom.google.com-{course_code}"

        # This cache speeds up the function in cases where courses have several assignments
        if course_key not in self.student_list_cache:
            lms = LMSGoogleClassroom(build=unit, course_code=course_code, env_dict=self.env_dict)
            class_list = lms.get_class_list(suppress_logs=True)
            self.student_list_cache[course_key] = class_list
        else:
            class_list = self.student_list_cache[course_key]
        return class_list

    def _sync_active_teachers(self):
        teachers_db = [t['email'] for t in self.users.list_instructors()]
        registered_teachers = set(
            teacher.email.lower()
            for teacher in self.teacher_list_cache.values()
        )

        new_teachers = []
        for teacher in registered_teachers:
            if teacher not in teachers_db:
                new_teachers.append(teacher)

        if new_teachers:
            self.users.create_teachers(new_teachers)
            self.logger.info(f'{self.class_name} - Found {len(new_teachers)} new teachers to add to {self.env.project}')
        else:
            self.logger.info(f'{self.class_name} - No new teachers found to sync')

    def sync_classes_with_db(self):
        """Synchronizes classroom data with an external datastore.

        This includes adding new courses, updating existing courses, and removing
        courses that no longer exist in the LMSGoogleClassroom.
        """
        lms_classroom = LMSGoogleClassroom(
            build=None,
            course_code=None,
            env_dict=self.env_dict
        )
        # Accept any pending course invitations for project user first
        lms_classroom.accept_all_invitations()

        # Get all currently synced courses from database
        query_existing_courses = self.db.query(collection_name=self.collection)
        existing_courses_dict = {
            course['id']: course for course in query_existing_courses
        }
        existing_course_ids = set(existing_courses_dict.keys())

        # Get updated list of active courses from Classroom API
        lms_courses = lms_classroom.get_all_courses()
        lms_course_ids = {course['id'] for course in lms_courses if course.get('courseState') == 'ACTIVE'}

        # Determine courses to be removed
        courses_to_remove_ids = existing_course_ids - lms_course_ids
        courses_to_remove = [
            self.db.operation(
                collection_name=self.collection,
                doc_id=course,
                operation_type=DbOperationTypes.DELETE,
            )
            for course in courses_to_remove_ids
        ]

        # Remove courses that no longer exist in LMS
        if courses_to_remove_ids:
            self.logger.debug(f"{self.class_name} - removed {len(courses_to_remove_ids)} "
                              f"archived courses from database")
            self.db.batch_write(courses_to_remove)

        # Generate course object and get instructor list for each active course
        courses_to_update = []
        for course in lms_courses:
            course_id = course['id']
            if course_id in courses_to_remove:
                continue

            courses_db_obj = {
                'id': course_id,
                'name': course['name'],
                'owner': {'id': course['ownerId'], 'email': ''},
                'teachers': []
            }
            teachers = lms_classroom.get_teachers(course_id=course_id)
            for teacher in teachers.values():
                email_lower = str(teacher.email).lower()
                if teacher.user_id == course['ownerId']:
                    courses_db_obj['owner']['email'] = email_lower
                courses_db_obj['teachers'].append(email_lower)
            self.teacher_list_cache.update(teachers)

            existing_course = existing_courses_dict.get(course_id)
            if not existing_course:
                operation = self.db.operation(
                    collection_name=self.collection,
                    doc_id=course_id,
                    operation_type=DbOperationTypes.SET,
                    data=courses_db_obj
                )
                courses_to_update.append(operation)
            elif existing_course != courses_db_obj:
                operation = self.db.operation(
                    collection_name=self.collection,
                    doc_id=course_id,
                    operation_type=DbOperationTypes.UPDATE,
                    data=courses_db_obj
                )
                courses_to_update.append(operation)

        self._sync_active_teachers()
        if courses_to_update:
            self.logger.debug(f"{self.class_name} - synced {len(courses_to_update)} courses with database")
            self.db.batch_write(courses_to_update)

        if not courses_to_remove_ids and not courses_to_update:
            self.logger.debug(f"{self.class_name} - No classroom changes to sync")

# [ eof ]
