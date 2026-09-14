import logging
from pydantic_core import ValidationError
from typing import Optional

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
    """Register existing GCE images for selection in the app's server library."""

    def __init__(self, project: Optional[str] = None) -> None:
        """Initializes ImageManager, setting up environment variables,
        the ComputeManager, and a Firestore database connection.
        """
        logger.debug("Initializing ImageManager.")
        self.env = CloudEnv(project=project)
        self.env_dict = self.env.get_env()
        self.compute = ComputeResources(clean=True, env_dict=self.env_dict)
        self.db = DocumentDatabaseFactory.create_db_object(
            db_type=DatabaseTypes.firestore,
            database_name=DATABASE_NAME,
            project_id=self.env.project,
        )
        self.message = Message()
        self.existing_images: set[str] = set()

    def run(self) -> None:
        """Save each accepted image without requiring an existing lab specification."""
        self.message.info(
            f"Importing GCP images from project '{self.env.project}' into Firestore "
            f"database '{DATABASE_NAME}', collection '{DbCollections.IMAGE.value}'."
        )

        try:
            custom_images = self.compute.get_custom_images()
        except Exception as e:
            self.message.error(f"Failed to retrieve custom images from GCP: {e}")
            return

        try:
            self._fetch_existing_images()
        except Exception as e:
            self.message.error(f"Import stopped: could not read existing images from Firestore: {e}")
            return

        imported = skipped = failed = 0
        for image in custom_images or []:
            image_name = image.get("name", "")
            if not image_name:
                self.message.warning("Encountered a custom image without a name. Skipping.")
                failed += 1
                continue
            if image_name in self.existing_images:
                skipped += 1
                continue

            resp = input(
                f"Custom image '{image_name}' is not registered in the app. "
                "Import it for server selection? (y/N): "
            ).strip().lower()
            if resp not in {"y", "yes"}:
                skipped += 1
                continue

            prepared_image = self._prepare_image(image)
            if prepared_image and self._save_image(prepared_image):
                self.existing_images.add(image_name)
                imported += 1
            else:
                failed += 1

        self.message.info(
            f"Imported {imported} image(s); skipped {skipped}; failed {failed}."
        )

    def _fetch_existing_images(self) -> None:
        """Read registered images; abort the import if this lookup fails."""
        image_specs = self.db.query(collection_name=DbCollections.IMAGE)
        self.existing_images = {
            image["image"] for image in image_specs if image.get("image")
        }

    def _save_image(self, image: AgogeImageModel) -> bool:
        """Commit an accepted image before prompting for the next one."""
        try:
            operation = self.db.operation(
                collection_name=DbCollections.IMAGE,
                doc_id=image.name,
                data=image.model_dump(),
                operation_type=DbOperationTypes.SET
            )
            self.db.batch_write([operation])
        except Exception as e:
            self.message.error(f"Failed to save image '{image.image}' to Firestore: {e}")
            return False

        self.message.success(
            f"Saved '{image.image}' to project '{self.env.project}', database "
            f"'{DATABASE_NAME}', document '{DbCollections.IMAGE.value}/{image.name}'. "
            "It is now registered for server selection."
        )
        return True

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

        # sourceImage/sourceDisk describe how the custom image was created.
        # New servers must boot from the custom image itself.
        source_image = input_image.get("selfLink") or (
            f"https://www.googleapis.com/compute/v1/projects/{self.env.project}/"
            f"global/images/{input_image['name']}"
        )

        disk_model = {
            "boot": True,
            "autoDelete": True,
            "initializeParams": {
                "diskSizeGb": input_image.get("diskSizeGb"),
                "sourceImage": source_image,
                "type": (
                    f"https://www.googleapis.com/compute/v1/projects/"
                    f"{self.env.project}/zones/{self.env.zone}/diskTypes/pd-standard"
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
                self_link=source_image,
                dns_record="",
                base_family=base_family,
                image_exists=True
            )
            return prepared_image
        except ValidationError as e:
            self.message.error(
                f"Could not import '{input_image.get('name', 'unknown')}': "
                f"{e.errors(include_input=False)}"
            )
            return None
