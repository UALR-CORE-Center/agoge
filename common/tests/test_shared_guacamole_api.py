"""Offline Guacamole HTTP-boundary scenarios for shared and Solo workouts.

The real API selects owned runtime VMs and signs the actual JSON credential.
Only Firestore, Secret Manager and Guacamole's external HTTP exchange are fake.
"""
import base64
from copy import deepcopy
import hashlib
import hmac
import json
from types import SimpleNamespace

import pytest
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.padding import PKCS7

from common.constants.database import DbCollections
from common.constants.states import ServerStates, UnitStates, WorkoutStates
from common.exceptions import BadRequest, GuacamoleInvalidSession, GuacamoleServerNotFound
from common.services import community_guacamole as secrets_module
from core import guacamole_api as api_module


UNIT_ID = 'abcdefghij'
FIRST_ID = 'klmnopqrst'
SECOND_ID = 'uvwxyzabcd'
NOW = 1_000
KEY = bytes(range(16))
SECRET_VERSION = f'projects/offline-project/secrets/agoge-guac-{UNIT_ID}/versions/1'
PROXY_NAME = f'{UNIT_ID}-display-guacamole-server'


class MemoryDatabase:
    def __init__(self):
        self.records = {collection: {} for collection in DbCollections}

    def get(self, collection_name, doc_id):
        return deepcopy(self.records[collection_name].get(doc_id))


def decode_json_auth(encoded):
    """Stand in for Guacamole's independent authentication boundary."""
    decryptor = Cipher(algorithms.AES(KEY), modes.CBC(bytes(16))).decryptor()
    padded = decryptor.update(base64.b64decode(encoded, validate=True)) + decryptor.finalize()
    unpadder = PKCS7(128).unpadder()
    signed = unpadder.update(padded) + unpadder.finalize()
    signature, plaintext = signed[:32], signed[32:]
    assert hmac.compare_digest(signature, hmac.new(KEY, plaintext, hashlib.sha256).digest())
    return json.loads(plaintext)


@pytest.fixture
def context(monkeypatch):
    db = MemoryDatabase()
    env = SimpleNamespace(parent_dns_suffix='.labs.example.', main_app_url='https://app.example/test')
    env.get_env = lambda: {'project': 'offline-project'}
    monkeypatch.setattr(api_module, 'CloudEnv', lambda **_: env)
    monkeypatch.setattr(api_module.DocumentDatabaseFactory, 'create_db_object', lambda **_: db)
    monkeypatch.setattr(api_module.time, 'time', lambda: NOW)
    requests, payloads, secret_reads = [], [], []

    class Secrets:
        def __init__(self, env_dict):
            assert env_dict == {'project': 'offline-project'}

        def get_key(self, unit_id, version):
            secret_reads.append((unit_id, version))
            assert (unit_id, version) == (UNIT_ID, SECRET_VERSION)
            return KEY

    monkeypatch.setattr(secrets_module, 'CommunityGuacamoleService', Secrets)

    def post(url, **kwargs):
        requests.append((url, kwargs))
        assert kwargs['timeout'] == (5, 15)
        assert kwargs['allow_redirects'] is False
        assert set(kwargs['data']) == {'data'}
        payload = decode_json_auth(kwargs['data']['data'])
        assert payload['expires'] > NOW * 1000
        payloads.append(payload)
        return SimpleNamespace(status_code=200, json=lambda: {'authToken': f'session-{len(payloads)}',
                               'username': payload['username'], 'dataSource': 'json'})

    monkeypatch.setattr(api_module.requests, 'post', post)
    proxy = {'name': 'display-guacamole-server', 'community_proxy': True,
             'community_server': True, 'guacamole_secret_version_name': SECRET_VERSION}
    db.records[DbCollections.UNIT][UNIT_ID] = {
        'id': UNIT_ID, 'unit_type': 'community', 'state': UnitStates.READY.value,
        'workspace_settings': {'expires': NOW + 3600},
        'networks': [{'name': 'external', 'subnets': [{'ip_subnet': '10.20.0.0/24'}]}],
        'servers': [proxy, {'name': 'kali'}, {'name': 'windows'}],
    }
    db.records[DbCollections.SERVER][PROXY_NAME] = {
        **proxy, 'id': PROXY_NAME, 'parent_id': UNIT_ID, 'state': ServerStates.RUNNING.value,
    }
    for student, addresses in [(FIRST_ID, ('10.20.0.30', '10.20.0.31')),
                               (SECOND_ID, ('10.20.0.32', '10.20.0.33'))]:
        db.records[DbCollections.WORKOUT][student] = {
            'id': student, 'parent_id': UNIT_ID, 'state': WorkoutStates.RUNNING.value,
            'guacamole_auth': 'json', 'expires': None, 'shutoff_timestamp': NOW + 600,
            'servers': [{'name': 'windows'}, {'name': 'kali'}],
            # A stale or tampered descriptor must never be a connection target.
            'proxy_connections': [{'server': 'kali', 'internal_ip_address': '10.20.0.99',
                                   'username': 'guacadmin', 'password': 'wrong'}],
        }
        for name, address in zip(('kali', 'windows'), addresses):
            db.records[DbCollections.SERVER][f'{student}-{name}'] = {
                'id': f'{student}-{name}', 'name': name, 'parent_id': student,
                'state': ServerStates.RUNNING.value, 'hostname': f'{student}-{name}.labs.example',
                'nics': [{'internal_ip': address}],
                'human_interaction': [
                    {'display': False, 'protocol': 'ssh', 'password': 'hidden-connection'},
                    {'display': True, 'protocol': 'rdp', 'username': 'student',
                     'password': f'{student}-vm-password', 'security_mode': 'nla'},
                ],
            }
    return SimpleNamespace(db=db, requests=requests, payloads=payloads, secret_reads=secret_reads,
                           session=lambda student=FIRST_ID: api_module.Guacamole(student, {}))


