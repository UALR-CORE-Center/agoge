from common.constants.database import DbCollections, DbOperators, DbOperationTypes
from common.constants.states import ServerStates, ImageStatus
from common.document_database import DatabaseQueries
from common.exceptions import NotFound, BaseAgogeException, BadRequest
from common.models.agoge import AgogeImageModel
from .base_compute_manager import BaseComputeManager


class ProjectServerManager(BaseComputeManager):
    def __init__(
        self,
        env_dict: dict,
        debug: bool = False
    ) -> None:
        super().__init__(env_dict=env_dict, machine_types=False)
        self.debug = debug
        self.db_query = DatabaseQueries(db=self.db)

    def load(self, server_name: str, **kwargs) -> None:
        pass

    def stop_everything(self) -> None:
        instances = self.compute_instance.list(project=self.env.project, zone=self.env.zone, wait=False)
        if instances:
            for instance in instances:
                try:
                    self.compute_instance.stop(resource_name=instance.name, wait=False)
                except (BadRequest, BaseAgogeException, NotFound) as e:
                    self.logger.warning(
                        f'{self.class_name}:{instance.name} - Error attempting to stop server : {str(e)}',
                        server=instance.name
                    )

            self.logger.info(f"{self.class_name} - All machines stopped (daily cleanup)")

        # Sync Image database with new machine states
        filters = [('status', DbOperators.EQUAL, ImageStatus.CHECKED_OUT.value)]
        images = self.db.query(collection_name=self.collection.IMAGE, filters=filters)
        operations = []
        for image in images:
            image['state'] = ServerStates.STOPPED.value
            if validated := self.validate(AgogeImageModel, log_location=self.log_name).load(image):
                operations.append(
                    self.db.operation(
                        collection_name=DbCollections.IMAGE,
                        doc_id=image['name'],
                        operation_type=DbOperationTypes.UPDATE,
                        data={'state': validated.state}
                    )
                )
            self.db.batch_write(operations)

    def _add_nics(self) -> None:
        pass

    def _dns_record(self) -> str:
        pass
