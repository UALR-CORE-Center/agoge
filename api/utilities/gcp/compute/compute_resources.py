import re
from googleapiclient import discovery
from google.cloud import compute_v1
from typing import List, Union

from common.constants.database import DbCollections, DATABASE_NAME, DatabaseTypes
from common.document_database import DocumentDatabaseFactory
from common.models.google import MachineTypeModel
from common.utilities.gcp.cloud_env import CloudEnv
from common.utilities.gcp.cloud_logger import Logger, LoggerNames


class ComputeResources:
    ALLOWED_M_TYPES = ["n1", "n2", "e2"]
    IGNORE = {
        'guacamole-ssl',
        'image-cyberarena-labentry-ssl',
        'image-cyberarena-labentry-ssl-dev'
    }

    def __init__(
        self,
        doc_id: str = None,
        clean: bool = False,
        env_dict: dict = None
    ) -> None:
        self.class_name = self.__class__.__name__
        self.log_name = LoggerNames.API
        self.collection = DbCollections.IMAGE
        self.doc_id = doc_id
        self.env = CloudEnv(log_name=self.log_name, env_dict=env_dict) if env_dict else CloudEnv(log_name=self.log_name)
        self.db = DocumentDatabaseFactory.create_db_object(
            db_type=DatabaseTypes.firestore,
            database_name=DATABASE_NAME,
            log_name=self.log_name
        )
        self.compute = discovery.build('compute', 'v1')
        self.compute_client = compute_v1.ImagesClient()
        self.machine_client = compute_v1.MachineTypesClient()
        self.logger = Logger(log_name=self.log_name, class_name=self.class_name)
        self.regx_str = r'^[a-zA-Z0-9]{10}-'
        self.pattern = re.compile(self.regx_str)
        self.clean = clean

    def _safe_to_return(
        self,
        name: str,
        filters: list[str] = None
    ) -> bool:
        return (
                name not in ComputeResources.IGNORE
                and not bool(self.pattern.match(name))
                and (not filters or name in filters)
        )

    def get_machine_types(self) -> List[MachineTypeModel]:
        request_body = compute_v1.ListMachineTypesRequest(
            project=self.env.project,
            zone=self.env.zone,
        )
        resp = self.machine_client.list(request=request_body)

        machine_types = []
        for m_type in resp:
            if cleaned_machine_type := self._machine_type_object(m_type):
                machine_types.append(cleaned_machine_type)

        return machine_types

    def get_custom_images(self):
        """Retrieves list of Custom images

        Returns:
            list: The list of custom compute images
        """
        filters = 'status = READY'
        custom_images = []
        response = self.compute.images().list(project=self.env.project, filter=filters).execute()

        while response:
            if items := response.get('items'):

                custom_images.extend(items)
            next_page_token = response.get('nextPageToken')
            if not next_page_token:
                break
            response = self.compute.images().list(project=self.env.project, filter=filters,
                                                  pageToken=next_page_token).execute()
        return custom_images

    def _machine_type_object(
        self,
        request: compute_v1.MachineType
    ) -> Union[MachineTypeModel, None]:
        name = request.name
        if (name.split("-")[0] in self.ALLOWED_M_TYPES
                and request.memory_mb <= 17000):
            return MachineTypeModel(
                id=name,
                name=name,
                description=request.description,
                is_shared_core=request.is_shared_cpu,
                memory_mb=request.memory_mb,
                guest_cpus=request.guest_cpus
            )

    def _get_images_from_db(self) -> List:
        query = self.db.query(collection_name=self.collection)
        if not query:
            return []
        return [
            {
                "name": image['name'],
                "disk_size": image["add_disk"],
                "self_link": image["self_link"],
                "os": image['os']
            }
            for image in query if 'self_link' in image
        ] if self.clean else query

    def _get_cleaned_image(self, name, response) -> dict:
        """Returns image dict based on `self.clean` value

        Args:
            name (str): Name of image
            response (dict): single dictionary object from API response

        Returns:
            Image dictionary based on intended usage.
            If not `self.clean`, returns entire image
        """
        if self.clean:
            img_obj = {
                "name": name,
                "disk_size": response["diskSizeGb"],
                "self_link": response["selfLink"]
            }
        else:
            img_obj = {"name": name, "image": response}
        return img_obj
