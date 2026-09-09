"""Cloud orchestration tests; all cloud requests and interactive input are mocked."""

from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import MagicMock

import httplib2
import pytest
from googleapiclient.errors import HttpError

from cloud_deployment.operations.app_install_updates import shared_load_balancer as module
from cloud_deployment.operations.app_install_updates.shared_load_balancer import (
    COMPUTE_ROOT,
    SharedLoadBalancer,
)
from cloud_deployment.operations.app_install_updates.shared_routing import merge_tenant_routes


TENANT = 'test-dev-787001'
PARENT = 'agoge-shared-resources'
REGION = 'us-central1'
HOSTS = {'react': 'app.agoge-labs.com', 'api': 'api.agoge-labs.com'}
BACKENDS = {
    host: f'projects/{TENANT}/global/backendServices/{TENANT}-{role}'
    for role, host in HOSTS.items()
}


def http_error(status):
    return HttpError(httplib2.Response({'status': str(status)}), b'{"error":{"message":"test failure"}}')


def request(value=None, *, error=None):
    result = MagicMock()
    result.execute.return_value = value
    result.execute.side_effect = error
    return result


def ready_service():
    return {
        'generation': '2',
        'observedGeneration': '2',
        'reconciling': False,
        'terminalCondition': {'state': 'CONDITION_SUCCEEDED'},
        'latestCreatedRevision': 'projects/test/locations/us-central1/services/app/revisions/app-00002',
        'latestReadyRevision': 'projects/test/locations/us-central1/services/app/revisions/app-00002',
        'trafficStatuses': [{'revision': 'app-00002', 'percent': 100}],
    }


def ready_function():
    return {
        'state': 'ACTIVE',
        'environment': 'GEN_2',
        'eventTrigger': {
            'eventType': 'google.cloud.pubsub.topic.v1.messagePublished',
            'pubsubTopic': f'projects/{TENANT}/topics/agoge',
        },
    }


def existing_map():
    return {
        'name': 'agoge-shared-lb',
        'fingerprint': 'original-fingerprint',
        'defaultService': f'projects/{PARENT}/global/backendBuckets/default-404-backend',
        'hostRules': [
            {'hosts': [host], 'pathMatcher': f'{role}-matcher'} for role, host in HOSTS.items()
        ],
        'pathMatchers': [
            {
                'name': f'{role}-matcher',
                'defaultService': f'projects/{PARENT}/global/backendBuckets/default-404-backend',
                'pathRules': [{
                    'paths': ['/ualr/*'],
                    'service': f'projects/agoge-ualr/global/backendServices/agoge-ualr-{role}',
                    'routeAction': {'urlRewrite': {'pathPrefixRewrite': '/'}},
                }],
            }
            for role in HOSTS
        ],
    }


@pytest.fixture
def router(monkeypatch):
    result = object.__new__(SharedLoadBalancer)
    result.project = TENANT
    result.parent = PARENT
    result.region = REGION
    result.path = '/test-dev'
    result.hosts = HOSTS.copy()
    result.services = {'react': 'agoge-react', 'api': 'agoge-api'}
    result.function = 'agoge'
    result.config = {}
    result.url_map = 'agoge-shared-lb'
    result.env = SimpleNamespace(
        project=TENANT, parent_project=PARENT, region=REGION,
        parent_dns_suffix='.agoge-labs.com', project_path='test-dev', db=MagicMock(),
    )
    result.compute = MagicMock()
    result.cloud_run = MagicMock()
    result.functions = MagicMock()
    result.cloud_run.projects().locations().services().get.return_value = request(ready_service())
    result.functions.projects().locations().functions().get.return_value = request(ready_function())
    result.compute.urlMaps().get.return_value = request(existing_map())
    result.compute.urlMaps().validate.return_value = request({
        'result': {'loadSucceeded': True, 'testPassed': True},
    })
    result.compute.urlMaps().update.return_value = request({'name': 'update-map', 'status': 'DONE'})
    result.compute.backendServices().get.return_value = request(error=http_error(404))
    result.compute.regionNetworkEndpointGroups().get.return_value = request(error=http_error(404))
    result.compute.regionNetworkEndpointGroups().insert.return_value = request({'name': 'create-neg', 'status': 'DONE'})
    result.compute.backendServices().insert.return_value = request({'name': 'create-backend', 'status': 'DONE'})
    clients = {'compute': result.compute, 'run': result.cloud_run, 'cloudfunctions': result.functions}
    monkeypatch.setattr(module.discovery, 'build', lambda api, version, **kwargs: clients[api])
    # Unexpected prompts must never hang or silently approve these tests.
    monkeypatch.setattr('builtins.input', lambda prompt: pytest.fail(f'Unexpected prompt: {prompt}'))
    return result


