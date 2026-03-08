from typing import Union, Tuple, List

from cloud_fn_utilities.course_objects.compute.base_compute_manager import BaseComputeManager
from cloud_fn_utilities.state_managers import ImageStateManager, ServerStateManager
from common.constants.database import DbCollections, DatabaseTypes, DATABASE_NAME
from common.constants.enumerators import SnapshotTypes
from common.constants.pub_sub import PubSub
from common.constants.states import WorkoutStates
from common.document_database import DocumentDatabaseFactory, DatabaseQueries
from common.exceptions import NotFound, BadRequest, BaseAgogeException
from common.models.agoge import SnapshotsModel, SnapshotModel, WorkoutModel
from common.utilities.gcp.cloud_env import CloudEnv
from common.utilities.gcp.cloud_logger import LoggerNames, Logger
from common.utilities.gcp.compute.base_compute_api import BaseComputeAPI
from common.utilities.gcp.compute.resources.attached_disk_resource import AttachedDiskResource
from common.utilities.id_generator import IdGenerator
from common.utilities.timestamps import Timestamps


class SnapshotManager(BaseComputeManager):

    DEFAULT_MAX_SNAPSHOTS = BaseComputeAPI.DEFAULT_MAX_SNAPSHOTS
    DEFAULT_MAX_AUTO = BaseComputeAPI.DEFAULT_MAX_AUTO
    TWO_WEEKS_TS = int(14*86400)

    def __init__(
        self,
        server_type: PubSub.CourseObjects = PubSub.CourseObjects.LAB_SERVER,
        env_dict: dict = None,
        debug: bool = False,
        snapshot_type: str = SnapshotTypes.AUTO.value
    ) -> None:
        """
        Args:
            server_type (PubSub.CourseObjects): Enumerator for specifying how the server is used.
                Defaults to `PubSub.CourseObjects.LAB_SERVER` (lab workout server)
            env_dict (dict, optional): Optional dictionary containing project environment
            debug (bool, optional): Execute in debug mode. Defaults to `False`.
        """
        super().__init__(
            env_dict=env_dict,
            instances=True,
            images=False,
            disks=True,
            snapshots=True,
            machine_types=False
        )
        self.class_name = self.__class__.__name__
        self.log_name = LoggerNames.CLOUD_FN
        self.debug = debug
        self.logger = Logger(self.log_name, class_name=self.class_name)
        self.env = CloudEnv(env_dict=env_dict) if env_dict else CloudEnv()
        self.db = DocumentDatabaseFactory.create_db_object(
            db_type=DatabaseTypes.firestore,
            database_name=DATABASE_NAME
        )
        self.db_queries = DatabaseQueries(db=self.db, log_name=self.log_name)
        self.collection = DbCollections.SNAPSHOTS
        self.server_type = server_type
        self.snapshot_type = snapshot_type

    @property
    def snapshot_type(self) -> str:
        return self._snapshot_type

    @snapshot_type.setter
    def snapshot_type(self, new_value: str) -> None:
        self._snapshot_type = new_value

    def snapshot_name(
        self,
        server_name: str,
        idx: int = None
    ) -> str:
        if idx is not None:
            return f'{server_name}-{self.snapshot_type}-{idx}'
        return f'{server_name}-{self.snapshot_type}'

    def load(
        self,
        server_name: str,
        network_prefix: str = None,
        **kwargs
    ) -> None:
        if self.server_type == PubSub.CourseObjects.LAB_SERVER:
            if 'server_spec' in kwargs:
                server_spec = kwargs['server_spec']
            else:
                server_spec = self.db.get(collection_name=DbCollections.SERVER, doc_id=server_name)
                if not server_spec:
                    raise NotFound(
                        f"{self.class_name}:{self.server_name} - No lab server found with name {self.server_name}"
                    )
            self.state_manager = ServerStateManager()
            self._load_lab_server(server_name, server_spec, network_prefix=network_prefix)
            self.state_manager.set_build_record(server_name)
        elif self.server_type == PubSub.CourseObjects.TEMPLATE_SERVER:
            self.state_manager = ImageStateManager()
            self.image_name, self.server_name = self._extract_image_and_server_names(server_name)

            if 'image_spec' in kwargs:
                image_spec = kwargs['image_spec']
            else:
                image_spec = self.db.get(collection_name=DbCollections.IMAGE, doc_id=self.server_name)
                if not image_spec:
                    raise NotFound(
                        f"{self.class_name}:{self.server_name} - No image template found with name {self.server_name}"
                    )
            self._load_template_server(image_spec)
            self.state_manager.set_build_record(self.server_name)
        else:
            raise ValueError(f'Unsupported server_type {self.server_type}')

    def create_snapshot(
        self,
        expiration_date: int = None,
    ) -> Union[str, None]:
        """
        Creates a new snapshot while managing the number of snapshots.

        Args:
            expiration_date (int, Optional): Optional timestamp of when snapshot is safe to delete.

        Returns:
            str: The name of the created snapshot, or None if the snapshot could not be created.
        """
        # self._is_safe_to_perform_action()

        disk_name = self.server_name
        next_snapshot_name, delete_existing = self.get_next_snapshot_name()
        if delete_existing:
            self.delete_snapshot(next_snapshot_name)

        # create the snapshot
        try:
            _, current_disk = self.compute_instance.get_boot_disk_name(self.server_name)
            self.compute_disk.create_snapshot(
                disk_name=current_disk,
                snapshot_name=next_snapshot_name
            )
        except (NotFound, BadRequest, BaseAgogeException) as e:
            self.logger.error(
                f"{self.class_name}:{self.server_name} - Error creating snapshot {next_snapshot_name} from "
                f"disk {disk_name}: {e.message}",
                server_name=self.server_name
            )
            raise

        self._update_snapshots_record(next_snapshot_name, expiration_date)
        return next_snapshot_name

    def list_server_snapshots(self) -> List:
        snapshot_name_filter = self.snapshot_name(self.server_name)
        list_filters = f'(name="{snapshot_name_filter}-*")'
        try:
            snapshots = self.compute_snapshot.list(filters=list_filters)
            return list(snapshots)
        except NotFound as e:
            return []
        except (BadRequest, BaseAgogeException) as e:
            return []

    def get_next_snapshot_name(self) -> Tuple[str, bool]:
        """Lists all server snapshots and generates the next available snapshot name.

        Returns:
            Tuple[str, bool]: A tuple containing:
                - The name of the next available snapshot (str).
                - Indicate whether an existing snapshot must be deleted (bool).
        """
        if self.snapshot_type == SnapshotTypes.MANUAL.value:
            max_snapshots = self.DEFAULT_MAX_SNAPSHOTS
        else:
            max_snapshots = self.DEFAULT_MAX_AUTO
        snapshots = self.list_server_snapshots()
        num_snapshots = len(snapshots)
        snapshot_idx = 0
        delete_existing = False

        if num_snapshots == max_snapshots:
            # If snapshots are at max capacity, find the oldest snapshot to overwrite.
            oldest_snapshot = min(snapshots, key=lambda s: s.creation_timestamp)
            snapshot_idx = oldest_snapshot.name.split('-')[-1]
            delete_existing = True
        elif 0 < num_snapshots < max_snapshots:
            # since num_snapshots and max_snapshots define an index starting at 1 instead of 0,
            # the current snapshot index is used instead of current index + 1.
            snapshot_idx = num_snapshots % max_snapshots

        next_snapshot_name = self.snapshot_name(server_name=self.server_name, idx=snapshot_idx)
        return next_snapshot_name, delete_existing

    def delete_snapshot(
        self,
        snapshot_name: str,
    ) -> bool:
        """
        Deletes a snapshot if it exists.

        Args:
            snapshot_name (str): The name of the snapshot to delete.
        """
        try:
            if not self.compute_snapshot.delete(snapshot_name):
                self.logger.error(
                    f"{self.class_name}:{self.server_name} - Timeout waiting for snapshot "
                    f"{snapshot_name} to delete.",
                    server_name=self.server_name
                )
                return False
        except NotFound as e:
            self.logger.error(
                f"{self.class_name}:{self.server_name} - Error deleting snapshot {snapshot_name}: {e.message}",
                server_name=self.server_name
            )
        except (BadRequest, BaseAgogeException) as e:
            self.logger.error(f'{self.class_name}:{self.server_name} - {e.message}')
            raise

        self._remove_snapshot_from_record(snapshot_name)
        return True

    def delete_snapshots(self) -> None:
        """Delete all snapshots attached to an image server"""
        if server_snapshots := self.db.get(collection_name=DbCollections.SNAPSHOTS, doc_id=self.server_name):
            snapshots_model = SnapshotsModel(**server_snapshots)

            if snapshots_model.snapshots is not None:
                self.logger.info(f"{self.class_name}:{self.image_name} - Deleting any snapshots ...")
                for snapshot in snapshots_model.snapshots:
                    if self.debug:
                        self.delete_snapshot(snapshot.name)
                    else:
                        message_attr = {
                            PubSub.EventAttributes.HANDLER: PubSub.Handlers.CONTROL.value,
                            PubSub.EventAttributes.ACTION: PubSub.Actions.DELETE.value,
                            PubSub.EventAttributes.COURSE_OBJECT: PubSub.CourseObjects.SNAPSHOT.value,
                            PubSub.EventAttributes.SERVER_TYPE: self.server_type.value,
                            PubSub.EventAttributes.SERVER_NAME: snapshot.name
                        }
                        self.pubsub_manager.msg(**message_attr)

    def snapshot_lab_workout(
        self,
        workout_id: str,
        workout: dict = None
    ) -> None:
        if not workout:
            workout = self.db.get(collection_name=DbCollections.WORKOUT, doc_id=workout_id)

        workout_servers = self.db_queries.get_servers(parent_id=workout_id)
        if workout_servers and workout:
            # self._is_safe_to_perform_action(workout)
            workout = WorkoutModel(**workout)
            expires = int(workout.expires + self.TWO_WEEKS_TS)
            for server in workout_servers:
                server_name = f'{server["parent_id"]}-{server["name"]}'
                if 'display-guacamole' not in server_name:
                    self.pubsub_manager.msg(
                        handler=str(PubSub.Handlers.CONTROL.value),
                        action=str(PubSub.Actions.SNAPSHOT.value),
                        server_name=server_name,
                        course_object=str(PubSub.CourseObjects.LAB_SERVER.value),
                        expires=str(expires),
                        snapshot_type=self.snapshot_type
                    )
        else:
            raise NotFound(
                f'{self.class_name}:{workout_id} - No servers found for workout with id {workout_id}',
            )

    def snapshot_unit(
        self,
        unit_id: str
    ) -> None:
        workouts = self.db_queries.get_children(parent_id=unit_id, child_collection=DbCollections.WORKOUT)
        if workouts:
            for workout in workouts:
                try:
                    self.snapshot_lab_workout(workout['id'], workout=workout)
                except BadRequest:
                    continue
        else:
            raise NotFound(
                f'{self.class_name}:{unit_id} - No workouts found for unit with id {unit_id}'
            )

    def restore_from_snapshot(
        self,
        snapshot_name: str = None
    ) -> None:
        # self._is_safe_to_perform_action()

        server_snapshots = self._get_snapshot_record(ignore_missing=False)
        snapshots = server_snapshots.snapshots
        if not snapshots:
            self.logger.error(
                f'{self.class_name}:{self.server_name} - Restore from snapshot called'
                f'but no snapshots exist for server {self.server_name}!',
                server_name=self.server_name
            )
            raise BadRequest

        # verify snapshot exists in database first
        if snapshot_name:
            exists = any(s.name == snapshot_name for s in snapshots)
            if not exists:
                raise NotFound(f'{self.class_name}:{self.server_name} - Restore from snapshot {snapshot_name}'
                               f'failed. Snapshot not found!')
        else:
            snapshot = max(snapshots, key=lambda s: s.creation_timestamp)
            snapshot_name = snapshot.name

        # verify snapshot exists in cloud project before executing any dangerous requests
        if not (snapshot_resource := self.compute_snapshot.get(snapshot_name)):
            raise NotFound(
                f'{self.class_name}:{self.server_name} - Restore from snapshot called'
                f'but no snapshot exists for server with name {snapshot_name}',
            )

        try:
            # create the disk so that it's available to reattach
            new_disk_name = f'{IdGenerator.build_id(16)}-disk'
            disk_operation = self.compute_disk.create(
                resource_name=new_disk_name,
                source_snapshot=snapshot_resource.self_link,
                wait=False
            )

            # stop the server so that the current boot disk can be detached
            self._stop_server()

            # detach current boot disk
            old_disk_name, _ = (
                self.compute_instance.detach_boot_disk(resource_name=self.server_name)
            )

            # attach the new boot disk based off the selected snapshot
            self._get_attached_disk(new_disk_name, disk_operation.name)
        except BadRequest as e:
            self.logger.error(
                f"{self.class_name}:{self.server_name} - Server restore failed with reason: {e}",
                server_name=self.server_name
            )
            raise

        if self.debug:
            self._start_server()
        else:
            message_attr = {
                PubSub.EventAttributes.HANDLER: PubSub.Handlers.CONTROL.value,
                PubSub.EventAttributes.ACTION: PubSub.Actions.START.value,
                PubSub.EventAttributes.COURSE_OBJECT: self.server_type.value,
                PubSub.EventAttributes.IMAGE_NAME: self.image_name
            }
            self.pubsub_manager.msg(**message_attr)

        try:
            self.compute_disk.delete(old_disk_name, wait=False)
            return
        except NotFound as e:
            self.logger.debug(
                f'{self.class_name}:{self.server_name} - Delete disk failed with reason: {e}.',
                server_name=self.server_name
            )

    def _get_attached_disk(
        self,
        disk_name: str,
        disk_operation_id: str
    ) -> None:
        try:
            completed = self.compute_disk.wait_for_operation(operation_id=disk_operation_id)
            if not completed:
                raise TimeoutError(
                    f'{self.class_name}:{self.server_name} - timeout attempting to create new disk {disk_name}'
                )
        except Exception as e:
            self.logger.error(
                f'{self.class_name}:{self.server_name} - Error occurred when attaching '
                f'new disk: {str(e)}',
                server_name=self.server_name
            )
            self.state_manager.state_transition(self.s.BROKEN)
            raise

        # Attached disk
        disk_source = (
            self.compute_disk
            .get_source(project_id=self.env.project, zone=self.env.zone, disk_name=disk_name)
        )
        attached_disk_resource = AttachedDiskResource(zone=self.env.zone)
        new_boot_disk = attached_disk_resource.new(
            boot=True,
            auto_delete=True,
            source=disk_source,
            device_name=disk_name
        )
        self.compute_instance.attach_boot_disk(
            resource_name=self.server_name,
            disk_resource=new_boot_disk
        )

        # Only Lab servers have multiple disks; Remove any boot disks if necessary
        if (disks := self.server_spec.disks) is not None:
            try:
                old_disk_idx = next(i for i, v in enumerate(disks) if v.get('boot'))
                disks.pop(old_disk_idx)
            except StopIteration:
                self.logger.warning(
                    f'{self.class_name}:{self.server_name} - Could not find boot disk in '
                    f'server record',
                    server_name=self.server_name
                )

            disks.append(new_boot_disk)
            self.server_spec.disks = disks

    def _add_nics(self) -> None:
        raise NotImplemented

    def _dns_record(self) -> str:
        if self.server_type == PubSub.CourseObjects.TEMPLATE_SERVER:
            return self._template_dns_record()
        else:
            return self._server_dns_record()

    def _get_snapshot_record(self, ignore_missing: bool = True) -> SnapshotsModel:
        """Retrieve existing server snapshots record or creates a new one"""
        existing_snapshots_record = self.db.get(
            collection_name=DbCollections.SNAPSHOTS,
            doc_id=self.server_name
        )
        if existing_snapshots_record:
            server_snapshots_model = SnapshotsModel(**existing_snapshots_record)
        else:
            if not ignore_missing:
                self.logger.error(
                    f'{self.class_name}:{self.server_name} - Restore from snapshot called'
                    f'but no snapshots exist for server {self.server_name}!',
                    server_name=self.server_name
                )
                raise BadRequest

            server_snapshots_model = SnapshotsModel(server_id=self.server_name, server_type=self.server_type.value)
            if self.network_prefix:
                server_snapshots_model.parent_build_id = self.network_prefix

        return server_snapshots_model

    def _update_snapshots_record(
        self,
        snapshot_name: str,
        expiration_date: int = None
    ) -> None:
        """Rotates existing server snapshots in database record"""
        server_snapshots_model = self._get_snapshot_record()

        # Rotate existing snapshots if necessary
        existing_snapshots = []
        auto_snapshots = []
        manual_snapshots = []

        # Sort snapshots by SnapshotTypes
        if server_snapshots_model.snapshots is not None:
            existing_snapshots = server_snapshots_model.snapshots

        for snapshot in existing_snapshots:
            if snapshot.type_ == SnapshotTypes.MANUAL.value:
                manual_snapshots.append(snapshot)
            else:
                auto_snapshots.append(snapshot)

        # Rotate snapshots based on SnapshotType
        if self.snapshot_type == SnapshotTypes.MANUAL.value:
            manual_snapshots = (
                self._rotate_existing_snapshots(
                    snapshot_name=snapshot_name,
                    snapshots=manual_snapshots,
                    max_snapshots=self.DEFAULT_MAX_SNAPSHOTS
                )
            )
        else:
            auto_snapshots = (
                self._rotate_existing_snapshots(
                    snapshot_name=snapshot_name,
                    snapshots=auto_snapshots,
                    max_snapshots=self.DEFAULT_MAX_AUTO
                )
            )
        # Update combined lists
        existing_snapshots = auto_snapshots + manual_snapshots

        # Generate snapshot db object for new snapshot
        snapshot_source = (
            self.compute_snapshot
            .get_source(project=self.env.project, snapshot_name=snapshot_name)
        )
        new_snapshot = SnapshotModel(
            name=snapshot_name,
            creation_timestamp=int(Timestamps.get_current_timestamp_utc()),
            source=snapshot_source,
            type_=self.snapshot_type
        )
        existing_snapshots.append(new_snapshot)

        # Update database record
        server_snapshots_model.snapshots = existing_snapshots
        if expiration_date:
            server_snapshots_model.expiration_date = int(expiration_date)

        self.db.update(
            collection_name=DbCollections.SNAPSHOTS,
            doc_id=self.server_name,
            data=server_snapshots_model.model_dump()
        )

    def _remove_snapshot_from_record(
        self,
        snapshot_name: str
    ) -> None:
        """
        Filters snapshot document record for a matching snapshot and removes it from the record.
        """
        snapshots_model = self._get_snapshot_record()
        snapshots = snapshots_model.snapshots
        if snapshots is not None:
            snapshot_found = False
            for snapshot in snapshots:
                if snapshot.name == snapshot_name:
                    snapshot_found = True
                    snapshots.remove(snapshot)
                    break

            if snapshot_found:
                self.db.update(
                    collection_name=DbCollections.SNAPSHOTS,
                    doc_id=self.server_name,
                    data=snapshots_model.model_dump()
                )

    def _is_safe_to_perform_action(
        self,
        workout: dict = None
    ) -> bool:
        """Verify CourseObject is in a valid state to snapshot or restore from snapshot"""
        if workout:
            valid_states = [
                WorkoutStates.READY.value,
                WorkoutStates.STOPPING.value,
                WorkoutStates.RUNNING.value,
            ]
            current_state = workout.get('state')
        else:
            valid_states = [
                self.s.READY.value,
                self.s.STOPPING.value,
                self.s.STOPPED.value,
                self.s.RUNNING.value,
            ]
            current_state = self.state_manager.get_state()

        if current_state not in valid_states:
            raise BadRequest(f'Snapshot / Snapshot Restore action called, but resource is not ready!')
        return True

    @staticmethod
    def _rotate_existing_snapshots(
        snapshot_name: str,
        snapshots: list,
        max_snapshots: DEFAULT_MAX_AUTO
    ) -> List:
        if len(snapshots) == max_snapshots:
            oldest_snapshot = min(snapshots, key=lambda s: s.creation_timestamp)
            snapshots.remove(oldest_snapshot)
        elif len(snapshots) > 0:
            existing_snapshot = next((i for i in snapshots if i.name == snapshot_name), None)
            if existing_snapshot is not None:
                snapshots.remove(existing_snapshot)
        return snapshots
