"""Enrollment and exclusive kit leases for managed WireGuard Community Labs.

Private keys and callback credentials live only in Secret Manager. Firestore and
Unit/API payloads contain public keys, digests and non-secret lease metadata.
"""
import base64
import hashlib
import hmac
import ipaddress
import json
import re
import secrets
import time
from urllib.parse import urlsplit

from common.constants.database import DATABASE_NAME, DatabaseTypes, DbCollections
from common.exceptions import BadRequest, Conflict, NotFound, NotReady, Unauthorized
from common.models.wireguard_provisioning import (
    WireGuardHealthReport, WireGuardKitCreate, WireGuardKitModel, WireGuardLeaseModel,
    WireGuardRemotePeerCreate, WireGuardRemotePeerModel,
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

    def reserve(self, unit, kit_id, requester):
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
        equipment = ipaddress.ip_network(kit.equipment_subnet)
        private_ranges = [ipaddress.ip_network(value) for value in ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16')]
        if any(network.version != 4 or not any(network.subnet_of(private) for private in private_ranges)
               or network.overlaps(equipment) or network.overlaps(self.TUNNEL_NETWORK)
               for network in networks) or equipment.overlaps(self.TUNNEL_NETWORK):
            raise BadRequest('Student networks must be RFC1918 IPv4 ranges; equipment, student, and tunnel networks must not overlap')
        expires = unit.workspace_settings.expires if unit.workspace_settings else None
        if not expires or expires <= self.clock():
            raise BadRequest('A future lab expiration is required')
        private_key, public_key = self._new_gateway_keys()
        callback_token = secrets.token_urlsafe(48)
        payload = {
            'unit_id': unit.id, 'private_key': private_key, 'gateway_public_key': public_key,
            'peer_public_key': kit.peer_public_key, 'gateway_address': '10.254.254.1/30',
            'peer_address': '10.254.254.2/32', 'equipment_subnet': kit.equipment_subnet,
            'student_subnets': subnets, 'listen_port': unit.wireguard_endpoint.port,
            'callback_token': callback_token, 'health_url': self._health_url(unit.id),
        }
        # Secret creation is idempotent; private material is never committed to Firestore.
        payload = self.secret_store.ensure(unit.id, payload)
        if any(payload.get(key) != expected for key, expected in (
            ('unit_id', unit.id), ('peer_public_key', kit.peer_public_key),
            ('equipment_subnet', kit.equipment_subnet), ('student_subnets', subnets),
            ('listen_port', unit.wireguard_endpoint.port),
        )):
            raise Conflict('Existing gateway configuration does not match this lab and remote peer')
        lease = WireGuardLeaseModel(
            unit_id=unit.id, kit_id=kit.id, device_id=kit.device_id,
            endpoint_id=unit.wireguard_endpoint.id, equipment_subnet=kit.equipment_subnet,
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
            transaction.set(lease_doc, {**lease.model_dump(), 'callback_token_digest': self._digest(payload['callback_token'])})
            transaction.set(kit_doc, {'assigned_unit_id': unit.id}, merge=True)
            return lease
        claimed = self.db.transaction(claim)
        unit.wireguard_lease = claimed
        for server in unit.servers or []:
            if server.wireguard_gateway:
                server.wireguard_managed = True
        return claimed

    def get_lease(self, unit_id):
        record = self.db.get(collection_name=DbCollections.WIREGUARD_LEASE, doc_id=unit_id)
        if not record:
            raise NotFound('WireGuard lease not found')
        return WireGuardLeaseModel(**record)

    get_gateway_lease = get_lease

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
            if not bearer_token or not hmac.compare_digest(self._digest(bearer_token), lease.get('callback_token_digest', '')):
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
        endpoint = self.db.get(collection_name=DbCollections.WIREGUARD_ENDPOINT, doc_id=lease.endpoint_id)
        unit = self.db.get(collection_name=DbCollections.UNIT, doc_id=lease.unit_id)
        now = self.clock()
        if (lease.kit_id != kit_id or not lease.is_ready(now) or not unit
                or endpoint.get('unit_id') != lease.unit_id or endpoint.get('status') != 'active'
                or (unit.get('workspace_settings') or {}).get('expires', 0) <= now):
            raise NotReady('The assigned gateway is stopped, expired, or not ready')
        return {
            'unit_id': lease.unit_id, 'kit_id': kit_id, 'device_id': lease.device_id,
            'endpoint_id': lease.endpoint_id, 'hostname': endpoint['hostname'], 'port': endpoint['port'],
            'gateway_public_key': lease.gateway_public_key, 'peer_public_key': lease.peer_public_key,
            'gateway_address': lease.gateway_address, 'peer_address': lease.peer_address,
            'equipment_subnet': lease.equipment_subnet, 'student_subnets': lease.student_subnets,
            'allowed_ips': [*lease.student_subnets, str(ipaddress.ip_interface(lease.gateway_address).ip) + '/32'],
            'service_ready': True, 'tunnel_ready': lease.tunnel_ready,
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
            return lease['secret_version_name']
        name = self.db.transaction(release_claim)
        if name:
            self.secret_store.delete(name)

    def cancel_if_uncommitted(self, unit):
        if not self.db.get(collection_name=DbCollections.UNIT, doc_id=unit.id):
            self.release(unit.id)
            # A failure between secret creation and the transactional kit claim
            # still owns this deterministic, otherwise orphaned Unit secret.
            self.secret_store.delete(f'projects/{self.env_dict["project"]}/secrets/agoge-wg-{unit.id}/versions/latest')
