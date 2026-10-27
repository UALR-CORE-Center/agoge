import base64
import hashlib
import hmac
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.padding import PKCS7
from google.api_core.exceptions import AlreadyExists, InvalidArgument, NotFound
from google.iam.v1 import policy_pb2
import pytest

from common.exceptions import BadRequest
from common.services.community_guacamole import CommunityGuacamoleService, encode_json_auth

UNIT = 'abcdefghij'
PROJECT = 'tenant-project'
SECRET = f'projects/{PROJECT}/secrets/agoge-guac-{UNIT}'
VERSION = SECRET + '/versions/1'
EMAIL = f'agoge-guac-{UNIT}@{PROJECT}.iam.gserviceaccount.com'
KEY = bytes.fromhex('00112233445566778899aabbccddeeff')


def response(name=VERSION, key=KEY.hex()):
    return SimpleNamespace(name=name, payload=SimpleNamespace(data=json.dumps({'key': key}).encode()))


def decode_by_apache_protocol(value, key):
    decryptor = Cipher(algorithms.AES(key), modes.CBC(bytes(16))).decryptor()
    padded = decryptor.update(base64.b64decode(value, validate=True)) + decryptor.finalize()
    unpadder = PKCS7(128).unpadder()
    signed = unpadder.update(padded) + unpadder.finalize()
    digest, plaintext = signed[:32], signed[32:]
    assert hmac.compare_digest(digest, hmac.new(key, plaintext, hashlib.sha256).digest())
    return json.loads(plaintext)


def test_actual_encrypted_json_auth_roundtrip_and_independent_user_payloads():
    first = {'username': 'workout-one', 'expires': 2000000000000,
             'connections': {'student desktop': {'protocol': 'rdp', 'parameters': {
                 'hostname': '10.0.0.10', 'username': 'student', 'password': 'pässword'}}}}
    second = {'username': 'workout-two', 'expires': 2000000000000,
              'connections': {'another desktop': {'protocol': 'vnc', 'parameters': {'hostname': '10.0.0.11'}}}}
    token = encode_json_auth(first, KEY)
    assert decode_by_apache_protocol(token, KEY) == first
    assert decode_by_apache_protocol(encode_json_auth(second, KEY), KEY) == second
    assert '10.0.0.10' not in token
    assert encode_json_auth(first, KEY) != encode_json_auth(second, KEY)
    with pytest.raises((AssertionError, ValueError)):
        decode_by_apache_protocol(token, b'x' * 16)


@pytest.mark.parametrize('key', [b'x' * 15, b'x' * 32, 'not-a-key', None])
def test_rejects_invalid_signing_keys(key):
    with pytest.raises(BadRequest):
        encode_json_auth({}, key)


def test_ensure_creates_one_random_key_and_reuses_immutable_version_on_retry():
    client = MagicMock()
    client.add_secret_version.return_value = SimpleNamespace(name=VERSION)
    client.access_secret_version.return_value = response()
    service = CommunityGuacamoleService({'project': PROJECT}, client)
    assert service.ensure_key(UNIT) == VERSION
    key_payload = json.loads(client.add_secret_version.call_args.kwargs['request']['payload']['data'])
    assert len(bytes.fromhex(key_payload['key'])) == 16
    client.create_secret.side_effect = AlreadyExists('exists')
    client.access_secret_version.return_value = response()
    assert service.ensure_key(UNIT) == VERSION
    assert service.get_key(UNIT, VERSION) == KEY
    assert client.add_secret_version.call_count == 1


def test_interrupted_empty_secret_is_recovered_and_racing_initializers_use_first_version():
    client = MagicMock()
    client.create_secret.side_effect = AlreadyExists('creator crashed before its first version')
    # The final recovery adds version 2 because another creator won version 1
    # at the same time. Both operations must return the original first key.
    client.access_secret_version.side_effect = [NotFound('empty')] * 10 + [response(
        name=VERSION.replace(PROJECT, '123456789'))]
    client.add_secret_version.return_value = SimpleNamespace(name=SECRET + '/versions/2')
    with patch('common.services.community_guacamole.time.sleep'):
        service = CommunityGuacamoleService({'project': PROJECT}, client)
        assert service.ensure_key(UNIT) == VERSION
    client.add_secret_version.assert_called_once()
    assert all(call.kwargs['request']['name'] == VERSION for call in client.access_secret_version.call_args_list)


