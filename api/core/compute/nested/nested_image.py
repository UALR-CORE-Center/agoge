"""Create a nested lab host image server and list the OS catalog (Nested Image Builder Contract, Create step)."""
import json
from typing import List

from markupsafe import escape

from common.constants.database import DbCollections
from common.constants.google import ImageProjects
from common.constants.pub_sub import PubSub
from common.constants.states import ImageStatus
from common.exceptions import Conflict
from common.models.agoge import AgogeImageModel, NestedBuildStatusModel, NestedImageCreateRequest, NestedOsCatalogModel
from common.models.model_validators.model_validator import ModelValidator
from common.models.users import AgogeUser

from core.compute.image import ComputeImage
from core.compute.nested.validator import NestedHostValidator


class NestedImage(ComputeImage):
    """The record is an ordinary CHECKED_OUT template, so the existing check-out builds it."""

    def __init__(self, env_dict: dict, validator: NestedHostValidator = None) -> None:
        super().__init__(env_dict=env_dict)
        self._validator = validator
        self.catalog_validator = ModelValidator(model=NestedOsCatalogModel)

    @property
    def validator(self) -> NestedHostValidator:
        # Lazy: listing the catalog needs no Compute machine-type client.
        if self._validator is None:
            self._validator = NestedHostValidator(env_dict=self.env_dict, db=self.db)
        return self._validator

    def list_catalog(self) -> List[NestedOsCatalogModel]:
        records = self.db.query(collection_name=DbCollections.NESTED_OS_CATALOG) or []
        # A malformed entry loads as None (logged) rather than failing the whole list.
        entries = self.catalog_validator.load(records, halt_on_error=False) or []
        enabled = [entry for entry in entries if entry and entry.is_enabled]
        return sorted(enabled, key=lambda entry: (entry.group, entry.display_name))

    def create(self, user: AgogeUser, request: NestedImageCreateRequest) -> AgogeImageModel:
        """Validate, derive, write image/<name>, then publish CHECK_OUT.

        Raises:
            BadRequest: The spec breaks a validation rule
            AgogeValidationError: username or ssh_key fails the parent access rules
            Conflict: A template with this name already exists
        """
        server_name = request.server_name
        self.user = user.email
        self.validator.validate(request)
        if self.db.get(collection_name=self.collection, doc_id=server_name):
            raise Conflict(f'Template {server_name} already exists. Choose a different name.')

        spec = self.validator.derive(request.nested)
        # The parent boots from the Debian family; V11 resolves it again on the first build.
        source = f'projects/{ImageProjects.DEBIAN}/global/images/family/{spec.parent_os}'
        parent_access = self._generate_human_interaction(
            {'username': request.username, 'ssh_key': request.ssh_key}, infer_from_os=False
        )
        disk_size = request.disk_size if request.disk_size is not None else self.validator.min_disk_size(spec.guests)
        image = AgogeImageModel(
            name=server_name,
            status=ImageStatus.CHECKED_OUT.value,
            machine_type=request.machine_type,
            description=str(escape(request.description)),
            tags=['https-server', 'http-server'],
            image=source,
            os='linux',
            add_disk=str(disk_size),
            self_link=source,
            human_interaction=[parent_access],
            labels=self._sanitize_labels(request.labels),
            base_family=spec.parent_os,
            # NESTED_MACHINE_FAMILIES (N1, N2) are all x86.
            architecture='X86_64',
            nested=spec,
            nested_build=NestedBuildStatusModel(phase='queued'),
        )
        # product_keys is not a field of the record; it only travels in the CHECK_OUT message.
        self._create_record(image.model_dump())
        self.logger.info(f"{self.class_name}:{server_name} - Created nested image record",
                         image=server_name, user=user.uid, guests=len(spec.guests))
        self._publish_check_out(server_name, request.product_keys)
        return image

    def _publish_check_out(self, server_name: str, product_keys: dict) -> None:
        msg_args = {
            self.pubsub_keys.HANDLER: str(PubSub.Handlers.CONTROL.value),
            self.pubsub_keys.ACTION: str(PubSub.Actions.CHECK_OUT.value),
            self.pubsub_keys.IMAGE_NAME: str(server_name),
            self.pubsub_keys.USER: str(self.user),
            self.pubsub_keys.COURSE_OBJECT: str(PubSub.CourseObjects.TEMPLATE_SERVER.value),
        }
        if product_keys:
            # Eight guests' keys stay well under Pub/Sub's 1024-byte attribute value limit.
            msg_args[self.pubsub_keys.PRODUCT_KEYS] = json.dumps(product_keys, separators=(',', ':'))
        self.pubsub_manager.msg(**msg_args)