@pytest.mark.parametrize('changes', [
    {'reconciling': True},
    {'terminalCondition': {'state': 'CONDITION_FAILED'}},
    {'terminalCondition': {'state': 'CONDITION_PENDING'}},
    {'observedGeneration': '1'},
    {'generation': None, 'observedGeneration': None},
    {'latestCreatedRevision': 'app-00003'},
    {'latestReadyRevision': None},
    {'trafficStatuses': [{'revision': 'app-00001', 'percent': 100}]},
    {'trafficStatuses': [{'revision': 'app-00002', 'percent': 80}, {'revision': 'app-00001', 'percent': 20}]},
    {'trafficStatuses': []},
])
def test_cloud_run_readiness_rejects_stale_failed_or_partial_deployments(changes):
    service = ready_service()
    service.update(changes)
    assert SharedLoadBalancer._run_service_ready(service) is False


def test_cloud_run_readiness_accepts_observed_generation_and_full_latest_traffic():
    service = ready_service()
    service['observedGeneration'] = 2
    service['trafficStatuses'].append({'revision': 'app-00001', 'percent': 0, 'tag': 'old'})
    assert SharedLoadBalancer._run_service_ready(service) is True
    assert SharedLoadBalancer._run_service_ready(None) is False


def test_ready_checks_explicit_tenant_run_services_and_background_function(router):
    assert router._ready() is True
    assert [call.kwargs['name'] for call in router.cloud_run.projects().locations().services().get.call_args_list] == [
        f'projects/{TENANT}/locations/{REGION}/services/agoge-react',
        f'projects/{TENANT}/locations/{REGION}/services/agoge-api',
    ]
    router.functions.projects().locations().functions().get.assert_called_once_with(
        name=f'projects/{TENANT}/locations/{REGION}/functions/agoge',
    )
    router.compute.urlMaps().update.assert_not_called()


@pytest.mark.parametrize('function', [
    None,
    {**ready_function(), 'state': 'DEPLOYING'},
    {**ready_function(), 'state': 'FAILED'},
    {**ready_function(), 'environment': 'GEN_1'},
    {**ready_function(), 'eventTrigger': {}},
    {**ready_function(), 'eventTrigger': {'pubsubTopic': 'projects/another-project/topics/agoge'}},
])
def test_unready_or_wrong_function_can_defer_without_any_compute_mutations(router, monkeypatch, function):
    router.functions.projects().locations().functions().get.return_value = request(function)
    monkeypatch.setattr('builtins.input', lambda _: '')
    assert router.run() is False
    router.compute.urlMaps().list.assert_not_called()
    router.compute.regionNetworkEndpointGroups().insert.assert_not_called()
    router.compute.backendServices().insert.assert_not_called()
    router.compute.urlMaps().update.assert_not_called()
    router.env.db.update.assert_not_called()


def test_readiness_retry_uses_supplied_resource_names(router, monkeypatch):
    router.cloud_run.projects().locations().services().get.side_effect = [
        request(None), request(None), request(ready_service()), request(ready_service()),
    ]
    router.functions.projects().locations().functions().get.side_effect = [request(None), request(ready_function())]
    replies = iter(['N', 'custom-react', 'custom-api', 'custom-worker'])
    monkeypatch.setattr('builtins.input', lambda _: next(replies))
    assert router._ready() is True
    assert router.services == {'react': 'custom-react', 'api': 'custom-api'}
    assert router.function == 'custom-worker'
    calls = router.cloud_run.projects().locations().services().get.call_args_list
    assert calls[-2].kwargs['name'].endswith('/services/custom-react')
    assert calls[-1].kwargs['name'].endswith('/services/custom-api')
    assert router.functions.projects().locations().functions().get.call_args.kwargs['name'].endswith('/functions/custom-worker')