def test_concurrent_creator_is_given_time_to_initialize_without_rotating_key():
    client = MagicMock()
    client.create_secret.side_effect = AlreadyExists('exists')
    client.access_secret_version.side_effect = [NotFound('not initialized'), response()]
    with patch('common.services.community_guacamole.time.sleep') as sleep:
        assert CommunityGuacamoleService({'project': PROJECT}, client).ensure_key(UNIT) == VERSION
    sleep.assert_called_once_with(0.2)
    client.add_secret_version.assert_not_called()


@pytest.mark.parametrize('version', [
    VERSION.replace(PROJECT, 'other-project'), VERSION.replace(UNIT, 'klmnopqrst'),
    SECRET + '/versions/latest', VERSION + '/extra', '', None,
])
def test_secret_references_cannot_escape_unit_project_or_numeric_version(version):
    client = MagicMock()
    with pytest.raises(BadRequest):
        CommunityGuacamoleService({'project': PROJECT}, client).get_key(UNIT, version)
    client.access_secret_version.assert_not_called()


def test_secret_access_preserves_policy_etag_and_conditional_bindings():
    client = MagicMock()
    policy = policy_pb2.Policy(version=3, etag=b'retain-me')
    policy.bindings.add(role='roles/viewer', members=['user:keep@example.test'])
    conditional = policy.bindings.add(role='roles/secretmanager.secretAccessor', members=['user:conditional@example.test'])
    conditional.condition.expression = 'true'
    client.get_iam_policy.return_value = policy
    service = CommunityGuacamoleService({'project': PROJECT}, client)
    service.grant_proxy_access(UNIT, VERSION, EMAIL)
    saved = client.set_iam_policy.call_args.kwargs['request']['policy']
    assert saved.etag == b'retain-me'
    assert saved.bindings[1].condition.expression == 'true'
    assert list(saved.bindings[2].members) == ['serviceAccount:' + EMAIL]
    client.set_iam_policy.reset_mock()
    service.grant_proxy_access(UNIT, VERSION, EMAIL)
    client.set_iam_policy.assert_not_called()


def test_wireguard_identity_is_never_granted_proxy_secret_access():
    client = MagicMock()
    with pytest.raises(BadRequest):
        CommunityGuacamoleService({'project': PROJECT}, client).grant_proxy_access(
            UNIT, VERSION, EMAIL.replace('agoge-guac-', 'agoge-wg-'))
    client.get_iam_policy.assert_not_called()


def test_new_proxy_identity_propagation_is_retried_but_other_errors_are_not():
    client = MagicMock()
    client.get_iam_policy.side_effect = [
        InvalidArgument(f'Service account {EMAIL} does not exist'), policy_pb2.Policy(),
    ]
    service = CommunityGuacamoleService({'project': PROJECT}, client)
    with patch('common.services.community_guacamole.time.sleep') as sleep:
        service.grant_proxy_access(UNIT, VERSION, EMAIL)
    sleep.assert_called_once_with(1)
    client.get_iam_policy.side_effect = InvalidArgument('Invalid IAM policy')
    with patch('common.services.community_guacamole.time.sleep') as sleep, pytest.raises(InvalidArgument):
        service.grant_proxy_access(UNIT, VERSION, EMAIL)
    sleep.assert_not_called()


def test_delete_is_safe_to_retry_and_does_not_require_secret_access():
    client = MagicMock()
    client.delete_secret.side_effect = NotFound('gone')
    CommunityGuacamoleService({'project': PROJECT}, client).delete(UNIT)
    client.delete_secret.assert_called_once_with(request={'name': SECRET})
    client.access_secret_version.assert_not_called()
