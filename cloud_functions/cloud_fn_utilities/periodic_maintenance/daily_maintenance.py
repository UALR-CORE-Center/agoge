from common.constants.enumerators import SnapshotTypes, ImageScopes
from common.document_database import DocumentDatabaseFactory, DatabaseQueries
from common.utilities.gcp.cloud_env import CloudEnv
from common.utilities.gcp.cloud_logger import LoggerNames
from common.utilities.gcp.pubsub_manager import PubSubManager
from common.constants.pub_sub import PubSub
from common.constants.database import DbCollections, DATABASE_NAME, DatabaseTypes
from common.models.agoge import UnitModel
from common.models.model_validators.model_validator import ModelValidator
from common.utilities.timestamps import Timestamps
from ..course_objects.compute.snapshot_manager import SnapshotManager
from ..course_objects.workout.factory_workout import WorkoutFactory
from ..course_objects.vulnerabilities import Vulnerabilities
from ..course_objects.compute.google_image_sync_manager import GoogleImageSyncManager
from ..course_objects.compute.project_server_manager import ProjectServerManager
from ..course_objects.compute.factory import ComputeManagerFactory
from ..send_mail.send_mail import SendMail


class DailyMaintenance:
    def __init__(
        self,
        debug: bool = False,
        env_dict: dict = None
    ) -> None:
        self.log_name = LoggerNames.CLOUD_FN
        self.env = CloudEnv(env_dict=env_dict) if env_dict else CloudEnv()
        self.env_dict = self.env.get_env()
        self.project_server_manager = ProjectServerManager(env_dict=self.env.get_env())
        self.pub_sub_mgr = PubSubManager(PubSub.Topics.AGOGE, env_dict=self.env.get_env())
        self.debug = debug
        self.db = DocumentDatabaseFactory.create_db_object(
            db_type=DatabaseTypes.firestore,
            database_name=DATABASE_NAME
        )
        self.db_query = DatabaseQueries(db=self.db)
        self.snapshot_manager = SnapshotManager(env_dict=env_dict, debug=debug)

    def run(self):
        # Stop all lab servers, template servers, and instances
        self._stop_all()

        # Notify instructors of lab expiry within 48 hours
        self._notify_expiring_units()

        # Snapshot built workout servers
        self._snapshot_workouts()

        # Update project databases
        self._sync_google_images()
        self._update_nvd_database()

    def _stop_all(self):
        # Stop any running workouts
        running_workouts = self.db_query.get_running(collection_name=DbCollections.WORKOUT)
        for workout in running_workouts:
            workout_id = workout['id']
            if self.debug:
                workout_obj = WorkoutFactory.create_workout_object(workout_id=workout_id, env_dict=self.env_dict)
                workout_obj.stop()
            else:
                message_attr = {
                    PubSub.EventAttributes.HANDLER: PubSub.Handlers.CONTROL.value,
                    PubSub.EventAttributes.ACTION: PubSub.Actions.STOP.value,
                    PubSub.EventAttributes.COURSE_OBJECT: PubSub.CourseObjects.WORKOUT.value,
                    PubSub.EventAttributes.BUILD_ID: workout_id,
                }
                self.pub_sub_mgr.msg(**message_attr)

        # Stop any running checked out template servers
        image_mgr = ComputeManagerFactory.create_manager_object(
            manager_type=PubSub.CourseObjects.TEMPLATE_SERVER,
            env_dict=self.env_dict
        )
        image_mgr.stop_all_running()

        # Stop any remaining compute instances
        self.project_server_manager.stop_everything()

    def _notify_expiring_units(self):
        """
        sends an email to the owner of all units that expire within 48 hours
        @return:
        """
        try:
            mail = SendMail()
        except ValueError:
            return

        expiring_units = self.db_query.get_expiring_units()
        for expiring_unit in expiring_units:
            if unit := ModelValidator(UnitModel, log_location=self.log_name).load(expiring_unit, halt_on_error=False):
                workout_name = unit.summary.name
                instructors = unit.instructor_id
                num_workouts = unit.workspace_settings.count
                expires = unit.workspace_settings.expires

                hours_until_expired = round((expires - Timestamps.get_current_timestamp_utc()) / 3600)
                if hours_until_expired >= 0:
                    if isinstance(instructors, list):
                        for instructor in instructors:
                            mail.send_expiring_units(
                                unit_id=unit.id,
                                workout_name=workout_name,
                                instructor=instructor,
                                num_workouts=num_workouts,
                                hours_until_expires=hours_until_expired
                            )
                    else:
                        mail.send_expiring_units(
                            unit_id=unit.id,
                            workout_name=workout_name,
                            instructor=instructors,
                            num_workouts=num_workouts,
                            hours_until_expires=hours_until_expired
                        )

    def _snapshot_workouts(self):
        active_workouts = self.db_query.get_active(DbCollections.WORKOUT)
        for workout in active_workouts:
            workout_id = workout['id']
            if 'expires' not in workout:
                continue
            if workout.get('servers'):
                if self.debug:
                    self.snapshot_manager.snapshot_lab_workout(workout_id, workout=workout)
                else:
                    message_attr = {
                        PubSub.EventAttributes.HANDLER: PubSub.Handlers.CONTROL.value,
                        PubSub.EventAttributes.ACTION: PubSub.Actions.SNAPSHOT.value,
                        PubSub.EventAttributes.COURSE_OBJECT: PubSub.CourseObjects.WORKOUT.value,
                        PubSub.EventAttributes.BUILD_ID: workout_id,
                        PubSub.EventAttributes.SNAPSHOT_TYPE: SnapshotTypes.AUTO.value
                    }
                    self.pub_sub_mgr.msg(**message_attr)

    def _sync_google_images(self) -> None:
        # Update database with available public images provided by Google
        if self.debug:
            GoogleImageSyncManager(env=self.env_dict).sync()
        else:
            message_attr = {
                PubSub.EventAttributes.HANDLER: PubSub.Handlers.CONTROL.value,
                PubSub.EventAttributes.ACTION: PubSub.Actions.SYNC.value,
                PubSub.EventAttributes.IMAGE_NAME: ImageScopes.GLOBAL.value,
                PubSub.EventAttributes.COURSE_OBJECT: PubSub.CourseObjects.PUBLIC_IMAGE.value
            }
            self.pub_sub_mgr.msg(**message_attr)

    def _update_nvd_database(self) -> None:
        if self.debug:
            Vulnerabilities().update()
        else:
            message_attr = {
                PubSub.EventAttributes.HANDLER: PubSub.Handlers.CONTROL.value,
                PubSub.EventAttributes.ACTION: PubSub.Actions.SYNC.value,
                PubSub.EventAttributes.IMAGE_NAME: ImageScopes.GLOBAL.value,
                PubSub.EventAttributes.COURSE_OBJECT: PubSub.CourseObjects.NVD.value
            }
            self.pub_sub_mgr.msg(**message_attr)
