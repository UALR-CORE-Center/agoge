from common.constants.database import DbCollections, DatabaseTypes, DATABASE_NAME
from common.constants.pub_sub import PubSub
from common.document_database import DocumentDatabaseFactory, DatabaseQueries
from common.utilities.gcp.cloud_env import CloudEnv
from common.utilities.gcp.pubsub_manager import PubSubManager
from ..course_objects.workout.factory_workout import WorkoutFactory
from ..lms.lms_synchronizer_factory import LMSSynchronizerFactory


class QuarterHourlyMaintenance:
    def __init__(
        self,
        debug: bool = False,
        env_dict: dict = None
    ) -> None:
        self.debug = debug
        self.env = CloudEnv(env_dict=env_dict) if env_dict else CloudEnv()
        self.env_dict = self.env.get_env()
        self.db = DocumentDatabaseFactory.create_db_object(
            db_type=DatabaseTypes.firestore,
            database_name=DATABASE_NAME
        )
        self.db_queries = DatabaseQueries(db=self.db)
        self.pub_sub_mgr = PubSubManager(PubSub.Topics.AGOGE, env_dict=self.env_dict)

    def run(self) -> None:
        self._stop_lapsed()
        self._sync_lms_courses()

    def _stop_lapsed(self) -> None:
        workouts = self.db_queries.get_ready_for_shutoff(collection_name=DbCollections.WORKOUT)
        for workout in workouts:
            workout_id = workout['id']
            if self.debug:
                workout_obj = WorkoutFactory.create_workout_object(workout_id=workout_id, env_dict=self.env_dict)
                workout_obj.stop()
            else:
                self.pub_sub_mgr.msg(
                    handler=str(PubSub.Handlers.CONTROL.value),
                    course_object=str(PubSub.CourseObjects.WORKOUT.value),
                    build_id=workout_id,
                    action=str(PubSub.Actions.STOP.value)
                )

    def _sync_lms_courses(self) -> None:
        LMSSynchronizerFactory(env_dict=self.env_dict).sync_classes_with_db()
