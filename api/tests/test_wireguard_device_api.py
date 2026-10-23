"""HTTP authentication boundaries without loading the deployed app or cloud clients."""
import base64
from types import SimpleNamespace
from unittest.mock import MagicMock

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
import pytest

from common.exceptions import BadRequest, NotFound, NotReady, Unauthorized
from common.models.wireguard import WireGuardEndpointRecordModel
from dependencies import admin_required, get_cloud_env, teacher_required
from routers import wireguard


@pytest.fixture(scope='session', autouse=True)
def check_test_project_id():
    # This isolated router never creates a GCP client or uses the deployed app.
    # Override the integration-suite credential guard for this module only.
    yield


@pytest.fixture
def http(monkeypatch):
    app = FastAPI()
    app.include_router(wireguard.wireguard_router)
    app.dependency_overrides[get_cloud_env] = lambda: {'project': 'test-project'}
    service = MagicMock()
    registry = MagicMock()
    monkeypatch.setattr(wireguard, 'WireGuardProvisioningService', lambda *a, **k: service)
    monkeypatch.setattr(wireguard, 'WireGuardEndpointRegistry', lambda *a, **k: registry)
    def instructor_auth():
        raise HTTPException(403, 'Instructor authorization required')
    def admin_auth():
        raise HTTPException(403, 'Administrator authorization required')
    app.dependency_overrides[teacher_required] = instructor_auth
    app.dependency_overrides[admin_required] = admin_auth
    return SimpleNamespace(app=app, client=TestClient(app), service=service, registry=registry)


def endpoint():
    return WireGuardEndpointRecordModel(id='10000', hostname='wg10000.example.edu.',
        server_name='abcdefghij-wireguard', unit_id='abcdefghij', status='active',
        created_timestamp=10, updated_timestamp=20)


def enrollment():
    return {'id': 'kit-one', 'device_id': 'pi-one', 'equipment_subnet': '172.30.0.0/24',
            'peer_public_key': base64.b64encode(b'1' * 32).decode(),
            'authorized_instructors': ['teacher@example.edu']}


def test_instructor_and_admin_routes_require_their_own_authorization(http):
    assert http.client.get('/wireguard/kits/').status_code == 403
    assert http.client.post('/wireguard/kits/', json=enrollment()).status_code == 403
    assert http.client.post('/wireguard/labs/', json={'kit_id': 'kit-one'}).status_code == 403
    http.service.list_kits.assert_not_called()
    http.service.enroll.assert_not_called()


def test_teacher_can_list_kits_but_cannot_enroll(http):
    user = SimpleNamespace(is_admin=False, email='teacher@example.edu')
    http.app.dependency_overrides[teacher_required] = lambda: user
    http.service.list_kits.return_value = [{'id': 'kit-one', 'equipment_subnet': '172.30.0.0/24'}]
    response = http.client.get('/wireguard/kits/')
    assert response.status_code == 200
    assert response.json()['data']['items'][0]['id'] == 'kit-one'
    assert 'token' not in response.text
    assert http.client.post('/wireguard/kits/', json=enrollment()).status_code == 403


def test_admin_receives_one_time_token_without_caching(http):
    user = SimpleNamespace(is_admin=True, email='admin@example.edu')
    http.app.dependency_overrides[admin_required] = lambda: user
    http.service.enroll.return_value = {'kit': enrollment(), 'enrollment_token': 'one-time-token'}
    response = http.client.post('/wireguard/kits/', json=enrollment())
    assert response.status_code == 201
    assert response.headers['cache-control'] == 'no-store'
    assert response.json()['data']['enrollment_token'] == 'one-time-token'
    http.service.enroll.assert_called_once()


def test_device_endpoints_do_not_accept_missing_bearer(http):
    response = http.client.get('/wireguard/kits/kit-one/configuration/')
    assert response.status_code == 401
    http.service.pi_configuration.assert_not_called()
    response = http.client.post('/wireguard/gateways/abcdefghij/health/', json={
        'boot_id': 'boot-nonce-long-enough', 'service_ready': True})
    assert response.status_code == 401
    http.service.report_health.assert_not_called()


def test_pi_bearer_is_verified_by_kit_service_without_firebase_login(http):
    http.service.pi_configuration.return_value = {'unit_id': 'abcdefghij', 'gateway_public_key': 'PUBLIC'}
    response = http.client.get('/wireguard/kits/kit-one/configuration/', headers={'Authorization': 'Bearer enrollment-token'})
    assert response.status_code == 200
    assert response.headers['cache-control'] == 'no-store'
    http.service.pi_configuration.assert_called_once_with('kit-one', 'enrollment-token')
    assert 'enrollment-token' not in response.text


@pytest.mark.parametrize('error,status', [(Unauthorized('Invalid kit credentials'), 401),
    (NotReady('The assigned gateway is stopped, expired, or not ready'), 409)])
def test_pi_auth_and_lifecycle_failures_map_to_http_without_credentials(http, error, status):
    http.service.pi_configuration.side_effect = error
    response = http.client.get('/wireguard/kits/kit-one/configuration/', headers={'Authorization': 'Bearer secret-token'})
    assert response.status_code == status
    assert 'secret-token' not in response.text