def test_readiness_retry_rechecks_without_changing_names(router, monkeypatch):
    router.cloud_run.projects().locations().services().get.side_effect = [
        request(None), request(ready_service()), request(ready_service()), request(ready_service()),
    ]
    monkeypatch.setattr('builtins.input', lambda _: 'R')
    assert router._ready() is True
    assert router.services == {'react': 'agoge-react', 'api': 'agoge-api'}


def test_lookup_only_treats_not_found_as_missing(router):
    assert router._get_or_none(request(error=http_error(404))) is None
    with pytest.raises(HttpError):
        router._get_or_none(request(error=http_error(403)))


def test_discovery_reads_all_pages_and_fetches_full_candidate(router):
    maps = router.compute.urlMaps()
    first = request({'items': [{'name': 'unrelated', 'hostRules': []}]})
    second = request({'items': [existing_map()]})
    maps.list.return_value = first
    maps.list_next.side_effect = [second, None]
    assert router._select_url_map() == existing_map()
    maps.list.assert_called_once_with(project=PARENT)
    maps.get.assert_called_once_with(project=PARENT, urlMap='agoge-shared-lb')


def test_discovery_ambiguity_prompts_for_name_and_supports_defer(router, monkeypatch):
    maps = router.compute.urlMaps()
    maps.list.return_value = request({'items': [existing_map(), {**existing_map(), 'name': 'other-map'}]})
    maps.list_next.return_value = None
    monkeypatch.setattr('builtins.input', lambda _: '')
    assert router._select_url_map() is None
    maps.get.assert_not_called()
    monkeypatch.setattr('builtins.input', lambda _: 'chosen-map')
    router._select_url_map()
    maps.get.assert_called_once_with(project=PARENT, urlMap='chosen-map')


def test_separate_app_api_maps_are_rejected_before_parent_mutation(router):
    app_map = existing_map()
    api_map = existing_map()
    app_map['name'] = 'app-only'
    app_map['hostRules'] = [app_map['hostRules'][0]]
    api_map['name'] = 'api-only'
    api_map['hostRules'] = [api_map['hostRules'][1]]
    router.compute.urlMaps().list.return_value = request({'items': [app_map, api_map]})
    router.compute.urlMaps().list_next.return_value = None
    with pytest.raises(ValueError, match='separate URL maps'):
        router._select_url_map()
    router.compute.urlMaps().get.assert_not_called()
    router.compute.urlMaps().update.assert_not_called()


def test_partial_host_match_requires_manual_confirmation(router, monkeypatch):
    partial = existing_map()
    partial['hostRules'] = [partial['hostRules'][0]]
    wildcard = {**existing_map(), 'name': 'wildcard-only', 'hostRules': [{'hosts': ['*'], 'pathMatcher': 'default'}]}
    router.compute.urlMaps().list.return_value = request({'items': [partial, wildcard]})
    router.compute.urlMaps().list_next.return_value = None
    prompts = []

    def confirm(prompt):
        prompts.append(prompt)
        return 'wildcard-only'

    monkeypatch.setattr('builtins.input', confirm)
    router._select_url_map()
    assert len(prompts) == 1
    router.compute.urlMaps().get.assert_called_once_with(project=PARENT, urlMap='wildcard-only')


def test_cached_map_skips_list_but_fetches_current_fingerprint(router):
    router.config['url_map'] = 'cached-map'
    router._select_url_map()
    router.compute.urlMaps().list.assert_not_called()
    router.compute.urlMaps().get.assert_called_once_with(project=PARENT, urlMap='cached-map')


