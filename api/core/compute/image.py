import json
import re

from google.api_core.exceptions import AlreadyExists
from markupsafe import escape
from pydantic import ValidationError
from typing import List, Union, Tuple

from common.models.model_validators.model_validator import ModelValidator
from common.models.users import AgogeUser
from common.models.agoge import AgogeImageModel, HumanInteractionModel
from common.models.google import ComputeImageModel, MachineTypeModel
from common.utilities.gcp.cloud_env import CloudEnv
from common.utilities.gcp.cloud_logger import Logger, LoggerNames
from common.constants.build_constants import BuildConstants
from common.constants.database import (
    DatabaseTypes,
    DbCollections,
    DbOperationTypes,
    DATABASE_NAME,
    DbOperators
)
from common.constants.pub_sub import PubSub
from common.constants.states import ImageStatus, ServerStates
from common.constants.google import ImageSource
from common.constants.enumerators import ImageScopes, SnapshotTypes
from common.utilities.gcp.compute.compute_image import ComputeImageAPI
from common.utilities.gcp.compute.compute_instance import ComputeInstanceAPI
from common.utilities.gcp.compute.compute_disk import ComputeDiskAPI
from common.utilities.gcp.compute.compute_machine_type import ComputeMachineTypesAPI
from common.utilities.gcp.compute.image_compatibility import compatible_boot_image, normalize_architecture
from common.utilities.gcp.compute.image_ownership import image_source, image_source_project, is_shared_image
from common.utilities.gcp.pubsub_manager import PubSubManager
from common.document_database.factory import DocumentDatabaseFactory
from common.exceptions import BadRequest, Conflict, NotFound, AgogeValidationError, NotReady, OperationTimeout

from utilities.gcp.compute.compute_resources import ComputeResources
from utilities.global_objects.words import Words