@pytest.mark.parametrize('error,status', [(Unauthorized('Invalid gateway credentials'), 401),
    (NotReady('Gateway lease or boot is no longer current'), 409),
    (BadRequest('Gateway handshake timestamp is in the future'), 400)])
def test_gateway_health_auth_and_replay_failures_map_without_leaks(http, error, status):
    http.service.report_health.side_effect = error
    response = http.client.post('/wireguard/gateways/abcdefghij/health/',
        headers={'Authorization': 'Bearer callback-secret'},
        json={'boot_id': 'boot-nonce-long-enough', 'service_ready': True})
    assert response.status_code == status
    assert 'callback-secret' not in response.text
    http.service.report_health.assert_called_once()


def test_health_rejects_unstructured_error_output(http):
    response = http.client.post('/wireguard/gateways/abcdefghij/health/',
        headers={'Authorization': 'Bearer callback-secret'},
        json={'boot_id': 'boot-nonce-long-enough', 'service_ready': False, 'error': 'PrivateKey=secret/key'})
    assert response.status_code == 422
    http.service.report_health.assert_not_called()


def test_public_resolver_never_returns_stale_managed_readiness(http):
    http.registry.get.return_value = endpoint()
    http.service.get_lease.return_value = SimpleNamespace(is_ready=lambda now: False)
    response = http.client.get('/wireguard/endpoints/10000/')
    assert response.status_code == 404
    assert response.headers['cache-control'] == 'no-store'
    assert 'unit_id' not in response.text


def test_public_ready_resolver_is_not_cached_and_exposes_no_private_record(http):
    http.registry.get.return_value = endpoint()
    http.service.get_lease.return_value = SimpleNamespace(is_ready=lambda now: True)
    response = http.client.get('/wireguard/endpoints/10000/')
    assert response.status_code == 200
    assert response.headers['cache-control'] == 'no-store'
    assert set(response.json()['data']) == {'id', 'hostname', 'port', 'status'}


def test_legacy_unmanaged_resolver_remains_compatible(http):
    http.registry.get.return_value = endpoint()
    http.service.get_lease.side_effect = NotFound('WireGuard lease not found')
    assert http.client.get('/wireguard/endpoints/10000/').status_code == 200


def test_instructor_can_create_lab_through_authorized_route(http, monkeypatch):
    from core import wireguard_lab
    manager = MagicMock()
    manager.build.return_value = 'abcdefghij'
    monkeypatch.setattr(wireguard_lab, 'WireGuardLab', lambda **kwargs: manager)
    user = SimpleNamespace(is_admin=False, email='teacher@example.edu')
    http.app.dependency_overrides[teacher_required] = lambda: user
    body = {'kit_id': 'kit-one', 'expires': '2030-01-01T00:00:00Z'}
    response = http.client.post('/wireguard/labs/', json=body)
    assert response.status_code == 201
    assert response.json()['data']['build_id'] == 'abcdefghij'
    manager.build.assert_called_once_with(requester=user, data=body)


def test_remote_peer_inventory_and_enrollment_preserve_authorization_boundaries(http):
    assert http.client.get('/wireguard/remote-peers/').status_code == 403
    body = enrollment()
    body['remote_network_cidr'] = body.pop('equipment_subnet')
    assert http.client.post('/wireguard/remote-peers/', json=body).status_code == 403
    http.service.list_remote_peers.assert_not_called()
    http.service.enroll_remote_peer.assert_not_called()


def test_remote_peer_inventory_exposes_private_lan_with_canonical_name(http):
    from common.models.wireguard_provisioning import WireGuardRemotePeerModel
    http.app.dependency_overrides[teacher_required] = lambda: SimpleNamespace(is_admin=False)
    http.service.list_remote_peers.return_value = [WireGuardRemotePeerModel(**enrollment())]
    response = http.client.get('/wireguard/remote-peers/')
    assert response.status_code == 200
    peer = response.json()['data']['items'][0]
    assert peer['remote_network_cidr'] == '172.30.0.0/24'
    assert 'equipment_subnet' not in peer and 'token_digest' not in peer


def test_admin_remote_peer_enrollment_uses_canonical_response_and_one_time_token(http):
    from common.models.wireguard_provisioning import WireGuardRemotePeerModel
    http.app.dependency_overrides[admin_required] = lambda: SimpleNamespace(is_admin=True)
    http.service.enroll_remote_peer.return_value = {
        'remote_peer': WireGuardRemotePeerModel(**enrollment()), 'enrollment_token': 'one-time-token'}
    body = enrollment()
    body['remote_network_cidr'] = body.pop('equipment_subnet')
    response = http.client.post('/wireguard/remote-peers/', json=body)
    assert response.status_code == 201
    assert response.headers['cache-control'] == 'no-store'
    assert response.json()['data']['remote_peer']['remote_network_cidr'] == '172.30.0.0/24'
    assert response.json()['data']['enrollment_token'] == 'one-time-token'
    http.service.enroll_remote_peer.assert_called_once()


def test_remote_peer_http_conflicting_lan_aliases_are_rejected(http):
    http.app.dependency_overrides[admin_required] = lambda: SimpleNamespace(is_admin=True)
    response = http.client.post('/wireguard/remote-peers/', json={
        **enrollment(), 'remote_network_cidr': '192.168.1.0/24'})
    assert response.status_code == 422
    http.service.enroll_remote_peer.assert_not_called()
