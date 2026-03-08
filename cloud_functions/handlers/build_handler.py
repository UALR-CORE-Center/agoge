from common.constants.database import DbCollections, DatabaseTypes, DATABASE_NAME
from common.constants.pub_sub import PubSub
from common.document_database import DocumentDatabaseFactory
from common.utilities.gcp.cloud_env import CloudEnv
from common.utilities.gcp.cloud_logger import Logger, LoggerNames

from cloud_fn_utilities.course_objects.compute.factory import ComputeManagerFactory
from cloud_fn_utilities.server_specific.guacamole.display_proxy import DisplayProxy
from cloud_fn_utilities.course_objects.unit.factory_unit import UnitFactory
from cloud_fn_utilities.course_objects.workout.factory_workout import WorkoutFactory


class BuildHandler:
    def __init__(
        self,
        event_attributes,
        env_dict: dict = None,
        debug_mode: bool = False
    ) -> None:
        self.class_name = self.__class__.__name__
        self.log_name = LoggerNames.CLOUD_FN
        self.env = CloudEnv(env_dict=env_dict) if env_dict else CloudEnv()
        self.env_dict = self.env.get_env()
        self.debug_mode = debug_mode
        self.logger = Logger(self.log_name, class_name=self.class_name)
        self.event_attr_keys = PubSub.EventAttributes
        self.event_attributes = event_attributes
        self.db = DocumentDatabaseFactory.create_db_object(
            db_type=DatabaseTypes.firestore,
            database_name=DATABASE_NAME
        )

    def route(self) -> None:
        action = self.event_attributes.get(self.event_attr_keys.ACTION, None)
        course_object = self.event_attributes.get(self.event_attr_keys.COURSE_OBJECT, None)
        if not course_object:
            self.logger.error(
                f"{self.class_name} - No course object provided in cloud function build handler",
                course_object=course_object,
                action=action
            )
            raise ValueError
        elif course_object == str(PubSub.CourseObjects.UNIT.value):
            build_id = self.event_attributes.get(self.event_attr_keys.BUILD_ID, None)
            self.logger.info(
                f"{self.class_name}:{course_object} - Build action called for build_id {build_id}",
                course_object=course_object,
                action=action
            )
            child_id = self.event_attributes.get(self.event_attr_keys.CHILD_ID, None)
            form_data = self.event_attributes.get(self.event_attr_keys.CLAIMED_BY, None)
            unit = UnitFactory.create_unit_object(
                unit_id=build_id,
                workout_id=child_id,
                form_data=form_data,
                env_dict=self.env_dict,
                debug=self.debug_mode
            )
            unit.build()
        elif course_object == str(PubSub.CourseObjects.WORKOUT.value):
            build_id = self.event_attributes.get(self.event_attr_keys.BUILD_ID, None)
            if not build_id:
                self.logger.error(
                    f"{self.class_name}:{course_object} - No build id provided for build handler action",
                    course_object=course_object,
                    action=action
                )
                raise ValueError
            workout = WorkoutFactory.create_workout_object(
                workout_id=build_id,
                env_dict=self.env_dict,
                debug=self.debug_mode
            )
            workout.build()
        elif course_object == str(PubSub.CourseObjects.LAB_SERVER.value):
            network_prefix = self.event_attributes.get(self.event_attr_keys.NETWORK_PREFIX, None)
            server_name = self.event_attributes.get(self.event_attr_keys.SERVER_NAME, None)
            if not server_name:
                self.logger.error(
                    f"{self.class_name}:{course_object} - No server_name variable provided "
                    f"for the build handler action",
                    course_object=course_object,
                    action=action
                )
                raise ValueError

            lab_server_mgr = ComputeManagerFactory.create_manager_object(env_dict=self.env_dict, log_name=self.log_name)
            lab_server_mgr.load(server_name=server_name, network_prefix=network_prefix)
            lab_server_mgr.build()
        elif course_object == str(PubSub.CourseObjects.DISPLAY_PROXY.value):
            collection = self.event_attributes.get(self.event_attr_keys.KEY_TYPE, None)
            build_id = self.event_attributes.get(self.event_attr_keys.BUILD_ID, None)

            if not collection:
                self.logger.error(
                    f"{self.class_name}:{course_object} - No key_type provided for the build action!",
                    course_object=course_object,
                    action=action
                )
                raise ValueError
            if not build_id:
                self.logger.error(
                    f"{self.class_name}:{course_object} - No build_id provided for the build action.",
                    course_object=course_object,
                    action=action
                )
                raise ValueError

            try:
                collection_enum = DbCollections(collection)  # Convert string to enum
            except ValueError:
                self.logger.error(
                    f"{self.class_name}:{course_object} - Unsupported collection {collection} supplied to build action",
                    course_object=course_object,
                    action=action
                )
                raise ValueError

            if collection_enum in [DbCollections.WORKOUT]:
                build_spec = self.db.get(collection_name=collection_enum, doc_id=build_id)
            else:
                self.logger.error(
                    f"{self.class_name}:{course_object} - Unsupported collection "
                    f"{collection_enum} supplied to build action",
                    course_object=course_object,
                    action=action
                )
                raise ValueError
            display_proxy = DisplayProxy(
                build_id=build_id,
                build_spec=build_spec,
                collection=collection_enum,
                env_dict=self.env_dict
            )
            display_proxy.build()
        else:
            self.logger.error(
                f"{self.class_name}:{course_object} - Unsupported course_object supplied to build handler",
                course_object=course_object,
                action=action
            )
            raise ValueError

