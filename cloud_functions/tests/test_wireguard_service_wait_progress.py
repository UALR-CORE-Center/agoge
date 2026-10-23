"""Observable guest readiness waits without cloud access or real sleeps."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from cloud_fn_utilities.course_objects.compute import lab_server_manager as module
from common.models.wireguard_provisioning import WireGuardLeaseModel


@pytest.fixture
def waiter(monkeypatch):
    clock = SimpleNamespace(now=1000.0, elapsed=0.0, sleeps=[])

    def sleep(seconds):
        clock.sleeps.append(seconds)
        clock.now += seconds
        clock.elapsed += seconds

    monkeypatch.setattr(module, 'time', SimpleNamespace(
        time=lambda: clock.now, monotonic=lambda: clock.elapsed, sleep=sleep))
    value = object.__new__(module.LabServerManager)
    value.parent_build_id = 'abcdefghij'
    value.server_name = 'abcdefghij-wireguard'
    value.logger = Mock()
    value._wireguard_provisioning = Mock(return_value=Mock())
    return value, clock


def lease(**changes):
    return WireGuardLeaseModel(**{
        'unit_id': 'abcdefghij', 'kit_id': 'remote-lab-01', 'device_id': 'device-01',
        'endpoint_id': '10000', 'equipment_subnet': '192.168.50.0/24',
        'student_subnets': ['10.20.0.0/24'], 'gateway_public_key': 'public-gateway-key',
        'peer_public_key': 'public-peer-key', 'secret_version_name': 'private-secret-reference',
        'boot_id': 'private-boot-nonce', 'expires': 2000.0, 'health_timestamp': None,
        **changes,
    })


def test_fresh_service_reports_success_without_a_remote_handshake(waiter):
    value, clock = waiter
    value._wireguard_provisioning.return_value.get_lease.return_value = lease(
        service_ready=True, tunnel_ready=False, health_timestamp=1000.0)

    value._wait_for_wireguard_service()

    assert clock.sleeps == []
    assert value.logger.info.call_args.kwargs['status'] == 'ready'
    assert value.logger.info.call_args.kwargs['service_ready'] is True
    assert value.logger.info.call_args.kwargs['tunnel_ready'] is False
    value.logger.warning.assert_not_called()


def test_wait_reports_periodic_progress_and_keeps_existing_poll_policy(waiter):
    value, clock = waiter
    value._WIREGUARD_READY_ATTEMPTS = 13
    service = value._wireguard_provisioning.return_value
    service.get_lease.side_effect = [lease()] * 12 + [lease(
        service_ready=True, health_timestamp=1060.0)]

    value._wait_for_wireguard_service()

    assert clock.sleeps == [5] * 12
    assert service.get_lease.call_count == 13
    progress = [call.kwargs for call in value.logger.info.call_args_list
                if call.args[0].startswith('Still waiting')]
    assert [event['attempt'] for event in progress] == [1, 7]
    assert [event['elapsed_seconds'] for event in progress] == [0.0, 30.0]
    assert all(event['status'] == 'awaiting_first_health_report' for event in progress)
    assert value.logger.info.call_args.kwargs['elapsed_seconds'] == 60.0
    assert value.logger.info.call_args.kwargs['status'] == 'ready'


@pytest.mark.parametrize('changes,status', [
    ({}, 'awaiting_first_health_report'),
    ({'health_timestamp': 990.0, 'health_error': 'wireguard_service_unready'}, 'gateway_service_unready'),
    ({'service_ready': True, 'health_timestamp': 800.0}, 'stale_health_report'),
    ({'expires': 999.0}, 'lease_expired'),
    ({'status': 'released'}, 'lease_released'),
    ({'service_ready': True, 'health_timestamp': 1010.0}, 'health_timestamp_in_future'),
])
def test_timeout_distinguishes_missing_unready_stale_and_inactive_health(waiter, changes, status):
    value, clock = waiter
    value._WIREGUARD_READY_ATTEMPTS = 2
    value._wireguard_provisioning.return_value.get_lease.return_value = lease(**changes)

    with pytest.raises(TimeoutError) as error:
        value._wait_for_wireguard_service()

    assert clock.sleeps == [5]
    assert 'debug_lab.py status --unit-id abcdefghij' in str(error.value)
    assert 'HTTPS health endpoint' in str(error.value)
    assert value.logger.warning.call_args.kwargs['status'] == status
    assert value.logger.warning.call_args.kwargs['attempt'] == 2
    assert value.logger.warning.call_args.kwargs['elapsed_seconds'] == 5.0


@pytest.mark.parametrize('error,expected', [
    ('wireguard_service_unready', 'wireguard_service_unready'),
    ('bootstrap_failed', 'bootstrap_failed'),
    ('private-callback-token', 'other_error'),
])
def test_progress_logs_only_public_metadata_and_predefined_error_codes(waiter, error, expected):
    value, _ = waiter
    value._WIREGUARD_READY_ATTEMPTS = 1
    value._wireguard_provisioning.return_value.get_lease.return_value = lease(
        health_timestamp=990.0, health_error=error)

    with pytest.raises(TimeoutError):
        value._wait_for_wireguard_service()

    output = str(value.logger.mock_calls)
    assert 'private-secret-reference' not in output
    assert 'private-boot-nonce' not in output
    assert 'public-gateway-key' not in output and 'public-peer-key' not in output
    assert 'private-callback-token' not in output
    assert value.logger.warning.call_args.kwargs['health_error'] == expected
    assert value.logger.warning.call_args.kwargs['health_age_seconds'] == 10.0
