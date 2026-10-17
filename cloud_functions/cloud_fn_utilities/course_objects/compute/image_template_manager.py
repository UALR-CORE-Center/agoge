from secrets import token_hex
import time
from datetime import datetime, timezone
from typing import Union, Any

from common.constants.google import ImageProjects, ImageSource
from common.constants.nested import ENABLE_VMX_LICENSE, NESTED_FINALIZE_TIMEOUT_SECONDS
from common.constants.states import ImageStatus, ServerStates
from common.constants.pub_sub import PubSub
from common.constants.database import DbCollections, DATABASE_NAME, DatabaseTypes, DbOperators
from common.document_database import DocumentDatabaseFactory, DatabaseQueries
from common.exceptions import Conflict, NotFound, BaseAgogeException, BadRequest, OperationTimeout
from common.models.agoge import AgogeImageModel, NestedHostSpecModel, NestedMediaModel, NestedOsCatalogModel
from common.models.model_validators.model_validator import ModelValidator
from common.utilities.gcp.cloud_env import CloudEnv
from common.utilities.gcp.cloud_logger import Logger, LoggerNames
from common.utilities.gcp.compute.compute_image import ComputeImageAPI
from common.utilities.gcp.compute.image_compatibility import compatible_boot_image
from common.utilities.gcp.compute.image_ownership import image_source, image_source_project, is_shared_image
from common.utilities.gcp.compute.resources.network_interface_resource import NetworkInterfaceResource
from common.utilities.gcp.compute.resources.image_resource import ImageResource
from common.utilities.nested_build_monitor import is_active_nested_build
from common.utilities.nested_manifest import render_manifest, render_secrets

from cloud_fn_utilities.gcp.dns_manager import DnsManager
from cloud_fn_utilities.server_specific.agoge_user_startup_script import AgogeUserStartupScript, MetadataKey
from cloud_fn_utilities.server_specific.nested_scripts import render_builder_bootstrap, render_finalize_bootstrap

from .base_compute_manager import BaseComputeManager
from .snapshot_manager import SnapshotManager
from ...state_managers import ImageStateManager


FINALIZE_METADATA_KEY = 'agoge-nested-finalize'
FINALIZE_ATTRIBUTE_PATH = 'agoge-nested/'
FINALIZE_RESULT_ATTRIBUTE = 'finalize-result'
FINALIZE_POLL_SECONDS = 10
# Phases a Check In finalizes from; `failed` qualifies only when a finalize failed (finalize_nonce kept).
FINALIZABLE_PHASES = ('ready', 'finalized')
MSG_FINALIZE_TIMEOUT = (f'The host did not answer the finalize within {NESTED_FINALIZE_TIMEOUT_SECONDS} seconds. '
                        'Check In again to retry.')
MSG_CHECK_IN_FAILED = 'The image could not be created after the finalize. Check In again to retry.'


