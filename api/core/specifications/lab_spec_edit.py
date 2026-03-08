from common.constants.database import (
    DbCollections,
    DatabaseTypes,
    DATABASE_NAME
)
from common.constants.states import SpecificationStates
from common.document_database.factory import DocumentDatabaseFactory
from common.exceptions import BadRequest, NotFound, AgogeValidationError
from common.models.agoge import CatalogEditModel
from common.models.model_validators.model_validator import ModelValidator
from common.models.users import AgogeUser
from common.utilities.gcp.cloud_env import CloudEnv
from common.utilities.gcp.cloud_logger import Logger, LoggerNames

from .utilities.edit_manager import SpecEditManager


class LabSpecsEdit:
    def __init__(
        self,
        env_dict: dict
    ) -> None:
        self.log_name = LoggerNames.API
        self.env = CloudEnv(log_name=self.log_name, env_dict=env_dict)
        self.env_dict = self.env.get_env()
        self.collection = DbCollections.SPECIFICATION_EDITS
        self.db = DocumentDatabaseFactory.create_db_object(
            db_type=DatabaseTypes.firestore,
            database_name=DATABASE_NAME,
            log_name=self.log_name
        )
        self.logger = Logger(self.log_name, class_name=self.__class__.__name__)

    def get(
        self,
        edit_id: str
    ) -> CatalogEditModel:
        if spec := self.db.get(collection_name=self.collection, doc_id=edit_id):
            return CatalogEditModel(**spec)
        raise NotFound(message="No specification found for given ID")

    def list(self) -> list[CatalogEditModel]:
        if specs := self.db.query(collection_name=self.collection):
            return ModelValidator(model=CatalogEditModel).load(specs, halt_on_error=False)
        raise NotFound

    def create(
        self,
        requester: AgogeUser
    ) -> dict:
        lab_spec = SpecEditManager(env_dict=self.env_dict)
        lab_spec.create_base_spec(requester)
        edit_id = lab_spec.edit_id

        self.logger.info(f'creating blank lab specification {edit_id} for user {requester.uid}',
                         user=requester.uid, edit_id=edit_id)
        return {'build_id': edit_id}

    def edit(
        self,
        edit_id: str,
        data: dict,
    ) -> dict:
        """
        Edits data stored in SpecificationEdit datastore
        Args:
            edit_id ():
            data ():
        Returns:
        """
        lab_spec = SpecEditManager(env_dict=self.env_dict)
        lab_spec.load(edit_id=edit_id, form=data)
        valid, msg = lab_spec.is_valid()
        if not valid:
            raise AgogeValidationError(message=msg)

        lab_spec.save()
        return lab_spec.spec

    def process_action(
        self,
        spec_id: str,
        data: dict,
        requester: AgogeUser
    ) -> dict:
        spec_action = data.get('spec_action')
        if not spec_action:
            raise BadRequest(message="Missing or invalid specification action")

        lab_spec = SpecEditManager(env_dict=self.env_dict)
        if spec_action in [SpecificationStates.EDIT, SpecificationStates.COPY]:
            self.logger.info(
                f'processing action {SpecificationStates(spec_action).name} on specification with id {spec_id}',
                spec_id=spec_id,
                action=spec_action
            )
            spec_db = self.db.get(collection_name=DbCollections.CATALOG, doc_id=spec_id)

            if not spec_db:
                raise NotFound("No specification found for given ID")

            if spec_db.get('status') == SpecificationStates.EDIT and spec_action == SpecificationStates.EDIT:
                raise BadRequest(message="Could not process request. Specification already reserved for edits!")

            lab_spec.create_spec_copy(spec_db, spec_action, requester=requester)
        else:
            raise BadRequest(message="Invalid or missing specification action")

        # Temporary object created; Redirect to edit pages
        edit_id = lab_spec.edit_id
        return {'build_id': edit_id}

    def delete_edit(
        self,
        edit_id: str
    ) -> None:
        lab_spec = SpecEditManager(env_dict=self.env_dict)
        lab_spec.delete(edit_id=edit_id)

    @staticmethod
    def _parse_boolean(value):
        return str(value).lower() in ['true', '1', 'on']
