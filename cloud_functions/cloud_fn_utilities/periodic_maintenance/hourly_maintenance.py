import time

from common.constants.database import DbCollections, DatabaseTypes, DATABASE_NAME
from common.document_database import DocumentDatabaseFactory, DatabaseQueries
from common.constants.pub_sub import PubSub
from common.exceptions import NotFound, BadRequest, BaseAgogeException
from common.models.agoge import SnapshotsModel
from common.utilities.gcp.pubsub_manager import PubSubManager
from common.utilities.gcp.cloud_env import CloudEnv
from common.utilities.gcp.cloud_logger import Logger, LoggerNames
from ..course_objects.unit.factory_unit import UnitFactory
from ..course_objects.workout.factory_workout import WorkoutFactory
from ..course_objects.compute.factory import ComputeManagerFactory
from ..lms.lms_synchronizer_factory import LMSSynchronizerFactory


class HourlyMaintenance:
    def __init__(
        self,
        debug: bool = False,
        env_dict: dict = None
    ) -> None:
        self.class_name = self.__class__.__name__
        self.logger = Logger(LoggerNames.CLOUD_FN, class_name=self.class_name)
        self.debug = debug
        self.env = CloudEnv(env_dict=env_dict) if env_dict else CloudEnv()
        self.env_dict = self.env.get_env()
        self.pub_sub_mgr = PubSubManager(PubSub.Topics.AGOGE, env_dict=self.env_dict)
        self.db = DocumentDatabaseFactory.create_db_object(
            db_type=DatabaseTypes.firestore,
            database_name=DATABASE_NAME
        )
        self.db_queries = DatabaseQueries(db=self.db)
        self.snapshot_manager = ComputeManagerFactory.create_manager_object(env_dict=env_dict)

    def run(self) -> None:
        self.logger.info(f"{self.class_name} - Completed deleting expired classes")
        self.logger.info(f"{self.class_name} - Beginning to delete expired units")
        self._delete_expired_units()
        self.logger.info(f"{self.class_name} - Beginning to delete expired workouts")
        self._delete_expired_workouts()
        self.logger.info(f"{self.class_name} - Completed deleting expired workouts")
        self._delete_expired_snapshots()
        self.logger.info(f"{self.class_name} - Completed deleting expired workout snapshots")
        self.logger.info(f"{self.class_name} - Beginning to sync LMS students with active workouts")
        self._lms_sync()
        self.logger.info(f"{self.class_name} - Completed syncing LMS students")

    def _delete_expired_units(self) -> None:
        expired_units = self.db_queries.get_expired(collection_name=DbCollections.UNIT)

        deleted = 0
        for unit in expired_units:
            build_id = unit['id']
            if self.debug:
                try:
                    unit = UnitFactory.create_unit_object(
                        unit_id=build_id, debug=self.debug,
                        env_dict=self.env_dict
                    )
                    unit.delete()
                except ValueError as e:
                    self.logger.warning(f"{self.class_name}:{build_id} - "
                                        f"Error when attempting to delete Unit: {e}")
            else:
                self.pub_sub_mgr.msg(
                    handler=str(PubSub.Handlers.CONTROL.value),
                    course_object=str(PubSub.CourseObjects.UNIT.value),
                    build_id=build_id,
                    action=str(PubSub.Actions.DELETE.value)
                )
            deleted += 1
        self.logger.info(f"{self.class_name} - Completed deleting {deleted} expired units")

    def _delete_expired_workouts(self) -> None:
        """
        For long-running units used in asynchronous classes, workouts may be deleted before the unit expires. This
        keeps the project clear of stale workouts during the asynchronous class.
        """
        deleted = 0
        workouts = self.db_queries.get_expired(collection_name=DbCollections.WORKOUT)
        for workout in workouts:
            build_id = workout['id']
            if self.debug:
                workout_obj = WorkoutFactory.create_workout_object(
                    workout_id=build_id, debug=self.debug,
                    env_dict=self.env_dict
                )
                workout_obj.delete()
            else:
                self.pub_sub_mgr.msg(
                    handler=str(PubSub.Handlers.CONTROL.value),
                    course_object=str(PubSub.CourseObjects.WORKOUT.value),
                    build_id=build_id,
                    action=str(PubSub.Actions.DELETE.value)
                )
                time.sleep(20)
            deleted += 1

        self.logger.info(f"{self.class_name} - Deleted {deleted} expired workouts")

    def _lms_sync(self) -> None:
        """
        LMS units may have students added throughout the course, and this adds their workouts to units when a new
        student gets added to the LMS
        """
        if self.debug:
            LMSSynchronizerFactory().sync_units_with_class_list()
        else:
            message_attr = {
                PubSub.EventAttributes.HANDLER: PubSub.Handlers.CONTROL.value,
                PubSub.EventAttributes.COURSE_OBJECT: PubSub.CourseObjects.LMS.value,
                PubSub.EventAttributes.ACTION: PubSub.Actions.SYNC.value,
                PubSub.EventAttributes.IMAGE_NAME: PubSub.CourseObjects.LMS.value
            }
            self.pub_sub_mgr.msg(**message_attr)

    def _delete_expired_snapshots(self) -> None:
        # TODO: Determine the best way of keeping the following query as small as possible
        snapshots_records = self.db_queries.get_expired(collection_name=DbCollections.SNAPSHOTS)
        for server in snapshots_records:
            snapshots_model = SnapshotsModel(**server)
            if (server_snapshots := snapshots_model.snapshots) is not None:
                for snapshot in server_snapshots:
                    if self.debug:
                        try:
                            self.snapshot_manager.load(server_name=snapshots_model.server_id)
                            self.snapshot_manager.delete_snapshot(snapshot.name)
                        except (NotFound, BadRequest, BaseAgogeException) as e:
                            continue
                    else:
                        self.pub_sub_mgr.msg(
                            handler=str(PubSub.Handlers.CONTROL.value),
                            action=str(PubSub.Actions.DELETE.value),
                            server_name=str(snapshots_model.server_id),
                            snapshot_name=snapshot.name,
                            course_object=str(PubSub.CourseObjects.SNAPSHOT.value)
                        )
