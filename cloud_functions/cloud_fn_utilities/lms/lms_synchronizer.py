from common.constants.database import DbCollections, DatabaseTypes, DATABASE_NAME
from common.document_database import DocumentDatabaseFactory, DatabaseQueries
from common.models.agoge import UnitModel
from common.models.model_validators.model_validator import ModelValidator
from common.utilities.gcp.cloud_env import CloudEnv
from common.utilities.gcp.cloud_logger import Logger, LoggerNames
from ..course_objects.unit.factory_unit import UnitFactory


class LMSSynchronizer:
    def __init__(
        self,
        env_dict: dict = None
    ) -> None:
        self.log_name = LoggerNames.CLOUD_FN
        self.env = CloudEnv(env_dict=env_dict) if env_dict else CloudEnv()
        self.env_dict = self.env.get_env()
        self.student_list_cache = {}
        self.db = self.db = DocumentDatabaseFactory.create_db_object(
            db_type=DatabaseTypes.firestore,
            database_name=DATABASE_NAME
        )
        self.db_queries = DatabaseQueries(db=self.db)
        self.logger = Logger(log_name=self.log_name, class_name=self.__class__.__name__)
        self.active_students = {}

    def sync_units_with_class_list(self, active_units):
        # Identify each unit with lms build
        units = self._filter_active_lms_units(active_units)
        for unit in units:
            unit_id = unit['id']
            unit_obj = UnitFactory.create_unit_object(unit_id=unit_id, env_dict=self.env_dict)    
            self.active_students = self._get_active_students(unit=unit)
            new_student_emails = [student['email'].lower() for student in self.active_students]

            workouts = self.db_queries.get_children(parent_id=unit_id, child_collection=DbCollections.WORKOUT)
            for workout in workouts:
                student_email = workout.get('student_email', '').lower()
                if student_email in new_student_emails:
                    new_student_emails.remove(student_email)
            for student in self.active_students:
                active_email = student['email'].lower()
                if student['email'].lower() in new_student_emails:
                    unit_obj.add_student_workout_record(student_email=active_email, student_name=student['name'])

            # Update unit object with new roster count
            if new_student_emails:
                unit['workspace_settings']['count'] = len(self.active_students)
                if unit := ModelValidator(model=UnitModel, log_location=self.log_name).load(data=unit, as_dict=True):
                    self.db.update(collection_name=DbCollections.UNIT, doc_id=unit_id, data=unit)

    def sync_classes_with_db(self):
        raise NotImplementedError('sync_classes_with_db not implemented for this object')

    def _filter_active_lms_units(self, active_units):
        raise NotImplementedError("_get_active_lms_units not implemented for this object.")

    def _get_active_students(self, unit):
        raise NotImplementedError("_get_active_students not implemented for this object.")
