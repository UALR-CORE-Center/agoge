"""Copy a nested image build's guest attributes into its record (Nested Image Builder Contract, Monitor step).

Lives in common/ because both deployables call it: the API on every status poll, and
QuarterHourlyMaintenance over every active build, so a build nobody watches still gets its
secrets removed and still fails when it stalls.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

from common.constants.database import DbCollections, DbOperators, DatabaseTypes, DATABASE_NAME
from common.constants.nested import NESTED_BUILD_MAX_MINUTES, NESTED_BUILD_STALL_MINUTES
from common.constants.pub_sub import PubSub
from common.constants.states import ImageStatus
from common.document_database import DocumentDatabaseFactory
from common.exceptions import NotFound
from common.models.agoge import NestedBuildStatusModel
from common.models.model_validators.model_validator import ModelValidator
from common.utilities.gcp.cloud_env import CloudEnv
from common.utilities.gcp.cloud_logger import Logger, LoggerNames
from common.utilities.gcp.compute.compute_instance import ComputeInstanceAPI
from common.utilities.gcp.compute.image_ownership import is_shared_image
from common.utilities.gcp.pubsub_manager import PubSubManager

ATTRIBUTE_NAMESPACE = 'agoge-nested/'
ATTRIBUTE_PHASE = 'phase'
ATTRIBUTE_MESSAGE = 'message'
ATTRIBUTE_HEARTBEAT = 'heartbeat'
ATTRIBUTE_GUEST_PREFIX = 'guest-'
SECRETS_METADATA_KEY = 'agoge-nested-secrets'

# Phases the builder owns. `queued` is not here: nothing runs until the check-out does.
ACTIVE_PHASES = ('provisioning', 'building')
# The builder's `phase` attribute values (the contract's guest-attribute table) and the phase each records.
REPORTED_PHASES = {'building': 'building', 'ready': 'ready', 'failed': 'failed'}
TERMINAL_PHASES = ('ready', 'failed')
GUEST_STATUSES = ('pending', 'downloading', 'installing', 'post_install', 'manual', 'ready', 'failed')
MESSAGE_MAX_LENGTH = 200

MSG_STALLED = f'The build stopped reporting progress for {NESTED_BUILD_STALL_MINUTES} minutes and was stopped.'
MSG_TIMED_OUT = f'The build ran longer than {NESTED_BUILD_MAX_MINUTES} minutes and was stopped.'


class NestedBuildMonitor:
    def __init__(
        self,
        env_dict: dict = None,
        log_name: LoggerNames = LoggerNames.CLOUD_FN,
        db=None,
        compute_instance: ComputeInstanceAPI = None,
        pubsub_manager: PubSubManager = None,
    ) -> None:
        self.class_name = self.__class__.__name__
        self.log_name = log_name
        self.logger = Logger(log_name, class_name=self.class_name)
        self.env = CloudEnv(log_name=log_name, env_dict=env_dict)
        self.env_dict = self.env.get_env()
        self.db = db or DocumentDatabaseFactory.create_db_object(
            db_type=DatabaseTypes.firestore, database_name=DATABASE_NAME, log_name=log_name
        )
        self.compute_instance = compute_instance or ComputeInstanceAPI(
            project=self.env.project, region=self.env.region, zone=self.env.zone, log_name=log_name
        )
        self.pubsub_manager = pubsub_manager or PubSubManager(
            topic=PubSub.Topics.AGOGE, log_name=log_name, env_dict=self.env_dict
        )
        self.validator = ModelValidator(model=NestedBuildStatusModel, log_location=log_name)

    def refresh(self, image: dict, now: datetime = None) -> Optional[NestedBuildStatusModel]:
        """Bring `image`'s `nested_build` up to date and return it; None for a standard image.

        Only an active build (provisioning or building) is polled, so a record already in `ready`,
        `failed`, or a finalize phase is returned as stored and its secrets are never touched twice.
        """
        if not image.get('nested'):
            return None
        name = image['name']
        build = self.validator.load(image.get('nested_build') or {})
        if build.phase not in ACTIVE_PHASES:
            return build
        now = now or datetime.now(timezone.utc)

        try:
            attributes = self.compute_instance.get_guest_attributes(name, query_path=ATTRIBUTE_NAMESPACE)
        except NotFound:
            # The check-out may not have created the server yet; the stall clock still runs.
            attributes = {}
        except Exception as error:
            # Unreadable is not stalled: judging a stored (possibly old) heartbeat now could fail a healthy build.
            self.logger.warning(f'{self.class_name}:{name} - Guest attributes unreadable: {error}', image=name)
            return build
        updated = self._apply(build, attributes)
        if not updated.started_at:
            # Without a start the timeout could never fire; start the clock at first sight.
            updated.started_at = now.isoformat()

        if updated.phase in ACTIVE_PHASES and (failure := self._overdue(updated, now)):
            updated.phase, updated.message = 'failed', failure
            self.logger.warning(f'{self.class_name}:{name} - {failure}', image=name)
            self._stop_server(image)

        if updated == build:
            return build
        if updated.phase in TERMINAL_PHASES:
            # Before the write: if removal raises, the record stays active and the next refresh retries.
            self._remove_secrets(name)
        updated.updated_at = now.isoformat()
        self.db.update(
            collection_name=DbCollections.IMAGE, doc_id=name, data={'nested_build': updated.model_dump()}
        )
        return updated

    def refresh_active(self) -> None:
        """Refresh every checked-out nested build the builder still owns (quarter-hourly maintenance)."""
        images = self.db.query(
            collection_name=DbCollections.IMAGE,
            filters=[
                ('status', DbOperators.EQUAL, ImageStatus.CHECKED_OUT.value),
                ('nested_build.phase', DbOperators.IN, list(ACTIVE_PHASES)),
            ],
        ) or []
        for image in images:
            try:
                self.refresh(image)
            except Exception as error:
                # One unreadable build must not hold up the others.
                self.logger.error(
                    f'{self.class_name}:{image.get("name")} - Build refresh failed: {error}', image=image.get('name')
                )

    def _apply(self, build: NestedBuildStatusModel, attributes: dict) -> NestedBuildStatusModel:
        updated = build.model_copy(deep=True)
        if (phase := REPORTED_PHASES.get(attributes.get(ATTRIBUTE_PHASE))) is not None:
            updated.phase = phase
        if message := attributes.get(ATTRIBUTE_MESSAGE):
            updated.message = message[:MESSAGE_MAX_LENGTH]
        if heartbeat := self._heartbeat(attributes.get(ATTRIBUTE_HEARTBEAT)):
            updated.heartbeat_at = heartbeat
        for key, value in attributes.items():
            if not key.startswith(ATTRIBUTE_GUEST_PREFIX):
                continue
            # `failed:<message>` carries the reason; the builder's `message` attribute already names the guest.
            status = value.split(':', 1)[0]
            if status in GUEST_STATUSES:
                updated.guests[key.removeprefix(ATTRIBUTE_GUEST_PREFIX)] = status
        return updated

    @staticmethod
    def _heartbeat(value: Optional[str]) -> Optional[str]:
        try:
            return datetime.fromtimestamp(int(value), tz=timezone.utc).isoformat()
        except (TypeError, ValueError, OverflowError, OSError):
            return None

    @staticmethod
    def _overdue(build: NestedBuildStatusModel, now: datetime) -> Optional[str]:
        started = _parse_time(build.started_at)
        if started and now - started > timedelta(minutes=NESTED_BUILD_MAX_MINUTES):
            return MSG_TIMED_OUT
        # Before the first heartbeat (server booting, apt installs), the build is measured from its start.
        last_seen = _parse_time(build.heartbeat_at) or started
        if last_seen and now - last_seen > timedelta(minutes=NESTED_BUILD_STALL_MINUTES):
            return MSG_STALLED
        return None

    def _remove_secrets(self, name: str) -> None:
        try:
            self.compute_instance.set_metadata(name, remove=[SECRETS_METADATA_KEY], wait=False)
        except NotFound:
            # No server, no metadata left to hold the secrets.
            pass

    def _stop_server(self, image: dict) -> None:
        # Through the existing template-server STOP, which also records the server's stopped state.
        self.pubsub_manager.msg(
            handler=str(PubSub.Handlers.CONTROL.value),
            action=str(PubSub.Actions.STOP.value),
            course_object=str(PubSub.CourseObjects.TEMPLATE_SERVER.value),
            image_name=str(image['name']),
            shared_edit_authorized=str(is_shared_image(image, self.env.project)).lower(),
        )


def _parse_time(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def is_active_nested_build(image: dict) -> bool:
    """True while the builder runs on the image's template server, which must not be stopped."""
    return bool(image.get('nested')) and (image.get('nested_build') or {}).get('phase') in ACTIVE_PHASES

