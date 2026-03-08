import re
from typing import Optional
from fastapi import File
from pydantic import ValidationError
from starlette.datastructures import FormData

from common.constants.build_constants import BuildConstants
from common.constants.database import (
    DbCollections,
    DatabaseTypes,
    DATABASE_NAME, DbOperators
)
from common.document_database.factory import DocumentDatabaseFactory
from common.exceptions import NotFound, Unauthorized, BadRequest, AgogeValidationError
from common.models.agoge import AgogeInstructionsModel
from common.models.model_validators.model_validator import ModelValidator
from common.utilities.gcp.bucket_manager import BucketManager
from common.utilities.gcp.cloud_env import CloudEnv
from common.utilities.gcp.cloud_logger import Logger, LoggerNames
from common.utilities.id_generator import IdGenerator
from common.utilities.timestamps import Timestamps


class Docs:
    def __init__(
        self,
        env_dict: dict
    ) -> None:
        self.class_name = self.__class__.__name__
        self.log_name = LoggerNames.API
        self.collection = DbCollections.INSTRUCTIONS
        self.env = CloudEnv(log_name=self.log_name, env_dict=env_dict)
        self.env_dict = self.env.get_env()
        self.logger = Logger(log_name=self.log_name, class_name=self.class_name)
        self.db = DocumentDatabaseFactory.create_db_object(
            DatabaseTypes.firestore,
            database_name=DATABASE_NAME,
            log_name=self.log_name
        )

    async def get_instructions(
        self,
        build_id: str,
        build_type: DbCollections = DbCollections.WORKOUT,
    ) -> dict:
        if build_type == DbCollections.WORKOUT:
            if build := self.db.get(collection_name=build_type, doc_id=build_id):
                file_id = build['summary'].get('student_instructions_id')
                if file_id and (instructions := self.db.get(collection_name=self.collection, doc_id=file_id)):
                    if instructions.get('instructions_type') == BuildConstants.InstructionsType.STUDENT:
                        return instructions
                    raise Unauthorized(message=f"Requester is not authorized to view requested instruction")
                raise NotFound(message=f"No instructions found for id {file_id}")
            raise NotFound("No build found with matching ID")
        elif build_type == DbCollections.UNIT:
            if build := self.db.get(collection_name=build_type, doc_id=build_id):
                file_id = build['summary'].get('teacher_instructions_id')
                if file_id and (instructions := self.db.get(collection_name=self.collection, doc_id=file_id)):
                    return instructions
                raise NotFound(message=f"No instructions found for id {file_id}")
            raise NotFound(message=f"No build found for id {build_id}")
        else:
            raise BadRequest(message='Unrecognized or unsupported type')

    def get_markdown_instruction(
        self,
        uid: str,
    ):
        if instruction := self.db.get(collection_name=self.collection, doc_id=uid):
            return (
                ModelValidator(model=AgogeInstructionsModel)
                .load(instruction,halt_on_error=False)
            )
        else:
            raise NotFound(message=f"No instructions found for id {uid}")

    def list_instructions_full(self) -> list[dict]:
        if instructions := self.db.query(collection_name=self.collection):
            return (
                ModelValidator(model=AgogeInstructionsModel)
                .load(instructions, halt_on_error=False)
            )
        return []

    def list_instructions(self) -> list[dict]:
        instructions = self.db.query(collection_name=self.collection)
        if not instructions:
            raise NotFound(message=f"No instructions found")

        # Return only the uid, type, and name of each instruction
        return [
            {
                "uid": item.get("uid"),
                "instructions_type": item.get("instructions_type"),
                "name": item.get("name"),
            }
            for item in instructions
        ]

    def create_instructions(
        self,
        form_data: FormData,
    ) -> str:
        filename = form_data.get('filename')
        instructions_type = form_data.get('instructions_type')

        if not instructions_type and not filename:
            raise BadRequest(message="Missing or invalid data for required fields filename, or "
                                     "instructions_type")
        if instructions_type not in [
            BuildConstants.InstructionsType.TEACHER,
            BuildConstants.InstructionsType.STUDENT
        ]:
            raise BadRequest(message=f"Missing or invalid instructions_type: "
                                     f"{instructions_type}")

        self._validate(filename=filename)
        current_ts = Timestamps.get_current_timestamp_utc()
        uid = IdGenerator.uuid()

        default_file = self.db.query(collection_name=self.collection, filters=[("name", DbOperators.EQUAL, "Markdown Tips")])
        if default_file is None:
            self.logger.error(
                f"No tips file found",
                collection_name=self.collection,
            )
            default_file = {'content': ''}
        default_content = default_file[0].get("content", "")
        try:
            new_file = AgogeInstructionsModel(
                uid=uid,
                content=default_content,
                name=filename,
                instructions_type=instructions_type,
                modified=current_ts
            )
        except ValidationError as e:
            self.logger.error(
                f"create instructions failed with validation errors: {e}",
                collection_name=self.collection,
                doc_id=uid
            )
            raise AgogeValidationError(f"Create instructions failed with validation errors: {e}")

        self.db.update(
            collection_name=self.collection,
            doc_id=uid,
            data=new_file.model_dump()
        )
        return uid

    def edit_instructions(
        self,
        uid: str,
        form_data: FormData,
    ) -> str:
        file = form_data.get('file')
        filename = form_data.get('filename')
        instructions_type = form_data.get('instructions_type')

        if not instructions_type and not file:
            raise BadRequest(message="Missing or invalid data for required fields file or "
                                     "instructions_type")
        if instructions_type not in [
            BuildConstants.InstructionsType.TEACHER,
            BuildConstants.InstructionsType.STUDENT
        ]:
            raise BadRequest(message="Missing or invalid instructions_type: "
                                     "{instructions_type}")
        if filename:
            self._validate(filename=filename)

        current_ts = Timestamps.get_current_timestamp_utc()
        if saved_file := self.db.get(collection_name=self.collection, doc_id=uid):
            if filename:
                saved_file['name'] = filename
            saved_file['instructions_type'] = instructions_type
            saved_file['content'] = file
            saved_file['modified'] = current_ts

            try:
                AgogeInstructionsModel(**saved_file)
            except ValidationError as e:
                self.logger.error(
                    f"update instructions failed with validation errors: {e}",
                    collection_name=self.collection,
                    doc_id=uid
                )
                raise AgogeValidationError(message=f"Update instructions failed with validation errors: {e}")

            self.db.update(collection_name=self.collection, doc_id=uid, data=saved_file)
            return uid
        else:
            raise NotFound(message=f"No instructions found with given ID {uid}")

    async def upload_image(
        self,
        file: File,
        form_data: FormData,
        max_size: int = 10 * 1024 * 1024  # 5 MB default limit
    ) -> str:
        """
        Processes the image file submitted via a form and uploads it using BucketManager.

        :param file: The image file object.
        :param form_data: The form data containing the image metadata.
        :param max_size: The maximum allowed file size in bytes (default is 5 MB).
        """
        image_name = form_data.get('image_name') or file.filename
        if not image_name:
            raise BadRequest(message='No image file selected')

        # Validate the image name and type
        self._validate(image_name=image_name)

        # Check the size of the file before reading it
        if file.size > max_size:
            raise BadRequest(message=f'File size exceeds the allowed limit of {max_size / (1024 * 1024)} MB')

        make_public = True
        instructions_type = form_data.get('instructions_type', BuildConstants.InstructionsType.STUDENT)
        if instructions_type == BuildConstants.InstructionsType.TEACHER:
            make_public = False

        bucket_mgr = BucketManager(env_dict=self.env_dict)
        try:
            image_content = await file.read()
            return bucket_mgr.upload_image(
                image_name=image_name,
                image_content=image_content,
                make_public=make_public,
            )
        except Exception as e:
            self.logger.error(
                message=f'Error processing image: {str(e)}',
                image=image_name
            )
            raise BadRequest(message="Error processing image")

    @staticmethod
    def _validate(
        filename: Optional[str] = None,
        image_name: Optional[str] = None,
    ) -> bool:
        """
        Validate strings based on argument type
        Args:
            filename (): Validate filename
            image_name (): Validate image name

        Returns: True
        Raises: ValidationError
        """
        valid = True
        if filename:
            pattern = r'^[a-zA-Z0-9\-: ]{3,63}$'
            valid = bool(re.match(pattern, filename))
            if not valid:
                raise AgogeValidationError(
                    message="Names must be between 3 and 63 characters long and can only "
                            "contain letters (a-z, A-Z), digits (0-9), hyphens (-), "
                            "colons (:), and spaces."
                )
        elif image_name:
            if not image_name.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
                raise AgogeValidationError(message='Invalid image type')
        return valid