def test_shared_session_contains_only_requested_workout_connection(context):
    response = context.session().get_connection_from_server('1')
    payload = context.payloads[-1]
    assert response == {'token': 'session-1', 'protocol': 'rdp',
                        'hostname': f'{FIRST_ID}-windows.labs.example', 'server': 'windows',
                        'url': f'https://{UNIT_ID}-display.labs.example/guacamole'}
    assert payload == {'username': f'agoge-{FIRST_ID}', 'expires': (NOW + 120) * 1000,
                       'connections': {f'{FIRST_ID}-windows': {'protocol': 'rdp', 'parameters': {
                           'hostname': '10.20.0.31', 'port': '3389', 'username': 'student',
                           'password': f'{FIRST_ID}-vm-password', 'security': 'nla',
                           'ignore-cert': 'true'}}}}
    assert context.requests[0][0] == f'{response["url"]}/api/tokens'
    assert context.secret_reads == [(UNIT_ID, SECRET_VERSION)]
    assert 'password' not in response and 'guacadmin' not in json.dumps(payload)


def test_two_students_use_same_proxy_and_distinct_user_scopes(context):
    first = context.session(FIRST_ID).get_connection_from_server('0')
    second = context.session(SECOND_ID).get_connection_from_server('0')
    assert first['url'] == second['url']
    assert first['token'] != second['token']
    assert [item['username'] for item in context.payloads] == [f'agoge-{FIRST_ID}', f'agoge-{SECOND_ID}']
    first_payload, second_payload = context.payloads
    assert list(first_payload['connections']) == [f'{FIRST_ID}-kali']
    assert list(second_payload['connections']) == [f'{SECOND_ID}-kali']
    assert FIRST_ID not in json.dumps(second_payload)
    assert SECOND_ID not in json.dumps(first_payload)
    assert {payload['connections'][next(iter(payload['connections']))]['parameters']['hostname']
            for payload in context.payloads} == {'10.20.0.30', '10.20.0.32'}


