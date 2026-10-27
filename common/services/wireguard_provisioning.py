"""Enrollment and exclusive kit leases for managed WireGuard Community Labs.

Private keys and callback credentials live only in Secret Manager. Firestore and
Unit/API payloads contain public keys, digests and non-secret lease metadata.
"""
import base64
from copy import deepcopy
import hashlib
import hmac
import ipaddress
import json
import math
import re
import secrets
import time
from uuid import uuid4
from urllib.parse import urlsplit

from common.constants.database import DATABASE_NAME, DatabaseTypes, DbCollections, DbOperators
from common.constants.states import ServerStates, UnitStates, WorkoutStates
from common.exceptions import BadRequest, Conflict, NotFound, NotReady, Unauthorized
from common.models.wireguard_provisioning import (
    WireGuardHealthReport, WireGuardKitCreate, WireGuardKitModel, WireGuardLeaseModel,
    WireGuardRemotePeerCreate, WireGuardRemotePeerModel, WireGuardRemotePeerUpdate, WireGuardLabSettingsUpdate,
)


def resolve_remote_peer_id(data: dict) -> str:
    """Accept old build requests without silently preferring conflicting inputs."""
    canonical, legacy = data.get('remote_peer_id'), data.get('kit_id')
    if canonical is not None and legacy is not None and canonical != legacy:
        raise BadRequest('remote_peer_id conflicts with legacy kit_id')
    identifier = canonical if canonical is not None else legacy
    if not isinstance(identifier, str) or not re.fullmatch(r'[a-z][a-z0-9-]{0,39}', identifier):
        raise BadRequest('Select a registered remote peer for this WireGuard Lab')
    return identifier


def gateway_lifecycle_ready(lease, unit, unit_id, endpoint_id, now):
    """Confirm an active GCP lifecycle without requiring optional guest telemetry.

    The caller separately verifies that the authoritative endpoint is active and
    owned by this Unit. A stopped or incomplete Unit must never become usable
    merely because a delayed guest health report says its interface is healthy.
    """
    def future(timestamp):
        return (type(timestamp) in (int, float) and math.isfinite(timestamp)
                and timestamp > now)

    return bool(
        lease.unit_id == unit_id and lease.endpoint_id == endpoint_id
        and lease.status == 'reserved' and future(lease.expires)
        and unit and unit.get('state') in (UnitStates.READY.value, UnitStates.RUNNING.value)
        and future((unit.get('workspace_settings') or {}).get('expires'))
    )


