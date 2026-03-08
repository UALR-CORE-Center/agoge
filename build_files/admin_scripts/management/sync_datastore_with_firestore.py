import json
from pydantic_core import ValidationError

from cloud_fn_utilities.document_database import DocumentDatabaseFactory
from cloud_fn_utilities.common import (
    DbCollections,
    DATABASE_NAME,
    DatabaseTypes,
    DatastoreKeyTypes,
    DbOperationTypes
)
from main_app.api import CloudEnv, AgogeValidationError
from cloud_fn_utilities.gcp.datastore_manager import DataStoreManager
from models.agoge import CatalogModel, HumanInteractionModel, CVEModel, UnitModel, WorkoutModel, ServerModel
from models.google import ClassroomModel
from models.model_loaders import AgogeImage, GoogleImageObject
from models.users import AgogeUser


class Transfer:
    def __init__(self) -> None:
        self.env = CloudEnv()
        self.db = DocumentDatabaseFactory.create_db_object(
            db_type=DatabaseTypes.firestore,
            database_name=DATABASE_NAME
        )
        self.ds = DataStoreManager
        self.operations = []
        self.op_type = DbOperationTypes.SET

    def _old(self, kind) -> list:
        items = self.ds(key_type=kind.value).query()
        return items or []

    def google_images(self) -> None:
        old = self._old(DatastoreKeyTypes.GOOGLE_IMAGES)
        print('Syncing all records for GOOGLE_IMAGES')
        for i in old:
            try:
                updated = GoogleImageObject.load(i)
                operation = self.db.operation(
                    collection_name=DbCollections.GOOGLE_IMAGES,
                    doc_id=updated.uuid,
                    operation_type=self.op_type,
                    data=updated.model_dump(),
                )
                self.operations.append(operation)
            except AgogeValidationError as e:
                print(f"Validation error for {i['id']} - {e}")

    def images(self) -> None:
        def _update_image(image):
            try:
                key = 'human_interaction'
                update_image = HumanInteractionModel(**image[key])
                image[key] = [update_image]
                return AgogeImage.load(image)
            except ValidationError as e:
                print(f"Validation error for {image['id']} - {e}")

        old = self._old(DatastoreKeyTypes.IMAGE)
        print('Syncing all records for IMAGES')
        for i in old:
            try:
                i["machine_type"] = i.pop("machineType", i.get("machine_type"))  # Fix for key name with machineType
                updated = _update_image(i)
                operation = self.db.operation(
                    collection_name=DbCollections.IMAGE,
                    doc_id=updated.name,
                    operation_type=self.op_type,
                    data=updated.model_dump(),
                )
                self.operations.append(operation)
            except AgogeValidationError as e:
                print(f"Validation error for {i['id']} - {e}")

    def users(self) -> None:
        old = self._old(DatastoreKeyTypes.USERS)
        print('Syncing all records for USERS')
        for i in old:
            new_user = AgogeUser(**i)
            if new_user.email == self.env.admin_email:
                continue

            print(f"Creating record for user {new_user.uid}:{new_user.email} ...")
            op = self.db.operation(
                collection_name=DbCollections.USERS,
                doc_id=new_user.uid,
                data=new_user.model_dump(),
                operation_type=self.op_type
            )
            self.operations.append(op)

    def catalog(self) -> None:
        old = self._old(DatastoreKeyTypes.CATALOG)
        print('Syncing all records for CATALOG')
        for i in old:
            try:
                new_spec = CatalogModel(**i)
                operation = self.db.operation(
                    collection_name=DbCollections.CATALOG,
                    doc_id=new_spec.id,
                    operation_type=self.op_type,
                    data=new_spec.model_dump(),
                )
                self.operations.append(operation)
            except AgogeValidationError as e:
                print(f"Validation error for {i['id']} - {e}")

    def nvd_data(self) -> None:
        old = self._old(DatastoreKeyTypes.NVD_DATA)
        print('Syncing all records for NVD_DATA')
        for i in old:
            try:
                new_obj = CVEModel(**i)
                operation = self.db.operation(
                    collection_name=DbCollections.NVD_DATA,
                    doc_id=new_obj.cve_id,
                    operation_type=self.op_type,
                    data=new_obj.model_dump()
                )
                self.operations.append(operation)
            except AgogeValidationError as e:
                print(f"Validation error: {e}")

    def classroom(self) -> None:
        old = self._old(DatastoreKeyTypes.CLASSROOM)
        print('Syncing all records for Classroom')
        for i in old:
            try:
                new_obj = ClassroomModel(**i)
                operation = self.db.operation(
                    collection_name=DbCollections.CLASSROOM,
                    doc_id=new_obj.id,
                    operation_type=self.op_type,
                    data=new_obj.model_dump()
                )
                self.operations.append(operation)
            except AgogeValidationError as e:
                print(f"Validation error: {e}")

    def unit(self) -> None:
        old = self._old(DatastoreKeyTypes.UNIT)
        print('Syncing all records for Unit')
        for i in old:
            try:
                new_obj = UnitModel(**i)
                operation = self.db.operation(
                    collection_name=DbCollections.UNIT,
                    doc_id=new_obj.id,
                    operation_type=self.op_type,
                    data=new_obj.model_dump()
                )
                self.operations.append(operation)
            except AgogeValidationError as e:
                print(f"Validation error: {e}")

    def workout(self) -> None:
        old = self._old(DatastoreKeyTypes.WORKOUT)
        print('Syncing all records for Workout')
        for i in old:
            try:
                new_obj = WorkoutModel(**i)
                operation = self.db.operation(
                    collection_name=DbCollections.WORKOUT,
                    doc_id=new_obj.id,
                    operation_type=self.op_type,
                    data=new_obj.model_dump()
                )
                self.operations.append(operation)
            except AgogeValidationError as e:
                print(f"Validation error: {e}")

    def servers(self) -> None:
        old = self._old(DatastoreKeyTypes.SERVER)
        print('Syncing all records for Server')
        for i in old:
            try:
                new_obj = ServerModel(**i)
                operation = self.db.operation(
                    collection_name=DbCollections.SERVER,
                    doc_id=new_obj.name,
                    operation_type=self.op_type,
                    data=new_obj.model_dump()
                )
                self.operations.append(operation)
            except AgogeValidationError as e:
                print(f"Validation error: {e}; {i['name']}")
            except ValidationError as e:
                print(f'Validation error: {e}; {i['name']}')

    def all(self) -> None:
        self.users()
        self.google_images()
        self.images()
        self.catalog()
        self.nvd_data()
        self.classroom()
        self.unit()
        self.workout()
        self.servers()

        exit()

    def sync(self) -> None:
        key_types = DatastoreKeyTypes
        options = {
            0: (key_types.GOOGLE_IMAGES.value, self.google_images),
            1: (key_types.IMAGE.value, self.images),
            2: (key_types.USERS.value, self.users),
            3: (key_types.CATALOG.value, self.catalog),
            4: (key_types.NVD_DATA.value, self.nvd_data),
            5: (key_types.CLASSROOM.value, self.classroom),
            6: (key_types.SERVER.value, self.servers),
            7: (key_types.WORKOUT.value, self.workout),
            8: (key_types.UNIT.value, self.unit),
            9: ('ALL', self.all),
            10: ('QUIT', None)
        }

        while True:
            for key, opt in options.items():
                print(f'[{key}] {opt[0]}')

            selection = int(input('Select KEY_TYPE to sync: '))
            if selection == 10:
                exit()
            else:
                if selection in options:
                    options[selection][1]()
                    self.db.batch_write(self.operations)


if __name__ == '__main__':
    Transfer().sync()