def test_invalid_manual_map_url_cannot_be_used_as_a_resource_name(router):
    router.config['url_map'] = 'https://console.cloud.google.com/net-services/loadbalancing/details/example'
    with pytest.raises(ValueError, match='resource name'):
        router._select_url_map()
    router.compute.urlMaps().get.assert_not_called()


def test_existing_tenant_route_selects_its_custom_backend_name(router):
    current = existing_map()
    current['pathMatchers'][0]['pathRules'].append({
        'paths': ['/test-dev/*'],
        'service': COMPUTE_ROOT + f'projects/{TENANT}/global/backendServices/legacy-custom-react',
        'routeAction': {'urlRewrite': {'pathPrefixRewrite': '/'}},
    })
    assert router._backend_name(current, 'react') == 'legacy-custom-react'
    assert router._backend_name(current, 'api') == TENANT + '-api'


@pytest.mark.parametrize('references', [
    ['projects/someone-else/global/backendServices/existing-react'],
    [f'projects/{TENANT}/global/backendServices/one', f'projects/{TENANT}/global/backendServices/two'],
])
def test_existing_path_cannot_be_taken_over_or_merge_conflicting_backends(router, references):
    current = existing_map()
    for path, reference in zip(['/test-dev', '/test-dev/*'], references):
        current['pathMatchers'][0]['pathRules'].append({'paths': [path], 'service': reference})
    with pytest.raises(ValueError):
        router._backend_name(current, 'react')


def test_existing_custom_backend_and_neg_are_reused_without_rewriting_settings(router):
    group = COMPUTE_ROOT + f'projects/{TENANT}/regions/{REGION}/networkEndpointGroups/original-neg'
    backend = {
        'name': 'legacy-react', 'loadBalancingScheme': 'EXTERNAL_MANAGED',
        'backends': [{'group': group}], 'securityPolicy': 'keep-armor',
        'enableCDN': True, 'logConfig': {'enable': True}, 'fingerprint': 'preserve-me',
    }
    before = deepcopy(backend)
    router.compute.backendServices().get.return_value = request(backend)
    router.compute.regionNetworkEndpointGroups().get.return_value = request({
        'name': 'original-neg', 'networkEndpointType': 'SERVERLESS', 'cloudRun': {'service': 'agoge-react'},
    })
    plan = router._plan_backend('legacy-react', 'agoge-react')
    router._ensure_backend(plan)
    assert plan['neg_name'] == 'original-neg'
    assert plan['reference'].endswith('/legacy-react')
    assert backend == before
    router.compute.backendServices().insert.assert_not_called()
    router.compute.backendServices().patch.assert_not_called()
    router.compute.regionNetworkEndpointGroups().insert.assert_not_called()


@pytest.mark.parametrize('group', [
    COMPUTE_ROOT + f'projects/foreign/regions/{REGION}/networkEndpointGroups/neg',
    COMPUTE_ROOT + f'projects/{TENANT}/regions/us-east1/networkEndpointGroups/neg',
    COMPUTE_ROOT + f'projects/{TENANT}/zones/us-central1-a/instanceGroups/group',
])
def test_backend_other_project_region_or_instance_group_is_rejected(router, group):
    router.compute.backendServices().get.return_value = request({
        'loadBalancingScheme': 'EXTERNAL_MANAGED', 'backends': [{'group': group}],
    })
    with pytest.raises(ValueError, match='different project, region, or endpoint type'):
        router._plan_backend('existing-react', 'agoge-react')
    router.compute.regionNetworkEndpointGroups().get.assert_not_called()


@pytest.mark.parametrize('backend', [
    {'loadBalancingScheme': 'EXTERNAL', 'backends': [{'group': 'existing'}]},
    {'loadBalancingScheme': 'EXTERNAL_MANAGED', 'backends': []},
    {'loadBalancingScheme': 'EXTERNAL_MANAGED', 'backends': [{'group': 'one'}, {'group': 'two'}]},
])
def test_incompatible_or_multi_region_existing_backend_requires_manual_review(router, backend):
    router.compute.backendServices().get.return_value = request(backend)
    with pytest.raises(ValueError, match='one EXTERNAL_MANAGED serverless NEG'):
        router._plan_backend('existing-react', 'agoge-react')
    router.compute.regionNetworkEndpointGroups().get.assert_not_called()


