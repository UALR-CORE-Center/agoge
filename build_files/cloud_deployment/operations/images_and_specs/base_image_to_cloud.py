import json
import platform
import re
import time
from typing import List, Tuple, Any, Set, Dict
from google.api_core.exceptions import NotFound, Forbidden
from google.api_core.extended_operation import ExtendedOperation
from google.cloud import compute_v1
from google.cloud.exceptions import GoogleCloudError, BadRequest
from googleapiclient.errors import HttpError

from api.utilities.gcp.compute.compute_resources import ComputeResources
from cloud_functions.cloud_fn_utilities.course_objects.compute.google_image_sync_manager import GoogleImageSyncManager
from common.constants.database import DbCollections, DATABASE_NAME, DatabaseTypes
from common.constants.google import ImageProjects
from common.models.agoge import AgogeImageModel, ImageStatus
from common.models.google import DiskModel, DiskInitializeParamsModel
from common.utilities.gcp.cloud_env import CloudEnv
from common.utilities.gcp.bucket_manager import BucketManager
from common.exceptions.agoge import NotFound
from common.document_database.factory import DocumentDatabaseFactory

from .human_interaction import HumanInteraction
from .message import Message


class ImageTypes:
    IMG = 'img'
    RAW = 'raw'
    VMDK = 'vmdk'
    VHD = 'vhd'
    VDI = 'vdi'
    QCOW2 = 'qcow2'

    @classmethod
    def valid_type(cls, img_type: str) -> bool:
        """Check if the provided image type is valid.

        Args:
            img_type: The image type to validate.

        Returns:
            True if img_type is valid, False otherwise.
        """
        return img_type in cls.all()

    @classmethod
    def all(cls):
        return [cls.IMG, cls.RAW, cls.VMDK, cls.VHD, cls.VDI, cls.QCOW2]


