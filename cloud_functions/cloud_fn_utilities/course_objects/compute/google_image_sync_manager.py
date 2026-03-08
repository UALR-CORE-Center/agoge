from datetime import UTC, datetime
from typing import Union, Dict, List
from google.cloud.compute_v1 import Image

from common.exceptions.agoge import ServiceUnavailable, NotFound
from common.constants.database import DbCollections, DATABASE_NAME, DatabaseTypes, DbOperationTypes
from common.constants.google import ImageProjects
from common.document_database import DocumentDatabaseFactory
from common.models.google import ComputeImageModel
from common.utilities.gcp.cloud_env import CloudEnv
from common.utilities.gcp.cloud_logger import Logger, LoggerNames
from common.utilities.gcp.compute.compute_image import ComputeImageAPI
from common.utilities.id_generator import IdGenerator


class GoogleImageSyncManager:
    class GenericFamily:
        WINDOWS = 'windows'
        LINUX = 'linux'

    DEFAULT_ENABLED = [ImageProjects.DEBIAN, ImageProjects.UBUNTU, ImageProjects.WINDOWS]

    class SyncActions:
        SYNCING = 0
        COMPLETE = 1

    def __init__(self, env: dict = None) -> None:
        self.class_name = self.__class__.__name__
        self.logger = Logger(LoggerNames.CLOUD_FN, class_name=self.class_name)
        self.env = CloudEnv(env_dict=env) if env else CloudEnv()
        self.env_dict = self.env.get_env()
        self.compute_images = ComputeImageAPI(self.env.project, self.env.region, self.env.zone)
        self.db = DocumentDatabaseFactory.create_db_object(
            db_type=DatabaseTypes.firestore,
            database_name=DATABASE_NAME
        )
        self.collection = DbCollections.GOOGLE_IMAGES
        self.image_data = {}
        self.images: List[ComputeImageModel] = []
        self.image_keys = set()

    def get_image_data(self) -> Dict:
        """Returns the Google Cloud Compute image data."""
        return self.image_data

    def get_all_images(
        self,
        sort: bool = False
    ) -> Union[List, Dict]:
        """Get a family image for all global Google Cloud Compute image project"""
        for project in ImageProjects.ALL:
            images = self._get_family_images(project)
            self.image_data[project] = images

        if sort:
            return self.image_data
        return self.images

    def sync(self) -> None:
        """
        Sync the document database with available Global Google Cloud compute images
        """
        self._log_update(action=self.SyncActions.SYNCING)

        self.logger.info("Beginning to sync global images ...")
        self.get_all_images()
        existing_images = self.db.query(collection_name=self.collection)

        existing_image_map = {}
        if existing_images:
            existing_image_map = {db_image.get('global_id'): db_image for db_image in existing_images}

        images_to_sync = []
        operation_type = DbOperationTypes.SET
        for image in self.images:
            global_id = str(image.global_id)

            # Check if the image exists in the database
            existing_image = existing_image_map.pop(global_id, None)

            if existing_image:
                # Preserve `is_enabled` status from database if available
                is_enabled = False
                if image.is_enabled is not None:
                    is_enabled = image.is_enabled
                image.is_enabled = existing_image.get('is_enabled', is_enabled)
                operation_type = DbOperationTypes.UPDATE

            images_to_sync.append(
                self.db.operation(
                    collection_name=self.collection,
                    doc_id=image.uuid,
                    operation_type=operation_type,
                    data=image.model_dump()
                )
            )

        # Remaining items in `db_image_map` are no longer in `self.images` and should be deleted
        to_delete = [
            self.db.operation(
                collection_name=self.collection,
                doc_id=i['uuid'],
                operation_type=DbOperationTypes.DELETE
            )
            for i in existing_image_map.values()
        ]
        if to_delete:
            self.db.batch_write(to_delete)

        self.db.batch_write(images_to_sync)
        self._log_update(self.SyncActions.COMPLETE)

    def _get_family_images(
        self,
        project: str,
    ) -> Union[List[ComputeImageModel], List]:
        """
        Fetches the latest image for each family in the specified project
        """
        processed_images = []
        is_enabled = bool(project in self.DEFAULT_ENABLED)

        self.logger.info(f'{self.class_name}:_get_family_images - Retrieving images from project {project}')
        for family in self._get_families(project=project):
            try:
                image_family_request = self.compute_images.get(
                    resource=family,
                    project=project,
                    zone=self.env.zone,
                    family=True,
                )
                if image_family_request:
                    db_image = self._create_image_object(
                        image=image_family_request.image,
                        family=family,
                        project=project,
                        is_enabled=is_enabled
                    )
                    processed_images.append(db_image)
                    self.images.append(db_image)
            except NotFound:
                self.logger.warning(
                    f"{self.class_name}:_get_family_images - family '{family}' "
                    f"not found in project '{project}'. Ignoring ..."
                )
                continue
            except AttributeError as e:
                self.logger.debug(str(e))
            except Exception as e:
                raise ServiceUnavailable(
                    message=f"{self.class_name}:_get_family_images - An error occurred while "
                            f"fetching images: {e}"
                )

        return processed_images

    def _get_families(
        self,
        project: str
    ) -> List[str]:
        families = set()
        image_filter = None
        if project in [ImageProjects.WINDOWS, ImageProjects.SQL_SERVER]:
            image_filter = "(deprecated.state != DEPRECATED)"

        family_images = self.compute_images.list(project=project, request_filter=image_filter)
        if family_images:
            for image in family_images:
                if family := image.family:
                    if self._is_valid_family(family=family):
                        families.add(family)

            return list(families)
        return []

    def _get_custom_images(self) -> Union[List[Dict], List[str]]:
        """
        Retrieves custom images from project
        """
        processed_images = []
        images = self.compute_images.list(project=self.env.project)
        for image in images:
            pass

        return processed_images

    def _create_image_object(
        self,
        image: Image,
        family: str,
        project: str,
        is_enabled: bool
    ) -> Union[ComputeImageModel]:
        new_image = {
            'uuid': IdGenerator.uuid(),
            'global_id': str(image.id),
            'name': self._get_name_from_image(family),
            'self_link': image.self_link,
            'project': project,
            'family': family,
            'is_enabled': is_enabled,
            'creationTimestamp': image.creation_timestamp,
            'description': image.description,
            'disk_size': image.disk_size_gb,
            'os': self._get_os_from_project(project)
        }
        return ComputeImageModel(**new_image)

    def _get_os_from_project(
        self,
        project: str
    ) -> str:
        if project in [ImageProjects.WINDOWS, ImageProjects.SQL_SERVER]:
            return self.GenericFamily.WINDOWS
        else:
            return self.GenericFamily.LINUX

    def _log_update(
        self,
        action: int
    ) -> None:
        record = {
            'action': action,
            'update_time': datetime.now(UTC).isoformat(),
        }
        self.db.update(
            collection_name=DbCollections.UPDATES,
            doc_id=DbCollections.GOOGLE_IMAGES.value,
            data=record
        )
        return

    @staticmethod
    def _is_valid_family(family: str) -> bool:
        valid = True
        if 'windows' not in family:
            suffix = family.split("-")[-1]
            if suffix in ['backports']:
                valid = False
        else:
            if "2016-core" in family:
                valid = False
        return valid

    @staticmethod
    def _get_name_from_image(image_name: str) -> str:
        return image_name.replace("-", " ").title()
