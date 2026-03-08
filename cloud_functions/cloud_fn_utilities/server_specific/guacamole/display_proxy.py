from ipaddress import ip_address, ip_network
from typing import Type, Union
from pydantic import BaseModel
from common.constants.database import DbCollections, DatabaseTypes, DATABASE_NAME
from common.constants.build_constants import BuildConstants
from common.document_database import DocumentDatabaseFactory, DatabaseMask
from common.utilities.gcp.cloud_env import CloudEnv
from common.utilities.gcp.cloud_logger import Logger, LoggerNames
from common.models.agoge import WorkoutModel, UnitModel, ServerModel, NicModel, ProxyConnectionModel

from cloud_fn_utilities.course_objects.compute.factory import ComputeManagerFactory
from cloud_fn_utilities.state_managers import ServerStateManager
from cloud_fn_utilities.server_specific.guacamole.guacamole_configuration import GuacamoleConfiguration


class DisplayProxy:
    def __init__(
        self,
        build_id: str,
        build_spec: Union[dict, WorkoutModel],
        collection: DbCollections = DbCollections.UNIT,
        env_dict: dict = None
    ) -> None:
        """
        Creates a guacamole server with the configured connections for proxying servers used for displays
        @param build_id: The build ID used mainly for naming objects in the cloud
        @type build_id: str
        @param build_spec: The full build spec
        @type build_spec: DatastoreEntity
        """
        self.env = CloudEnv(env_dict=env_dict) if env_dict else CloudEnv()
        self.env_dict = self.env.get_env()
        self.server_name = "display-guacamole-server"
        self.server_id = f"{build_id}-{self.server_name}"
        self.s = ServerStateManager
        self.logger = Logger(LoggerNames.CLOUD_FN)
        self.server_spec = None
        self.build_id = build_id
        self.collection = collection
        self.is_dict = isinstance(build_spec, dict)
        self.build_type = self._set_build_type(build_spec)
        self.model = self._set_model(self.build_type)
        if self.is_dict:
            self.build_model = self.model(**build_spec)
        else:
            self.build_model = build_spec
        self.server_specs = self.build_model.servers
        self.firewalls = self.build_model.firewalls or False
        self.guac_connections = []
        self.db = DocumentDatabaseFactory.create_db_object(
            db_type=DatabaseTypes.firestore,
            database_name=DATABASE_NAME
        )
        self.db_mask = DatabaseMask(logger=self.logger)
        self.guac = GuacamoleConfiguration(self.build_id, env_dict=self.env_dict)
        self.compute_manager = ComputeManagerFactory.create_manager_object(env_dict=self.env_dict)
        self._create_network_settings()

    def _set_build_type(
        self,
        build_spec: Union[dict, BaseModel]
    ) -> BuildConstants.BuildType:
        if self.is_dict:
            return BuildConstants.BuildType(
                build_spec.get('build_type', BuildConstants.BuildType.UNIT.value)
            )
        else:
            return BuildConstants.BuildType(
                build_spec.build_type or BuildConstants.BuildType.UNIT.value
            )

    @staticmethod
    def _set_model(build_type: BuildConstants.BuildType) -> Type[Union[UnitModel, WorkoutModel]]:
        if build_type == BuildConstants.BuildType.WORKOUT.value:
            return WorkoutModel
        else:
            return UnitModel

    def build(self):
        build_record = self.db.get(collection_name=self.collection, doc_id=self.build_id)
        build_record = self.model(**build_record)
        proxy_configs = []
        proxy_connections = []
        for server in self.server_specs:
            human_interaction = server.human_interaction
            if human_interaction is not None:
                for connection in human_interaction:
                    if connection.display:
                        server_ip = server.nics[0].internal_ip
                        proxy_config = self.guac.prepare_guac_connection(connection=connection, server_ip=server_ip)
                        proxy_configs.append(proxy_config)
                        proxy_connection = ProxyConnectionModel(
                            server=server.name,
                            internal_ip_address=server_ip,
                            username=proxy_config['workspace_username'],
                            password=proxy_config['workspace_password'],
                        )
                        proxy_connections.append(proxy_connection)

        # Sort and index each proxy connection
        sorted_list = sorted(proxy_connections, key=lambda x: x.server)
        main_app_url = self.env.main_app_url
        if not main_app_url.startswith('https://'):
            main_app_url = f'https://{main_app_url}'

        for idx, connection in enumerate(sorted_list):
            connection.idx = idx
            connection.url = f'{main_app_url}/student/workout/{self.build_id}/guacamole/{idx}'

        # Update parent build record with sorted proxy connections
        build_record.proxy_connections = sorted_list

        build_record_dict = build_record.model_dump()
        update_mask = self.db_mask.get(build_record_dict, keys=['proxy_connections'])
        self.db.update(
            collection_name=self.collection,
            doc_id=self.build_id,
            data=update_mask
        )

        # Generate DisplayProxy server object
        guac_startup_script = self.guac.get_guac_startup_script(proxy_configs)
        server_model = ServerModel(
            parent_id=self.build_id,
            parent_build_type=self.build_type,
            name=self.server_name,
            image=BuildConstants.MachineImages.GUACAMOLE_SSL.format(
                project=BuildConstants.SharedResourceProjects.MAIN_SHARED_RESOURCE_PROJECT),
            tags=['student-entry', f"{self.build_id}-student-entry"],
            machine_type=BuildConstants.GoogleMachineTypes.E2_MEDIUM.value,
            nics=[
                NicModel(
                    network=self.network_name,
                    subnet_name="default",
                    external_nat=True,
                    internal_ip=self.internal_ip
                )
            ],
            build_type=self.build_type,
            hostname=f"{self.build_id}-display{self.env.parent_dns_suffix}",
            guacamole_startup_script=guac_startup_script
        )
        self.db.update(
            collection_name=DbCollections.SERVER,
            doc_id=self.server_id,
            data=server_model.model_dump()
        )
        self.compute_manager.load(self.server_id)
        self.compute_manager.build()

    def _create_network_settings(self) -> None:
        if self.firewalls or self.build_type not in [
            BuildConstants.BuildType.WORKOUT, BuildConstants.BuildType.ESCAPE_ROOM
        ]:
            self.network_name = BuildConstants.Networks.GATEWAY_NETWORK_NAME
            self.internal_ip = BuildConstants.Networks.Reservations.DISPLAY_SERVER
        else:
            self.network_name = BuildConstants.Networks.WORKOUT_EXTERNAL_NAME
            self.internal_ip = BuildConstants.Networks.Reservations.WORKOUT_PROXY_SERVER
            # TODO: Fix this code. It was created for the Forge Workouts
            try:
                workout_subnet = ip_network(self.build_model.networks[0].subnets[0].ip_subnet)
                internal_ip = ip_address(BuildConstants.Networks.Reservations.WORKOUT_PROXY_SERVER)
                if internal_ip not in workout_subnet:
                    self.internal_ip = '10.0.0.10'
                else:
                    self.internal_ip = BuildConstants.Networks.Reservations.WORKOUT_PROXY_SERVER
            except Exception:
                self.internal_ip = BuildConstants.Networks.Reservations.WORKOUT_PROXY_SERVER