def test_existing_backend_missing_its_neg_is_not_silently_repaired(router):
    group = COMPUTE_ROOT + f'projects/{TENANT}/regions/{REGION}/networkEndpointGroups/missing-neg'
    router.compute.backendServices().get.return_value = request({
        'loadBalancingScheme': 'EXTERNAL_MANAGED', 'backends': [{'group': group}],
    })
    with pytest.raises(ValueError, match='missing NEG'):
        router._plan_backend('existing-react', 'agoge-react')
    router.compute.regionNetworkEndpointGroups().insert.assert_not_called()


@pytest.mark.parametrize('neg', [
    {'networkEndpointType': 'SERVERLESS', 'cloudRun': {'service': 'another-app'}},
    {'networkEndpointType': 'SERVERLESS', 'cloudRun': {'service': 'agoge-react', 'tag': 'old'}},
    {'networkEndpointType': 'SERVERLESS', 'cloudRun': {'service': 'agoge-react', 'urlMask': '<service>'}},
    {'networkEndpointType': 'SERVERLESS', 'cloudFunction': {'function': 'agoge'}},
    {'networkEndpointType': 'GCE_VM_IP_PORT', 'cloudRun': {'service': 'agoge-react'}},
])
def test_existing_neg_must_exclusively_target_expected_service(router, neg):
    router.compute.regionNetworkEndpointGroups().get.return_value = request(neg)
    with pytest.raises(ValueError, match='exclusively target'):
        router._plan_backend('planned-react', 'agoge-react')
    router.compute.regionNetworkEndpointGroups().insert.assert_not_called()
    router.compute.backendServices().insert.assert_not_called()


def test_missing_resources_are_created_in_tenant_with_full_neg_url(router):
    plan = router._plan_backend('planned-react', 'agoge-react')
    router._ensure_backend(plan)
    router.compute.regionNetworkEndpointGroups().insert.assert_called_once_with(
        project=TENANT, region=REGION,
        body={'name': 'planned-react-neg', 'networkEndpointType': 'SERVERLESS', 'cloudRun': {'service': 'agoge-react'}},
    )
    router.compute.backendServices().insert.assert_called_once_with(
        project=TENANT,
        body={
            'name': 'planned-react', 'loadBalancingScheme': 'EXTERNAL_MANAGED',
            'backends': [{'group': COMPUTE_ROOT + f'projects/{TENANT}/regions/{REGION}/networkEndpointGroups/planned-react-neg'}],
        },
    )
    router.compute.urlMaps().update.assert_not_called()


@pytest.mark.parametrize('validation', [
    {},
    {'loadSucceeded': False, 'testPassed': True, 'loadErrors': ['bad map']},
    {'loadSucceeded': True, 'testPassed': False, 'testFailures': [{'path': '/test-dev'}]},
    {'loadSucceeded': True, 'testPassed': True, 'loadErrors': ['bad map']},
    {'loadSucceeded': True, 'testPassed': True, 'testFailures': [{'path': '/test-dev'}]},
])
def test_http_success_with_failed_validation_never_updates_map(router, validation):
    router.compute.urlMaps().validate.return_value = request({'result': validation})
    with pytest.raises(ValueError, match='validation failed'):
        router._publish(existing_map(), BACKENDS)
    router.compute.urlMaps().update.assert_not_called()


def test_publish_preserves_fingerprint_existing_tests_and_removes_only_output_fields(router):
    current = existing_map()
    current.update({'id': '1', 'kind': 'compute#urlMaps', 'creationTimestamp': 'old', 'selfLink': 'map-url', 'region': 'unused'})
    current['tests'] = [{'host': HOSTS['react'], 'path': '/ualr/', 'service': 'existing-service'}]
    before = deepcopy(current)
    router._publish(current, BACKENDS)
    body = router.compute.urlMaps().update.call_args.kwargs['body']
    assert body['fingerprint'] == 'original-fingerprint'
    assert body['tests'] == current['tests']
    assert not {'id', 'kind', 'creationTimestamp', 'selfLink', 'region'}.intersection(body)
    assert body['pathMatchers'][0]['pathRules'][0] == current['pathMatchers'][0]['pathRules'][0]
    assert current == before
    validation = router.compute.urlMaps().validate.call_args.kwargs
    assert validation['project'] == PARENT
    assert validation['body']['loadBalancingSchemes'] == ['EXTERNAL_MANAGED']
    assert len(validation['body']['resource']['tests']) == 7


