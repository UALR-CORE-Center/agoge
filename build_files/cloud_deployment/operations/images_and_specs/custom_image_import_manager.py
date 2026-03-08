import logging
from datetime import datetime, timezone
from pydantic_core import ValidationError
from typing import Optional, List

from api.utilities.gcp.compute.compute_resources import ComputeResources

from common.utilities.gcp.cloud_env import CloudEnv
from common.document_database import DocumentDatabaseFactory
from common.constants.database import (
    DbCollections,
    DATABASE_NAME,
    DatabaseTypes,
    DbOperationTypes,
)
from common.constants.build_constants import BuildConstants
from common.constants.states import ImageStatus
from common.models.agoge import AgogeImageModel, DiskModel

from .human_interaction import HumanInteraction
from .message import Message

# Configure module-level logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class CustomImageImportManager:
    """Manages GCE custom images and synchronizes them with Firestore.

    This class retrieves custom images from Google Compute Engine (GCE) and
    cross-references them with Firestore records. It identifies images that
    need to be added to Firestore and provides optional interactive prompts
    to confirm insertion.

    Attributes:
        env (CloudEnv): Holds environment details like project, zone, etc.
        env_dict (dict): A dictionary representation of environment variables.
        compute (ComputeResources): Manages interactions with GCE compute resources.
        db (Any): A Firestore (or other) database object created via DocumentDatabaseFactory.
        images (Optional[List[dict]]): Internal cache of images fetched from Firestore.
        existing_images (Optional[set]): Set of known image names from Firestore's IMAGE collection.
        catalog (Optional[List[dict]]): Catalog fetched from Firestore.
        current_timestamp (str): An ISO 8601 representation of the current UTC time.
        custom_images (Optional[List[dict]]): Custom images fetched from GCE.
        catalog_images (Optional[set]): Set of image names referenced in the catalog.
    """

    def __init__(self) -> None:
        """Initializes ImageManager, setting up environment variables,
        the ComputeManager, and a Firestore database connection.
        """
        logger.debug("Initializing ImageManager.")
        self.env = CloudEnv()
        self.env_dict = self.env.get_env()
        self.compute = ComputeResources(clean=True, env_dict=self.env_dict)
        self.db = DocumentDatabaseFactory.create_db_object(
            db_type=DatabaseTypes.firestore,
            database_name=DATABASE_NAME
        )
        self.message = Message()  # Potentially could use this class in addition to logs
        self.images: Optional[List[dict]] = None
        self.existing_images: Optional[set] = None
        self.catalog = None
        self.current_timestamp = datetime.now(timezone.utc).isoformat()

        # Set later in run()
        self.custom_images: Optional[List[dict]] = None
        self.catalog_images: Optional[set] = None

    def run(self) -> None:
        """Main entry point for syncing GCE custom images with Firestore.

        - Retrieves GCE custom images.
        - Fetches existing images and catalog references from Firestore.
        - Asks the user if new images should be added to Firestore.
        - Performs the Firestore synchronization in batches.
        """
        logger.info("Starting image sync process.")

        try:
            # Retrieve all custom images from GCE
            logger.debug("Fetching custom images from GCE.")
            self.custom_images = self.compute.get_custom_images()
        except Exception as e:
            logger.error(f"Failed to retrieve custom images from GCE: {e}")
            return

        # Retrieve existing images from Firestore
        self._fetch_existing_images()

        # Retrieve the catalog from Firestore
        self._fetch_catalog()

        images_with_lab_spec, orphaned_images = self._categorize_images()

        images_to_add = self._handle_images_with_lab_spec(images_with_lab_spec)
        self._handle_orphaned_images(orphaned_images, images_to_add)

        # Sync with Firestore
        self._sync_with_firestore(images_to_add)
        msg = f"Added {len(images_with_lab_spec)} images (with lab specs) to the database."
        logger.info(msg)

    def _fetch_existing_images(self) -> None:
        """Fetches existing images from the Firestore IMAGE collection."""
        logger.debug("Querying existing images from Firestore.")
        self.existing_images = set()
        try:
            image_specs = self.db.query(collection_name=DbCollections.IMAGE)
            for image in image_specs:
                if "image" in image:
                    self.existing_images.add(image["image"])
            logger.debug(f"Found {len(self.existing_images)} existing images in Firestore.")
        except Exception as e:
            logger.error(f"Failed to fetch images from Firestore: {e}")
            self.existing_images = set()

    def _fetch_catalog(self) -> None:
        """Fetches the catalog from the Firestore CATALOG collection."""
        logger.debug("Querying catalog from Firestore.")
        self.catalog_images = set()
        try:
            specs = self.db.query(collection_name=DbCollections.CATALOG)
            for spec in specs:
                for server in spec.get("servers", []):
                    image = server.get("image")
                    if image:
                        self.catalog_images.add(image)
            logger.debug(f"Found {len(self.catalog_images)} catalog references to images.")
        except Exception as e:
            logger.error(f"Failed to fetch catalog from Firestore: {e}")
            self.catalog_images = set()

    def _categorize_images(self):
        """Categorize custom images into those that have a corresponding lab
        specification and those that do not (orphaned).

        Returns:
            tuple: (images_with_lab_spec, orphaned_images), both of which are lists
            of prepared `AgogeImageModel` objects.
        """
        logger.debug("Categorizing custom images into lab-associated and orphaned.")
        images_with_lab_spec = []
        orphaned_images = []

        if not self.custom_images:
            logger.warning("No custom images returned from GCE.")
            return images_with_lab_spec, orphaned_images

        for image in self.custom_images:
            image_name = image.get("name", "")
            if not image_name:
                logger.warning("Encountered a custom image without a name. Skipping.")
                continue

            if image_name not in self.existing_images:
                resp = input(f"Custom image '{image_name}' not found in catalog. Add it? (y/N): ").strip().lower()
                if resp not in {"y", "yes"}:
                    logger.info("User skipped image %s", image_name)
                    continue  # skip to next image
                prepared_image = self._prepare_image(image)
                if not prepared_image:
                    # Log is already handled in `_prepare_image` for ValidationError.
                    continue

                if image_name in self.catalog_images:
                    images_with_lab_spec.append(prepared_image)
                else:
                    orphaned_images.append(prepared_image)
        logger.debug(
            f"Identified {len(images_with_lab_spec)} images with lab spec and "
            f"{len(orphaned_images)} orphaned images."
        )
        return images_with_lab_spec, orphaned_images

    def _handle_images_with_lab_spec(
        self,
        images_with_lab_spec: List[AgogeImageModel]
    ) -> List[dict]:
        """Interactively handles images that already have a lab spec.

        Args:
            images_with_lab_spec (List[AgogeImageModel]): Prepared images that match a lab spec.

        Returns:
            List[dict]: List of dicts (ready to sync) for images the user chooses to add.
        """
        images_to_add = []
        if images_with_lab_spec:
            add_all = self.message.confirm("Do you want to add all images corresponding labs to the database")

            if add_all:
                for image in images_with_lab_spec:
                    images_to_add.append(image.model_dump())
                logger.info(f"User chose to add {len(images_with_lab_spec)} images with lab spec.")
            else:
                logger.info("User skipped adding lab spec images.")
        return images_to_add

    def _handle_orphaned_images(
        self,
        orphaned_images: List[AgogeImageModel],
        images_to_add: List[dict]
    ) -> None:
        """Interactively handles images that do not have a corresponding lab spec.

        Args:
            orphaned_images (List[AgogeImageModel]): Prepared images without a lab spec.
            images_to_add (List[dict]): A mutable list of images to add to Firestore.
        """
        for image in orphaned_images:
            add_orphaned = self.message.confirm(f"Image '{image.name}' does not have a corresponding lab. "
                                                f"Do you want to make it available for custom labs")

            if add_orphaned:
                images_to_add.append(image.model_dump())
                logger.info(f"Adding orphaned image '{image.name}' to batch database insert.")
            else:
                logger.info(f"User skipped adding orphaned image '{image.name}'.")

    def _sync_with_firestore(self, images: List[dict]) -> None:
        """Commits a batch of images to Firestore.

        Args:
            images (List[dict]): List of image dictionaries ready for Firestore insertion.
        """
        if not images:
            logger.info("No images to sync with Firestore.")
            return

        logger.debug("Preparing batch Firestore operations.")
        operations = []
        for image in images:
            # Create a Firestore batch “operation” for each image
            operation = self.db.operation(
                collection_name=DbCollections.IMAGE,
                doc_id=image["name"],
                data=image,
                operation_type=DbOperationTypes.SET
            )
            operations.append(operation)

        try:
            # Commit all operations in one batch
            self.db.batch_write(operations)
            logger.info(f"Synced {len(images)} images to Firestore.")
        except Exception as e:
            logger.error(f"Failed to batch write images to Firestore: {e}")

    def _prepare_image(self, input_image: dict) -> Optional[AgogeImageModel]:
        """Prepares a raw GCE image dict into an `AgogeImageModel`.

        Args:
            input_image (dict): Raw image data from GCE.

        Returns:
            Optional[AgogeImageModel]: A valid `AgogeImageModel`, or None if there's a ValidationError.
        """
        if not input_image:
            logger.warning("Received an empty image dictionary. Skipping.")
            return None

        logger.debug(f"Preparing image '{input_image.get('name', 'unknown')}'.")
        image_license = next(iter(input_image.get("licenses", [])), None)
        if not image_license:
            os = ""
            base_family = ""
        else:
            base_family = image_license.rsplit("/", 1)[-1]
            if "windows" in image_license.lower():
                os = "windows"
            else:
                os = "linux"

        source_image = input_image.get("sourceImage", input_image.get("sourceDisk", ""))

        disk_model = {
            "boot": True,
            "autoDelete": True,
            "initializeParams": {
                "diskSizeGb": input_image.get("diskSizeGb"),
                "sourceImage": source_image,
                "type": (
                    f"https://www.googleapis.com/compute/v1/projects/"
                    f"{self.env.project}/zones/{self.env.zone}/diskType/pd-standard"
                ),
            },
        }
        add_human_interaction = self.message.confirm(f"Add human interaction to image "
                                                     f"[{input_image.get('name', 'unknown')}]")
        human_interaction = []
        if add_human_interaction:
            human_interaction = HumanInteraction().create()

        try:
            disk = DiskModel(**disk_model)
            prepared_image = AgogeImageModel(
                name=input_image.get("name", "").removeprefix("image-"),
                machine_type=BuildConstants.GoogleMachineTypes.E2_STANDARD_2.value,
                description="",
                tags=[],
                image=input_image.get("name", ""),
                os=os,
                add_disk=input_image.get("diskSizeGb"),
                disks=[disk],
                human_interaction=human_interaction,
                status=ImageStatus.CHECKED_IN.value,
                services=[],
                self_link=input_image.get("selfLink"),
                dns_record="",
                base_family=base_family,
                image_exists=True
            )
            return prepared_image
        except ValidationError as e:
            logger.error(f"Validation error for {input_image.get('name', 'unknown')}: {e}")
            return None
