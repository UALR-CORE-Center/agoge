import os
import subprocess
from typing import Any, Tuple

from google.api_core.exceptions import NotFound, BadRequest, Forbidden
from google.cloud.exceptions import GoogleCloudError
from google.cloud import compute_v1

from .base_image_to_cloud import BaseImageToCloud, ImageTypes


class LocalToCloud(BaseImageToCloud):
    def __init__(self):
        super().__init__()

        self.image_system_path = None
        self.image_tar_path = None
        self.tar_path = None

    @property
    def _image_tar_name(self) -> str:
        return f"{self.image_name}.tar.gz"

    def _additional_sync_tasks(self) -> None:
        image_path = input("Enter path to VM image to upload to cloud project: ")
        if image_path:
            image_path = os.path.expanduser(image_path)

            if not os.path.isfile(image_path):
                self.message.error(f"The file at '{image_path}' does not exist.")
                raise FileNotFoundError

            self.image_type = image_path.split(".")[-1]
            if not ImageTypes.valid_type(self.image_type):
                self.message.error(
                    f"Unsupported file type. Please use one of {ImageTypes.all()}"
                )
                raise ValueError
            elif self.image_type == ImageTypes.RAW:
                self.message.warning(
                    f"Detected image of type [{self.image_type}]. Prefer to use other valid types "
                    f"[{ImageTypes.VMDK}, {ImageTypes.VDI}, or {ImageTypes.QCOW2}]")

            self.image_system_path = image_path
            self.server_name, self.image_name = self._get_image_name()

            self._compress()

            # Upload image to predefined bucket
            image_url = self._upload_to_bucket()
            if image_url:
                self.message.success(f"Image uploaded to [{image_url}]")

            # Import image from Bucket to Compute
            if self._import(image_url):
                self.message.success("Image import complete.")

            self._delete_from_bucket()

    def _compress(self) -> bool:
        if self.image_type == ImageTypes.RAW:
            image_directory = os.path.dirname(self.image_system_path)
            self.image_tar_path = os.path.join(image_directory, self._image_tar_name)
            self.message.info(f"Compressing to [{self.image_tar_path}]")

            command = (f"--format=oldgnu -Sczf {self.image_tar_path} -C "
                       f"{image_directory} {os.path.basename(self.image_system_path)}")
            if self.system.lower() in ['linux', 'windows']:
                compress = f"tar {command}"
            else:
                compress = f"gtar {command}"
            return self._run_command(compress)
        return True

    def _upload_to_bucket(self) -> str:
        """Uploads image to bucket with error handling."""
        while True:
            try:
                self.message.info(f"Uploading image to [{self.bucket_name}]. This could take a few minutes ...")
                bucket = self.bucket_mgr.get_bucket(self.bucket_name)
                blob = bucket.blob(self._image_tar_name)
                blob.upload_from_filename(self.image_tar_path)
                return blob.public_url
            except NotFound as e:
                self.message.error(f"Bucket [{self.bucket_name}] not found: {e}")
                self.message.info(f"Attempting to create bucket [{self.bucket_name}]...")
                if self.create_bucket():
                    continue
                raise e
            except Forbidden as e:
                self.message.error(f"Permission denied for bucket [{self.bucket_name}]: {e}")
                raise e
            except GoogleCloudError as e:
                self.message.error(f"GCP error during upload: {e}")
                raise e
            except Exception as e:
                self.message.error(f"Unexpected error during upload: {e}")
                raise e

    def _import(self, image_url: str) -> bool:
        try:
            raw_disk = compute_v1.RawDisk(source=image_url)
            image = compute_v1.Image(
                name=self.image_name,
                source_type="RAW",
                raw_disk=raw_disk,
            )
            operation = self.compute.insert(project=self.env.project, image_resource=image)
            self.message.info(f"Started image import: [{operation.name}]. This could take a few minutes ...")

            # Wait for operation to complete
            return self._follow_operation(operation)
        except BadRequest as e:
            self.message.error(f"Bad request when importing image: {e}")
            raise e
        except Forbidden as e:
            self.message.error(f"Permission denied during image import: {e}")
            raise e
        except NotFound as e:
            self.message.error(f"Image URL or resources not found during import: {e}")
            raise e
        except GoogleCloudError as e:
            self.message.error(f"GCP error during image import: {e}")
            raise e
        except Exception as e:
            self.message.error(f"Unexpected error during image import: {e}")
            raise e

    def _delete_from_bucket(self) -> None:
        try:
            bucket = self.bucket_mgr.bucket(self.bucket_name)
            blob = bucket.blob(self.bucket_url)
            blob.delete()
            self.message.success(f"Successfully deleted image from bucket [{self.bucket_url}]")
            self.message.info(f"Local image tar exists at [{self.image_tar_path}]")
        except NotFound:
            self.message.warning(f"Blob [{self.bucket_url}] not found. It might have been deleted already.")
        except Forbidden as e:
            self.message.error(f"Permission denied while deleting blob: {e}")
        except GoogleCloudError as e:
            self.message.error(f"Error with GCP service while deleting blob: {e}")
        except Exception as e:
            self.message.error(f"Unexpected error during cleanup: {e}")

    def _cleanup_tasks(self) -> None:
        pass

    def get_image_os(self, image: Any) -> Tuple[str, str]:
        return self._get_image_os()

    def get_image_name(self) -> Tuple[str, str]:
        return self._get_image_name()

    def _run_command(self, command: str) -> bool:
        ret = subprocess.run(command, capture_output=True, shell=True, text=True)
        ret_msg = ret.stderr.strip() or ret.stdout.strip()  # Log stderr if available, else stdout
        if ret.returncode != 0:
            self.message.error(f"{ret_msg}")
            raise Exception
        return True
