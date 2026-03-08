from typing import Optional
from google.cloud import storage

from ...constants.buckets import Buckets
from ..id_generator import IdGenerator
from .cloud_env import CloudEnv
from .cloud_logger import Logger, LoggerNames


class BucketManager:
    def __init__(
        self,
        log_name: str = LoggerNames.CLOUD_FN,
        env_dict: dict = None
    ) -> None:
        self.class_name = self.__class__.__name__
        self.env = CloudEnv(env_dict=env_dict) if env_dict else CloudEnv()
        self.logger = Logger(log_name, class_name=self.class_name)
        self.bucket_manager = storage.Client()

    def _get_bucket(self, suffix) -> str:
        return f"{self.env.project}_{suffix}"

    def get(
        self,
        bucket: str,
        file: str
    ) -> str:
        bucket = self.bucket_manager.get_bucket(bucket)
        blob = bucket.get_blob(file)
        if not blob:
            self.logger.error(f"Requested file was not found in bucket.", file=file, bucket=bucket)
            raise FileNotFoundError
        file_contents = blob.download_as_string()
        return file_contents

    def put(
        self,
        bucket: str,
        file: Optional[str] = None,
        name: Optional[str] = None,
        from_file: bool = True,
        file_content: Optional[bytes] = None
    ) -> None:
        bucket_name = self._get_bucket(Buckets.BUILD_SPEC_BUCKET_SUFFIX)
        new_bucket = self.bucket_manager.get_bucket(bucket_name)

        if from_file:
            filename = f'{bucket}{file}'.lower()
            new_blob = new_bucket.blob(filename)
            with open(filename, 'rb') as temp:
                new_blob.upload_from_file(temp, content_type='application/octet-stream')
                temp.close()
        else:
            filename = f'{bucket}{name or file}'.lower()
            new_blob = new_bucket.blob(filename)
            if file_content:
                new_blob.upload_from_string(file_content, content_type='application/octet-stream')
            else:
                raise ValueError("No file content provided for upload.")

    def upload_image(
        self,
        image_name: str,
        image_content: bytes,
        bucket: str = Buckets.MARKDOWN_BUCKET_SUFFIX,
        use_uuid: bool = True,
        make_public: bool = False
    ) -> str:
        """
        Uploads an image to the specified folder within the given bucket.

        :param image_name: The name of the image file.
        :param image_content: The content of the image file.
        :param bucket: The name of the bucket (default is 'build-specs').
        :param use_uuid: Whether to append a UUID to the image name to ensure uniqueness (default is True).
        :param make_public: Whether to make image publicly accessible.
        """
        if use_uuid:
            unique_id = IdGenerator.uuid()
            base_name, ext = image_name.rsplit('.', 1)
            unique_image_name = f"{base_name}_{unique_id}.{ext}".lower()
        else:
            unique_image_name = image_name.lower()

        # Construct the full path including the folder
        file_path = f'{unique_image_name}'.lower()

        # Get the bucket object
        bucket_name = self._get_bucket(bucket)
        new_bucket = self.bucket_manager.get_bucket(bucket_name)
        new_blob = new_bucket.blob(file_path)

        # Upload the image
        new_blob.upload_from_string(image_content, content_type='image/png')

        # Make the file public if specified
        if make_public:
            new_blob.make_public()
            return new_blob.public_url

        # Return the permanent URL for the private image
        return f"https://storage.cloud.google.com/{new_bucket.name}/{file_path}"

    def get_scripts(self) -> list[str]:
        """
        Get the names of scripts in the spec folder.
        Returns: List

        """
        bucket = self.bucket_manager.get_bucket(f"{self.env.project}_{Buckets.BUILD_SPEC_BUCKET_SUFFIX}")
        scripts = []
        for blob in bucket.list_blobs(prefix=Buckets.Folders.STARTUP_SCRIPTS):
            scripts.append(blob.name)
        return scripts

    def get_workouts(self) -> list[str]:
        """Retrieves list of standard Cyber Gym workout spec files"""
        folder_name = Buckets.Folders.SPECS.value
        bucket = self.bucket_manager.get_bucket(CloudEnv().spec_bucket)

        workout_specs = []
        for blob in bucket.list_blobs(prefix=folder_name):
            blob_name = blob.name
            formatted_blob_name = blob_name.replace(folder_name, "").split('.')[0]
            if formatted_blob_name != "":
                workout_specs.append(formatted_blob_name)
        return workout_specs

    def get_attacks(self) -> list[str]:
        # TODO: Update the following two lines to match current standards
        bucket_name = 'ualr-cybersecurity_build-specs'
        folder_name = 'attacks'
        bucket = self.bucket_manager.get_bucket(bucket_name)

        attacks = []
        for blob in bucket.list_blobs(prefix=folder_name):
            blob_name = blob.name
            formatted_blob_name = blob_name.replace(folder_name, "").split('/')[1]
            if formatted_blob_name != 'attack.yaml':
                attack_spec = blob.download_as_string()
                attacks.append(attack_spec)
        return attacks

    def get_class_list(self) -> list[str]:
        """Returns list of all spec names used for building fixed-arena classes"""
        bucket = self.bucket_manager.get_bucket(self.env.spec_bucket)
        class_list = []
        for blob in bucket.list_blobs():
            formatted_blob_name = blob.name.replace(self.env.spec_bucket, "").split('/')[1]
            if 'class' in formatted_blob_name:
                class_list.append(formatted_blob_name.split(".yaml")[0])
        return class_list
