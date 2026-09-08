from cloud_fn_utilities.course_objects.compute.snapshot_manager import SnapshotManager
from cloud_fn_utilities.course_objects.vulnerabilities import Vulnerabilities
from cloud_fn_utilities.lms.lms_synchronizer_factory import LMSSynchronizerFactory
from common.constants.enumerators import SnapshotTypes
from common.constants.pub_sub import PubSub
from common.constants.database import DatabaseTypes, DATABASE_NAME
from common.document_database import DocumentDatabaseFactory
from common.utilities.gcp.cloud_env import CloudEnv
from common.utilities.gcp.cloud_logger import Logger, LoggerNames
from common.utilities.gcp.pubsub_manager import PubSubManager

from cloud_fn_utilities.course_objects.compute.google_image_sync_manager import GoogleImageSyncManager
from cloud_fn_utilities.course_objects.compute.factory import ComputeManagerFactory
from cloud_fn_utilities.course_objects.unit.factory_unit import UnitFactory
from cloud_fn_utilities.course_objects.workout.factory_workout import WorkoutFactory


class ControlHandler:
    def __init__(
        self,
        event_attributes,
        env_dict: dict = None,
        debug: bool = False
    ) -> None:
        self.class_name = self.__class__.__name__
        self.event_attributes = event_attributes
        self.env = CloudEnv(env_dict=env_dict) if env_dict else CloudEnv()
        self.env_dict = self.env.get_env()
        self.debug = debug
        self.logger = Logger(LoggerNames.CLOUD_FN, class_name=self.class_name)
        self.pub_sub_mgr = PubSubManager(PubSub.Topics.AGOGE, env_dict=self.env_dict)
        self.db = DocumentDatabaseFactory.create_db_object(
            db_type=DatabaseTypes.firestore,
            database_name=DATABASE_NAME
        )
        self.event_attr_keys = PubSub.EventAttributes
        self.action = self.event_attributes.get(self.event_attr_keys.ACTION, None)
        self.course_object = self.event_attributes.get(self.event_attr_keys.COURSE_OBJECT, None)
        self.build_id = self.event_attributes.get(self.event_attr_keys.BUILD_ID, None)
        self.image_name = self.event_attributes.get(self.event_attr_keys.IMAGE_NAME, None)
        self.user = self.event_attributes.get(self.event_attr_keys.USER, None)
        self.snapshot_name = self.event_attributes.get(self.event_attr_keys.SNAPSHOT_NAME, None)
        self.server_name = self.event_attributes.get(self.event_attr_keys.SERVER_NAME, None)
        self.network_prefix = self.event_attributes.get(
            self.event_attr_keys.NETWORK_PREFIX,
            None,
        )
        self.expires = self.event_attributes.get(self.event_attr_keys.EXPIRES, None)
        self.snapshot_type = self.event_attributes.get(self.event_attr_keys.SNAPSHOT_TYPE, SnapshotTypes.AUTO.value)

        if not self.action:
            self.logger.error(f"{self.class_name} - No action provided in cloud function control handler")
            raise ValueError

        if not self.image_name and not self.server_name:
            if not self.course_object:
                self.logger.error(f"{self.class_name}:{self.action} - No course object provided for control "
                                  f"handler action.")
                raise ValueError

            if not self.build_id:
                self.logger.error(f"{self.class_name}:{self.action} - No build id provided for control handler action.")
                raise ValueError

        self.action_map = {
            str(PubSub.Actions.START.value): self._start,
            str(PubSub.Actions.STOP.value): self._stop,
            str(PubSub.Actions.DELETE.value): self._delete,
            str(PubSub.Actions.NUKE.value): self._nuke,
            str(PubSub.Actions.EXTEND_RUNTIME.value): self._extend_runtime,
            str(PubSub.Actions.SNAPSHOT.value): self._snapshot,
            str(PubSub.Actions.RESTORE.value): self._snapshot_restore,
            str(PubSub.Actions.SYNC.value): self._sync,
            str(PubSub.Actions.CHECK_IN.value): self._check_in,
            str(PubSub.Actions.CHECK_OUT.value): self._check_out,
            str(PubSub.Actions.CANCEL.value): self._cancel_image_changes,
        }

    def route(self) -> None:
        action_func = self.action_map.get(self.action)
        if action_func is None:
            self.logger.error(
                f"{self.class_name}:{self.action} - Unsupported action supplied to the control handler",
                action=self.action
            )
            raise ValueError

        # Perform action
        action_func()

    def _start(self) -> None:
        if self.course_object == str(PubSub.CourseObjects.LAB_SERVER.value):
            cm = ComputeManagerFactory.create_manager_object(env_dict=self.env_dict)
            cm.load(server_name=self.build_id)
            cm.start()
        elif self.course_object == str(PubSub.CourseObjects.WORKOUT.value):
            duration_hours = self.event_attributes.get(self.event_attr_keys.DURATION, 2)
            workout = WorkoutFactory.create_workout_object(
                workout_id=self.build_id,
                duration_hours=duration_hours,
                debug=self.debug,
                env_dict=self.env_dict
            )
            workout.start()
        elif self.course_object == str(PubSub.CourseObjects.UNIT.value):
            unit = UnitFactory.create_unit_object(
                unit_id=self.build_id,
                debug=self.debug,
                env_dict=self.env_dict
            )
            unit.start()
        elif self.course_object == str(PubSub.CourseObjects.TEMPLATE_SERVER.value) and self.image_name:
            cm = ComputeManagerFactory.create_manager_object(
                manager_type=PubSub.CourseObjects.TEMPLATE_SERVER,
                env_dict=self.env_dict,
                user=self.user
            )
            cm.load(server_name=self.image_name)
            cm.start_server()
        else:
            self.logger.error(
                f"{self.class_name}:{self.action} - Unsupported object passed to the control "
                f"handler for action",
                course_object=self.course_object,
                action=self.action,
            )
            raise ValueError

    def _stop(self) -> None:
        if self.course_object == str(PubSub.CourseObjects.LAB_SERVER.value):
            cm = ComputeManagerFactory.create_manager_object(env_dict=self.env_dict)
            cm.load(server_name=self.build_id)
            cm.stop()
        elif self.course_object == str(PubSub.CourseObjects.WORKOUT.value):
            workout = WorkoutFactory.create_workout_object(
                workout_id=self.build_id,
                debug=self.debug,
                env_dict=self.env_dict
            )
            workout.stop()
        elif self.course_object == str(PubSub.CourseObjects.UNIT.value):
            unit = UnitFactory.create_unit_object(
                unit_id=self.build_id,
                debug=self.debug,
                env_dict=self.env_dict
            )
            unit.stop()
        elif self.course_object == str(PubSub.CourseObjects.TEMPLATE_SERVER.value) and self.image_name:
            cm = ComputeManagerFactory.create_manager_object(
                manager_type=PubSub.CourseObjects.TEMPLATE_SERVER,
                env_dict=self.env_dict,
                user=self.user
            )
            cm.load(server_name=self.image_name)
            cm.stop_server()
        else:
            self.logger.error(
                f"{self.class_name}:{self.action} - Unsupported object passed to the "
                f"control handler for action",
                course_object=self.course_object,
                action=self.action,
            )
            raise ValueError
            
    def _delete(self) -> None:
        if self.course_object == str(PubSub.CourseObjects.LAB_SERVER.value):
            cm = ComputeManagerFactory.create_manager_object(env_dict=self.env_dict)
            cm.load(server_name=self.build_id)
            cm.delete()
        elif self.course_object == str(PubSub.CourseObjects.WORKOUT.value):
            workout = WorkoutFactory.create_workout_object(
                workout_id=self.build_id,
                debug=self.debug,
                env_dict=self.env_dict
            )
            workout.delete()
        elif self.course_object == str(PubSub.CourseObjects.UNIT.value):
            unit = UnitFactory.create_unit_object(
                unit_id=self.build_id,
                debug=self.debug,
                env_dict=self.env_dict
            )
            unit.delete()
        elif self.course_object == str(PubSub.CourseObjects.TEMPLATE_SERVER.value):
            cm = ComputeManagerFactory.create_manager_object(
                manager_type=PubSub.CourseObjects.TEMPLATE_SERVER,
                env_dict=self.env_dict
            )
            cm.load(server_name=self.image_name)
            cm.delete_server(state_transition=False)
        elif self.course_object == str(PubSub.CourseObjects.IMAGE.value):
            cm = ComputeManagerFactory.create_manager_object(
                manager_type=PubSub.CourseObjects.TEMPLATE_SERVER,
                env_dict=self.env_dict
            )
            cm.load(server_name=self.image_name)
            cm.delete()
        elif self.course_object == str(PubSub.CourseObjects.SNAPSHOT.value):
            server_type = self.event_attributes.get(self.event_attr_keys.SERVER_TYPE)
            if server_type == str(PubSub.CourseObjects.TEMPLATE_SERVER.value):
                server_type = PubSub.CourseObjects.TEMPLATE_SERVER
            else:
                server_type = PubSub.CourseObjects.LAB_SERVER

            snapshot_manager = SnapshotManager(
                server_type=server_type,
                env_dict=self.env_dict,
                debug=self.debug
            )
            snapshot_manager.load(server_name=self.server_name)
            snapshot_manager.delete_snapshot(snapshot_name=self.snapshot_name)
        else:
            self.logger.error(
                f"{self.class_name}:{self.action} - Unsupported object {self.course_object} "
                f"passed to the control handler for action",
                action=self.action,
                course_object=self.course_object
            )
            raise ValueError

    def _nuke(self) -> None:
        if self.course_object == str(PubSub.CourseObjects.LAB_SERVER.value):
            cm = ComputeManagerFactory.create_manager_object(env_dict=self.env_dict)
            cm.load(
                server_name=self.build_id,
                network_prefix=self.network_prefix,
            )
            cm.nuke()
        elif self.course_object == str(PubSub.CourseObjects.WORKOUT.value):
            workout = WorkoutFactory.create_workout_object(
                workout_id=self.build_id,
                debug=self.debug,
                env_dict=self.env_dict
            )
            workout.nuke()
        else:
            self.logger.error(
                f"{self.class_name}:{self.action} - Unsupported object passed to the control handler "
                f"for action.",
                course_object=self.course_object,
                action=self.action,
            )
            raise ValueError

    def _extend_runtime(self) -> None:
        duration = self.event_attributes.get(self.event_attr_keys.DURATION, 1)
        if self.course_object == str(PubSub.CourseObjects.WORKOUT.value):
            workout = WorkoutFactory.create_workout_object(
                workout_id=self.build_id,
                debug=self.debug,
                duration_hours=duration,
                env_dict=self.env_dict
            )
            workout.extend_runtime()
        else:
            self.logger.error(
                f'{self.class_name}:{self.action} - Unsupported object passed to the control handler for '
                f'action.',
                course_object=self.course_object,
                action=self.action,
            )
            raise ValueError

    def _check_in(self) -> None:
        image_manager = ComputeManagerFactory.create_manager_object(
            manager_type=PubSub.CourseObjects.TEMPLATE_SERVER,
            env_dict=self.env_dict
        )
        image_manager.load(server_name=self.image_name)
        image_manager.check_in()

    def _check_out(self) -> None:
        image_manager = ComputeManagerFactory.create_manager_object(
            manager_type=PubSub.CourseObjects.TEMPLATE_SERVER,
            env_dict=self.env_dict,
            user=self.user
        )
        image_manager.load(server_name=self.image_name)
        image_manager.check_out()

    def _snapshot(self) -> None:
        if self.course_object == str(PubSub.CourseObjects.TEMPLATE_SERVER.value):
            snapshot_manager = SnapshotManager(
                server_type=PubSub.CourseObjects.TEMPLATE_SERVER,
                env_dict=self.env_dict,
                debug=self.debug,
                snapshot_type=self.snapshot_type
            )
            snapshot_manager.load(self.server_name)
            snapshot_manager.create_snapshot()
        elif self.course_object == str(PubSub.CourseObjects.LAB_SERVER.value):
            snapshot_manager = SnapshotManager(
                server_type=PubSub.CourseObjects.LAB_SERVER,
                env_dict=self.env_dict,
                debug=self.debug,
                snapshot_type=self.snapshot_type
            )
            snapshot_manager.load(self.server_name)
            snapshot_manager.create_snapshot(expiration_date=self.expires)
        elif self.course_object == str(PubSub.CourseObjects.WORKOUT.value):
            snapshot_manager = SnapshotManager(
                server_type=PubSub.CourseObjects.WORKOUT,
                env_dict=self.env_dict,
                debug=self.debug,
                snapshot_type=self.snapshot_type
            )
            snapshot_manager.snapshot_lab_workout(workout_id=self.build_id)

    def _snapshot_restore(self) -> None:
        if self.course_object in [
            str(PubSub.CourseObjects.LAB_SERVER.value),
            str(PubSub.CourseObjects.TEMPLATE_SERVER.value)
        ]:
            if self.course_object == str(PubSub.CourseObjects.TEMPLATE_SERVER.value):
                server_type = PubSub.CourseObjects.TEMPLATE_SERVER
            else:
                server_type = PubSub.CourseObjects.LAB_SERVER

            snapshot_manager = SnapshotManager(
                server_type=server_type,
                env_dict=self.env_dict,
                debug=self.debug
            )
            snapshot_manager.load(self.server_name)
            snapshot_manager.restore_from_snapshot(snapshot_name=self.snapshot_name)
        else:
            self.logger.error(
                f'{self.class_name}:{self.action} - Unsupported object {self.course_object} '
                f'pass to the control handler for snapshot_restore',
                course_object=self.course_object,
                action=self.action
            )
            raise ValueError

    def _cancel_image_changes(self) -> None:
        image_manager = ComputeManagerFactory.create_manager_object(
            manager_type=PubSub.CourseObjects.TEMPLATE_SERVER,
            env_dict=self.env_dict
        )
        image_manager.load(server_name=self.image_name)
        image_manager.cancel()

    def _sync(self) -> None:
        if self.course_object == str(PubSub.CourseObjects.PUBLIC_IMAGE.value):
            GoogleImageSyncManager(env=self.env_dict).sync()
        elif self.course_object == str(PubSub.CourseObjects.NVD.value):
            Vulnerabilities().update()
        elif self.course_object == str(PubSub.CourseObjects.LMS.value):
            # LMS units may have students added throughout the course, and this adds their
            # workouts to units when a new student gets added to the LMS
            LMSSynchronizerFactory().sync_units_with_class_list()