class WireGuardSecretStore:
    _GRANT_RETRY_DELAYS = (1, 2, 4, 8, 16, 32, 32)

    def __init__(self, project, client=None):
        from common.utilities.gcp.cloud_logger import Logger, LoggerNames

        if client is None:
            from google.cloud import secretmanager
            client = secretmanager.SecretManagerServiceClient()
        self.client, self.project = client, project
        self.logger = Logger(log_name=LoggerNames.CLOUD_FN, class_name=self.__class__.__name__)

    def ensure(self, unit_id, payload):
        """Only the creator adds the initial version; retries reuse its identity."""
        from google.api_core.exceptions import AlreadyExists, NotFound as GoogleNotFound
        name = f'projects/{self.project}/secrets/agoge-wg-{unit_id}'
        try:
            self.client.create_secret(request={
                'parent': f'projects/{self.project}', 'secret_id': f'agoge-wg-{unit_id}',
                'secret': {'replication': {'automatic': {}}, 'labels': {'agoge': 'wireguard'}},
            })
        except AlreadyExists:
            for attempt in range(10):
                try:
                    return self.access(f'{name}/versions/latest')
                except GoogleNotFound:
                    if attempt == 9:
                        raise BadRequest('WireGuard secret has no initialized version; inspect the failed provisioning operation')
                    time.sleep(0.2)
        self.client.add_secret_version(request={
            'parent': name, 'payload': {'data': json.dumps(payload).encode('utf-8')},
        })
        return payload

    def access(self, version_name):
        response = self.client.access_secret_version(request={'name': version_name})
        return json.loads(response.payload.data.decode('utf-8'))

    def stage_configuration(self, unit_id, revision, payload):
        """Use a new secret so an old `latest` reference never changes before CAS."""
        name = f'projects/{self.project}/secrets/agoge-wg-{unit_id}-cfg-{revision}'
        self.client.create_secret(request={
            'parent': f'projects/{self.project}', 'secret_id': name.rsplit('/', 1)[-1],
            'secret': {'replication': {'automatic': {}}, 'labels': {'agoge': 'wireguard'}},
        })
        try:
            response = self.client.add_secret_version(request={
                'parent': name, 'payload': {'data': json.dumps(payload).encode('utf-8')},
            })
        except Exception:
            # No database pointer can reference this new unique secret yet.
            try:
                self.client.delete_secret(request={'name': name})
            except Exception:
                self.logger.warning('Unable to remove an uninitialized remote lab configuration secret')
            raise
        return response.name

    def grant(self, version_name, email):
        from google.api_core.exceptions import InvalidArgument

        resource = version_name.split('/versions/')[0]
        member = f'serviceAccount:{email}'
        max_attempts = len(self._GRANT_RETRY_DELAYS) + 1
        for attempt in range(1, max_attempts + 1):
            operation = 'secretmanager.get_iam_policy'
            try:
                # A retry must read a fresh policy and etag, including any
                # conditional bindings, rather than replaying a stale write.
                policy = self.client.get_iam_policy(request={
                    'resource': resource, 'options': {'requested_policy_version': 3},
                })
                for binding in policy.bindings:
                    if binding.role == 'roles/secretmanager.secretAccessor' and not binding.HasField('condition'):
                        if member in binding.members:
                            self.logger.info('WireGuard gateway secret access is already granted.',
                                             operation=operation, attempt=attempt, max_attempts=max_attempts)
                            return
                        binding.members.append(member)
                        break
                else:
                    policy.bindings.add(role='roles/secretmanager.secretAccessor', members=[member])
                operation = 'secretmanager.set_iam_policy'
                self.client.set_iam_policy(request={'resource': resource, 'policy': policy})
            except Exception as error:
                missing_principal = (isinstance(error, InvalidArgument)
                                     and self._is_unpropagated_identity(error, email))
                fields = {'operation': operation, 'attempt': attempt, 'max_attempts': max_attempts,
                          'error_type': type(error).__name__,
                          'code': 'INVALID_ARGUMENT' if isinstance(error, InvalidArgument) else None}
                if not missing_principal or attempt == max_attempts:
                    self.logger.error('WireGuard gateway secret access grant failed.', **fields)
                    raise
                delay = self._GRANT_RETRY_DELAYS[attempt - 1]
                self.logger.warning(
                    'Waiting for the new gateway service account to become visible before granting secret access.',
                    **fields, retry_delay_seconds=delay)
                time.sleep(delay)
            else:
                self.logger.info('WireGuard gateway secret access granted.', operation=operation,
                                 attempt=attempt, max_attempts=max_attempts)
                return

    @staticmethod
    def _is_unpropagated_identity(error, email):
        """Recognize only a missing-principal response for this exact identity."""
        target = rf'(?<![a-z0-9_.@-]){re.escape(email)}(?![a-z0-9_@-]|\.[a-z0-9_-])'
        delimiter = r'''[\s:'"`<>\[\]]*'''
        principal = r'\b(?:service\s*account|principal)'
        missing = r'(?:does\s+not\s+exist|(?:was\s+)?not\s+found)\b'
        patterns = (
            rf'{principal}{delimiter}{target}{delimiter}{missing}',
            rf'\bunknown\s+service\s*account{delimiter}{target}',
            rf'{principal}\s+{missing}{delimiter}{target}',
        )
        # Inspect the response only for classification; never put its arbitrary
        # message, policy contents, or referenced credentials into logs.
        return any(re.search(pattern, str(error), re.IGNORECASE) for pattern in patterns)

    def delete(self, version_name):
        from google.api_core.exceptions import NotFound as GoogleNotFound
        try:
            self.client.delete_secret(request={'name': version_name.split('/versions/')[0]})
        except GoogleNotFound:
            pass


