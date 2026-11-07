import json
from datetime import datetime, timezone

from cloud_fn_utilities.course_objects.compute.snapshot_manager import SnapshotManager
from cloud_fn_utilities.build_execution import server_owner
from cloud_fn_utilities.course_objects.vulnerabilities import Vulnerabilities
from cloud_fn_utilities.lms.lms_synchronizer_factory import LMSSynchronizerFactory
from common.constants.enumerators import SnapshotTypes
from common.constants.pub_sub import PubSub
from common.constants.database import DatabaseTypes, DATABASE_NAME, DbCollections
from common.constants.states import ServerStates, UnitStates
from common.document_database import DocumentDatabaseFactory
from common.utilities.build_incidents import BuildIncidents
from common.utilities.gcp.cloud_env import CloudEnv
from common.utilities.gcp.cloud_logger import Logger, LoggerNames
from common.utilities.gcp.compute.quota_failure import ComputeQuotaFailure
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
        self.event_id = None
        self.env = CloudEnv(env_dict=env_dict) if env_dict else CloudEnv()
        self.env_dict = self.env.get_env()
        self.debug = debug
        # This field is issued by the authenticated API, never a user payload.
        self.shared_edit_authorized = event_attributes.get('shared_edit_authorized') == 'true'
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
            str(PubSub.Actions.NESTED_FINALIZE.value): self._nested_finalize,
        }

    def route(self) -> None:
        action_func = self.action_map.get(self.action)
        if action_func is None:
            self.logger.error(
                f"{self.class_name}:{self.action} - Unsupported action supplied to the control handler",
                action=self.action
            )
            raise ValueError

        if self.action == str(PubSub.Actions.DELETE.value):
            self._tracked_delete(action_func)
        elif self.action == str(PubSub.Actions.START.value) and self._lab_start_is_stale():
            self.logger.info('Skipped starting a failed or deleted lab', build_id=self.build_id)
        else:
            action_func()

    def _lab_start_is_stale(self):
        if self.course_object == str(PubSub.CourseObjects.UNIT.value):
            collection, target_id = DbCollections.UNIT, self.build_id
        elif self.course_object == str(PubSub.CourseObjects.WORKOUT.value):
            collection, target_id = DbCollections.WORKOUT, self.build_id
        elif self.course_object == str(PubSub.CourseObjects.LAB_SERVER.value):
            server = self.db.get(DbCollections.SERVER, self.build_id) or {}
            if not server or (server.get('state') or 0) >= ServerStates.DELETING.value:
                return True
            collection, target_id = server_owner(self.db, self.build_id)
            if not collection:
                return True
        else:
            return False

        def unavailable(record):
            return (not record or record.get('build_failure_id')
                    or (record.get('state') or 0) >= UnitStates.DELETING_SERVERS.value)

        target = self.db.get(collection, target_id) or {}
        if unavailable(target):
            return True
        if collection == DbCollections.WORKOUT and target.get('parent_id'):
            return bool(unavailable(self.db.get(DbCollections.UNIT, target['parent_id'])))
        return False

    def _tracked_delete(self, delete):
        unit_kind = str(PubSub.CourseObjects.UNIT.value)
        workout_kind = str(PubSub.CourseObjects.WORKOUT.value)
        server_kind = str(PubSub.CourseObjects.LAB_SERVER.value)
        if self.course_object == unit_kind:
            collection, target_id = DbCollections.UNIT, self.build_id
        elif self.course_object == workout_kind:
            collection, target_id = DbCollections.WORKOUT, self.build_id
        elif self.course_object == server_kind:
            collection, target_id = server_owner(self.db, self.build_id)
        else:
            collection, target_id = None, None
        if not target_id:
            delete()
            return

        target = self.db.get(collection, target_id) or {}
        workout_id = target_id if collection == DbCollections.WORKOUT else None
        unit_id = target.get('parent_id') if workout_id else target_id
        if not unit_id:
            delete()
            return

        location = {
            'unit_id': unit_id,
            'workout_id': workout_id,
            'attempt_id': target.get('build_attempt_id'),
        }
        incidents = BuildIncidents(self.db, self.env.project)
        try:
            deleted = delete()
            if deleted is False:
                raise ConnectionError('Lab server deletion was not confirmed')
            if self.course_object == server_kind:
                # Only the owner knows whether the rest of the lab is gone.
                return
            target = self.db.get(collection, target_id) or {}
            if target.get('state') != UnitStates.DELETED.value:
                raise ConnectionError('Lab deletion was not confirmed')
        except Exception:
            incidents.record_cleanup_failure(**location, event_id=self.event_id,
                                             stage='server_cleanup' if self.course_object == server_kind else 'cleanup')
            raise

        incidents.resolve_target(**location)

    def _start(self) -> None:
        if self.course_object == str(PubSub.CourseObjects.LAB_SERVER.value):
            cm = ComputeManagerFactory.create_manager_object(env_dict=self.env_dict)
            cm.load(server_name=self.build_id)
            claim = self.event_attributes.get('community_start_claim')
            cm.start(**({'community_start_claim': claim} if claim else {}))
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
                shared_edit_authorized=self.shared_edit_authorized,
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
            claim = self.event_attributes.get('community_stop_claim')
            cm.stop(**({'community_stop_claim': claim} if claim else {}))
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
                shared_edit_authorized=self.shared_edit_authorized,
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
            return cm.delete()
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
                shared_edit_authorized=self.shared_edit_authorized,
                env_dict=self.env_dict
            )
            cm.load(server_name=self.image_name)
            cm.delete_server(state_transition=False)
        elif self.course_object == str(PubSub.CourseObjects.IMAGE.value):
            cm = ComputeManagerFactory.create_manager_object(
                manager_type=PubSub.CourseObjects.TEMPLATE_SERVER,
                shared_edit_authorized=self.shared_edit_authorized,
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
                shared_edit_authorized=self.shared_edit_authorized,
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
            try:
                cm.nuke()
            except ComputeQuotaFailure as error:
                if error.category != 'allocation' or not getattr(self, 'event_id', None):
                    raise
                collection, target_id = server_owner(self.db, self.build_id)
                if not target_id:
                    raise
                target = self.db.get(collection, target_id) or {}
                workout_id = target_id if collection == DbCollections.WORKOUT else None
                unit_id = target.get('parent_id') if workout_id else target_id
                BuildIncidents(self.db, self.env.project).record_quota(
                    error, unit_id=unit_id, workout_id=workout_id, stage='server_rebuild',
                    event_id=self.event_id, attempt_id=target.get('build_attempt_id'),
                    target_patch={'state': UnitStates.BROKEN.value,
                                  'state_timestamp': datetime.now(timezone.utc).isoformat(),
                                  **({'active': False} if workout_id else {})},
                )
        elif self.course_object == str(PubSub.CourseObjects.WORKOUT.value):
            workout = WorkoutFactory.create_workout_object(
                workout_id=self.build_id,
                debug=self.debug,
                env_dict=self.env_dict
            )
            workout.rebuild_event_id = getattr(self, 'event_id', None)
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
            shared_edit_authorized=self.shared_edit_authorized,
            env_dict=self.env_dict
        )
        image_manager.load(server_name=self.image_name)
        image_manager.check_in()

    def _nested_finalize(self) -> None:
        image_manager = ComputeManagerFactory.create_manager_object(
            manager_type=PubSub.CourseObjects.TEMPLATE_SERVER,
            shared_edit_authorized=self.shared_edit_authorized,
            env_dict=self.env_dict,
            user=self.user
        )
        image_manager.load(server_name=self.image_name)
        image_manager.finalize_nested()

    def _check_out(self) -> None:
        image_manager = ComputeManagerFactory.create_manager_object(
            manager_type=PubSub.CourseObjects.TEMPLATE_SERVER,
            shared_edit_authorized=self.shared_edit_authorized,
            env_dict=self.env_dict,
            user=self.user
        )
        image_manager.load(server_name=self.image_name)
        image_manager.check_out(product_keys=self._product_keys())

    def _product_keys(self) -> dict:
        """Guest -> Windows product key from a nested create's CHECK_OUT; the keys are never persisted."""
        raw = self.event_attributes.get(self.event_attr_keys.PRODUCT_KEYS)
        if not raw:
            return {}
        try:
            keys = json.loads(raw)
        except ValueError:
            keys = None
        if not isinstance(keys, dict):
            # Never log the raw value: it holds the keys.
            self.logger.error(f"{self.class_name}:{self.image_name} - Ignoring malformed product_keys attribute",
                              image_name=self.image_name)
            return {}
        return {str(guest): str(key) for guest, key in keys.items()}

    def _snapshot(self) -> None:
        if self.course_object == str(PubSub.CourseObjects.TEMPLATE_SERVER.value):
            snapshot_manager = SnapshotManager(
                shared_edit_authorized=self.shared_edit_authorized,
                server_type=PubSub.CourseObjects.TEMPLATE_SERVER,
                env_dict=self.env_dict,
                debug=self.debug,
                snapshot_type=self.snapshot_type
            )
            snapshot_manager.load(self.server_name)
            snapshot_manager.create_snapshot()
        elif self.course_object == str(PubSub.CourseObjects.LAB_SERVER.value):
            snapshot_manager = SnapshotManager(
                shared_edit_authorized=self.shared_edit_authorized,
                server_type=PubSub.CourseObjects.LAB_SERVER,
                env_dict=self.env_dict,
                debug=self.debug,
                snapshot_type=self.snapshot_type
            )
            snapshot_manager.load(self.server_name)
            snapshot_manager.create_snapshot(expiration_date=self.expires)
        elif self.course_object == str(PubSub.CourseObjects.WORKOUT.value):
            snapshot_manager = SnapshotManager(
                shared_edit_authorized=self.shared_edit_authorized,
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
                shared_edit_authorized=self.shared_edit_authorized,
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
            shared_edit_authorized=self.shared_edit_authorized,
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