class BaseImageToCloud:
    RESERVED_NAMES = ["agoge", "display", "project"]

    def __init__(self) -> None:
        self.env = CloudEnv()
        self.env_dict = self.env.get_env()
        self.message = Message()
        self.compute = compute_v1.ImagesClient()
        self.db = DocumentDatabaseFactory.create_db_object(
            db_type=DatabaseTypes.firestore,
            database_name=DATABASE_NAME
        )
        self.projects = ImageProjects
        self.generic_family = GoogleImageSyncManager.GenericFamily
        self.bucket_mgr = BucketManager(env_dict=self.env_dict).bucket_manager
        self.bucket_name = f"temp-disks-{self.env.project}"
        self.system = platform.system()
        self.reserved_names = self._reserved_names()

        # Image variables
        self.old_image = None
        self.image_type = None
        self.server_name = None
        self.image_name = None
        self.bucket_url = None

    def copy_image(
        self,
        image: Any,
        destination_name: str
    ) -> bool:
        """Copy an existing image to a new image with a different name.

        Args:
            image: The existing image to copy.
            destination_name: The name of the new image.

        Returns:
            True if the image was copied successfully.

        Raises:
            BadRequest: If the request was invalid.
            Forbidden: If permission is denied.
            NotFound: If the image was not found.
            GoogleCloudError: For other GCP-related errors.
            Exception: For unexpected errors.
        """
        self.old_image = image
        image = compute_v1.Image(
            name=destination_name,
            source_image=self.old_image.self_link
        )
        try:
            operation = self.compute.insert(project=self.env.project, image_resource=image)
            self.message.info(f"Started image copy: [{operation.name}]. This could take a few minutes ...")

            # Wait for operation to complete
            return self._follow_operation(operation)
        except BadRequest as e:
            self.message.error(f"Bad request when copying image: {e}")
            raise e
        except Forbidden as e:
            self.message.error(f"Permission denied during image copy: {e}")
            raise e
        except NotFound as e:
            self.message.error(f"Image URL or resources not found during copy: {e}")
            raise e
        except GoogleCloudError as e:
            self.message.error(f"GCP error during image copy: {e}")
            raise e
        except Exception as e:
            self.message.error(f"Unexpected error during image copy: {e}")
            raise e

    def delete_image(self, image: Any) -> bool:
        """Delete an image from Google Cloud.

        Args:
            image: The image to delete.

        Returns:
            True if the image was deleted successfully.

        Raises:
            BadRequest: If the request was invalid.
            Forbidden: If permission is denied.
            NotFound: If the image was not found.
            GoogleCloudError: For other GCP-related errors.
            Exception: For unexpected errors.
        """
        try:
            operation = self.compute.delete(project=self.env.project, image=image.name)
            self.message.info(f"Started image delete: [{operation.name}]. This could take a few minutes ...")

            return self._follow_operation(operation)
        except BadRequest as e:
            self.message.error(f"Bad request when deleting image: {e}")
            raise e
        except Forbidden as e:
            self.message.error(f"Permission denied during image delete: {e}")
            raise e
        except NotFound as e:
            self.message.error(f"Image URL or resources not found during delete: {e}")
            raise e
        except GoogleCloudError as e:
            self.message.error(f"GCP error during image delete: {e}")
            raise e
        except Exception as e:
            self.message.error(f"Unexpected error during image delete: {e}")
            raise e

    def create_bucket(self) -> bool:
        try:
            bucket = self.bucket_mgr.create_bucket(self.bucket_name)
            return True if bucket else False
        except HttpError as e:
            self.message.error(f'Failed to create bucket [{self.bucket_name}] with reason {e}')
            raise

    def run(self) -> None:
        """Synchronize the image by performing additional tasks and updating the database.

        Raises:
            NotFound: If the image could not be retrieved after retries.
            Exception: For unexpected errors during synchronization.
        """
        self._additional_sync_tasks()

        # Create database object
        if image := self._get_image():
            self._create_db_object(image)
            self._cleanup_tasks()
            self.message.success(f"Image [{self.image_name}] synchronized with database.")
        else:
            self.message.error("Could not retrieve image after multiple attempts.")
            raise NotFound("Image not found after max retries.")

    def _get_image(
        self,
        image_name: str = None,
        retry: bool = True
    ) -> Any:
        """Retrieve an image from Google Cloud.

        Args:
            image_name: The name of the image to retrieve.
            retry: Whether to retry fetching the image upon failure.

        Returns:
            The image object if found, else None.
        """
        image = None
        name = self.image_name or image_name
        if name:
            attempts = 5 if retry else 1
            for attempt in range(attempts):
                try:
                    self.message.info(f"Fetching image details (attempt {attempt + 1}/{attempts})...")
                    image = self.compute.get(project=self.env.project, image=name)
                    break
                except NotFound as e:
                    self.message.error(f"Image not found: {e}")
                    time.sleep(attempts)
                except Forbidden as e:
                    self.message.error(f"Permission denied when fetching image details: {e}")
                    raise e  # Critical, likely configuration issue
                except GoogleCloudError as e:
                    self.message.error(f"GCP error while fetching image details: {e}")
                    time.sleep(attempts)
                except Exception as e:
                    self.message.error(f"Unexpected error: {e}")
                    time.sleep(attempts)
        return image

    def _additional_sync_tasks(self) -> None:
        """Perform additional synchronization tasks.

        Raises:
            NotImplementedError: This method should be implemented by subclasses.
        """
        raise NotImplemented

    def _cleanup_tasks(self) -> None:
        """Perform cleanup tasks after synchronization.

        Raises:
            NotImplementedError: This method should be implemented by subclasses.
        """
        raise NotImplemented

    def _import(self, image_url: str) -> bool:
        """Initiate image import from a bucket to compute and follow the API operation.

        Args:
            image_url: The URL of the image to import.

        Returns:
            True if the import was successful.

        Raises:
            NotImplementedError: This method should be implemented by subclasses.
        """
        raise NotImplemented

    def _create_db_object(self, image) -> None:
        """Create a database object for the image.

        Args:
            image: The image object to create a database entry for.

        Raises:
            Exception: For unexpected errors during database object creation.
        """
        disks = self._create_disk(image)
        general_os, base_family = self.get_image_os(image)
        machine_type = self._get_machine_type()
        services = self._get_services()
        description = self._get_description()
        human_interaction = HumanInteraction().create()

        try:
            img = AgogeImageModel(
                name=self.server_name,
                image=self.image_name,
                status=ImageStatus.CHECKED_IN.value,
                image_exists=True,
                self_link=image.self_link,
                add_disk=str(image.disk_size_gb),
                disks=disks,
                base_family=base_family,
                os=general_os,
                machine_type=machine_type,
                services=services,
                description=description,
                human_interaction=human_interaction,
                tags=["http-server", "https-server"]
            )

            self.message.default(f"---- {self.server_name} JSON ---- ")
            print(json.dumps(img.model_dump(), indent=2))
            self.message.default(f"---- END JSON ---- ")

            self.db.update(
                collection_name=DbCollections.IMAGE,
                doc_id=self.server_name,
                data=img.model_dump()
            )
        except Exception as e:
            self.message.error(f"Unexpected error during synchronization: {e}")
            raise e

    def _create_disk(
        self,
        image: Any
    ) -> List[Dict]:
        """Create a disk model from the image.

        Args:
            image: The image to create the disk from.

        Returns:
            A list containing the disk model.
        """
        initial_params = DiskInitializeParamsModel(
            sourceImage=image.self_link,
            diskSizeGb=image.disk_size_gb,
            type=f"projects/{self.env.project}/zones/{self.env.zone}/diskTypes/pd-standard"
        )
        disk_model = DiskModel(
            boot=True,
            autoDelete=True,
            initializeParams=initial_params
        )
        return [disk_model.model_dump()]

    def _get_services(self) -> List[str]:
        """Interactively get a list of services to associate with the image.

        Returns:
            A list of service names.
        """
        services = []
        if self.message.confirm("Add image services list"):
            while True:
                service = str(input("Enter a service: "))
                services.append(service)

                if not self.message.confirm("Add another service"):
                    break

        self.message.info(f"Setting services to {services}")
        return services

    def _get_description(self) -> str:
        """Interactively get a description for the image.

        Returns:
            The image description.
        """
        if self.message.confirm("Add an image description"):
            while True:
                description = str(input("Enter a general description: "))
                if self.message.confirm("Set description to", description):
                    return description
        return "Agoge managed image."

    def _get_machine_type(self) -> str:
        """Interactively select a machine type for the image.

        Returns:
            The selected machine type name.
        """
        machine_types_resp = ComputeResources().get_machine_types()
        machine_types = {idx: m_type for idx, m_type in enumerate(machine_types_resp)}

        selected_idx = None
        while True:
            print("\nAvailable Machine Types: ")
            for key, m_type in machine_types.items():
                self.message.default(f"[{key}] {m_type.name} - {m_type.description}", indent=True)

            try:
                selected_idx = int(input("Select a machine type: "))
                if selected_m_type := machine_types.get(selected_idx):
                    if self.message.confirm("Set machine type to", selected_m_type.name):
                        return selected_m_type.name
                    continue
                else:
                    self.message.error(f"Invalid selection: {selected_idx}")
            except ValueError:
                self.message.error("Unrecognized or unsupported input type.")

    def get_image_os(self, image: Any) -> Tuple[str, str]:
        """Get the general OS type and base family of the image.

        Args:
            image: The image to determine the OS from.

        Returns:
            A tuple containing the general OS type and the base family.

        Raises:
            NotImplementedError: This method should be implemented by subclasses.
        """
        raise NotImplemented("_get_image_os not implemented for class")

    def _get_image_os(self) -> Tuple[str, str]:
        """Interactively get the OS and base family of the image.

        Returns:
            A tuple containing the general OS type and the base family.
        """
        general_os = self.generic_family.LINUX

        while True:
            base_family = str(input("Enter image license (i.e. Ubuntu  20.04, Debian 12, etc.): "))
            if "windows" in base_family.lower():
                general_os = self.generic_family.WINDOWS

            base_family = base_family.lower().replace(" ", "-")
            if self.message.confirm(f"Set image license to", base_family):
                return general_os, base_family

    def get_image_name(self) -> Tuple[str, str]:
        """Interactively get the image name.

        Returns:
            A tuple containing the image name and formatted image name.

        Raises:
            NotImplementedError: This method should be implemented by subclasses.
        """
        raise NotImplemented("get_image_name is not implemented for this instance")

    def _get_image_name(self) -> Tuple[str, str]:
        """Interactively get and validate the image name.

        Returns:
            A tuple containing the image name and the formatted image name.
        """
        while True:
            name = str(input("Enter image name: "))

            # Validate input name matches expected format
            if not self._validate_image_name(name):
                continue

            if self.message.confirm("Set image to", name):
                return name, f'image-{name}'

    def _validate_image_name(self, name) -> bool:
        """Validate the provided image name meets Cloud-defined requirements.

        Args:
            name: The image name to validate.

        Returns:
            True if the name is valid, False otherwise.
        """
        # Check for empty input
        if not name.strip():
            self.message.error("Image name cannot be empty.")
            return False

        # Validate name matches allowed pattern
        if not re.match(r"^[a-z][-a-z0-9]{0,56}[a-z0-9]$", name):
            self.message.error(
                "Image name must be 1-56 characters long and contain only lowercase letters, "
                "numbers, and hyphens. It must start with a letter and end with a letter or number."
            )
            return False

        # Validate name doesn't already exist in database
        if name in self.reserved_names:
            self.message.error(
                f"Name, {name}, is already in use by another image. "
            )
            return False
        return True

    def _follow_operation(
        self,
        operation: ExtendedOperation
    ) -> bool:
        """Wait for a Google Cloud operation to complete.

        Args:
            operation: The operation to wait for.

        Returns:
            True if the operation completed successfully.

        Raises:
            RuntimeError: If the operation did not complete successfully.
        """
        result = operation.result(timeout=300)

        try:
            if result and result.error_code:
                self.message.error(f"Failed to import image: {operation.error_message}")
                raise operation.exception() or RuntimeError(operation.error_message)
        except AttributeError as e:
            self.message.error(f"Operation result is invalid or None: {e}")
            raise RuntimeError("Operation did not complete successfully.") from e
        return True

    def _reserved_names(self) -> Set:
        """Retrieve a set of existing image names (IDs) from the database.

        Returns:
            A set containing reserved image names.
        """
        images = self.db.query(collection_name=DbCollections.IMAGE)
        return {i['name'] for i in images}
