"""Unit-scoped secrets and Apache Guacamole encrypted JSON authentication.

Only immutable Secret Manager references belong in application records. Signing
keys are read by the API and the dedicated shared proxy identity, never clients.
"""
import base64
import hashlib
import hmac
import json
import re
import secrets
import time

from google.api_core.exceptions import AlreadyExists, InvalidArgument, NotFound

from common.exceptions import BadRequest


def _unit_id(value):
    if not isinstance(value, str) or not re.fullmatch(r'[a-z]{10}', value):
        raise BadRequest('Invalid community lab ID')
    return value


def _key(value):
    if isinstance(value, bytes) and len(value) == 16:
        return value
    if isinstance(value, str) and re.fullmatch(r'[a-fA-F0-9]{32}', value):
        return bytes.fromhex(value)
    raise BadRequest('Invalid community proxy signing key')


def encode_json_auth(payload: dict, key: bytes) -> str:
    """Implement Apache's HMAC-SHA256 + AES-128-CBC encrypted JSON protocol."""
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.primitives.padding import PKCS7

    key = _key(key)
    plaintext = json.dumps(payload, separators=(',', ':'), ensure_ascii=False,
                           allow_nan=False).encode('utf-8')
    signed = hmac.new(key, plaintext, hashlib.sha256).digest() + plaintext
    padder = PKCS7(128).padder()
    padded = padder.update(signed) + padder.finalize()
    encryptor = Cipher(algorithms.AES(key), modes.CBC(bytes(16))).encryptor()
    return base64.b64encode(encryptor.update(padded) + encryptor.finalize()).decode('ascii')


class CommunityGuacamoleService:
    _GRANT_RETRY_DELAYS = (1, 2, 4, 8, 16, 32, 32)

    def __init__(self, env_dict, secret_client=None):
        self.project = env_dict['project']
        if secret_client is None:
            from google.cloud import secretmanager
            secret_client = secretmanager.SecretManagerServiceClient()
        self.client = secret_client

    def secret_name(self, unit_id):
        return f'projects/{self.project}/secrets/agoge-guac-{_unit_id(unit_id)}'

    def _version(self, unit_id, value):
        if (not isinstance(value, str) or not re.fullmatch(
                re.escape(self.secret_name(unit_id)) + r'/versions/[1-9][0-9]*', value)):
            raise BadRequest('Invalid community proxy secret reference')
        return value

    @staticmethod
    def _read_key(response):
        try:
            payload = json.loads(response.payload.data.decode('utf-8'))
            return _key(payload['key'])
        except (KeyError, TypeError, ValueError, UnicodeError):
            raise BadRequest('Invalid community proxy signing configuration') from None

    def ensure_key(self, unit_id):
        name = self.secret_name(unit_id)
        # Secret Manager allocates version numbers atomically. Every initializer
        # selects version 1, including a recovery racing the original creator.
        # This also avoids depending on mutable aliases or returned project
        # numbers when the caller uses its project's textual ID.
        version = name + '/versions/1'
        try:
            self.client.create_secret(request={
                'parent': f'projects/{self.project}', 'secret_id': name.rsplit('/', 1)[-1],
                'secret': {'replication': {'automatic': {}},
                           'labels': {'agoge': 'community-guacamole', 'unit': unit_id}},
            })
        except AlreadyExists:
            # A concurrent creator may not have added its first version yet.
            for attempt in range(10):
                try:
                    response = self.client.access_secret_version(request={'name': version})
                    self._read_key(response)
                    return version
                except NotFound:
                    if attempt == 9:
                        break
                    time.sleep(0.2)
        # A crashed creator can leave an empty owned secret. Recover it after
        # the grace period. If another initializer wins concurrently, our extra
        # version is harmless: all callers still use the same first key.
        self.client.add_secret_version(request={
            'parent': name,
            'payload': {'data': json.dumps({'key': secrets.token_hex(16)}).encode('utf-8')},
        })
        self._read_key(self.client.access_secret_version(request={'name': version}))
        return version

    def get_key(self, unit_id, secret_version_name):
        version = self._version(unit_id, secret_version_name)
        response = self.client.access_secret_version(request={'name': version})
        return self._read_key(response)

    def grant_proxy_access(self, unit_id, secret_version_name, email):
        version = self._version(unit_id, secret_version_name)
        expected = f'agoge-guac-{_unit_id(unit_id)}@{self.project}.iam.gserviceaccount.com'
        if email != expected:
            raise BadRequest('The community proxy identity does not belong to this lab')
        member = 'serviceAccount:' + email
        for attempt in range(len(self._GRANT_RETRY_DELAYS) + 1):
            try:
                policy = self.client.get_iam_policy(request={
                    'resource': version.split('/versions/')[0],
                    'options': {'requested_policy_version': 3},
                })
                for binding in policy.bindings:
                    if binding.role == 'roles/secretmanager.secretAccessor' and not binding.HasField('condition'):
                        if member in binding.members:
                            return
                        binding.members.append(member)
                        break
                else:
                    policy.bindings.add(role='roles/secretmanager.secretAccessor', members=[member])
                self.client.set_iam_policy(request={
                    'resource': version.split('/versions/')[0], 'policy': policy,
                })
                return
            except InvalidArgument as error:
                # New IAM identities can take time to propagate. Retry only an
                # exact missing-principal response, never log arbitrary bodies.
                from common.services.wireguard_provisioning import WireGuardSecretStore
                if (attempt == len(self._GRANT_RETRY_DELAYS)
                        or not WireGuardSecretStore._is_unpropagated_identity(error, email)):
                    raise
                time.sleep(self._GRANT_RETRY_DELAYS[attempt])

    def delete(self, unit_id):
        try:
            self.client.delete_secret(request={'name': self.secret_name(unit_id)})
        except NotFound:
            pass