def test_shared_descriptors_do_not_expose_vm_credentials_or_internal_records(context):
    connections = context.session().get_all_connections()
    assert [connection['server'] for connection in connections] == ['kali', 'windows']
    assert [connection['idx'] for connection in connections] == [0, 1]
    for connection in connections:
        assert connection['username'] == f'agoge-{FIRST_ID}'
        assert connection['password'] is None
        assert not any(key.startswith('_') for key in connection)
        assert connection['url'].startswith(f'https://app.example/test/student/workout/{FIRST_ID}/')
    assert 'vm-password' not in json.dumps(connections)


def test_json_workout_never_falls_back_to_private_jdbc_when_shared_proxy_is_missing(context):
    workout = context.db.records[DbCollections.WORKOUT][FIRST_ID]
    workout.pop('guacamole_auth')
    workout['proxy_connections'][0]['auth_type'] = 'json'
    context.db.records[DbCollections.UNIT][UNIT_ID]['servers'] = [{'name': 'kali'}]
    with pytest.raises(GuacamoleInvalidSession):
        context.session().get_connection_from_server('0')
    assert not context.requests and not context.secret_reads


@pytest.mark.parametrize(('collection', 'identifier', 'change'), [
    (DbCollections.WORKOUT, FIRST_ID, {'state': WorkoutStates.READY.value}),
    (DbCollections.UNIT, UNIT_ID, {'state': UnitStates.DELETING_SERVERS.value}),
    (DbCollections.SERVER, f'{FIRST_ID}-kali', {'state': ServerStates.STOPPED.value}),
    (DbCollections.SERVER, PROXY_NAME, {'state': ServerStates.STOPPED.value}),
    (DbCollections.SERVER, f'{FIRST_ID}-kali', {'parent_id': SECOND_ID}),
    (DbCollections.SERVER, f'{FIRST_ID}-kali', {'nics': [{'internal_ip': '10.21.0.30'}]}),
    (DbCollections.SERVER, f'{FIRST_ID}-kali', {'nics': [{'internal_ip': '127.0.0.1'}]}),
    (DbCollections.WORKOUT, FIRST_ID, {'expires': NOW - 1}),
    (DbCollections.WORKOUT, FIRST_ID, {'shutoff_timestamp': NOW - 1}),
    (DbCollections.UNIT, UNIT_ID, {'workspace_settings': {'expires': NOW - 1}}),
    (DbCollections.UNIT, UNIT_ID, {'workspace_settings': {'expires': None}}),
])
def test_shared_rejects_inactive_expired_foreign_or_outside_targets(context, collection, identifier, change):
    context.db.records[collection][identifier].update(change)
    with pytest.raises(GuacamoleInvalidSession):
        context.session().get_connection_from_server('0')
    assert not context.requests


def test_shared_session_expiry_is_bounded_by_lab_and_workout(context):
    context.db.records[DbCollections.UNIT][UNIT_ID]['workspace_settings']['expires'] = NOW + 50
    context.db.records[DbCollections.WORKOUT][FIRST_ID]['expires'] = NOW + 30
    context.session().get_connection_from_server('0')
    assert context.payloads[-1]['expires'] == (NOW + 30) * 1000


@pytest.mark.parametrize('expiry', [NOW, NOW - 0.001, float('nan'), float('inf'), True, '2000'])
def test_shared_rejects_expiry_boundary_and_nonfinite_or_untyped_timestamps(context, expiry):
    context.db.records[DbCollections.WORKOUT][FIRST_ID]['expires'] = expiry
    with pytest.raises(GuacamoleInvalidSession):
        context.session().get_connection_from_server('0')
    assert not context.requests


def test_shared_shutdown_deadline_takes_precedence_over_credential_window(context):
    # Apache 1.6.0 UserDataService applies JSON expiry to connection directory
    # lookups, blocking new connections. It does not forcibly close a tunnel
    # already connected to its own VM; stopping/deleting that VM closes it.
    context.db.records[DbCollections.WORKOUT][FIRST_ID]['shutoff_timestamp'] = NOW + 1
    context.session().get_connection_from_server('0')
    assert context.payloads[-1]['expires'] == (NOW + 1) * 1000
    assert api_module.SHARED_CREDENTIAL_TTL_SECONDS == 120


