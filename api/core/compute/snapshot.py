from typing import Union, List
from fastapi import Request

from common.constants.enumerators import SnapshotTypes
from common.document_database import DatabaseQueries
from common.models.agoge import AgogeImageModel, SnapshotsModel
from common.models.google import ComputeImageModel, MachineTypeModel, DiskModel, DiskInitializeParamsModel
from common.models.model_validators import ModelValidator
from common.utilities.gcp.cloud_env import CloudEnv
from common.utilities.gcp.cloud_logger import Logger, LoggerNames
from common.constants.build_constants import BuildConstants
from common.constants.database import (
    DatabaseTypes,
    DbCollections,
    DbOperationTypes,
    DATABASE_NAME,
    DbOperators
)
from common.constants.states import ImageStatus
from common.constants.pub_sub import PubSub
from common.utilities.gcp.pubsub_manager import PubSubManager
from common.document_database.factory import DocumentDatabaseFactory
from common.exceptions import BadRequest, NotFound, AgogeValidationError


class ComputeSnapshot:
    NAME_RESERVATIONS = ["agoge", "google"]
    TWO_WEEKS_TS = int(14*86400)

    def __init__(self, env_dict: dict) -> None:
        self.class_name = self.__class__.__name__
        self.log_name = LoggerNames.API
        self.collection = DbCollections.SNAPSHOTS
        self.env = CloudEnv(log_name=self.log_name, env_dict=env_dict)
        self.env_dict = self.env.get_env()
        self.pubsub_manager = PubSubManager(
            topic=PubSub.Topics.AGOGE,
            log_name=self.log_name,
            env_dict=self.env.get_env()
        )
        self.db = DocumentDatabaseFactory.create_db_object(
            DatabaseTypes.firestore,
            database_name=DATABASE_NAME,
            log_name=self.log_name
        )
        self.db_queries = DatabaseQueries(db=self.db)
        self.handler = PubSub.Handlers
        self.pubsub_keys = PubSub.EventAttributes
        self.logger = Logger(log_name=self.log_name, class_name=self.class_name)
        self.user = None
        self.agoge_model_validator = ModelValidator(model=SnapshotsModel)

    async def get(
        self,
        server_name: str
    ) -> SnapshotsModel:
        if snapshot := self.db.get(self.collection, doc_id=server_name):
            return self.agoge_model_validator.load(snapshot)
        return SnapshotsModel(
            server_id=server_name,
            server_type=PubSub.CourseObjects.LAB_SERVER.value,
            snapshots=[]
        )

    async def list(
        self,
        build_id: str,
        course_object: int
    ) -> List[Union[SnapshotsModel, List[SnapshotsModel]]]:
        if not build_id or not course_object:
            raise BadRequest(message='Missing or invalid data for snapshot list request')

        if course_object == PubSub.CourseObjects.WORKOUT.value:
            return self._get_workout_snapshots(build_id=build_id)
        elif course_object == PubSub.CourseObjects.UNIT.value:
            workouts = self.db_queries.get_children(child_collection=DbCollections.WORKOUT, parent_id=build_id)
            if not workouts:
                raise NotFound(message=f'No snapshots found for given UNIT')
            return [self._get_workout_snapshots(w['id']) for w in workouts]
        elif course_object == PubSub.CourseObjects.TEMPLATE_SERVER.value:
            if snapshot := self.db.get(self.collection, doc_id=build_id):
                return [self.agoge_model_validator.load(snapshot)]
            return [SnapshotsModel(server_id=build_id, server_type=course_object, snapshots=[])]
        else:
            raise BadRequest(message=f'Unsupported value for course_object, {course_object}')

    def process_action_on_list(
        self,
        data: dict
    ) -> None:
        snapshot_items = data.get('items', [])
        course_object = data.get(self.pubsub_keys.COURSE_OBJECT)
        action = data.get(self.pubsub_keys.ACTION)

        if not snapshot_items and not course_object and not action:
            raise BadRequest(f"Invalid or missing value for action ({action})")

        msg_args = {
            self.pubsub_keys.HANDLER: str(PubSub.Handlers.CONTROL.value),
            self.pubsub_keys.ACTION: str(action),
            self.pubsub_keys.COURSE_OBJECT: str(course_object),
        }
        if action == PubSub.Actions.SNAPSHOT.value:
            msg_args[self.pubsub_keys.SNAPSHOT_TYPE] = str(SnapshotTypes.MANUAL)
            if course_object == PubSub.CourseObjects.WORKOUT.value:
                self.logger.info(
                    f'SNAPSHOT action called for WORKOUT list',
                    course_object=course_object,
                    snapshot_items=str(snapshot_items)
                )
                for item in snapshot_items:
                    msg_args[self.pubsub_keys.BUILD_ID] = str(item)
                    self.pubsub_manager.msg(**msg_args)
                return
            elif course_object == PubSub.CourseObjects.TEMPLATE_SERVER.value:
                self.logger.info(
                    f'SNAPSHOT action called for TEMPLATE_SERVER list',
                    course_object=course_object,
                    snapshot_items=str(snapshot_items)
                )
                for item in snapshot_items:
                    msg_args[self.pubsub_keys.SERVER_NAME] = str(item)
                    self.pubsub_manager.msg(**msg_args)
                return
        raise BadRequest(f'Missing or invalid data for snapshot POST request')

    def process_server_action(
        self,
        server_name: str,
        data: dict
    ) -> None:
        action = data.get(self.pubsub_keys.ACTION)
        course_object = data.get(self.pubsub_keys.COURSE_OBJECT)
        parent_build_id = data.get(self.pubsub_keys.BUILD_ID, None)

        self.logger.info(
            f"Action {PubSub.Actions(action).name} for {server_name}",
            server=server_name,
            action=action,
        )
        if not course_object or course_object not in [
            PubSub.CourseObjects.LAB_SERVER.value,
            PubSub.CourseObjects.TEMPLATE_SERVER.value,
        ]:
            raise BadRequest(
                message=f'Unsupported or missing course object, {course_object}, '
                        f'for {PubSub.Actions(action).name} request'
            )

        if action in [
            PubSub.Actions.SNAPSHOT.value,
            PubSub.Actions.RESTORE.value,
        ]:
            if course_object == PubSub.CourseObjects.TEMPLATE_SERVER.value:
                template_server = self.db.get(collection_name=DbCollections.IMAGE, doc_id=server_name)

                if template_server.get('status', None) == ImageStatus.CHECKED_IN.value:
                    raise BadRequest(
                        message=f'Cannot process action on template server. Image is already checked in!'
                    )

            # Construct PubSub object
            msg_args = {
                self.pubsub_keys.HANDLER: str(PubSub.Handlers.CONTROL.value),
                self.pubsub_keys.ACTION: str(action),
                self.pubsub_keys.SERVER_NAME: str(server_name),
                self.pubsub_keys.COURSE_OBJECT: str(course_object),
            }

            if action == PubSub.Actions.SNAPSHOT.value:
                msg_args[self.pubsub_keys.SNAPSHOT_TYPE] = str(SnapshotTypes.MANUAL.value)

                if course_object == PubSub.CourseObjects.LAB_SERVER.value:
                    if not parent_build_id:
                        raise BadRequest('Missing data for key parent_build_id')
                    else:
                        workout = self.db.get(collection_name=DbCollections.WORKOUT, doc_id=parent_build_id)
                        expires = int(workout.get('expires')) + self.TWO_WEEKS_TS
                    msg_args[self.pubsub_keys.EXPIRES] = str(expires)
            elif action == PubSub.Actions.RESTORE.value:
                if snapshot_name := data.get(self.pubsub_keys.SNAPSHOT_NAME):
                    msg_args[self.pubsub_keys.SNAPSHOT_NAME] = str(snapshot_name)

            self.pubsub_manager.msg(**msg_args)
        elif action == PubSub.Actions.DELETE.value:
            snapshot_name = data.get('snapshot_name')
            if not snapshot_name:
                raise BadRequest(f'Missing or invalid data for snapshot_name')

            if snapshots_doc := self.db.get(collection_name=self.collection, doc_id=server_name):
                snapshots = snapshots_doc.get('snapshots', [])
                for snapshot in snapshots:
                    if snapshot.get('name') == snapshot_name:
                        msg_args = {
                            self.pubsub_keys.HANDLER: PubSub.Handlers.CONTROL.value,
                            self.pubsub_keys.ACTION: action,
                            self.pubsub_keys.COURSE_OBJECT: PubSub.CourseObjects.SNAPSHOT.value,
                            self.pubsub_keys.SERVER_NAME: server_name,
                            self.pubsub_keys.SERVER_TYPE: course_object,
                            self.pubsub_keys.SNAPSHOT_NAME: snapshot_name
                        }
                        self.pubsub_manager.msg(**msg_args)
                        return
                raise NotFound(message=f"No snapshots found for server {server_name} with name {snapshot_name}")

    def _get_workout_snapshots(
        self,
        build_id: str,
    ) -> List[SnapshotsModel]:
        if not (servers := self.db_queries.get_servers(build_id)):
            raise BadRequest(f'No servers found for workout with id {build_id}')

        workout_snapshots = {}
        snapshot_ids = []
        for server in servers:
            if 'display-guacamole' in server['name']:
                continue

            server_name = f"{build_id}-{server['name']}"
            snapshot_ids.append(server_name)
            snapshots_model = SnapshotsModel(
                server_id=server_name,
                parent_build_id=build_id,
                snapshots=[],
                server_type=PubSub.CourseObjects.LAB_SERVER.value
            )
            workout_snapshots[server_name] = snapshots_model

        # Retrieve all server snapshots and add them to the existing server record
        snapshots_query = self.db.query(self.collection, filters=[('server_id', DbOperators.IN, snapshot_ids)])
        for snapshots_obj in snapshots_query:
            server_id = snapshots_obj['server_id']
            if server := workout_snapshots.get(server_id):
                snapshots = snapshots_obj.get('snapshots')
                if not snapshots:
                    snapshots = []
                server.snapshots = snapshots

        return [workout_snapshots[s] for s in workout_snapshots]