class ImageTemplateManager(BaseComputeManager):
    """
    Manages the creation, synchronization, and management of custom images in Google Cloud.

    Attributes:
        image_name (str): Name of the image to manage.
        server_name (str): Derived server name from the image name.
        delete_previous (bool): Whether to delete the previous image before creating a new one.
        class_name (str): Name of this class.
        logger (Logger): Logger for logging information.
        env (CloudEnv): Cloud environment configuration.
        source_image_project (str): Google Cloud project where the source image is located.
        db (DocumentDatabaseFactory): Manager for document database operations
    """

    SOURCE_IMAGE_PROJECT = ComputeImageAPI.SOURCE_IMAGE_PROJECT
    DEFAULT_MAX_SNAPSHOTS = ComputeImageAPI.DEFAULT_MAX_SNAPSHOTS

    def __init__(
        self,
        user: str = None,
        delete_previous: bool = False,
        env_dict: dict = None,
        source_image_project: str = SOURCE_IMAGE_PROJECT,
        debug: bool = False,
        shared_edit_authorized: bool = False,
    ) -> None:
        super().__init__(env_dict=env_dict, images=True, disks=True, snapshots=True)
        """
        Args:
            name (str): Name of the image to manage.
            delete_previous (bool, optional): Whether to delete the previous image before creating a new one. Defaults to False.
            env_dict (dict, optional): Environment configuration dictionary. Defaults to None.
            source_image_project (str, optional): Source project for the image. Defaults to SOURCE_IMAGE_PROJECT.
        """
        self.class_name = self.__class__.__name__
        self.log_name = LoggerNames.CLOUD_FN
        self.debug = debug
        self.user = user
        self.shared_edit_authorized = shared_edit_authorized is True
        self.delete_previous = delete_previous
        self.logger = Logger(self.log_name, class_name=self.class_name)
        self.env = CloudEnv(env_dict=env_dict) if env_dict else CloudEnv()
        self.env_dict = self.env.get_env()
        self.course_object = PubSub.CourseObjects.TEMPLATE_SERVER
        self.image_name = None
        self.server_name = None
        self.dns_manager = DnsManager(env_dict=self.env_dict)
        self.snapshot_manager = SnapshotManager(
            server_type=self.course_object,
            env_dict=self.env_dict,
            debug=self.debug,
            shared_edit_authorized=self.shared_edit_authorized,
        )
        self.source_image_project = source_image_project
        self.db = DocumentDatabaseFactory.create_db_object(
            db_type=DatabaseTypes.firestore,
            database_name=DATABASE_NAME
        )
        self.db_query = DatabaseQueries(db=self.db)
        self.collection = DbCollections.IMAGE
        self.state_manager = ImageStateManager()
        # Set by _prepare_nested_check_out for a record with `nested`; merged by _add_metadata.
        self.nested_metadata = []
        self.nested_bootstrap = None

    @property
    def dns_record(self) -> str:
        return self._dns_record()

    def load(
        self,
        server_name: str,
        **kwargs
    ) -> dict:
        """Loads the server specifications from the datastore based on server name.

        Args:
            server_name: A string name of the server.
            **kwargs: Arbitrary keyword arguments.

        Returns:
            A dictionary containing server specifications.

        Raises:
            LookupError: If no record exists for the compute record.
        """
        self.image_name, self.server_name = self._extract_image_and_server_names(server_name)

        if 'image_spec' in kwargs:
            image_spec = kwargs['image_spec']
        else:
            image_spec = self.db.get(collection_name=self.collection, doc_id=self.server_name)

        if not image_spec:
            self.logger.error(
                f"{self.class_name}:{self.server_name} - No record exists for compute image!",
                template_image_id=self.server_name,
                image_name=self.image_name
            )
            raise LookupError

        self.source_image_project = kwargs.get('source_image_project', self.env.project)
        self._load_template_server(server_spec=image_spec)
        self.server_spec.self_link = image_source(image_spec)
        self.state_manager.set_build_record(self.server_name)
        self.snapshot_manager.load(
            server_name=self.server_name,
            server_type=self.course_object,
            image_spec=image_spec
        )
        return image_spec

    def build(self) -> None:
        """Builds an individual server based on the image template specifications."""
        self._require_image_management()
        self._build_server()

    def check_in(self) -> None:
        """
        For a given compute instance, generates a production image before
        deleting the instance and associated DNS records.
        """
        self._require_image_management()
        try:
            if not self.create_production_image():
                raise OperationTimeout(f'Could not create image {self.image_name}. The server remains checked out.')
        except Exception:
            # The API refuses Check In while `finalizing`, so a failed image must not leave it there.
            self._reset_finalizing_phase()
            raise

        if self.debug:
            self.delete_server()
        else:
            self.pubsub_manager.msg(
                handler=str(PubSub.Handlers.CONTROL.value),
                image_name=str(self.image_name),
                course_object=str(PubSub.CourseObjects.TEMPLATE_SERVER.value),
                action=str(PubSub.Actions.DELETE.value),
                shared_edit_authorized=str(self.shared_edit_authorized).lower(),
            )

        # Publish the new source only after image creation and verification.
        self._update_record_status(ImageStatus.CHECKED_IN, image_created=True)

    def finalize_nested(self) -> bool:
        """Have the nested host's finalize watcher snapshot its guests, then publish CHECK_IN.

        Writes a fresh nonce to `agoge-nested-finalize` and waits up to NESTED_FINALIZE_TIMEOUT_SECONDS
        for `agoge-nested/finalize-result` to answer that nonce. `ok` publishes the existing CHECK_IN;
        an error records phase `failed` with the watcher's message; no answer returns the phase to
        `ready`. On failure the server stays checked out and running. Returns True when CHECK_IN was published.
        """
        self._require_image_management()
        record = self.db.get(collection_name=self.collection, doc_id=self.server_name)
        build = (record or {}).get('nested_build') or {}
        phase = build.get('phase')
        if not record or not record.get('nested'):
            raise BadRequest(f'Image {self.image_name} is not a nested host.')
        if record.get('status') != ImageStatus.CHECKED_OUT.value or not (
                phase in FINALIZABLE_PHASES or (phase == 'failed' and build.get('finalize_nonce'))):
            # Also what a duplicate delivery sees: a second nonce would race the first one's answer.
            raise Conflict(f'Nested image {self.image_name} cannot be finalized in build phase {phase}.')

        nonce = token_hex(16)
        self._write_nested_build(phase='finalizing', finalize_nonce=nonce, message=None)
        self.logger.info(f'{self.class_name}:{self.server_name} - Finalizing the nested host', image=self.server_name)
        try:
            self.compute_instance.set_metadata(self.server_name, items={FINALIZE_METADATA_KEY: nonce})
        except Exception as error:
            self.logger.error(f'{self.class_name}:{self.server_name} - Could not request the finalize: {error}')
            self._write_nested_build(phase='ready', finalize_nonce=None,
                                     message='The finalize could not be requested. Check In again to retry.')
            raise
        try:
            result = self._await_finalize_result(nonce)
        finally:
            try:
                self.compute_instance.set_metadata(self.server_name, remove=[FINALIZE_METADATA_KEY], wait=False)
            except Exception as error:
                # A leftover nonce is harmless: the watcher never answers a nonce twice.
                self.logger.warning(f'{self.class_name}:{self.server_name} - Could not remove the finalize key: '
                                    f'{error}')

        if result is None:
            self.logger.warning(f'{self.class_name}:{self.server_name} - {MSG_FINALIZE_TIMEOUT}')
            self._write_nested_build(phase='ready', finalize_nonce=None, message=MSG_FINALIZE_TIMEOUT)
            return False
        ok, message = result
        if not ok:
            self.logger.warning(f'{self.class_name}:{self.server_name} - Finalize failed: {message}')
            # finalize_nonce stays: it marks the failure as a finalize's, so the next Check In finalizes again.
            self._write_nested_build(phase='failed', message=message[:200])
            return False
        try:
            self.pubsub_manager.msg(
                handler=str(PubSub.Handlers.CONTROL.value),
                action=str(PubSub.Actions.CHECK_IN.value),
                course_object=str(PubSub.CourseObjects.TEMPLATE_SERVER.value),
                image_name=str(self.image_name),
                shared_edit_authorized=str(self.shared_edit_authorized).lower(),
            )
        except Exception:
            # The API refuses Check In while `finalizing`; finalizing again is safe (host.json lives in /etc).
            self._write_nested_build(phase='ready', finalize_nonce=None, message=MSG_CHECK_IN_FAILED)
            raise
        return True

    def _await_finalize_result(self, nonce: str) -> tuple[bool, str] | None:
        """Poll for the watcher's answer to `nonce`: (True, '') ok, (False, message) error, None on timeout."""
        deadline = time.monotonic() + NESTED_FINALIZE_TIMEOUT_SECONDS
        while True:
            try:
                attributes = self.compute_instance.get_guest_attributes(
                    self.server_name, query_path=FINALIZE_ATTRIBUTE_PATH)
            except Exception as error:
                # Keep waiting: one failed read is not an answer.
                self.logger.warning(f'{self.class_name}:{self.server_name} - Guest attributes unreadable: {error}')
                attributes = {}
            answer = attributes.get(FINALIZE_RESULT_ATTRIBUTE) or ''
            # An answer to another nonce is a stale one from an earlier finalize of this server.
            if answer == f'ok:{nonce}':
                return True, ''
            if answer.startswith(f'error:{nonce}:'):
                return False, answer.removeprefix(f'error:{nonce}:') or 'The finalize failed.'
            if time.monotonic() + FINALIZE_POLL_SECONDS > deadline:
                return None
            time.sleep(FINALIZE_POLL_SECONDS)

    def _write_nested_build(self, **fields) -> None:
        """Merge `fields` into the record's nested_build through a field mask."""
        record = self.db.get(collection_name=self.collection, doc_id=self.server_name) or {}
        build = {**(record.get('nested_build') or {}), **fields,
                 'updated_at': datetime.now(timezone.utc).isoformat()}
        self.db.update(collection_name=self.collection, doc_id=self.server_name, data={'nested_build': build})

    def _reset_finalizing_phase(self) -> None:
        record = self.db.get(collection_name=self.collection, doc_id=self.server_name) or {}
        if record.get('nested') and (record.get('nested_build') or {}).get('phase') == 'finalizing':
            self._write_nested_build(phase='ready', finalize_nonce=None, message=MSG_CHECK_IN_FAILED)

    def check_out(self, product_keys: dict = None) -> None:
        """
        Build a compute instance using the given compute image.
        If successful, image is reserved for changes by the requesting user
        until checked-in (released)

        Args:
            product_keys: guest -> Windows product key for a nested host's first build. Never persisted.
        """
        self._require_image_management()
        nested_phase = self._prepare_nested_check_out(product_keys)
        self.build()

        self._update_record_status(ImageStatus.CHECKED_OUT, nested_phase=nested_phase)

    def start_server(self) -> None:
        self._require_image_management()
        self._start_server()

    def stop_server(self) -> None:
        self._require_image_management()
        self._stop_server()

    def stop_all_running(self) -> None:
        """Stop any running checked out image servers"""
        running_images = self.db_query.get_running(collection_name=DbCollections.IMAGE)
        for image in running_images:
            image_id = str(image['name'])
            if is_active_nested_build(image):
                # A midnight stop would kill the builder mid-install; the build monitor bounds its runtime.
                continue
            # Trusted daily maintenance stops edit VMs in this site only.
            shared_edit_authorized = is_shared_image(image, self.env.project)
            if self.debug:
                previous_authorization = self.shared_edit_authorized
                try:
                    self.shared_edit_authorized = shared_edit_authorized
                    self.load(server_name=image_id, image_spec=image)
                    self.stop_server()
                finally:
                    self.shared_edit_authorized = previous_authorization
            else:
                self.pubsub_manager.msg(
                    handler=str(PubSub.Handlers.CONTROL.value),
                    action=str(PubSub.Actions.STOP.value),
                    course_object=str(PubSub.CourseObjects.TEMPLATE_SERVER.value),
                    image_name=str(image_id),
                    shared_edit_authorized=str(shared_edit_authorized).lower(),
                )

    def sync(
        self,
        source_project: str = None
    ) -> Union[bool, None]:
        """
        Synchronizes the image from the source project to the current project. If the image in the current project
        is older than the source image, it triggers a copy of the source image.

        Args:
            source_project (str, optional): The source project to sync the image from. Defaults to the class's
                source_image_project.

        Returns:
            bool: True if sync was successful or not needed, False if any errors occurred.
        """
        source_project = source_project if source_project else self.source_image_project
        if not self.image_name:
            self.logger.error(f"{self.class_name}: - Sync image called but no image name provided!")
            return False

        if not (src_image := self._get_image(self.image_name, source_project)):
            return False

        src_creation_ts = datetime.fromisoformat(src_image.creation_timestamp)

        if not (dst_image := self._get_image(self.image_name)):
            return self._copy_image()

        dst_creation_ts = datetime.fromisoformat(dst_image.creation_timestamp)
        if src_creation_ts > dst_creation_ts:
            return self._copy_image()

        return True

    def create_production_image(
        self,
        latest: bool = True,
        snapshot_name: str = None
    ) -> bool:
        """
        Creates a new production image from a snapshot of a specified disk.

        Args:
            latest (bool): Create a new snapshot of server and use latest to create a new image
            snapshot_name (str, optional): Create an image from existing snapshot
        """
        self._require_image_management()
        if latest:
            # latest is supplied, send request to generate a new snapshot from current template server state
            self.logger.info(f"{self.class_name}:{self.server_name} - Stopping the server before snapshotting.")
            self.stop_server()
            self.logger.info(
                f"{self.class_name}:{self.server_name} - Server has stopped. Now beginning to take a snapshot "
                f"before imaging."
            )

            snapshot_name = self.snapshot_manager.create_snapshot()
            self.logger.info(f"{self.class_name}:{self.server_name} - Completed taking the snapshot. "
                             f"Now beginning to image the server from the snapshot.")

        if not snapshot_name:
            raise ValueError("Missing value for `latest` or `snapshot_name`. Must provide one")

        # Verify the replacement source before deleting an image used by other sites.
        snapshot_source = self.compute_snapshot.get(resource_name=snapshot_name, project=self.env.project)
        expected_snapshot = f'projects/{self.env.project}/global/snapshots/{snapshot_name}'
        if (
            snapshot_source.status != 'READY'
            or self._canonical_compute_resource(snapshot_source.self_link) != expected_snapshot
        ):
            raise OperationTimeout(f'Snapshot {snapshot_name} is not ready. The existing image was retained.')

        # Wait for previous image to delete first to avoid any insert conflicts
        if not self.delete_image():
            raise OperationTimeout(f'Could not delete the existing image {self.image_name}. Retry check-in.')

        # It is now safe to send image insert request
        self.logger.info(f"{self.class_name}:{self.server_name} - Beginning to image the server.")
        if not self._create_image_from_snapshot(snapshot_source.self_link):
            raise OperationTimeout(f'Could not create image {self.image_name}. The server remains checked out.')
        image_project, image_name = self._production_image_target()
        created_image = self._production_image_api(image_project).get(
            image_name, project=image_project, fallback_to_shared=False,
        )
        expected_source = self.compute_image.self_link(image_name, image_project)
        if (
            created_image.status != 'READY'
            or self._canonical_compute_resource(created_image.self_link)
            != self._canonical_compute_resource(expected_source)
        ):
            raise OperationTimeout(f'Image {image_name} is not ready in project {image_project}. Retry check-in.')
        self.logger.info(f"{self.class_name}:{self.server_name} - Completed imaging the server.")
        return True

    def cancel(self) -> None:
        """
        Deletes instance and cancels image reservation
        """
        self._require_image_management()
        self.logger.info(f'canceling image template {self.image_name} changes')
        if not self.delete_server(state_transition=False):
            raise OperationTimeout(f'Could not delete server {self.server_name}. Retry canceling the changes.')

        self._update_record_status(ImageStatus.CHECKED_IN)

    def delete(self) -> None:
        """
        Delete production image, server, server snapshots, and image database records.
        """
        self._require_image_management()
        self.logger.info(f'starting deletion process for image template {self.image_name}')

        # Delete the template server
        self.delete_server()

        # Delete all template snapshots
        self.snapshot_manager.delete_snapshots()

        # Everything is deleted. It is safe to delete the template image
        self.delete_image()

        # Clean up DB records
        self.db.delete(collection_name=self.collection, doc_id=self.server_name)
        self.db.delete(collection_name=DbCollections.SNAPSHOTS, doc_id=self.server_name)

    def delete_server(self, state_transition: bool = True) -> bool:
        """Delete image server and server DNS records"""
        self._require_image_management()
        self.logger.info(f'{self.class_name}:{self.server_name} - Deleting server')
        if state_transition:
            self.state_manager.state_transition(self.s.DELETING)

        try:
            if not self.compute_instance.delete(self.server_name, wait=True):
                if state_transition:
                    self.state_manager.state_transition(self.s.BROKEN)
                return False
        except NotFound as e:
            # If the resource can't be found, it was either already deleted or never created
            self.logger.error(f'{self.class_name}:{self.server_name} - Deletion request returned status code 404. '
                              f'Marking {self.parent_build_id} server as deleted!')
            if state_transition:
                self.state_manager.state_transition(self.s.DELETED)
        except (BadRequest, BaseAgogeException) as e:
            if state_transition:
                self.state_manager.state_transition(self.s.BROKEN)
            return False

        if state_transition:
            self.state_manager.state_transition(self.s.DELETED)

        # Check if a dns record exists for deletion
        if dns_record := self._dns_record():
            self.logger.info(f'{self.class_name}:{self.server_name} - Deleting DNS record for server, '
                             f'{self.parent_build_id}')
            self.dns_manager.delete_dns(record_name=dns_record)

        return True

    def delete_image(self) -> bool:
        """Delete image server image"""
        self._require_image_management()
        if not self.image_name:
            self.logger.error(f'{self.class_name}: - Delete image called but no image name provided!')
            return False

        try:
            image_project, image_name = self._production_image_target()
            return self._production_image_api(image_project).delete(image_name, project=image_project, wait=True)
        except NotFound as e:
            self.logger.error(f"{self.class_name}:{self.image_name} - "
                              f"Error deleting image {self.image_name}: "
                              f"{e.message}")
            return True
        except (BadRequest, BaseAgogeException) as e:
            self.logger.error(f'{self.class_name}:{self.image_name} - {e.message}')
            raise

    def _copy_image(
        self,
        delete_previous: bool = False
    ) -> None:
        """
        Copies the image from the source project to the current project, optionally deleting the previous image.

        Raises:
            Exception: If the image deletion or copy fails or times out.
        """
        self.logger.info(f"{self.class_name}:{self.server_name} - Beginning to copy image from "
                         f"{self.source_image_project} to {self.env.project}")

        if delete_previous:
            if not self.compute_image.delete(self.image_name):
                msg = f"{self.class_name}:{self.server_name} - Timeout waiting for image to delete."
                self.logger.error(msg)
                raise Exception(msg)

        if image := self._get_image(self.image_name, project=self.source_image_project):
            image_resource = ImageResource(self.env.zone).new(
                name=self.image_name,
                source=image.self_link,
                source_type=ImageSource.IMAGE,
            )
            if not self.compute_image.create(
                resource_name=self.image_name,
                image_resource=image_resource,
                project=self.env.project
            ):
                raise Exception(f"timeout waiting for image {self.image_name} to copy.")

    def _get_image(
        self,
        image_name: str,
        project: str = None
    ) -> Any:
        if not project:
            project = self.env.project

        try:
            return self.compute_image.get(image_name, project=project)
        except NotFound as e:
            self.logger.error(
                f"{self.class_name}:{self.server_name} - The source image {image_name} does not "
                f"exist: {e.message}"
            )
            return False

    def _create_image_from_snapshot(
        self,
        snapshot_source: str
    ) -> bool:
        """Create a new image from a snapshot already verified as ready."""
        self._require_image_management()
        image_project, image_name = self._production_image_target()
        description = f'{str(image_project).capitalize()} production image.'
        if self.server_spec.description:
            description = f'{description} {self.server_spec.description}'

        return self._production_image_api(image_project).create(
            resource_name=image_name,
            project=image_project,
            description=description,
            source_type=ImageSource.SNAPSHOT,
            source=snapshot_source,
            # nested_host comes from the record's `nested` block (_load_template_server).
            licenses=[ENABLE_VMX_LICENSE] if getattr(self, 'nested_host', False) else None,
        )

    def _prepare_nested_check_out(self, product_keys: dict = None) -> str | None:
        """Point a nested host's template server at its first build or at its finalized image.

        Returns the `nested_build.phase` to record after the build, or None for a standard image.
        """
        record = self.db.get(collection_name=self.collection, doc_id=self.server_name)
        if not record or not record.get('nested'):
            return None
        phase = (record.get('nested_build') or {}).get('phase', 'queued')
        # The builder and the build monitor report through guest attributes on both paths.
        self.nested_metadata = [{'key': 'enable-guest-attributes', 'value': 'TRUE'}]
        if phase == 'finalized':
            # The image already holds the installed guests, so nothing is rebuilt: the record's
            # self_link (image-<name> since check-in) and machine_type stand, and no manifest is sent.
            # Only the finalize watcher is installed, so Check In finalizes again.
            self.nested_bootstrap = render_finalize_bootstrap()
            return phase
        # provisioning too: a duplicate Pub/Sub delivery of the first check-out must reconcile, not fail.
        if phase not in ('queued', 'provisioning'):
            raise Conflict(
                f'Nested image {self.image_name} is in build phase {phase}. Only a queued build or a '
                'finalized image can be checked out.'
            )
        try:
            spec = ModelValidator(NestedHostSpecModel, log_location=self.log_name).load(record['nested'])
            catalog, media = self._nested_sources(spec)
            manifest = render_manifest(spec, catalog, media)
            secrets = render_secrets(spec, product_keys, catalog)
        except (BaseAgogeException, ValueError) as error:
            self.logger.error(f'{self.class_name}:{self.server_name} - Cannot render the nested build: {error}')
            self._fail_nested_build(record, str(error))
            raise
        self.server_spec.self_link = f'projects/{ImageProjects.DEBIAN}/global/images/family/{spec.parent_os}'
        self.server_spec.machine_type = spec.build_machine_type
        self.nested_metadata += [
            {'key': 'agoge-nested-manifest', 'value': manifest},
            {'key': 'agoge-nested-secrets', 'value': secrets},
        ]
        self.nested_bootstrap = render_builder_bootstrap() + render_finalize_bootstrap()
        return 'provisioning'

    def _nested_sources(
        self,
        spec: NestedHostSpecModel,
    ) -> tuple[dict[str, NestedOsCatalogModel], dict[str, NestedMediaModel]]:
        """Read the catalog entries and uploaded media the spec's guests name."""
        catalog, media = {}, {}
        for guest in spec.guests:
            if guest.os_id not in catalog:
                if not (entry := self.db.get(collection_name=DbCollections.NESTED_OS_CATALOG, doc_id=guest.os_id)):
                    raise NotFound(f'guest {guest.name}: no catalog entry {guest.os_id}')
                catalog[guest.os_id] = ModelValidator(NestedOsCatalogModel, log_location=self.log_name).load(entry)
            if guest.media_id and guest.media_id not in media:
                if not (medium := self.db.get(collection_name=DbCollections.NESTED_MEDIA, doc_id=guest.media_id)):
                    raise NotFound(f'guest {guest.name}: no uploaded medium {guest.media_id}')
                media[guest.media_id] = ModelValidator(NestedMediaModel, log_location=self.log_name).load(medium)
        return catalog, media

    def _fail_nested_build(self, record: dict, message: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        record['nested_build'] = {
            **(record.get('nested_build') or {}), 'phase': 'failed', 'message': message[:200], 'updated_at': now,
        }
        if ModelValidator(AgogeImageModel, log_location=self.log_name).load(record):
            self.db.update(collection_name=self.collection, doc_id=self.server_name, data=record)

    def _add_disks(self):
        try:
            source_image = compatible_boot_image(
                self.compute_image, self.compute_machine_types,
                self.server_spec.self_link, self.server_spec.machine_type,
            )
        except BadRequest as error:
            self.logger.error(f'{self.class_name}:{self.server_name} - {error}')
            self.state_manager.state_transition(ServerStates.BROKEN)
            raise
        image_source = source_image.self_link
        if (add_disk := self.server_spec.add_disk) == 0:
            add_disk = None
        boot_disk = self._get_boot_disk(image_source=image_source, disk_size_gb=add_disk)
        self._validate_boot_disk_reuse(boot_disk)
        disks = [boot_disk]

        self.server_spec.disks = disks

    def _validate_boot_disk_reuse(self, boot_disk) -> None:
        """Reject a retained disk that would override the selected source image.

        Compute attaches an existing initializeParams.diskName instead of
        initializing it again. Only an existing matching VM's boot disk is
        accepted, so duplicate build deliveries can still be reconciled.
        """
        disk_name = boot_disk.initialize_params.disk_name
        expected_disk = f'projects/{self.env.project}/zones/{self.env.zone}/disks/{disk_name}'
        expected_image = self._canonical_compute_resource(boot_disk.initialize_params.source_image)
        for attempt in range(4):
            try:
                disk = self.compute_disk.get(resource_name=disk_name)
            except NotFound:
                return
            try:
                instance = self.compute_instance.get(resource_name=self.server_name)
            except NotFound:
                instance = None

            attached = [item for item in instance.disks if item.boot] if instance is not None else []
            attached_to_requested_vm = len(attached) == 1 and (
                self._canonical_compute_resource(attached[0].source) == expected_disk
            )
            existing_image = self._canonical_compute_resource(disk.source_image)
            if attached_to_requested_vm and existing_image and existing_image == expected_image:
                return
            # A duplicate delivery may see the disk before its creating VM.
            if (disk.status == 'CREATING' or instance is None) and attempt < 3:
                time.sleep(1)
                continue
            if disk.status == 'CREATING':
                raise Conflict(f'Boot disk {disk_name} is still being created. Retry after the current build finishes.')
            break

        raise Conflict(
            f'Boot disk {disk_name} already exists and cannot be verified as the selected '
            'image on this template VM. Compute would reuse its contents instead of '
            'initializing the selected image. The disk was retained. Inspect its source '
            'and attachments, then create the server with a new name and fresh boot disk.'
        )

    @staticmethod
    def _canonical_compute_resource(value: str) -> str:
        """Compare project-qualified Compute resource paths across API URL forms."""
        value = (value or '').strip().rstrip('/')
        if '/projects/' in value:
            return 'projects/' + value.split('/projects/', 1)[1]
        return value

    def _add_metadata(self) -> None:
        """Generates and adds metadata for the server based on specifications."""
        metadata = {'items': []}
        # User creation goes first: a long-running or early-exiting image script
        # (e.g. the nested builder) must not delay or skip the login account.
        if connections := self.server_spec.human_interaction:
            if not isinstance(connections, list):
                connections = [connections]

            if startup_script := self._generate_startup_script(connections):
                metadata_key, script = startup_script
                self._merge_metadata_item(metadata['items'], {"key": metadata_key, "value": script})
        if bootstrap := getattr(self, 'nested_bootstrap', None):
            self._merge_metadata_item(metadata['items'], {"key": "startup-script", "value": bootstrap})
        if self.server_spec.startup_script:
            # Merged, not appended: a Linux user script shares the startup-script key (Working Note 21).
            self._merge_metadata_item(
                metadata['items'],
                {"key": "startup-script", "value": self.server_spec.startup_script},
            )
        if self.server_spec.ssh_keys:
            self._merge_metadata_item(metadata['items'], {"key": "ssh-keys", "value": self._ssh_keys()})
        for item in getattr(self, 'nested_metadata', None) or []:
            self._merge_metadata_item(metadata['items'], dict(item))
        self.server_spec.metadata = metadata

    def _add_nics(self) -> None:
        """Configures network interfaces for the server."""
        network_interface_resource = NetworkInterfaceResource(region=self.env.region, project=self.env.project)
        access_config = network_interface_resource.access_config(type_='ONE_TO_ONE_NAT', name="External NAT")
        default_network = network_interface_resource.default_network()
        attached_nic = (
            network_interface_resource
            .new(
                network=default_network,
                access_configs=[access_config]
            )
        )
        self.server_spec.network_interfaces = [attached_nic]

    def _dns_record(self) -> str:
        """Generates DNS record for the server.

        Returns:
            A DNS record string.
        """
        return self._template_dns_record()

    def _generate_startup_script(
        self,
        human_interactions: list[dict]
    ) -> bool | tuple[None, str]:
        """Generates startup script based on OS and user interaction settings.

        Returns:
            A startup script string if applicable, otherwise False.
        """
        script = []
        script_key = MetadataKey.__dict__.get(self.server_spec.os.upper(), None)
        if not script_key:
            return False

        if script_key == MetadataKey.LINUX:
            script.append(AgogeUserStartupScript.unix_prefix())

        for interaction in human_interactions:
            username = interaction.get('username')
            password = interaction.get('password')
            ssh_key = interaction.get('ssh_key')
            startup_script = AgogeUserStartupScript(username, password, ssh_key)
            if script_key == MetadataKey.WINDOWS:
                script.extend(startup_script.get_windows_script())
            elif script_key == MetadataKey.LINUX:
                script.extend(startup_script.get_unix_script())

        if script:
            return script_key, "\n".join(script)
        return False

    def _update_record_status(
        self,
        status: ImageStatus = ImageStatus.CHECKED_OUT,
        image_created: bool = False,
        nested_phase: str = None,
    ) -> None:
        """Updates image status and state.
        Resets image record to default state if image is marked as checked-in.

        Args:
            status (ImageStatus): Status of current image
            image_created (bool): A new production image was successfully created and verified.
            nested_phase (str): The `nested_build.phase` a nested host's check-out reached.
        """
        db_image = self.db.get(collection_name=self.collection, doc_id=self.server_name)

        if status == ImageStatus.CHECKED_OUT:
            # Legacy templates may store their only source URL in `image`.
            if resolved_source := image_source(db_image):
                db_image['self_link'] = resolved_source
            db_image['status'] = status.value
            db_image['image'] = self.image_name
            db_image['in_use_by'] = self.user
            db_image['dns_record'] = self.dns_record
            if nested_phase:
                build = dict(db_image.get('nested_build') or {})
                now = datetime.now(timezone.utc).isoformat()
                if build.get('phase') != nested_phase:
                    build['phase'] = nested_phase
                    build['updated_at'] = now
                if nested_phase == 'provisioning' and not build.get('started_at'):
                    build['started_at'] = now
                db_image['nested_build'] = build
        elif status == ImageStatus.CHECKED_IN:
            db_image['status'] = status.value
            db_image['state'] = ServerStates.START.value
            db_image['in_use_by'] = None
            db_image['dns_record'] = None
            if image_created and db_image.get('nested') and \
                    (db_image.get('nested_build') or {}).get('phase') == 'finalizing':
                db_image['nested_build'] = {
                    **db_image['nested_build'], 'phase': 'finalized', 'finalize_nonce': None, 'message': None,
                    'updated_at': datetime.now(timezone.utc).isoformat(),
                }
            if image_created:
                image_project, image_name = self._production_image_target(db_image)
                db_image['image_exists'] = True
                db_image['image'] = image_name
                db_image['self_link'] = self.compute_image.self_link(image_name, image_project)

        if ModelValidator(AgogeImageModel, log_location=self.log_name).load(db_image):
            self.db.update(collection_name=self.collection, doc_id=self.server_name, data=db_image)

    def _require_image_management(self) -> None:
        """Shared mutations require authorization issued by the API."""
        image_record = self.db.get(collection_name=self.collection, doc_id=self.server_name)
        if not image_record:
            raise NotFound(f'No image template found with name {self.server_name}.')
        if is_shared_image(image_record, self.env.project) and not getattr(self, 'shared_edit_authorized', False):
            raise BadRequest('Shared images require administrator authorization. Copy to this site under a new name to edit.')

    def _production_image_target(self, image_record: dict = None) -> tuple[str, str]:
        """Preserve an existing shared image's location; new templates save locally."""
        if image_record is None:
            image_record = self.db.get(collection_name=self.collection, doc_id=self.server_name)
        if is_shared_image(image_record, self.env.project):
            return image_source_project(image_record), image_source(image_record).rstrip('/').rsplit('/', 1)[-1]
        return self.env.project, self.image_name

    def _production_image_api(self, image_project: str) -> ComputeImageAPI:
        """Bind operation polling to the project where the production image lives."""
        if image_project == self.env.project:
            return self.compute_image
        client = getattr(self, '_shared_image_api', None)
        if client is None or client.project != image_project:
            client = ComputeImageAPI(
                project=image_project, region=self.env.region, zone=self.env.zone, log_name=self.log_name,
            )
            self._shared_image_api = client
        return client
