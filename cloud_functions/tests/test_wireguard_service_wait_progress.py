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


def test_local_startup_can_finish_after_five_minutes_without_a_pi(waiter):
    value, clock = waiter
    value.env_dict = {'_local_debug_wireguard_startup_timeout_seconds': 900}
    service = value._wireguard_provisioning.return_value
    service.get_lease.side_effect = lambda _: lease(
        service_ready=clock.elapsed >= 600, tunnel_ready=False,
        latest_handshake=0, health_timestamp=clock.now if clock.elapsed >= 600 else None)

    value._wait_for_wireguard_service()

    assert clock.elapsed == 600
    assert len(clock.sleeps) == 120
    assert value.logger.info.call_args.kwargs['status'] == 'ready'
    assert value.logger.info.call_args.kwargs['tunnel_ready'] is False
    assert value.logger.info.call_args.kwargs['timeout_seconds'] == 900
    value.logger.warning.assert_not_called()


def test_local_wait_checks_ready_at_the_end_of_its_full_startup_grace(waiter):
    value, clock = waiter
    value.env_dict = {'_local_debug_wireguard_startup_timeout_seconds': 65}
    value._wireguard_provisioning.return_value.get_lease.side_effect = lambda _: lease(
        service_ready=clock.elapsed == 65, health_timestamp=clock.now)

    value._wait_for_wireguard_service()

    assert clock.elapsed == 65
    assert value.logger.info.call_args.kwargs['status'] == 'ready'


def test_local_timeout_still_requires_guest_health_and_names_the_configured_limit(waiter):
    value, clock = waiter
    value.env_dict = {'_local_debug_wireguard_startup_timeout_seconds': 65}
    value._wireguard_provisioning.return_value.get_lease.return_value = lease()

    with pytest.raises(TimeoutError, match='within 65 seconds') as error:
        value._wait_for_wireguard_service()

    assert clock.elapsed == 65
    assert 'remote-peer connection is not required' in str(error.value)
    assert value.logger.warning.call_args.kwargs['status'] == 'awaiting_first_health_report'


def test_poll_request_latency_uses_up_local_startup_grace(waiter):
    value, clock = waiter
    value.env_dict = {'_local_debug_wireguard_startup_timeout_seconds': 60}

    def slow_read(_):
        clock.now += 40
        clock.elapsed += 40
        return lease()

    value._wireguard_provisioning.return_value.get_lease.side_effect = slow_read
    with pytest.raises(TimeoutError):
        value._wait_for_wireguard_service()

    assert value._wireguard_provisioning.return_value.get_lease.call_count == 2
    assert clock.sleeps == [5]
    assert value.logger.warning.call_args.kwargs['elapsed_seconds'] == 85


def test_deployed_wait_retains_five_minute_policy(waiter):
    value, clock = waiter
    value.env_dict = {'project': 'test-dev-787001'}
    value._wireguard_provisioning.return_value.get_lease.return_value = lease()

    with pytest.raises(TimeoutError, match='within 300 seconds'):
        value._wait_for_wireguard_service()

    assert value._wireguard_provisioning.return_value.get_lease.call_count == 60
    assert clock.sleeps == [5] * 59
    assert value.logger.warning.call_args.kwargs['timeout_seconds'] == 300


@pytest.mark.parametrize('timeout', [True, 0, 59, 3601, 900.0, '900'])
def test_invalid_internal_timeout_cannot_create_an_unbounded_wait(waiter, timeout):
    value, clock = waiter
    value.env_dict = {'_local_debug_wireguard_startup_timeout_seconds': timeout}

    with pytest.raises(module.BadRequest):
        value._wait_for_wireguard_service()

    value._wireguard_provisioning.return_value.get_lease.assert_not_called()
    assert clock.sleeps == []


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