class ComputeImage:
    NAME_RESERVATIONS = ["agoge", "google"]

    def __init__(
        self,
        env_dict: dict
    ) -> None:
        self.class_name = self.__class__.__name__
        self.log_name = LoggerNames.API
        self.collection = DbCollections.IMAGE
        self.env = CloudEnv(log_name=self.log_name, env_dict=env_dict)
        self.env_dict = self.env.get_env()
        self.pubsub_manager = PubSubManager(
            topic=PubSub.Topics.AGOGE,
            log_name=self.log_name,
            env_dict=self.env.get_env()
        )
        self.db = DocumentDatabaseFactory.create_db_object(
            DatabaseTypes.firestore,
            database_name=DATABASE_NAME,
            log_name=self.log_name
        )
        self.handler = PubSub.Handlers
        self.pubsub_keys = PubSub.EventAttributes
        self.logger = Logger(log_name=self.log_name, class_name=self.class_name)
        self.user = None
        self.compute_model_validator = ModelValidator(model=ComputeImageModel)
        self.agoge_model_validator = ModelValidator(model=AgogeImageModel)

    def get(
        self,
        image_name: str
    ) -> AgogeImageModel:
        if image := self.db.get(collection_name=self.collection, doc_id=image_name):
            return AgogeImageModel(**self._with_ownership(image))
        raise NotFound(message=f"No image found for ID: {image_name}")

    def get_image_state(
        self,
        server_name: str
    ) -> dict:
        if image := self.db.get(collection_name=self.collection, doc_id=server_name):
            return {"build_id": server_name, 'state': image.get('state')}
        raise NotFound(message=f"No image found for ID: {server_name}")

    def list_images(self) -> List[AgogeImageModel]:
        if images := self.db.query(collection_name=self.collection):
            return self.agoge_model_validator.load(
                [self._with_ownership(image) for image in images], halt_on_error=False
            )
        return []

    def list_project_images(
        self,
        scope: ImageScopes = ImageScopes.PROJECT
    ) -> Union[dict, List]:
        """
        Retrieve independently available public and custom image catalogs.

        Raises:
            BadRequest: Invalid value for scope
            NotFound: No data exists for requested resource
        """
        if scope == ImageScopes.PROJECT:
            google_images = self.db.query(collection_name=DbCollections.GOOGLE_IMAGES)
            custom_images = self.db.query(collection_name=self.collection)
            # A new project needs public images before it can create its first
            # custom image. Neither catalog requires the other to be populated.
            return {
                'custom': self.agoge_model_validator.load(
                    [self._with_ownership(image) for image in custom_images]
                ) if custom_images else [],
                'project': self.compute_model_validator.load(google_images) if google_images else [],
            }
        elif scope == ImageScopes.GLOBAL:
            if google_images := self.db.query(collection_name=DbCollections.GOOGLE_IMAGES):
                return self.compute_model_validator.load(google_images)
            raise NotFound(message="No image data found")
        raise BadRequest(message=f"List request with invalid or missing `scope`: {scope}")

    def machine_types(self) -> List[MachineTypeModel]:
        """Retrieve list of valid machine types to use in server builds"""
        return ComputeResources(env_dict=self.env_dict).get_machine_types()

    def _with_ownership(self, image: dict) -> dict:
        return {
            **image,
            'source_project': image_source_project(image),
            'is_shared': is_shared_image(image, self.env.project),
        }

    def _require_local_image(self, image: dict) -> None:
        if is_shared_image(image, self.env.project):
            raise BadRequest('Copy this shared image to a new local template before editing it.')

    def _validate_new_name(self, server_name: str) -> None:
        # Leave nine characters for the longest snapshot suffix (-manual-0).
        if not isinstance(server_name, str) or not re.fullmatch(r'[a-z](?:[a-z0-9-]{0,52}[a-z0-9])?', server_name):
            raise BadRequest('Use 1–54 lowercase letters, numbers, or hyphens. Start with a letter and end with a letter or number.')
        if server_name.startswith('image-') or server_name in self.NAME_RESERVATIONS:
            raise BadRequest('Choose a server name without the reserved image- prefix or reserved names agoge and google.')

    def _create_record(self, image: dict) -> None:
        """Create atomically: a competing request must never replace a template."""
        try:
            self.db.db.collection(self.collection.value).document(image['name']).create(image)
        except AlreadyExists as exc:
            raise Conflict(f'Template {image["name"]} already exists. Choose a different name.') from exc

    def copy_shared_image(self, image_name: str, server_name: str) -> AgogeImageModel:
        """Copy the saved shared image before exposing a renamed local template.

        The original catalog record and image are never modified. Compute insert
        and Firestore create both reject existing names, including concurrent
        requests. No editable record is published for an incomplete image copy.
        """
        self._validate_new_name(server_name)
        source_record = self.db.get(collection_name=self.collection, doc_id=image_name)
        if not source_record:
            raise NotFound(f'No image found for ID: {image_name}')
        if not is_shared_image(source_record, self.env.project):
            raise BadRequest('This template is already local. Edit the existing local template.')
        if server_name == image_name:
            raise BadRequest('The local copy must have a different server name.')
        if self.db.get(collection_name=self.collection, doc_id=server_name):
            raise Conflict(f'Template {server_name} already exists. Choose a different name.')

        source = image_source(source_record)
        match = re.search(r'(?:^|/)projects/([^/]+)/global/images/([^/]+)$', source)
        if not match:
            raise BadRequest('The shared template needs a concrete source image URL before it can be copied.')
        source_project, source_name = match.groups()
        local_image_name = f'image-{server_name}'
        if local_image_name == source_name:
            raise BadRequest('The local copy must have a different image name.')
        image_api = ComputeImageAPI(self.env.project, self.env.region, self.env.zone, log_name=self.log_name)
        source_image = image_api.get(resource=source_name, project=source_project, fallback_to_shared=False)
        if source_image.status != 'READY':
            raise NotReady('The shared image is not ready to copy. Try again after it finishes processing.')
        if image_source_project({'self_link': source_image.self_link}) != source_project:
            raise BadRequest('The source image does not match the shared template project.')

        # Reusing a VM/disk name could attach old contents on the first checkout.
        lookups = [
            lambda: image_api.get(resource=local_image_name, project=self.env.project, fallback_to_shared=False),
            lambda: ComputeInstanceAPI(self.env.project, self.env.region, self.env.zone).get(resource_name=server_name),
            lambda: ComputeDiskAPI(self.env.project, self.env.region, self.env.zone).get(resource_name=f'{server_name}-disk'),
        ]
        for lookup in lookups:
            try:
                lookup()
            except NotFound:
                continue
            raise Conflict(f'A local image, server, or disk already uses {server_name}. Choose a different name.')

        local_source = ComputeImageAPI.self_link(local_image_name, self.env.project)
        record = AgogeImageModel(**{
            **source_record,
            'name': server_name,
            'image': local_image_name,
            'self_link': local_source,
            'disks': None,
            'status': ImageStatus.CHECKED_IN.value,
            'state': ServerStates.START.value,
            'state_timestamp': None,
            'in_use_by': None,
            'dns_record': None,
            'image_exists': True,
            'is_shared': False,
            'source_project': self.env.project,
            'architecture': normalize_architecture(source_image.architecture) or source_record.get('architecture'),
        })

        if not image_api.create(
            resource_name=local_image_name, source=source_image.self_link,
            source_type=ImageSource.IMAGE, project=self.env.project, wait=True,
            description=record.description,
        ):
            raise OperationTimeout('The local image copy did not finish. No editable template was created.')
        local_image = image_api.get(resource=local_image_name, project=self.env.project, fallback_to_shared=False)
        if local_image.status != 'READY':
            raise NotReady('The local image copy is not ready. No editable template was created.')
        if local_image.self_link != local_source:
            raise BadRequest('The copied image does not match the requested local destination.')
        self._create_record(record.model_dump())
        return record

    def create_image_server(
        self,
        user: AgogeUser,
        data: dict
    ) -> None:
        """
        Create a new image server from user form

        Raises:
            BadRequest: If missing required server values in submitted form
        """
        server_name = data.get('server_name')
        action = data.get('action')
        self.user = user.email

        self.logger.info(
            f"create_image_server - action ({action}) called on server with name {server_name}",
            action=action,
            user=user.uid
        )
        if server_name and action == str(PubSub.Actions.BUILD.value):
            try:
                server_name = self._create_database_object(data)
            except (ValidationError, AgogeValidationError) as e:
                self.logger.error(f"Image failed validation with errors {e}", user=user.uid, action=action)
                raise BadRequest(message=f"Image failed validation with errors {e}")
            self._check_out(server_name)
            return
        else:
            self.logger.error(f"Invalid or missing data", action=action, server_name=server_name)
            raise BadRequest(message="Could not process request. Invalid or missing data")

    def delete(
        self,
        server_name: str
    ) -> None:
        if image := self.db.get(collection_name=self.collection, doc_id=server_name):
            self._require_local_image(image)
            msg_args = {
                self.pubsub_keys.HANDLER: str(PubSub.Handlers.CONTROL.value),
                self.pubsub_keys.ACTION: str(PubSub.Actions.DELETE.value),
                self.pubsub_keys.IMAGE_NAME: str(server_name),
                self.pubsub_keys.COURSE_OBJECT: str(PubSub.CourseObjects.IMAGE.value)
            }
            self.pubsub_manager.msg(**msg_args)
            return
        raise NotFound(message=f"No image found for id {server_name}")

    def process_action_on_list(
        self,
        user: str,
        data: dict,
    ) -> None:
        images = data.get("images", [])
        action = data.get('action', PubSub.Actions.CHECK_OUT.value)
        if images and action in [
            str(PubSub.Actions.START.value),
            str(PubSub.Actions.STOP.value),
            str(PubSub.Actions.CHECK_IN.value),
            str(PubSub.Actions.CHECK_OUT.value),
            str(PubSub.Actions.CANCEL.value)
        ]:
            msg_args = {
                self.pubsub_keys.HANDLER: str(PubSub.Handlers.CONTROL.value),
                self.pubsub_keys.ACTION: str(action),
                self.pubsub_keys.USER: str(user),
                self.pubsub_keys.COURSE_OBJECT: str(PubSub.CourseObjects.TEMPLATE_SERVER.value)
            }
            pending_messages = []
            for requested_image in images:
                name = self._get_image_name(requested_image)
                image = self.db.get(collection_name=self.collection, doc_id=name)
                if not image:
                    raise NotFound(f'No image found for ID: {name}')
                self._require_local_image(image)
                msg_args[self.pubsub_keys.IMAGE_NAME] = name
                # Only checkout boots from the saved image. Check-in must be
                # retryable if the previous image was deleted before a failed
                # replacement; start/stop/cancel operate on the working VM.
                if image.get('image_exists') and action == str(PubSub.Actions.CHECK_OUT.value):
                    img = (
                        ComputeImageAPI(self.env.project, self.env.region, self.env.zone)
                        .get(resource=image.get('image'), project=self.env.project, fallback_to_shared=False)
                    )
                    if img.status != "READY":
                        raise NotReady(message=f"Image {img.name} is not ready, current status: {img.status}")
                pending_messages.append(dict(msg_args))
            for message in pending_messages:
                self.pubsub_manager.msg(**message)
            return
        raise BadRequest(message="Invalid or missing data")

    def process_action_on_image(
        self,
        requester: AgogeUser,
        data: dict,
        server_name: str = None,
    ) -> None:
        self.user = requester.email
        action = data.get('action')
        if not action:
            raise BadRequest(message="Invalid or missing data for `action`")

        msg_args = {
            self.pubsub_keys.HANDLER: self.handler.CONTROL.value,
            self.pubsub_keys.ACTION: str(action),
            self.pubsub_keys.COURSE_OBJECT: str(PubSub.CourseObjects.TEMPLATE_SERVER.value)
        }

        if str(action) == str(PubSub.Actions.BUILD.value):
            self.logger.info(
                f"Check-out action called on image {server_name}",
                image=server_name,
                action=action,
                user=requester.uid
            )
            if not server_name:
                raise BadRequest(message="Invalid or missing data for `server_name`")

            try:
                server_name = self._create_database_object(data)
            except (ValidationError, AgogeValidationError) as e:
                raise BadRequest(message=f"Image create failed validation with errors {e}")
            return self._check_out(server_name)
        elif str(action) == str(PubSub.Actions.SYNC.value) and requester.is_admin:
            self.logger.info(
                f"Global image sync action called by user {requester.uid}",
                action=action,
                user=requester.uid
            )
            msg_args[self.pubsub_keys.IMAGE_NAME] = str(ImageScopes.GLOBAL.value)
            msg_args[self.pubsub_keys.COURSE_OBJECT] = str(PubSub.CourseObjects.PUBLIC_IMAGE.value)
        else:
            raise BadRequest(message="Invalid or unrecognized image action")

        # Send generated message
        self.pubsub_manager.msg(**msg_args)

    def update_image(
        self,
        image_name: str,
        json_data: dict
    ) -> None:
        """
        Update existing Agoge Compute Image based from form data
        Args:
            image_name (str): name of image to modify
            json_data (): submitted JSON form data

        Returns: None
        Raises:
            NotFound : Requested image does not exist in database
        """
        form_keys = [
            'machine_type',
            'description',
            'labels',
            'human_interaction',
            'disk_size',
        ]
        if image := self.db.get(collection_name=self.collection, doc_id=image_name):
            self._require_local_image(image)
            for key in form_keys:
                if new_value := json_data.get(key):
                    try:
                        if key == 'human_interaction':
                            human_interactions = [
                                self._generate_human_interaction(i, infer_from_os=False)
                                for i in new_value
                            ]
                            image[key] = human_interactions
                        elif key == 'disk_size':
                            old_value = int(image.get('add_disk', 10))
                            if int(new_value) < old_value or int(new_value) > 400:
                                error_msg = (f"Invalid value for `add_disk` {new_value}. "
                                             f"Disk sizes cannot be less than existing image "
                                             f"size or exceed 400 GB")
                                self.logger.error(
                                    f"image update failed with validation error: {error_msg}",
                                    current_disk_size=old_value,
                                    new_disk_size=new_value,
                                    image=image_name
                                )
                                raise BadRequest(message=error_msg)
                            image['add_disk'] = str(new_value)
                        elif key == 'labels':
                            image[key] = self._sanitize_labels(new_value)
                        else:
                            image[key] = str(new_value)
                    except ValueError as e:
                        self.logger.error(
                            f"{self.class_name}:update_image - ignoring key {key} "
                            f"with invalid type {type(key)}. {e}",
                            image=image_name
                        )
            try:
                validated = AgogeImageModel(**image)
                self.db.update(collection_name=self.collection, doc_id=image_name, data=validated.model_dump())
            except ValidationError as e:
                raise AgogeValidationError(message=str(e))
        else:
            msg = (f"{self.class_name} - Update request for project image "
                   f"{image_name} failed with status 404. Image does not exist!")
            self.logger.error(msg, image=image_name)
            raise NotFound(msg)

    def _check_out(
        self,
        server_name: str,
    ) -> None:
        msg_args = {
            self.pubsub_keys.HANDLER: str(PubSub.Handlers.CONTROL.value),
            self.pubsub_keys.ACTION: str(PubSub.Actions.CHECK_OUT.value),
            self.pubsub_keys.IMAGE_NAME: str(server_name),
            self.pubsub_keys.USER: str(self.user),
            self.pubsub_keys.COURSE_OBJECT: str(PubSub.CourseObjects.TEMPLATE_SERVER.value)
        }
        self.pubsub_manager.msg(**msg_args)

    def _create_database_object(
        self,
        form_data: dict
    ) -> str | bool:
        machine_type = form_data.get('machine_type', None)
        description = form_data.get('description', None)
        disk_size = form_data.get('disk_size', 50)
        image_id = form_data.get('image_template')
        image_scope = form_data.get('image_scope', ImageScopes.PROJECT.value)
        operating_system = form_data.get('os', None)
        server_name = form_data.get('server_name')

        if not (
            server_name
            and machine_type
            and description
            and image_id
            and operating_system
        ):
            raise BadRequest("Missing or invalid data")

        self._validate_new_name(server_name)
        if self.db.get(collection_name=self.collection, doc_id=server_name):
            raise Conflict(f'Template {server_name} already exists. Choose a different name.')

        image_template, image_family = self._get_image(image_scope, image_id)
        source_image = compatible_boot_image(
            ComputeImageAPI(self.env.project, self.env.region, self.env.zone, log_name=self.log_name),
            ComputeMachineTypesAPI(self.env.project, self.env.region, self.env.zone, log_name=self.log_name),
            image_template, machine_type,
        )
        image_template = source_image.self_link
        if labels := form_data.get('labels'):
            labels = self._sanitize_labels(labels)
        else:
            labels = []
        generated_connection = self._generate_human_interaction(form_data, image_family)
        image = AgogeImageModel(
            name=str(server_name),
            status=ImageStatus.CHECKED_OUT.value,
            machine_type=machine_type,
            description=str(escape(description)),
            tags=['https-server', 'http-server'],
            image=image_template,
            os=operating_system,
            add_disk=disk_size,
            self_link=image_template,
            human_interaction=[generated_connection],
            labels=labels,
            base_family=image_family,
            architecture=normalize_architecture(source_image.architecture),
        )
        self._create_record(image.model_dump())

        return server_name

    def _generate_human_interaction(
        self,
        form_data: dict,
        family: str = None,
        infer_from_os: bool = True,
    ) -> HumanInteractionModel:
        default_protocol = BuildConstants.Guacamole.Protocols.SSH.value
        ssh_key = form_data.get('ssh_key', None)

        password = form_data.get('password')
        if not password:
            password = Words().generate_str()
        elif len(password) > 200:
            raise AgogeValidationError("Password exceeds 200 characters in length!")

        username = form_data.get('username', 'pantheon')
        if not self._validate_username(username):
            raise AgogeValidationError("Username failed validation.")

        if infer_from_os:
            if form_data.get('os') == 'windows':
                if 'core' not in family:
                    default_protocol = BuildConstants.Guacamole.Protocols.RDP.value
                else:
                    default_protocol = BuildConstants.Guacamole.Protocols.SSH.value
                    if not ssh_key:
                        raise AgogeValidationError("Invalid or missing SSH key")
            else:
                if not ssh_key:
                    raise AgogeValidationError('Invalid or missing SSH key')

        display = self._parse_boolean(form_data.get('display', False))
        protocol = form_data.get('protocol', default_protocol)
        security_mode = form_data.get('security_mode', BuildConstants.Guacamole.SecurityModes.ANY.value)
        human_interaction = HumanInteractionModel(
            display=display,
            protocol=protocol,
            security_mode=security_mode,
            username=username,
            password=password,
            ssh_key=ssh_key
        )
        if domain := form_data.get('domain'):
            human_interaction.domain = domain

        return human_interaction

    def update_project_images(self, json_data: dict) -> List[ComputeImageModel]:
        action = json_data.get('action')
        modified_images = json_data.get('images')
        if modified_images and action:
            is_enabled = bool(action == 'enable')

            if db_images := self.db.query(collection_name=DbCollections.GOOGLE_IMAGES):
                collection = DbCollections.GOOGLE_IMAGES
                db_image_map = {
                    i['uuid']: self.compute_model_validator.load(i)
                    for i in db_images
                }

                operations = []
                for image in modified_images:
                    if db_image := db_image_map.get(image['uuid']):
                        db_image.is_enabled = is_enabled
                        operation = self.db.operation(
                            collection_name=collection,
                            doc_id=image['uuid'],
                            operation_type=DbOperationTypes.SET,
                            data=db_image.model_dump()
                        )
                        operations.append(operation)

                if operations:
                    self.db.batch_write(operations)
                    self.logger.info(f'Updated availability for {len(operations)} public images',
                                     action=action)
                return self.compute_model_validator.load(db_images)
            else:
                self.logger.error(f"Tried to update public images, but none found", action=action)
                raise NotFound(message="No Google compute images found")
        else:
            raise BadRequest(message="Missing or invalid data for key `images` or `action`")

    def _get_image(
        self,
        image_scope: ImageScopes,
        image_id: str
    ) -> Tuple[str, str]:
        if image_scope == ImageScopes.GLOBAL.value:
            collection = DbCollections.GOOGLE_IMAGES
            filters = [('uuid', DbOperators.EQUAL, image_id)]
            image = self.db.query(collection_name=collection, filters=filters)
        else:
            collection = DbCollections.IMAGE
            image = self.db.get(collection_name=collection, doc_id=image_id)

        # Verify it is enabled for use and get URL for image template
        if image:
            if isinstance(image, list):
                image = image[0]
            if image_scope == ImageScopes.GLOBAL.value:
                if not image.get('is_enabled', False):
                    self.logger.error(
                        f'Could not retrieve image with id {image_id}. Reason: image is not enabled for project',
                        image=image_id,
                        scope=image_scope
                    )
                    raise BadRequest(message="Invalid request. Image is not enabled for project.")
                image_family = image.get('family')
            else:
                image_family = image.get('base_family', None)
            image_template = image.get('self_link')
            if not isinstance(image_template, str) or not image_template.strip():
                raise BadRequest(
                    message='Selected image has no source image URL. Refresh the image catalog before creating a server.'
                )
            image_template = image_template.strip()
        else:
            self.logger.error(f"Requested image is invalid or does not exist",
                              image=image_id, image_scope=image_scope)
            raise NotFound(message="Requested image is invalid or does not exist")

        return image_template, image_family

    @staticmethod
    def _sanitize_labels(labels: Union[List, str]) -> List:
        sanitized = labels
        if isinstance(labels, str):
            sanitized = labels.split(',')
        return [s for s in sanitized if s != ""]

    @staticmethod
    def _parse_boolean(value):
        return str(value).lower() in ['true', '1', 'on']

    @staticmethod
    def _get_image_name(
        image: str | dict
    ) -> str:
        if isinstance(image, dict):
            return image.get('name')
        elif isinstance(image, str):
            try:
                img = json.loads(image)
                return img.get('name')
            except ValueError:
                return image

    @staticmethod
    def _validate_username(username: str) -> bool:
        username_regex = r"^[a-zA-Z0-9_]([a-zA-Z0-9_\.\-]{0,18}[a-zA-Z0-9_]?)?$"
        return re.match(username_regex, username) is not None
