import re
import secrets
from typing import Callable, Optional

from pydantic import ValidationError

try:
    from google.api_core.exceptions import AlreadyExists, Conflict
except ModuleNotFoundError:  # Keep model/service unit tests hermetic.
    class AlreadyExists(Exception):
        pass

    class Conflict(Exception):
        pass

from common.constants.database import DATABASE_NAME, DatabaseTypes, DbCollections, DbOperators
from common.exceptions import BadRequest, NotFound
from common.models.wireguard import WireGuardEndpointModel, WireGuardEndpointRecordModel
from common.utilities.gcp.cloud_logger import Logger, LoggerNames
from common.utilities.timestamps import Timestamps


class WireGuardEndpointRegistry:
    """Allocate and resolve the public identifiers used by WireGuard gateways."""

    MAX_ALLOCATION_ATTEMPTS = 100
    PUBLIC_STATUSES = {"active"}
    CLAIMABLE_STATUSES = {"reserved", "active", "error"}
    TOMBSTONE_RETENTION_SECONDS = 24 * 60 * 60
    TRANSITION_SOURCES = {
        "reserved": {"reserved", "active", "error"},
        "active": {"reserved", "active", "error"},
        "error": {"reserved", "active", "error"},
        "releasing": {"reserved", "active", "error", "releasing"},
        # A reservation can be cancelled before a VM exists. Otherwise normal
        # teardown reaches released through releasing.
        "released": {"reserved", "error", "releasing", "released"},
    }

    def __init__(
        self,
        env_dict: dict,
        db=None,
        log_name: LoggerNames = LoggerNames.API,
        peer_id_factory: Optional[Callable[[], str]] = None,
        timestamp_factory: Optional[Callable[[], float]] = None,
    ) -> None:
        self.env_dict = env_dict
        if db is None:
            # Import lazily so callers supplying a test double do not need the
            # Google Cloud SDK installed.
            from common.document_database.factory import DocumentDatabaseFactory

            db = DocumentDatabaseFactory.create_db_object(
                db_type=DatabaseTypes.firestore,
                database_name=DATABASE_NAME,
                log_name=log_name,
            )
        self.db = db
        self.logger = Logger(log_name=log_name, class_name=self.__class__.__name__)
        self.peer_id_factory = peer_id_factory or self._new_peer_id
        self.timestamp_factory = timestamp_factory or Timestamps.get_current_timestamp_utc

    def allocate(
        self,
        unit_id: str,
        server_name: str,
        external_ip_name: Optional[str] = None,
        expires: Optional[float] = None,
    ) -> WireGuardEndpointModel:
        """Atomically reserve a five-digit ID and its deterministic DNS name."""
        existing = self.db.query(
            collection_name=DbCollections.WIREGUARD_ENDPOINT,
            filters=[("unit_id", DbOperators.EQUAL, unit_id)],
        )
        for registration in existing or []:
            if registration.get("status") in self.CLAIMABLE_STATUSES:
                return self._claim_existing_endpoint(
                    unit_id,
                    registration["id"],
                ).public_endpoint()

        for _ in range(self.MAX_ALLOCATION_ATTEMPTS):
            peer_id = self.peer_id_factory()
            if not re.fullmatch(r"[1-9][0-9]{4}", peer_id):
                raise BadRequest("WireGuard endpoint ID generator returned an invalid value")

            timestamp = self._timestamp()
            registration = WireGuardEndpointRecordModel(
                id=peer_id,
                hostname=self._hostname(peer_id),
                unit_id=unit_id,
                server_name=server_name,
                port=self._port(),
                external_ip_name=external_ip_name,
                status="reserved",
                created_timestamp=timestamp,
                updated_timestamp=timestamp,
                expires=expires,
            )
            try:
                endpoint = self._reserve_endpoint_claim(registration)
                if endpoint is not None:
                    return endpoint.public_endpoint()
            except (AlreadyExists, Conflict):
                continue
            except ValidationError as error:
                raise BadRequest(f"Invalid WireGuard endpoint configuration: {error}") from error

        raise BadRequest("The WireGuard endpoint ID pool is exhausted or busy; retry the request")

    def _claim_existing_endpoint(
        self,
        unit_id: str,
        endpoint_id: str,
    ) -> WireGuardEndpointRecordModel:
        """Create a claim for a pre-claim-schema endpoint without a duplicate race."""
        claim = self._claim_document(unit_id)
        legacy_endpoint = self._endpoint_document(endpoint_id)

        def reserve_claim(transaction):
            claim_snapshot = claim.get(transaction=transaction)
            if claim_snapshot.exists:
                claimed_id = self._claimed_endpoint_id(claim_snapshot.to_dict(), unit_id)
                claimed = self._endpoint_document(claimed_id).get(transaction=transaction)
                if not claimed.exists:
                    raise BadRequest("WireGuard endpoint claim is missing its endpoint")
                endpoint = WireGuardEndpointRecordModel(**claimed.to_dict())
                self._verify_claim_owner(endpoint, unit_id)
                self._verify_claimable(endpoint)
                return endpoint

            endpoint_snapshot = legacy_endpoint.get(transaction=transaction)
            if not endpoint_snapshot.exists:
                raise NotFound("WireGuard endpoint not found")
            endpoint = WireGuardEndpointRecordModel(**endpoint_snapshot.to_dict())
            self._verify_claim_owner(endpoint, unit_id)
            self._verify_claimable(endpoint)
            transaction.set(claim, self._claim_data(unit_id, endpoint.id))
            return endpoint

        return self.db.transaction(reserve_claim)

    def _reserve_endpoint_claim(
        self,
        registration: WireGuardEndpointRecordModel,
    ) -> Optional[WireGuardEndpointRecordModel]:
        """Atomically reserve both the Unit claim and randomly selected endpoint ID."""
        claim = self._claim_document(registration.unit_id)
        candidate = self._endpoint_document(registration.id)

        def reserve(transaction):
            claim_snapshot = claim.get(transaction=transaction)
            if claim_snapshot.exists:
                claimed_id = self._claimed_endpoint_id(
                    claim_snapshot.to_dict(),
                    registration.unit_id,
                )
                claimed = self._endpoint_document(claimed_id).get(transaction=transaction)
                if not claimed.exists:
                    raise BadRequest("WireGuard endpoint claim is missing its endpoint")
                endpoint = WireGuardEndpointRecordModel(**claimed.to_dict())
                self._verify_claim_owner(endpoint, registration.unit_id)
                self._verify_claimable(endpoint)
                return endpoint

            candidate_snapshot = candidate.get(transaction=transaction)
            if candidate_snapshot.exists:
                return None

            transaction.set(candidate, registration.model_dump())
            transaction.set(
                claim,
                self._claim_data(registration.unit_id, registration.id),
            )
            return registration

        return self.db.transaction(reserve)

    def get(self, peer_id: str, public_only: bool = False) -> WireGuardEndpointRecordModel:
        self._validate_peer_id(peer_id)
        data = self.db.get(
            collection_name=DbCollections.WIREGUARD_ENDPOINT,
            doc_id=peer_id,
        )
        if not data:
            raise NotFound("WireGuard endpoint not found")

        endpoint = WireGuardEndpointRecordModel(**data)
        if public_only and endpoint.status not in self.PUBLIC_STATUSES:
            raise NotFound("WireGuard endpoint not found")
        return endpoint

    def require_provisionable(
        self,
        peer_id: str,
        unit_id: str,
    ) -> WireGuardEndpointModel:
        """Require a live reservation before a handler may mutate GCP resources.

        Ownership alone is insufficient: BUILD/START Pub/Sub deliveries can arrive
        after the same Unit has begun (or completed) endpoint teardown.  Callers use
        this read guard before reserving an address, creating/starting a VM, or
        publishing DNS and routes.  The later transactional stage/activate calls
        remain the final race check before publication.
        """
        endpoint = self.get(peer_id)
        if endpoint.unit_id != unit_id:
            raise BadRequest("WireGuard endpoint does not belong to the requested Unit")
        if endpoint.status not in self.CLAIMABLE_STATUSES:
            raise BadRequest(
                f"WireGuard endpoint in state {endpoint.status} cannot be provisioned"
            )
        return endpoint.public_endpoint()

    def activate(
        self,
        peer_id: str,
        unit_id: str,
        public_ip: Optional[str] = None,
    ) -> WireGuardEndpointModel:
        """Mark an endpoint ready after its address and DNS record exist."""
        update = {}
        if public_ip:
            update["public_ip"] = public_ip
        endpoint = self._transition(peer_id, "active", unit_id, update)
        self._require_transition_result(endpoint, {"active"}, "activated")
        return endpoint.public_endpoint()

    def mark_reserved(
        self,
        peer_id: str,
        unit_id: str,
        public_ip: Optional[str] = None,
    ) -> WireGuardEndpointModel:
        """Mark a stopped gateway as unavailable while retaining its address and DNS."""
        update = {"public_ip": public_ip} if public_ip else None
        return self._transition(peer_id, "reserved", unit_id, update).public_endpoint()

    def stage(self, peer_id: str, unit_id: str, public_ip: str) -> WireGuardEndpointModel:
        """Record build output without demoting an endpoint already made active."""
        endpoint = self._transition(
            peer_id,
            "reserved",
            unit_id,
            {"public_ip": public_ip},
            allowed_sources={"reserved", "error"},
        )
        # An active endpoint is an accepted idempotent result for a delayed
        # staging call. Releasing/released are teardown barriers, not silent
        # successes: callers must stop before recreating DNS or routes.
        self._require_transition_result(endpoint, {"reserved", "active"}, "staged")
        return endpoint.public_endpoint()

    def mark_error(self, peer_id: str, unit_id: str) -> WireGuardEndpointModel:
        return self._transition(peer_id, "error", unit_id).public_endpoint()

    def mark_releasing(self, peer_id: str, unit_id: str) -> WireGuardEndpointModel:
        return self._transition(peer_id, "releasing", unit_id).public_endpoint()

    def release(self, peer_id: str, unit_id: str) -> None:
        """Retain a released tombstone so stale peer IDs are not reused immediately."""
        timestamp = self._timestamp()
        self._transition(
            peer_id,
            "released",
            unit_id,
            {
                "public_ip": None,
                "released_timestamp": timestamp,
            },
        )

    def purge(
        self,
        peer_id: str,
        unit_id: Optional[str] = None,
        now: Optional[float] = None,
    ) -> None:
        """Delete a released tombstone after the 24-hour reuse quarantine."""
        cutoff = float(now if now is not None else self._timestamp()) - self.TOMBSTONE_RETENTION_SECONDS
        self._delete_if_releasable(peer_id, cutoff=cutoff, unit_id=unit_id)

    def purge_released(self, now: Optional[float] = None) -> int:
        """Purge all released endpoint IDs whose quarantine is at least 24 hours old."""
        now = float(now if now is not None else self._timestamp())
        cutoff = now - self.TOMBSTONE_RETENTION_SECONDS
        registrations = self.db.query(
            collection_name=DbCollections.WIREGUARD_ENDPOINT,
            filters=[("released_timestamp", DbOperators.LESS_THAN_EQ, cutoff)],
        )
        purged = 0
        for registration in registrations or []:
            if registration.get("status") != "released" or not registration.get("id"):
                continue
            try:
                self._delete_if_releasable(registration["id"], cutoff=cutoff)
                purged += 1
            except (BadRequest, NotFound):
                # Another maintenance invocation may have won the deletion race.
                continue
        return purged

    def cancel_reservation(self, peer_id: str, unit_id: str) -> None:
        """Immediately remove an allocation that never reached Unit persistence."""
        self._delete_if_status(peer_id, allowed_statuses={"reserved"}, unit_id=unit_id)

    def _transition(
        self,
        peer_id: str,
        status: str,
        unit_id: str,
        extra_update: Optional[dict] = None,
        allowed_sources: Optional[set[str]] = None,
    ) -> WireGuardEndpointRecordModel:
        """Compare and update state atomically, ignoring stale lifecycle events."""
        self._validate_peer_id(peer_id)
        allowed_sources = allowed_sources or self.TRANSITION_SOURCES[status]
        document = self.db.db.collection(DbCollections.WIREGUARD_ENDPOINT.value).document(peer_id)
        timestamp = self._timestamp()

        def transition(transaction):
            snapshot = document.get(transaction=transaction)
            if not snapshot.exists:
                raise NotFound("WireGuard endpoint not found")
            endpoint = WireGuardEndpointRecordModel(**snapshot.to_dict())
            if endpoint.unit_id != unit_id:
                raise BadRequest("WireGuard endpoint does not belong to the requested Unit")
            if endpoint.status not in allowed_sources:
                return endpoint
            if endpoint.status == status:
                # Active retries may refresh the observed address, and the
                # initial reserved staging pass records it before publication.
                # Other repeated transitions (especially release) are strict
                # no-ops so their original lifecycle timestamps are preserved.
                refreshes_endpoint = status == "active" or (
                    status == "reserved" and bool(extra_update)
                )
                if not refreshes_endpoint:
                    return endpoint

            update = {
                "status": status,
                "updated_timestamp": timestamp,
                **(extra_update or {}),
            }
            transaction.set(document, update, merge=True)
            return endpoint.model_copy(update=update)

        endpoint = self.db.transaction(transition)
        if endpoint.status != status:
            self.logger.warning(
                f"Ignored stale WireGuard transition {endpoint.status} -> {status}",
                endpoint_id=peer_id,
            )
        return endpoint

    @staticmethod
    def _require_transition_result(
        endpoint: WireGuardEndpointRecordModel,
        accepted_statuses: set[str],
        action: str,
    ) -> None:
        if endpoint.status not in accepted_statuses:
            raise BadRequest(
                f"WireGuard endpoint in state {endpoint.status} cannot be {action}"
            )

    def _delete_if_releasable(
        self,
        peer_id: str,
        cutoff: float,
        unit_id: Optional[str] = None,
    ) -> None:
        self._delete_if_status(
            peer_id,
            allowed_statuses={"released"},
            unit_id=unit_id,
            released_before=cutoff,
        )

    def _delete_if_status(
        self,
        peer_id: str,
        allowed_statuses: set[str],
        unit_id: Optional[str] = None,
        released_before: Optional[float] = None,
    ) -> None:
        self._validate_peer_id(peer_id)
        document = self.db.db.collection(DbCollections.WIREGUARD_ENDPOINT.value).document(peer_id)

        def delete(transaction):
            snapshot = document.get(transaction=transaction)
            if not snapshot.exists:
                raise NotFound("WireGuard endpoint not found")
            endpoint = WireGuardEndpointRecordModel(**snapshot.to_dict())
            if unit_id and endpoint.unit_id != unit_id:
                raise BadRequest("WireGuard endpoint does not belong to the requested Unit")
            claim = self._claim_document(endpoint.unit_id)
            claim_snapshot = claim.get(transaction=transaction)
            if claim_snapshot.exists:
                claimed_id = self._claimed_endpoint_id(
                    claim_snapshot.to_dict(),
                    endpoint.unit_id,
                )
                if claimed_id != peer_id:
                    raise BadRequest("WireGuard endpoint claim belongs to a different endpoint")
            if endpoint.status not in allowed_statuses:
                raise BadRequest(
                    f"WireGuard endpoint in state {endpoint.status} cannot be deleted"
                )
            if (
                released_before is not None
                and (
                    endpoint.released_timestamp is None
                    or endpoint.released_timestamp > released_before
                )
            ):
                raise BadRequest("WireGuard endpoint tombstone is still quarantined")
            transaction.delete(document)
            if claim_snapshot.exists:
                transaction.delete(claim)

        self.db.transaction(delete)

    def _hostname(self, peer_id: str) -> str:
        prefix = str(self.env_dict.get("wireguard_dns_prefix") or "wg").strip().lower().strip("-.")
        if (
            len(prefix) > 57
            or not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", prefix)
        ):
            raise BadRequest("wireguard_dns_prefix must be a valid DNS label of at most 57 characters")

        parent_suffix = self.env_dict.get("parent_dns_suffix")
        suffix = self.env_dict.get("wireguard_dns_suffix") or parent_suffix
        if not suffix or not parent_suffix:
            raise BadRequest("wireguard_dns_suffix and parent_dns_suffix must be configured")
        suffix = str(suffix).strip().lower().strip(".")
        parent_suffix = str(parent_suffix).strip().lower().strip(".")
        if suffix != parent_suffix and not suffix.endswith(f".{parent_suffix}"):
            raise BadRequest(
                "wireguard_dns_suffix must equal or be a subdomain of parent_dns_suffix"
            )

        # Endpoint IDs are allocated transactionally within one Agoge project,
        # while several projects may publish into the same parent Cloud DNS
        # zone. GCP project IDs are globally unique, so a mandatory project
        # label gives every tenant its own collision-free 90,000-name pool.
        project = str(self.env_dict.get("project") or "").strip()
        if not re.fullmatch(r"[a-z][a-z0-9-]{4,28}[a-z0-9]", project):
            raise BadRequest(
                "project must be configured as an immutable GCP project ID for the "
                "WireGuard namespace"
            )
        try:
            return WireGuardEndpointModel(
                id=peer_id,
                hostname=f"{prefix}-{peer_id}.{project}.{suffix}.",
                server_name="validation-only",
            ).hostname
        except ValidationError as error:
            raise BadRequest(f"Invalid WireGuard DNS configuration: {error}") from error

    def _port(self) -> int:
        configured = self.env_dict.get("wireguard_port", 51820)
        if isinstance(configured, bool):
            raise BadRequest("wireguard_port must be an integer from 1 through 65535")
        try:
            port = int(configured)
        except (TypeError, ValueError) as error:
            raise BadRequest("wireguard_port must be an integer from 1 through 65535") from error
        if not 1 <= port <= 65535:
            raise BadRequest("wireguard_port must be an integer from 1 through 65535")
        return port

    def _timestamp(self) -> float:
        return float(self.timestamp_factory())

    def _endpoint_document(self, endpoint_id: str):
        return self.db.db.collection(DbCollections.WIREGUARD_ENDPOINT.value).document(endpoint_id)

    def _claim_document(self, unit_id: str):
        return self.db.db.collection(DbCollections.WIREGUARD_ENDPOINT_CLAIM.value).document(unit_id)

    def _claim_data(self, unit_id: str, endpoint_id: str) -> dict:
        return {
            "id": unit_id,
            "unit_id": unit_id,
            "endpoint_id": endpoint_id,
            "updated_timestamp": self._timestamp(),
        }

    def _claimed_endpoint_id(self, claim: dict, unit_id: str) -> str:
        if claim.get("unit_id") != unit_id:
            raise BadRequest("WireGuard endpoint claim belongs to a different Unit")
        endpoint_id = claim.get("endpoint_id")
        self._validate_peer_id(endpoint_id)
        return endpoint_id

    @staticmethod
    def _verify_claim_owner(endpoint: WireGuardEndpointRecordModel, unit_id: str) -> None:
        if endpoint.unit_id != unit_id:
            raise BadRequest("WireGuard endpoint claim belongs to a different Unit")

    def _verify_claimable(self, endpoint: WireGuardEndpointRecordModel) -> None:
        if endpoint.status not in self.CLAIMABLE_STATUSES:
            raise BadRequest(
                f"WireGuard endpoint claim is not allocatable in state {endpoint.status}"
            )

    @staticmethod
    def _new_peer_id() -> str:
        return str(secrets.randbelow(90000) + 10000)

    @staticmethod
    def _validate_peer_id(peer_id: str) -> None:
        if not re.fullmatch(r"[1-9][0-9]{4}", peer_id):
            raise BadRequest("WireGuard endpoint ID must be exactly five digits")
