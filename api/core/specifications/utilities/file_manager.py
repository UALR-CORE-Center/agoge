from datetime import datetime
from common.exceptions import AgogeValidationError

from common.constants.build_constants import BuildConstants
from common.models.agoge import UnitModel

from utilities.infrastructure_as_code.object_validators.unit import UnitValidator
from .lab_spec_base import LabSpecBase


class SpecFileManager(LabSpecBase):
    def __init__(self, env_dict: dict) -> None:
        super().__init__(env_dict=env_dict)
        self.class_name = self.__class__.__name__

    def load(
        self,
        spec: dict
    ) -> None:
        self.spec = spec

    def is_valid(self):
        if not self.validated:
            try:
                self._validate_spec()
            except AgogeValidationError as e:
                return False, str(e)
            self.validated = True
        return True, "Spec is valid"

    def save(self):
        if not self.is_valid()[0]:
            raise AgogeValidationError("Cannot save invalid spec")

        # Passed validation. Generate spec catalog ID and discriminator
        name = self.spec['summary']['name']
        discriminator = self.spec['discriminator'] = self.generate_discriminator()
        spec_id = self._get_id_from_name(name, discriminator)
        self.spec['id'] = spec_id

        self.db.update(collection_name=self.catalog_collection, doc_id=spec_id, data=self.spec)

    def _validate_spec(self):
        if not (build_type := self.spec.get('build_type')):
            raise AgogeValidationError("Spec does not contain a build_type")

        # Set default placeholder values
        self.spec.setdefault('creation_timestamp', datetime.now().timestamp())
        if build_type in [
            BuildConstants.BuildType.UNIT.value,
            BuildConstants.BuildType.ESCAPE_ROOM.value
        ]:
            instructor_id = self.spec.get('instructor_id', ['instructor@example.com'])
            if not isinstance(instructor_id, list):
                instructor_id = [instructor_id]
            self.spec['instructor_id'] = instructor_id

            # Validate entire specification
            UnitModel(**self.spec)
            UnitValidator().load(self.spec)

        # Spec is now validated
        self.validated = True
