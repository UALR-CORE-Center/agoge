from typing import List

from common.constants.database import DbCollections, DATABASE_NAME, DatabaseTypes
from common.document_database import DocumentDatabaseFactory, DatabaseQueries
from common.utilities.gcp.cloud_env import CloudEnv

from .canvas.lms_canavas_synchronizer import LMSCanvasSynchronizer
from .google_classroom.lms_google_classroom_synchronizer import LMSGoogleClassroomSynchronizer


class LMSSynchronizerFactory:
    def __init__(
        self,
        env_dict: dict = None
    ) -> None:
        self.env = CloudEnv(env_dict=env_dict) if env_dict else CloudEnv()
        self.env_dict = self.env.get_env()
        self.class_name = self.__class__.__name__
        self.db = DocumentDatabaseFactory.create_db_object(
            db_type=DatabaseTypes.firestore,
            database_name=DATABASE_NAME
        )
        self.db_queries = DatabaseQueries(db=self.db)

    def sync_units_with_class_list(self):
        units = self._get_active_lms_units()
        LMSCanvasSynchronizer(env_dict=self.env_dict).sync_units_with_class_list(units)
        if self.env.classroom_user:
            LMSGoogleClassroomSynchronizer(env_dict=self.env_dict).sync_units_with_class_list(units)

    def _get_active_lms_units(self) -> List[dict]:
        return self.db_queries.get_active(collection_name=DbCollections.UNIT)

    def sync_classes_with_db(self):
        if self.env.classroom_user:
            LMSGoogleClassroomSynchronizer(env_dict=self.env_dict).sync_classes_with_db()

# [ eof ]