def test_publish_idempotence_validates_but_does_not_update(router):
    current = merge_tenant_routes(existing_map(), project_path='test-dev', backends=BACKENDS)
    router._publish(current, BACKENDS)
    router.compute.urlMaps().validate.assert_called_once()
    router.compute.urlMaps().update.assert_not_called()


def test_publish_refuses_missing_fingerprint(router):
    current = existing_map()
    current.pop('fingerprint')
    with pytest.raises(ValueError, match='fingerprint'):
        router._publish(current, BACKENDS)
    router.compute.urlMaps().update.assert_not_called()


def test_100_existing_tests_are_preserved_and_probe_batch_is_separate(router):
    current = existing_map()
    current['tests'] = [
        {'host': HOSTS['react'], 'path': f'/ualr/{i}', 'service': 'existing-service'} for i in range(100)
    ]
    router._publish(current, BACKENDS)
    calls = router.compute.urlMaps().validate.call_args_list
    assert len(calls) == 2
    assert calls[0].kwargs['body']['resource']['tests'] == current['tests']
    assert len(calls[1].kwargs['body']['resource']['tests']) == 6
    assert router.compute.urlMaps().update.call_args.kwargs['body']['tests'] == current['tests']


def test_412_retry_preserves_other_tenants_concurrent_changes(router):
    latest = existing_map()
    latest['fingerprint'] = 'concurrent-fingerprint'
    concurrent = {
        'paths': ['/new-college/*'],
        'service': 'projects/new-college/global/backendServices/new-react',
        'routeAction': {'urlRewrite': {'pathPrefixRewrite': '/'}},
    }
    latest['pathMatchers'][0]['pathRules'].append(concurrent)
    router.compute.urlMaps().get.return_value = request(latest)
    router.compute.urlMaps().update.side_effect = [request(error=http_error(412)), request({'status': 'DONE'})]
    router._publish(existing_map(), BACKENDS)
    assert router.compute.urlMaps().validate.call_count == 2
    body = router.compute.urlMaps().update.call_args.kwargs['body']
    assert body['fingerprint'] == 'concurrent-fingerprint'
    assert concurrent in body['pathMatchers'][0]['pathRules']
    router.compute.urlMaps().get.assert_called_once_with(project=PARENT, urlMap=router.url_map)


def test_412_new_tenant_conflict_aborts_instead_of_overwriting(router):
    concurrent = existing_map()
    concurrent['fingerprint'] = 'concurrent-fingerprint'
    concurrent['pathMatchers'][0]['pathRules'].append({
        'paths': ['/test-dev/*'],
        'service': 'projects/another-tenant/global/backendServices/claimed-react',
        'routeAction': {'urlRewrite': {'pathPrefixRewrite': '/'}},
    })
    router.compute.urlMaps().get.return_value = request(concurrent)
    router.compute.urlMaps().update.return_value = request(error=http_error(412))
    with pytest.raises(ValueError, match='ownership conflict'):
        router._publish(existing_map(), BACKENDS)
    assert router.compute.urlMaps().update.call_count == 1


def test_operation_failure_and_timeout_are_not_reported_as_success(router, monkeypatch):
    with pytest.raises(RuntimeError, match='Compute operation failed'):
        router._wait_operation({'status': 'DONE', 'error': {'errors': [{'code': 'QUOTA_EXCEEDED'}]}}, TENANT)
    monotonic = iter([0, 301])
    monkeypatch.setattr(module.time, 'monotonic', lambda: next(monotonic))
    with pytest.raises(TimeoutError, match='still running'):
        router._wait_operation({'status': 'RUNNING', 'name': 'unfinished'}, TENANT, region=REGION)
    router.compute.regionOperations().get.assert_not_called()