@pytest.mark.parametrize('index', ['nope', None, '100'])
def test_shared_invalid_server_index_cannot_create_session(context, index):
    with pytest.raises((BadRequest, GuacamoleServerNotFound)):
        context.session().get_connection_from_server(index)
    assert not context.requests


@pytest.mark.parametrize('result', [[], {'authToken': None}, {'authToken': ''}])
def test_shared_invalid_upstream_response_does_not_return_credentials(context, monkeypatch, result):
    monkeypatch.setattr(api_module.requests, 'post', lambda *_args, **_kwargs:
                        SimpleNamespace(status_code=200, json=lambda: result))
    with pytest.raises(GuacamoleInvalidSession) as error:
        context.session().get_connection_from_server('0')
    assert str(result) not in error.value.message


def test_shared_upstream_errors_do_not_disclose_signed_credentials(context, monkeypatch):
    def post(*args, **kwargs):
        raise api_module.requests.ConnectionError('unexpected-secret-body ' + kwargs['data']['data'])

    monkeypatch.setattr(api_module.requests, 'post', post)
    with pytest.raises(GuacamoleInvalidSession) as error:
        context.session().get_connection_from_server('0')
    assert error.value.message == 'The shared display proxy is temporarily unavailable'


def test_anonymous_workout_capability_route_returns_uncached_scoped_session(context):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from routers.guacamole import guacamole_router

    app = FastAPI()
    app.state.cloud_env = SimpleNamespace(get_env=lambda: {})
    app.include_router(guacamole_router)
    response = TestClient(app).get(f'/guacamole/{FIRST_ID}/servers/0/')
    assert response.status_code == 200
    assert response.headers['cache-control'] == 'no-store'
    data = response.json()['data']
    assert data['token'] == 'session-1'
    assert data['url'] == f'https://{UNIT_ID}-display.labs.example/guacamole'
    assert 'vm-password' not in response.text and KEY.hex() not in response.text


def test_route_errors_are_uncached_and_never_disclose_provider_response(context, monkeypatch, caplog):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from routers.guacamole import guacamole_router

    def post(*args, **kwargs):
        raise api_module.requests.ConnectionError('upstream-secret ' + kwargs['data']['data'])

    monkeypatch.setattr(api_module.requests, 'post', post)
    app = FastAPI()
    app.state.cloud_env = SimpleNamespace(get_env=lambda: {})
    app.include_router(guacamole_router)
    response = TestClient(app).get(f'/guacamole/{FIRST_ID}/servers/0/')
    assert response.status_code == 503
    assert response.headers['cache-control'] == 'no-store'
    assert response.json() == {'detail': 'The shared display proxy is temporarily unavailable'}
    assert 'upstream-secret' not in response.text + caplog.text


def test_solo_keeps_mysql_authentication_and_own_hostname(context, monkeypatch):
    context.db.records[DbCollections.UNIT][UNIT_ID].update({'unit_type': 'solo', 'servers': []})
    workout = context.db.records[DbCollections.WORKOUT][FIRST_ID]
    workout.pop('guacamole_auth')
    workout.update({'servers': [{'name': 'kali', 'hostname': 'solo-vm.labs.example',
                                'human_interaction': [{'protocol': 'rdp'}]}],
                    'proxy_connections': [{'server': 'kali', 'username': 'agoge1',
                                           'password': 'solo-proxy-password'}]})
    calls = []

    def session(*args):
        calls.append(args)
        return SimpleNamespace(token='solo-session')

    monkeypatch.setattr(api_module.guacamole, 'session', session)
    response = context.session().get_connection_from_server('0')
    assert calls == [(f'https://{FIRST_ID}-display.labs.example/guacamole',
                      'mysql', 'agoge1', 'solo-proxy-password')]
    assert response['token'] == 'solo-session'
    assert response['url'] == f'https://{FIRST_ID}-display.labs.example/guacamole'
    assert not context.requests and not context.secret_reads
