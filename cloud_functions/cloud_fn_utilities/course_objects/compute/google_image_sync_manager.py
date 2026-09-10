from datetime import UTC, datetime
from typing import Union, Dict, List
from uuid import NAMESPACE_URL, uuid5
from google.cloud.compute_v1 import Image

from common.exceptions.agoge import ServiceUnavailable, NotFound
from common.constants.database import DbCollections, DATABASE_NAME, DatabaseTypes, DbOperationTypes
from common.constants.google import ImageProjects
from common.document_database import DocumentDatabaseFactory
from common.models.google import ComputeImageModel
from common.utilities.gcp.cloud_env import CloudEnv
from common.utilities.gcp.cloud_logger import Logger, LoggerNames
from common.utilities.gcp.compute.compute_image import ComputeImageAPI
from common.utilities.gcp.compute.image_compatibility import normalize_architecture


class GoogleImageSyncManager:
    class GenericFamily:
        WINDOWS = 'windows'
        LINUX = 'linux'

    DEFAULT_ENABLED = [ImageProjects.DEBIAN, ImageProjects.UBUNTU, ImageProjects.WINDOWS]

    class SyncActions:
        SYNCING = 0
        COMPLETE = 1
        PARTIAL = 2
        FAILED = 3

    def __init__(self, env: dict = None) -> None:
        self.class_name = self.__class__.__name__
        self.logger = Logger(LoggerNames.CLOUD_FN, class_name=self.class_name)
        self.env = CloudEnv(env_dict=env) if env else CloudEnv()
        self.env_dict = self.env.get_env()
        self.compute_images = ComputeImageAPI(self.env.project, self.env.region, self.env.zone)
        self.db = DocumentDatabaseFactory.create_db_object(
            db_type=DatabaseTypes.firestore,
            database_name=DATABASE_NAME,
            project_id=self.env.project,
        )
        self.collection = DbCollections.GOOGLE_IMAGES
        self.image_data = {}
        self.images: List[ComputeImageModel] = []
        self.image_keys = set()
        self.failed_projects = {}
        self.successful_projects = set()

    def get_image_data(self) -> Dict:
        """Returns the Google Cloud Compute image data."""
        return self.image_data

    def get_all_images(
        self,
        sort: bool = False
    ) -> Union[List, Dict]:
        """Get a family image for all global Google Cloud Compute image project"""
        self.image_data = {}
        self.images = []
        self.failed_projects = {}
        self.successful_projects = set()
        for project in ImageProjects.ALL:
            try:
                images = self._get_family_images(project)
            except Exception as error:
                self.failed_projects[project] = str(error)
                self.logger.warning(
                    f'Public images from {project} could not be refreshed: {error}. '
                    'Existing records for this publisher will be retained.'
                )
                continue
            self.image_data[project] = images
            self.images.extend(images)
            self.successful_projects.add(project)

        if sort:
            return self.image_data
        return self.images

    def sync(self) -> dict:
        """Refresh available publishers and retain catalogs that could not be read."""
        self._log_update(action=self.SyncActions.SYNCING, error=None, failed_projects={})
        self.logger.info(f'Beginning public image sync for {self.env.project} ...')
        try:
            self.get_all_images()
            if not self.images:
                raise ServiceUnavailable(
                    'No public OS image families were retrieved. Existing catalog retained. '
                    'Check Compute API access and the publisher errors, then retry.'
                )
            self._save_catalog()
        except Exception as error:
            try:
                self._log_update(
                    self.SyncActions.FAILED, error=str(error),
                    failed_projects=self.failed_projects,
                )
            except Exception:
                self.logger.error('Could not record the failed public image sync status.')
            raise

        report = {
            'image_count': len(self.images),
            'enabled_count': sum(image.is_enabled is True for image in self.images),
            'project_counts': {project: len(images) for project, images in self.image_data.items()},
            'failed_projects': self.failed_projects,
        }
        action = self.SyncActions.PARTIAL if self.failed_projects else self.SyncActions.COMPLETE
        self._log_update(action, **report)
        self.logger.info(
            f'Public image sync for {self.env.project}: {report["image_count"]} families refreshed, '
            f'{report["enabled_count"]} enabled, {len(self.failed_projects)} publishers unavailable.'
        )
        return report

    def _save_catalog(self) -> None:
        existing_images = self.db.query(collection_name=self.collection) or []
        # A family moves to a new Compute image ID when its publisher releases
        # an update. Keep the Agoge selection ID and admin choice across versions.
        by_family = {}
        by_id = {}
        for record in sorted(existing_images, key=lambda item: item.get('uuid', '')):
            key = (record.get('project'), record.get('family'))
            if key not in by_family or record.get('is_enabled') is False:
                by_family[key] = record
            by_id[(record.get('project'), str(record.get('global_id')))] = record

        operations = []
        retained_ids = set()
        for image in self.images:
            previous = by_family.get((image.project, image.family)) or by_id.get(
                (image.project, str(image.global_id))
            )
            if previous:
                image.uuid = previous.get('uuid') or image.uuid
                if previous.get('is_enabled') is not None:
                    image.is_enabled = previous['is_enabled']
            retained_ids.add(image.uuid)
            operations.append(
                self.db.operation(
                    collection_name=self.collection,
                    doc_id=image.uuid,
                    operation_type=DbOperationTypes.SET,
                    data=image.model_dump(),
                )
            )

        # Write usable replacements before removing obsolete entries. A fetch
        # failure must never erase that publisher's previously available images.
        self._write_catalog_batches(operations)
        to_delete = [
            self.db.operation(
                collection_name=self.collection,
                doc_id=record['uuid'],
                operation_type=DbOperationTypes.DELETE,
            )
            for record in existing_images
            if record.get('project') in self.successful_projects
            and record.get('uuid') and record['uuid'] not in retained_ids
        ]
        if to_delete:
            self._write_catalog_batches(to_delete)

    def _write_catalog_batches(self, operations: list) -> None:
        # The database's legacy multi-batch helper logs and suppresses failures.
        # Use single batches so a failed write reaches sync() before any pruning.
        for start in range(0, len(operations), 500):
            self.db.batch_write(operations[start:start + 500])

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
                    fallback_to_shared=False,
                )
                if image_family_request:
                    db_image = self._create_image_object(
                        image=image_family_request.image,
                        family=family,
                        project=project,
                        is_enabled=is_enabled
                    )
                    processed_images.append(db_image)
            except NotFound:
                self.logger.warning(
                    f"{self.class_name}:_get_family_images - family '{family}' "
                    f"not found in project '{project}'. Ignoring ..."
                )
                continue
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

            return sorted(families)
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
            'uuid': str(uuid5(NAMESPACE_URL, f'https://compute.googleapis.com/projects/{project}/global/images/family/{family}')),
            'global_id': str(image.id),
            'name': self._get_name_from_image(family),
            'self_link': image.self_link,
            'project': project,
            'family': family,
            'is_enabled': is_enabled,
            'creationTimestamp': image.creation_timestamp,
            'description': image.description,
            'disk_size': image.disk_size_gb,
            'architecture': normalize_architecture(image.architecture),
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
        action: int,
        **details,
    ) -> None:
        record = {
            'action': action,
            'update_time': datetime.now(UTC).isoformat(),
            **details,
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