class WireGuardProvisioningService:
    TUNNEL_NETWORK = ipaddress.ip_network('10.254.254.0/30')
    HEALTH_MAX_AGE = 120

    def __init__(self, env_dict, db=None, secret_store=None, clock=None):
        self.env_dict = env_dict
        if db is None:
            from common.document_database.factory import DocumentDatabaseFactory
            db = DocumentDatabaseFactory.create_db_object(
                db_type=DatabaseTypes.firestore, database_name=DATABASE_NAME,
                project_id=env_dict['project'])
        self.db, self._secret_store = db, secret_store
        self.clock = clock or time.time

    @property
    def secret_store(self):
        if self._secret_store is None:
            self._secret_store = WireGuardSecretStore(self.env_dict['project'])
        return self._secret_store

    def _doc(self, collection, identifier):
        if not isinstance(identifier, str) or not identifier or '/' in identifier:
            raise BadRequest('Invalid WireGuard record identifier')
        return self.db.db.collection(getattr(collection, 'value', collection)).document(identifier)

    @staticmethod
    def _digest(token):
        return hashlib.sha256(token.encode('utf-8')).hexdigest()

    @staticmethod
    def _safe_kit(record):
        return WireGuardKitModel(**{name: value for name, value in record.items() if name in WireGuardKitModel.model_fields})

    def enroll(self, data, requester):
        if not requester.is_admin:
            raise Unauthorized('Only administrators can enroll remote WireGuard peers')
        kit = data if isinstance(data, WireGuardKitCreate) else WireGuardKitCreate(**data)
        token = secrets.token_urlsafe(48)
        record = {**kit.model_dump(), 'enabled': True, 'assigned_unit_id': None,
                  'token_digest': self._digest(token)}
        document = self._doc(DbCollections.WIREGUARD_KIT, kit.id)
        identity = self._doc('wireguard-kit-identity', self._digest(kit.device_id))
        peer_key = self._doc('wireguard-kit-peer', self._digest(kit.peer_public_key))

        def create(transaction):
            snapshots = [ref.get(transaction=transaction) for ref in (document, identity, peer_key)]
            if any(snapshot.exists for snapshot in snapshots):
                raise Conflict('This remote peer ID, device identity, or peer key is already enrolled')
            transaction.set(document, record)
            transaction.set(identity, {'kit_id': kit.id})
            transaction.set(peer_key, {'kit_id': kit.id})
        self.db.transaction(create)
        return {'kit': self._safe_kit(record), 'enrollment_token': token}

    def list_kits(self, requester):
        records = self.db.query(collection_name=DbCollections.WIREGUARD_KIT) or []
        email = (requester.email or '').lower()
        return [self._safe_kit(record) for record in records
                if requester.is_admin or email in record.get('authorized_instructors', [])]

    def list_remote_peers(self, requester):
        return [WireGuardRemotePeerModel(**kit.model_dump()) for kit in self.list_kits(requester)]

    def enroll_remote_peer(self, data, requester):
        peer = data if isinstance(data, WireGuardRemotePeerCreate) else WireGuardRemotePeerCreate(**data)
        result = self.enroll(peer, requester)
        return {'remote_peer': WireGuardRemotePeerModel(**result['kit'].model_dump()),
                'enrollment_token': result['enrollment_token']}

    def get_authorized_remote_peer(self, remote_peer_id, requester):
        kit = self.get_authorized_kit(remote_peer_id, requester)
        return WireGuardRemotePeerModel(**kit.model_dump())

    def update_remote_peer(self, remote_peer_id, data, requester):
        if not requester.is_admin:
            raise Unauthorized('Only administrators can edit remote labs')
        changes = data if isinstance(data, WireGuardRemotePeerUpdate) else WireGuardRemotePeerUpdate(**data)
        values = changes.model_dump(exclude_unset=True)
        document = self._doc(DbCollections.WIREGUARD_KIT, remote_peer_id)

        def update(transaction):
            snapshot = document.get(transaction=transaction)
            if not snapshot.exists:
                raise NotFound('Remote lab not found')
            current = snapshot.to_dict()
            merged = {**self._safe_kit(current).model_dump(), **values}
            if 'remote_network_cidr' in merged:
                merged['equipment_subnet'] = merged.pop('remote_network_cidr')
            peer = WireGuardRemotePeerModel(**merged)
            operational = ('equipment_subnet', 'peer_public_key', 'authorized_instructors', 'enabled')
            if current.get('assigned_unit_id') and any(getattr(peer, name) != current.get(name) for name in operational):
                raise Conflict('This remote lab is assigned. Change its lab settings, or release it before editing its registration.')
            old_key = self._doc('wireguard-kit-peer', self._digest(current['peer_public_key']))
            new_key = self._doc('wireguard-kit-peer', self._digest(peer.peer_public_key))
            key_snapshot = new_key.get(transaction=transaction)
            if key_snapshot.exists and key_snapshot.to_dict().get('kit_id') != remote_peer_id:
                raise Conflict('This public key is already registered to another remote lab')
            record = peer.model_dump()
            transaction.set(document, record, merge=True)
            if peer.peer_public_key != current['peer_public_key']:
                transaction.delete(old_key)
                transaction.set(new_key, {'kit_id': remote_peer_id})
            return peer
        return self.db.transaction(update)

    @staticmethod
    def _require_lab_owner(unit, requester):
        owners = unit.get('instructor_id') or []
        owners = [owners] if isinstance(owners, str) else owners
        if not requester.is_admin and (requester.email or '').lower() not in {
                owner.lower() for owner in owners if isinstance(owner, str)}:
            raise Unauthorized('Only an assigned instructor or administrator can edit this lab')

    def _lab_settings_context(self, unit_id, requester):
        unit = self.db.get(collection_name=DbCollections.UNIT, doc_id=unit_id)
        if not unit:
            raise NotFound('Lab not found')
        self._require_lab_owner(unit, requester)
        lease = self.get_lease(unit_id)
        gateways = [server for server in unit.get('servers') or [] if server.get('wireguard_gateway')]
        if len(gateways) != 1:
            raise BadRequest('This lab does not have one managed WireGuard gateway')
        server_name = f'{unit_id}-{gateways[0]["name"]}'
        server = self.db.get(collection_name=DbCollections.SERVER, doc_id=server_name) or {}
        workouts = self.db.query(collection_name=DbCollections.WORKOUT,
                                 filters=[('parent_id', DbOperators.EQUAL, unit_id)]) or []
        endpoint = self.db.get(collection_name=DbCollections.WIREGUARD_ENDPOINT, doc_id=lease.endpoint_id) or {}
        return unit, lease, server_name, server, workouts, endpoint

    def _settings_blocked_reason(self, unit, lease, server, workouts, endpoint):
        now = self.clock()
        expires = (unit.get('workspace_settings') or {}).get('expires')
        if (lease.status != 'reserved' or lease.unit_id != unit.get('id')
                or not math.isfinite(lease.expires) or lease.expires <= now
                or type(expires) not in (int, float) or not math.isfinite(expires) or expires <= now):
            return 'The lab or remote peer lease has expired or been released.'
        if unit.get('state') not in (UnitStates.READY.value, UnitStates.RUNNING.value):
            return 'The lab must finish building before its remote settings can be changed.'
        if server.get('state') != ServerStates.STOPPED.value:
            return 'Stop all students and the gateway before changing the remote lab.'
        if endpoint.get('unit_id') != lease.unit_id or endpoint.get('status') != 'reserved':
            return 'The gateway endpoint must be stopped and reserved for this lab.'
        inactive = {WorkoutStates.NOT_BUILT.value, WorkoutStates.READY.value, WorkoutStates.DELETED.value}
        if any(workout.get('state') not in inactive for workout in workouts):
            return 'Stop every student workout before changing the remote lab.'
        return None

    def lab_settings(self, unit_id, requester):
        unit, lease, _, server, workouts, endpoint = self._lab_settings_context(unit_id, requester)
        peer = self.db.get(collection_name=DbCollections.WIREGUARD_KIT, doc_id=lease.kit_id)
        reason = self._settings_blocked_reason(unit, lease, server, workouts, endpoint)
        return {'unit_id': unit_id, 'remote_peer_id': lease.kit_id,
                'remote_network_cidr': lease.equipment_subnet,
                'remote_peer': WireGuardRemotePeerModel(**self._safe_kit(peer).model_dump()).model_dump(by_alias=True) if peer else None,
                'can_edit': reason is None, 'blocked_reason': reason,
                'configuration_status': 'saved' if lease.configuration_pending else 'current'}

    def update_lab_settings(self, unit_id, data, requester):
        settings = data if isinstance(data, WireGuardLabSettingsUpdate) else WireGuardLabSettingsUpdate(**data)
        unit, lease, server_name, server, workouts, endpoint = self._lab_settings_context(unit_id, requester)
        reason = self._settings_blocked_reason(unit, lease, server, workouts, endpoint)
        if reason:
            raise Conflict(reason)
        peer = self.get_authorized_kit(settings.remote_peer_id, requester)
        remote = ipaddress.ip_network(settings.remote_network_cidr)
        if remote.overlaps(self.TUNNEL_NETWORK) or any(remote.overlaps(ipaddress.ip_network(subnet)) for subnet in lease.student_subnets):
            raise BadRequest('The remote LAN overlaps the existing student or tunnel networks')
        if peer.assigned_unit_id not in (None, unit_id):
            raise Conflict('This remote lab is already assigned to another lab')
        routes = [route for route in unit.get('routes') or [] if route.get('name') == 'wireguard-equipment']
        rules = [rule for rule in unit.get('firewall_rules') or [] if rule.get('name') == 'allow-kit-to-students']
        if len(routes) != 1 or len(rules) != 1:
            raise BadRequest('This lab does not have the managed remote LAN route and firewall rule')
        if (lease.kit_id == peer.id and lease.equipment_subnet == str(remote)
                and lease.peer_public_key == peer.peer_public_key):
            return self.lab_settings(unit_id, requester)
        payload = self.secret_store.access(lease.secret_version_name)
        payload.update(peer_public_key=peer.peer_public_key, equipment_subnet=str(remote))
        revision = uuid4().hex
        version = self.secret_store.stage_configuration(unit_id, revision, payload)
        expected_secret = f'projects/{self.env_dict["project"]}/secrets/agoge-wg-{unit_id}-cfg-{revision}/versions/'
        if not isinstance(version, str) or not version.startswith(expected_secret) or not version[len(expected_secret):].isdigit():
            raise BadRequest('Secret Manager did not return an immutable configuration version')
        record = lease.model_dump()
        record.update(kit_id=peer.id, device_id=peer.device_id, peer_public_key=peer.peer_public_key,
                      equipment_subnet=str(remote), remote_peer_id=peer.id, remote_network_cidr=str(remote),
                      previous_secret_version_name=lease.previous_secret_version_name if lease.configuration_pending else lease.secret_version_name,
                      secret_version_name=version, configuration_revision=revision, configuration_pending=True,
                      boot_id=None, service_ready=False, tunnel_ready=False, health_timestamp=None,
                      latest_handshake=0, health_error=None)
        record['secret_history'] = sorted(set([*lease.secret_history, lease.secret_version_name]))
        updated_unit = deepcopy(unit)
        for route in updated_unit.get('routes') or []:
            if route.get('name') == 'wireguard-equipment':
                route['dest_range'] = str(remote)
        for rule in updated_unit.get('firewall_rules') or []:
            if rule.get('name') == 'allow-kit-to-students':
                rule['ip_ranges'] = [str(remote)]
        updated_unit['wireguard_lease'] = WireGuardLeaseModel(**record).model_dump()
        unit_ref = self._doc(DbCollections.UNIT, unit_id)
        lease_ref = self._doc(DbCollections.WIREGUARD_LEASE, unit_id)
        endpoint_ref = self._doc(DbCollections.WIREGUARD_ENDPOINT, lease.endpoint_id)
        server_ref = self._doc(DbCollections.SERVER, server_name)
        old_peer_ref = self._doc(DbCollections.WIREGUARD_KIT, lease.kit_id)
        new_peer_ref = self._doc(DbCollections.WIREGUARD_KIT, peer.id)
        workout_refs = [(workout, self._doc(DbCollections.WORKOUT, workout['id'])) for workout in workouts]

        def save(transaction):
            refs = [unit_ref, lease_ref, endpoint_ref, server_ref, old_peer_ref, new_peer_ref]
            snapshots = [ref.get(transaction=transaction) for ref in refs]
            current_unit, current_lease, current_endpoint, current_server, old_peer, new_peer = [
                snapshot.to_dict() if snapshot.exists else {} for snapshot in snapshots]
            current_workouts = [ref.get(transaction=transaction).to_dict() or {} for _, ref in workout_refs]
            self._require_lab_owner(current_unit, requester)
            current = WireGuardLeaseModel(**current_lease)
            blocked = self._settings_blocked_reason(current_unit, current, current_server, current_workouts, current_endpoint)
            if blocked:
                raise Conflict(blocked)
            if (current_lease.get('secret_version_name') != lease.secret_version_name
                    or current_lease.get('configuration_revision') != lease.configuration_revision
                    or current_lease.get('kit_id') != lease.kit_id):
                raise Conflict('The lab settings changed; refresh and try again')
            if old_peer.get('assigned_unit_id') != unit_id:
                raise Conflict('The current remote peer assignment changed; refresh and try again')
            if (not new_peer.get('enabled') or new_peer.get('assigned_unit_id') not in (None, unit_id)
                    or new_peer.get('peer_public_key') != peer.peer_public_key
                    or new_peer.get('device_id') != peer.device_id
                    or (not requester.is_admin and (requester.email or '').lower() not in new_peer.get('authorized_instructors', []))):
                raise Conflict('The selected remote lab is no longer available or authorized')
            transaction.set(lease_ref, record, merge=True)
            transaction.set(unit_ref, {'wireguard_lease': updated_unit['wireguard_lease'],
                                     'routes': updated_unit.get('routes') or [],
                                     'firewall_rules': updated_unit.get('firewall_rules') or []}, merge=True)
            transaction.set(server_ref, {'wireguard_configuration_revision': revision}, merge=True)
            if lease.kit_id != peer.id:
                if old_peer.get('assigned_unit_id') == unit_id:
                    transaction.set(old_peer_ref, {'assigned_unit_id': None}, merge=True)
            transaction.set(new_peer_ref, {'assigned_unit_id': unit_id}, merge=True)
        try:
            self.db.transaction(save)
        except Exception:
            # A transport failure can be ambiguous after commit. Never delete
            # a selected secret or one retained in the authoritative history.
            try:
                selected = self.db.get(collection_name=DbCollections.WIREGUARD_LEASE, doc_id=unit_id) or {}
                if version not in [selected.get('secret_version_name'), *(selected.get('secret_history') or [])]:
                    self.secret_store.delete(version)
            except Exception:
                pass  # Preserve the original failure; uncertain selections stay intact.
            raise
        return self.lab_settings(unit_id, requester)

    def configuration_applied(self, unit_id, revision):
        lease_ref = self._doc(DbCollections.WIREGUARD_LEASE, unit_id)
        unit_ref = self._doc(DbCollections.UNIT, unit_id)

        def finish(transaction):
            lease_snapshot = lease_ref.get(transaction=transaction)
            unit_snapshot = unit_ref.get(transaction=transaction)
            if not lease_snapshot.exists or not unit_snapshot.exists:
                raise NotReady('The lab configuration no longer exists')
            record = lease_snapshot.to_dict()
            if record.get('configuration_revision') != revision or record.get('status') != 'reserved':
                raise Conflict('The remote lab configuration changed while applying it')
            record.update(configuration_pending=False, previous_secret_version_name=None)
            transaction.set(lease_ref, {'configuration_pending': False, 'previous_secret_version_name': None}, merge=True)
            transaction.set(unit_ref, {'wireguard_lease': WireGuardLeaseModel(**record).model_dump()}, merge=True)
        self.db.transaction(finish)

    def get_authorized_kit(self, kit_id, requester):
        if not isinstance(kit_id, str) or not re.fullmatch(r'[a-z][a-z0-9-]{0,39}', kit_id):
            raise BadRequest('Invalid remote WireGuard peer ID')
        record = self.db.get(collection_name=DbCollections.WIREGUARD_KIT, doc_id=kit_id)
        if not record or not record.get('enabled'):
            raise NotFound('Enabled remote WireGuard peer not found')
        if not requester.is_admin and (requester.email or '').lower() not in record.get('authorized_instructors', []):
            raise Unauthorized('Instructor is not authorized to use this remote WireGuard peer')
        return self._safe_kit(record)

    def _health_url(self, unit_id):
        domain = str(self.env_dict.get('parent_dns_suffix') or self.env_dict.get('dns_suffix') or '').strip('.')
        path = str(self.env_dict.get('project_path') or '').strip('/')
        origin = self.env_dict.get('wireguard_api_url') or f'https://api.{domain}' + (f'/{path}' if path else '')
        parsed = urlsplit(origin)
        if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise BadRequest('A valid HTTPS WireGuard API URL is required')
        return f'{origin.rstrip("/")}/wireguard/gateways/{unit_id}/health/'

    @staticmethod
    def _new_gateway_keys():
        from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
        from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, PublicFormat, NoEncryption
        key = X25519PrivateKey.generate()
        return (base64.b64encode(key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())).decode('ascii'),
                base64.b64encode(key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)).decode('ascii'))

    def reserve(self, unit, kit_id, requester, remote_network_cidr=None):
        if not re.fullmatch(r'[a-z]{10}', unit.id):
            raise BadRequest('Invalid WireGuard lab ID')
        kit = self.get_authorized_kit(kit_id, requester)
        if not unit.wireguard_endpoint:
            raise BadRequest('Allocate a WireGuard endpoint before reserving its remote peer')
        subnets = sorted({str(ipaddress.ip_network(subnet.ip_subnet, strict=True))
                          for network in unit.networks or [] for subnet in network.subnets or []})
        if not subnets:
            raise BadRequest('Managed WireGuard labs require student network subnets')
        networks = [ipaddress.ip_network(value) for value in subnets]
        effective_subnet = self.validate_remote_network(remote_network_cidr or kit.equipment_subnet)
        equipment = ipaddress.ip_network(effective_subnet)
        private_ranges = [ipaddress.ip_network(value) for value in ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16')]
        if any(network.version != 4 or not any(network.subnet_of(private) for private in private_ranges)
               or network.overlaps(equipment) or network.overlaps(self.TUNNEL_NETWORK)
               for network in networks) or equipment.overlaps(self.TUNNEL_NETWORK):
            raise BadRequest('Student networks must be RFC1918 IPv4 ranges; equipment, student, and tunnel networks must not overlap')
        expires = unit.workspace_settings.expires if unit.workspace_settings else None
        if not expires or expires <= self.clock():
            raise BadRequest('A future lab expiration is required')
        private_key, public_key = self._new_gateway_keys()
        health_reporting = self.env_dict.get('wireguard_health_reporting_enabled', False)
        if type(health_reporting) is not bool:
            raise BadRequest('wireguard_health_reporting_enabled must be a boolean')
        payload = {
            'unit_id': unit.id, 'private_key': private_key, 'gateway_public_key': public_key,
            'peer_public_key': kit.peer_public_key, 'gateway_address': '10.254.254.1/30',
            'peer_address': '10.254.254.2/32', 'equipment_subnet': effective_subnet,
            'student_subnets': subnets, 'listen_port': unit.wireguard_endpoint.port,
            'health_reporting_enabled': health_reporting,
        }
        if health_reporting:
            payload.update(callback_token=secrets.token_urlsafe(48), health_url=self._health_url(unit.id))
        # Secret creation is idempotent; private material is never committed to Firestore.
        payload = self.secret_store.ensure(unit.id, payload)
        if any(payload.get(key) != expected for key, expected in (
            ('unit_id', unit.id), ('peer_public_key', kit.peer_public_key),
            ('equipment_subnet', effective_subnet), ('student_subnets', subnets),
            ('listen_port', unit.wireguard_endpoint.port),
        )):
            raise Conflict('Existing gateway configuration does not match this lab and remote peer')
        lease = WireGuardLeaseModel(
            unit_id=unit.id, kit_id=kit.id, device_id=kit.device_id,
            endpoint_id=unit.wireguard_endpoint.id, equipment_subnet=effective_subnet,
            student_subnets=subnets, gateway_public_key=payload['gateway_public_key'],
            peer_public_key=kit.peer_public_key,
            secret_version_name=f'projects/{self.env_dict["project"]}/secrets/agoge-wg-{unit.id}/versions/latest',
            expires=expires,
        )
        kit_doc = self._doc(DbCollections.WIREGUARD_KIT, kit.id)
        lease_doc = self._doc(DbCollections.WIREGUARD_LEASE, unit.id)

        def claim(transaction):
            kit_snapshot = kit_doc.get(transaction=transaction)
            lease_snapshot = lease_doc.get(transaction=transaction)
            current = kit_snapshot.to_dict() if kit_snapshot.exists else None
            if not current or not current.get('enabled'):
                raise NotFound('Enabled remote WireGuard peer not found')
            if not requester.is_admin and (requester.email or '').lower() not in current.get('authorized_instructors', []):
                raise Unauthorized('Instructor authorization changed before remote peer assignment')
            if current.get('assigned_unit_id') not in (None, unit.id):
                raise Conflict('This remote peer is assigned to another lab')
            if lease_snapshot.exists:
                stored = WireGuardLeaseModel(**lease_snapshot.to_dict())
                if stored.status == 'released' or stored.kit_id != kit.id:
                    raise Conflict('This lab already has a different or released remote peer lease')
                return stored
            record = lease.model_dump()
            callback_token = payload.get('callback_token')
            if isinstance(callback_token, str) and callback_token:
                record['callback_token_digest'] = self._digest(callback_token)
            transaction.set(lease_doc, record)
            transaction.set(kit_doc, {'assigned_unit_id': unit.id}, merge=True)
            return lease
        claimed = self.db.transaction(claim)
        unit.wireguard_lease = claimed
        for server in unit.servers or []:
            if server.wireguard_gateway:
                server.wireguard_managed = True
        return claimed

    @staticmethod
    def validate_remote_network(value):
        try:
            return WireGuardKitCreate.subnet(value)
        except (ValueError, TypeError):
            raise BadRequest('Use an explicit RFC1918 private IPv4 remote LAN') from None

    def get_lease(self, unit_id):
        record = self.db.get(collection_name=DbCollections.WIREGUARD_LEASE, doc_id=unit_id)
        if not record:
            raise NotFound('WireGuard lease not found')
        return WireGuardLeaseModel(**record)

    get_gateway_lease = get_lease

    def extend_lease(self, unit_id, expires):
        """Keep the lease expiry in step with its Unit's expiration; returns False if there is no live lease."""
        document = self._doc(DbCollections.WIREGUARD_LEASE, unit_id)
        def extend(transaction):
            snapshot = document.get(transaction=transaction)
            if not snapshot.exists or snapshot.to_dict().get('status') == 'released':
                return False
            transaction.set(document, {'expires': expires}, merge=True)
            return True
        return self.db.transaction(extend)

    def gateway_secret(self, unit_id):
        lease = self.get_lease(unit_id)
        if lease.status == 'released':
            raise NotReady('WireGuard lease has been released')
        return self.secret_store.access(lease.secret_version_name)

    def grant_gateway_access(self, unit_id, email):
        expected = f'agoge-wg-{unit_id}@{self.env_dict["project"]}.iam.gserviceaccount.com'
        if email != expected:
            raise BadRequest('Gateway access must use the dedicated per-lab identity')
        self.secret_store.grant(self.get_lease(unit_id).secret_version_name, email)

    def prepare_boot(self, unit_id, force=False):
        boot_id = secrets.token_urlsafe(24)
        document = self._doc(DbCollections.WIREGUARD_LEASE, unit_id)
        def reset(transaction):
            snapshot = document.get(transaction=transaction)
            if not snapshot.exists or snapshot.to_dict().get('status') == 'released':
                raise NotReady('WireGuard lease is no longer provisionable')
            current = snapshot.to_dict()
            if not force and current.get('boot_id') and not current.get('service_ready') and current.get('health_timestamp') is None:
                return current['boot_id']
            transaction.set(document, {
                'boot_id': boot_id, 'service_ready': False, 'tunnel_ready': False,
                'health_timestamp': None, 'latest_handshake': 0, 'health_error': None,
            }, merge=True)
            return boot_id
        return self.db.transaction(reset)

    def invalidate_health(self, unit_id):
        return self.prepare_boot(unit_id, force=True)

    def report_health(self, unit_id, bearer_token, report):
        report = report if isinstance(report, WireGuardHealthReport) else WireGuardHealthReport(**report)
        document = self._doc(DbCollections.WIREGUARD_LEASE, unit_id)
        now = self.clock()
        endpoint_collection = DbCollections.WIREGUARD_ENDPOINT
        def record_health(transaction):
            snapshot = document.get(transaction=transaction)
            if not snapshot.exists:
                raise Unauthorized('Invalid gateway credentials')
            lease = snapshot.to_dict()
            digest = lease.get('callback_token_digest')
            if (not bearer_token or not isinstance(digest, str) or not digest
                    or not hmac.compare_digest(self._digest(bearer_token), digest)):
                raise Unauthorized('Invalid gateway credentials')
            endpoint = self._doc(endpoint_collection, lease['endpoint_id']).get(transaction=transaction)
            endpoint = endpoint.to_dict() if endpoint.exists else {}
            if (lease['status'] == 'released' or lease['expires'] <= now
                    or lease.get('boot_id') != report.boot_id
                    or endpoint.get('unit_id') != unit_id
                    or endpoint.get('status') in ('releasing', 'released')):
                raise NotReady('Gateway lease or boot is no longer current')
            if report.latest_handshake > now + 5:
                raise BadRequest('Gateway handshake timestamp is in the future')
            health = {
                'service_ready': report.service_ready,
                'tunnel_ready': bool(report.service_ready and report.tunnel_ready and report.latest_handshake
                                     and 0 <= now - report.latest_handshake <= 180),
                'health_timestamp': now, 'latest_handshake': report.latest_handshake,
                'health_error': report.error,
            }
            transaction.set(document, health, merge=True)
            return {'accepted': True}
        return self.db.transaction(record_health)

    def pi_configuration(self, kit_id, bearer_token):
        kit = self.db.get(collection_name=DbCollections.WIREGUARD_KIT, doc_id=kit_id)
        if not kit or not bearer_token or not hmac.compare_digest(self._digest(bearer_token), kit.get('token_digest', '')):
            raise Unauthorized('Invalid remote peer credentials')
        if not kit.get('enabled') or not kit.get('assigned_unit_id'):
            raise NotReady('This remote peer has no active lab assignment')
        lease = self.get_lease(kit['assigned_unit_id'])
        endpoint = self.db.get(collection_name=DbCollections.WIREGUARD_ENDPOINT, doc_id=lease.endpoint_id) or {}
        unit = self.db.get(collection_name=DbCollections.UNIT, doc_id=lease.unit_id)
        now = self.clock()
        if (lease.kit_id != kit_id or lease.unit_id != kit['assigned_unit_id']
                or lease.device_id != kit.get('device_id') or lease.peer_public_key != kit.get('peer_public_key')
                or not gateway_lifecycle_ready(lease, unit, lease.unit_id, lease.endpoint_id, now)
                or endpoint.get('unit_id') != lease.unit_id or endpoint.get('status') != 'active'):
            raise NotReady('The assigned gateway is stopped, expired, or not ready')
        telemetry_ready = lease.is_ready(now)
        return {
            'unit_id': lease.unit_id, 'kit_id': kit_id, 'device_id': lease.device_id,
            'endpoint_id': lease.endpoint_id, 'hostname': endpoint['hostname'], 'port': endpoint['port'],
            'gateway_public_key': lease.gateway_public_key, 'peer_public_key': lease.peer_public_key,
            'gateway_address': lease.gateway_address, 'peer_address': lease.peer_address,
            'equipment_subnet': lease.equipment_subnet, 'student_subnets': lease.student_subnets,
            'allowed_ips': [*lease.student_subnets, str(ipaddress.ip_interface(lease.gateway_address).ip) + '/32'],
            'gateway_ready': True,
            'service_ready': telemetry_ready,
            'tunnel_ready': bool(telemetry_ready and lease.tunnel_ready),
        }

    def release(self, unit_id):
        document = self._doc(DbCollections.WIREGUARD_LEASE, unit_id)
        def release_claim(transaction):
            snapshot = document.get(transaction=transaction)
            if not snapshot.exists:
                return None
            lease = snapshot.to_dict()
            kit_doc = self._doc(DbCollections.WIREGUARD_KIT, lease['kit_id'])
            kit_snapshot = kit_doc.get(transaction=transaction)
            kit = kit_snapshot.to_dict() if kit_snapshot.exists else {}
            transaction.set(document, {'status': 'released', 'service_ready': False, 'tunnel_ready': False,
                                       'boot_id': None}, merge=True)
            if kit.get('assigned_unit_id') == unit_id:
                transaction.set(kit_doc, {'assigned_unit_id': None}, merge=True)
            return [lease['secret_version_name'], *(lease.get('secret_history') or [])]
        names = self.db.transaction(release_claim)
        for name in set(names or []):
            self.secret_store.delete(name)

    def cancel_if_uncommitted(self, unit):
        if not self.db.get(collection_name=DbCollections.UNIT, doc_id=unit.id):
            self.release(unit.id)
            # A failure between secret creation and the transactional kit claim
            # still owns this deterministic, otherwise orphaned Unit secret.
            self.secret_store.delete(f'projects/{self.env_dict["project"]}/secrets/agoge-wg-{unit.id}/versions/latest')
