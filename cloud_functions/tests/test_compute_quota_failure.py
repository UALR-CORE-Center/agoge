from unittest.mock import Mock

import pytest
from google.api_core.exceptions import Forbidden, TooManyRequests
from google.cloud.compute_v1 import Error, ErrorDetails, Errors, Network, Operation, QuotaExceededInfo
from google.rpc import error_details_pb2

from common.constants.google import OperationType
from common.exceptions import BaseAgogeException, ResourceExhausted
from common.utilities.gcp.compute.compute_networks import ComputeNetworksAPI
from common.utilities.gcp.compute.compute_operations import ComputeOperationsAPI
from common.utilities.gcp.compute.quota_failure import ComputeQuotaFailure


SAMPLE_MESSAGE = "QUOTA_EXCEEDED: Quota 'NETWORKS' exceeded.  Limit: 30.0 globally."


@pytest.fixture
def api():
    api = ComputeNetworksAPI('hosting-project', 'us-central1', 'us-central1-a')
    api.networks_client = Mock()
    api.cloud_ops_mgr.client = Mock()
    return api


def create_network(api):
    return api.create('lab-network', network_resource=Network(name='lab-network'), project='target-project')


@pytest.mark.parametrize(
    'operation_error',
    [
        Errors(message=SAMPLE_MESSAGE),
        Errors(code='QUOTA_EXCEEDED', error_details=[ErrorDetails(quota_info=QuotaExceededInfo(
            metric_name='compute.googleapis.com/networks', limit_name='NETWORKS-per-project',
            limit=30, dimensions={'location': 'global', 'unrelated': 'secret'},
        ))]),
    ],
    ids=['observed-log-format', 'structured-without-http-error-message'],
)
def test_done_operation_reports_quota_from_target_project(api, operation_error):
    api.networks_client.insert.return_value = Operation(name='operation-test')
    client = api.cloud_ops_mgr.client.return_value
    client.wait.return_value = Operation(status=Operation.Status.DONE, error=Error(errors=[operation_error]))

    with pytest.raises(ResourceExhausted) as caught:
        create_network(api)

    failure = caught.value
    assert isinstance(failure, ComputeQuotaFailure)
    assert (failure.reason, failure.category, failure.metric, failure.scope, failure.limit) == (
        'QUOTA_EXCEEDED', 'allocation', 'NETWORKS', 'global', 30,
    )
    assert (failure.project, failure.operation_id, failure.resource_type, failure.resource, failure.action) == (
        'target-project', 'operation-test', 'NETWORKS', 'lab-network', 'insert',
    )
    assert client.wait.call_args.kwargs['request'].project == 'target-project'
    assert 'secret' not in str(failure.as_dict())


def test_immediate_forbidden_preserves_typed_quota_and_discards_raw_message(api):
    error = Forbidden('private payload', error_info=error_details_pb2.ErrorInfo(
        reason='QUOTA_EXCEEDED', metadata={
            'quota_metric': 'compute.googleapis.com/networks',
            'quota_limit': 'NETWORKS-per-project',
            'quota_limit_value': '30',
            'quota_location': 'global',
        },
    ))
    api.networks_client.insert.side_effect = error

    with pytest.raises(ComputeQuotaFailure) as caught:
        create_network(api)

    failure = caught.value
    assert (failure.metric, failure.limit_name, failure.limit, failure.scope, failure.category) == (
        'NETWORKS', 'NETWORKS-per-project', 30, 'global', 'allocation',
    )
    assert failure.project == 'target-project'
    assert failure.__cause__ is error
    assert 'private payload' not in str(failure)
    assert 'private payload' not in str(failure.as_dict())


def test_immediate_concurrent_operation_rate_limit_is_not_allocation_quota(api):
    api.networks_client.insert.side_effect = Forbidden(
        'Rate Limit Exceeded',
        errors=[{'reason': 'rateLimitExceeded'}],
        details=[{'reason': 'CONCURRENT_OPERATIONS_QUOTA_EXCEEDED', 'metadata': {
            'quotaMetric': 'compute.googleapis.com/global_concurrent_operations',
            'quotaLimit': 'GlobalConcurrentOperationsPerProject',
            'location': 'global',
        }}],
    )

    with pytest.raises(ComputeQuotaFailure) as caught:
        create_network(api)

    failure = caught.value
    assert failure.category == 'rate'
    assert failure.reason == 'CONCURRENT_OPERATIONS_QUOTA_EXCEEDED'
    assert failure.metric == 'compute.googleapis.com/global_concurrent_operations'
    assert failure.scope == 'global'


def test_http_status_without_provider_evidence_does_not_identify_allocation_quota(api):
    api.networks_client.insert.side_effect = Forbidden('Permission denied')
    with pytest.raises(BaseAgogeException) as caught:
        create_network(api)
    assert not isinstance(caught.value, ComputeQuotaFailure)

    api.networks_client.insert.side_effect = TooManyRequests('Too many requests')
    with pytest.raises(ComputeQuotaFailure) as caught:
        create_network(api)
    assert caught.value.category == 'unknown'
    assert caught.value.metric is None


def test_done_operation_keeps_stockout_code_for_zone_fallback():
    operations = ComputeOperationsAPI('hosting-project', 'us-central1', 'us-central1-a')
    operations.client = Mock()
    operations.client.return_value.wait.return_value = Operation(
        status=Operation.Status.DONE, error=Error(errors=[Errors(code='ZONE_RESOURCE_POOL_EXHAUSTED')]),
    )
    with pytest.raises(RuntimeError, match='ZONE_RESOURCE_POOL_EXHAUSTED'):
        operations.wait('operation-test')


def test_nonterminal_compute_operations_stop_at_deadline(monkeypatch):
    operations = ComputeOperationsAPI('hosting-project', 'us-central1', 'us-central1-a')
    operations.client = Mock()
    client = operations.client.return_value
    client.wait.return_value = Operation(status=Operation.Status.RUNNING)
    now = 0

    def sleep(seconds):
        nonlocal now
        now += seconds

    monkeypatch.setattr('common.utilities.gcp.compute.compute_operations.time.monotonic', lambda: now)
    monkeypatch.setattr('common.utilities.gcp.compute.compute_operations.time.sleep', sleep)

    assert operations.wait('operation-test', type_=OperationType.GLOBAL, wait_seconds=2) is False
    assert [call.kwargs['timeout'] for call in client.wait.call_args_list] == [2, 1]