@pytest.mark.parametrize('region', [REGION, None])
def test_operation_polling_uses_matching_project_and_scope(router, monkeypatch, region):
    monkeypatch.setattr(module.time, 'sleep', lambda _: None)
    operations = router.compute.regionOperations() if region else router.compute.globalOperations()
    operations.get.return_value = request({'name': 'operation', 'status': 'DONE'})
    router._wait_operation({'status': 'PENDING', 'name': 'operation'}, TENANT, region=region)
    expected = {'project': TENANT, 'operation': 'operation'}
    if region:
        expected['region'] = region
    operations.get.assert_called_once_with(**expected)


def test_backend_creation_failure_leaves_parent_map_and_cache_unchanged(router):
    router.config['url_map'] = router.url_map
    router.compute.backendServices().insert.return_value = request({
        'status': 'DONE', 'error': {'errors': [{'code': 'PERMISSION_DENIED'}]},
    })
    assert router.run() is False
    router.compute.urlMaps().update.assert_not_called()
    router.env.db.update.assert_not_called()


def test_run_only_publishes_and_caches_after_both_child_backends_are_ready(router):
    router.config['url_map'] = router.url_map
    assert router.run() is True
    assert router.compute.regionNetworkEndpointGroups().insert.call_count == 2
    assert router.compute.backendServices().insert.call_count == 2
    router.compute.urlMaps().update.assert_called_once()
    router.env.db.update.assert_called_once()
    cached = router.env.db.update.call_args.kwargs['data']['shared_load_balancer']
    assert cached == {'url_map': router.url_map, 'react_service': 'agoge-react', 'api_service': 'agoge-api', 'function': 'agoge'}
    body = router.compute.urlMaps().update.call_args.kwargs['body']
    services = [rule.get('service') for matcher in body['pathMatchers'] for rule in matcher['pathRules']]
    assert set(BACKENDS.values()).issubset(services)
    assert not any('/functions/' in (service or '') for service in services)


def test_run_normalizes_domain_and_reuses_existing_custom_route_backends(router):
    router.env.parent_dns_suffix = '.Agoge-Labs.COM.'
    router.config['url_map'] = router.url_map
    current = existing_map()
    for role, matcher in zip(HOSTS, current['pathMatchers']):
        matcher['pathRules'].append({
            'paths': ['/test-dev/*'],
            'service': f'projects/{TENANT}/global/backendServices/legacy-{role}',
            'routeAction': {'urlRewrite': {'pathPrefixRewrite': '/'}},
        })
    router.compute.urlMaps().get.return_value = request(current)

    def backend_get(*, project, backendService):
        assert project == TENANT
        return request({
            'loadBalancingScheme': 'EXTERNAL_MANAGED',
            'backends': [{'group': COMPUTE_ROOT + f'projects/{TENANT}/regions/{REGION}/networkEndpointGroups/{backendService}-neg'}],
        })

    def neg_get(*, project, region, networkEndpointGroup):
        assert project == TENANT
        assert region == REGION
        role = 'react' if networkEndpointGroup == 'legacy-react-neg' else 'api'
        return request({'networkEndpointType': 'SERVERLESS', 'cloudRun': {'service': f'agoge-{role}'}})

    router.compute.backendServices().get.side_effect = backend_get
    router.compute.regionNetworkEndpointGroups().get.side_effect = neg_get
    assert router.run() is True
    assert router.hosts == HOSTS
    router.compute.backendServices().insert.assert_not_called()
    router.compute.regionNetworkEndpointGroups().insert.assert_not_called()
    body = router.compute.urlMaps().update.call_args.kwargs['body']
    assert len(body['hostRules']) == 2
    for role, matcher in zip(HOSTS, body['pathMatchers']):
        exact = [rule for rule in matcher['pathRules'] if '/test-dev' in rule['paths']]
        assert exact[0]['service'] == f'projects/{TENANT}/global/backendServices/legacy-{role}'
