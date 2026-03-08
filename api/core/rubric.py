from typing import Optional, Union
from pydantic import ValidationError
from fastapi import Request

from common.constants.pub_sub import PubSub
from common.constants.database import (
    DbCollections,
    DatabaseTypes,
    DATABASE_NAME
)
from common.document_database.factory import DocumentDatabaseFactory
from common.exceptions import BadRequest, NotFound, Unauthorized, AgogeValidationError
from common.models.agoge import RubricModel
from common.models.model_validators.model_validator import ModelValidator
from common.models.users import AgogeUser
from common.utilities.gcp.cloud_env import CloudEnv
from common.utilities.gcp.cloud_logger import Logger, LoggerNames
from common.utilities.gcp.pubsub_manager import PubSubManager


class Rubric:
    def __init__(
        self,
        env_dict: dict
    ) -> None:
        self.class_name = self.__class__.__name__
        self.log_name = LoggerNames.API
        self.collection = DbCollections.RUBRIC
        self.pubsub_actions = PubSub.Actions
        self.handler = PubSub.Handlers
        self.env = CloudEnv(log_name=self.log_name, env_dict=env_dict)
        self.env_dict = self.env.get_env()
        self.db = DocumentDatabaseFactory.create_db_object(
            db_type=DatabaseTypes.firestore,
            database_name=DATABASE_NAME,
            log_name=self.log_name
        )
        self.pubsub_mgr = PubSubManager(
            topic=PubSub.Topics.AGOGE,
            log_name=self.log_name,
            env_dict=self.env_dict
        )
        self.logger = Logger(self.log_name, class_name=self.class_name)
        self.model_validator = ModelValidator(model=RubricModel)

    def get(
        self,
        build_id: str,
        as_dict: bool = False
    ) -> Optional[Union[RubricModel, dict]]:
        if rubric := self.db.get(collection_name=self.collection, doc_id=build_id):
            if as_dict:
                return rubric
            else:
                try:
                    return self.model_validator.load(data=rubric)
                except (AgogeValidationError, ValidationError) as e:
                    raise BadRequest(message=f"Rubric.get failed with validation errors: {e}")
        return None

    async def update(
        self,
        build_id: str,
        request: Request,
        requester: AgogeUser
    ) -> None:
        """
        Updates a rubric in document database.

        Args:
            requester (AgogeUser): User initiating request
            build_id (str): ID of the rubric to update
            request (Request): Request object containing update data

        Raises:
            BadRequest: Missing or Invalid Data
            NotFound: Invalid or missing build_id
            Unauthorized: User is not an admin
        """
        if not requester.is_authorized:
            raise Unauthorized(message=f"User is not authorized to make this request. {requester.uid}")

        json_data = await request.json()
        if not json_data:
            raise BadRequest(message="Rubric update request made but no data was found")

        rubric = self.get(build_id, as_dict=True)
        if not rubric:
            raise NotFound(message=f"Rubric with ID {build_id} not found")

        update = False
        self.logger.info(f'processing update for rubric with id {build_id}',
                         user=requester.uid, input_data=json_data)
        for key, value in json_data.items():
            if key in rubric:
                update = True

                # Handle specific field updates if necessary
                if key == 'criteria':
                    # Validate that criteria is a list of dicts with required fields
                    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
                        raise BadRequest(message="Invalid data format for 'criteria'")
                    rubric[key] = value
                else:
                    rubric[key] = value

        # Save updated entity back to datastore
        if update:
            self.db.update(collection_name=self.collection, doc_id=build_id, data=rubric)
            return

        # Raise an error if no valid data was updated
        raise BadRequest(message="Could not process update. Invalid data given")