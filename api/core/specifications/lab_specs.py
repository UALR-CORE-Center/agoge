import json
from fastapi import File, UploadFile
from starlette.datastructures import FormData

from common.constants.buckets import Buckets
from common.constants.database import (
    DbCollections,
    DatabaseTypes,
    DATABASE_NAME
)
from common.document_database.factory import DocumentDatabaseFactory
from common.exceptions import BadRequest, NotFound, AgogeValidationError, ContentTooLarge
from common.models.agoge import CatalogModel
from common.models.model_validators.model_validator import ModelValidator
from common.utilities.gcp.bucket_manager import BucketManager
from common.utilities.gcp.cloud_env import CloudEnv
from common.utilities.gcp.cloud_logger import Logger, LoggerNames

from .utilities.language_lookup import LanguageLookup
from .utilities.file_manager import SpecFileManager


class LabSpecs:
    def __init__(
        self,
        env_dict: dict
    ) -> None:
        self.class_name = self.__class__.__name__
        self.log_name = LoggerNames.API
        self.logger = Logger(self.log_name, class_name=self.class_name)
        self.env = CloudEnv(log_name=self.log_name, env_dict=env_dict)
        self.env_dict = self.env.get_env()
        self.collection = DbCollections.CATALOG
        self.db = DocumentDatabaseFactory.create_db_object(
            db_type=DatabaseTypes.firestore,
            database_name=DATABASE_NAME,
            log_name=self.log_name
        )
        self.model_validator = ModelValidator(model=CatalogModel)

    def get(
        self,
        spec_id: str
    ) -> CatalogModel:
        if spec := self.db.get(collection_name=self.collection, doc_id=spec_id):
            return self.model_validator.load(data=spec, halt_on_error=False)
        raise NotFound(message="No specification found for given ID")

    def list(self) -> list[CatalogModel]:
        if specs := self.db.query(collection_name=self.collection):
            return self.model_validator.load(data=specs, halt_on_error=False)
        raise NotFound

    async def upload_file(
        self,
        file: File,
        form_data: FormData
    ) -> None:
        # process form
        sync_servers = self._parse_boolean(form_data.get('sync_servers', False))
        image_servers = self._parse_boolean(form_data.get('image_servers', False))

        # parse and validate uploaded file
        file_contents = await self.read_uploaded_json(file)
        lab_spec = SpecFileManager(env_dict=self.env_dict)
        lab_spec.load(spec=file_contents)
        valid, msg = lab_spec.is_valid()
        if not valid:
            raise AgogeValidationError(message=msg)
        lab_spec.save()

        if sync_servers or image_servers:
            lab_spec.sync_computer_images(create=image_servers)

    def delete(
        self,
        spec_id: str,
    ) -> None:
        if self.db.get(collection_name=self.collection, doc_id=spec_id):
            self.db.delete(collection_name=self.collection, doc_id=spec_id)
            return
        raise NotFound(message="Could not find specification with given ID")

    def list_startup_scripts(self):
        bucket_mgr = BucketManager(log_name=self.log_name, env_dict=self.env_dict)
        scripts = bucket_mgr.get_scripts()
        return scripts

    async def upload_script(
        self,
        file: File,
        form_data: FormData
    ) -> None:
        filename = form_data.get('filename') or file.filename
        if not filename:
            raise BadRequest(message='No selected file')

        # Validates filename and extension
        LanguageLookup.validate(filename)

        bucket_mgr = BucketManager(log_name=self.log_name, env_dict=self.env_dict)
        try:
            contents = await file.read()
            bucket_mgr.put(
                bucket=Buckets.Folders.STARTUP_SCRIPTS.value,
                name=filename,
                file_content=contents,
                from_file=False
            )
        except Exception as e:
            raise BadRequest(message=f'Error processing file: {str(e)}')

        return Buckets.Folders.STARTUP_SCRIPTS.value + filename

    async def read_uploaded_json(
        self,
        file: UploadFile = File(...),
        max_size_mb: int = 5
    ) -> dict:
        """
        - Streams the upload in chunks.
        - Rejects files over `max_size_mb`.
        - Ensures the file is valid JSON.
        Returns a Python dict if successful.
        """
        if file.filename == '':
            raise BadRequest(message="No selected file")

        extension = file.filename.rsplit('.', 1)[-1]
        extension = f'.{extension}'
        if file.content_type != "application/json" or extension != '.json':
            raise BadRequest(message="Only JSON files are allowed.")

        # Stream in chunks and track size
        max_file_size = max_size_mb * 1024 * 1024
        chunk_size = 1024 * 1024  # 1 MB
        file_contents = bytearray()
        total_size = 0

        while True:
            chunk = await file.read(chunk_size)
            if not chunk:
                # end of file
                break

            total_size += len(chunk)
            if total_size > max_file_size:
                raise ContentTooLarge(message=f"File too large (max {max_size_mb} MB).")
            file_contents.extend(chunk)

        try:
            return json.loads(file_contents)
        except json.JSONDecodeError:
            raise BadRequest(message="Invalid JSON format.")

    @staticmethod
    def _parse_boolean(value):
        return str(value).lower() in ['true', '1', 'on']