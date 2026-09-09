from copy import deepcopy

import pytest

from cloud_deployment.operations.app_install_updates.shared_routing import merge_tenant_routes


APP_HOST = 'app.agoge-labs.com'
API_HOST = 'api.agoge-labs.com'
DEFAULT_BACKEND = 'projects/agoge-shared-resources/global/backendBuckets/default-404-backend'
APP_BACKEND = 'projects/test-dev-787001/global/backendServices/test-dev-react'
API_BACKEND = 'projects/test-dev-787001/global/backendServices/test-dev-api'


def tenant_rule(paths, backend=APP_BACKEND):
    return {
        'paths': paths,
        'service': backend,
        'routeAction': {'urlRewrite': {'pathPrefixRewrite': '/'}},
    }


@pytest.fixture
def shared_url_map():
    tenants = [
        ('ualr', 'agoge-ualr', 'agoge-ualr-react'),
        ('cccua', 'cccua-prod-711037', 'cccau-prod-react'),
        ('northark', 'northark-prod-893762', 'northark-prod-react'),
        ('ouachita-baptist', 'ouachita-baptist-prod-949187', 'ouachita-baptist-prod-react'),
        ('uaccb', 'uaccb-prod-253421', 'uaccb-prod-react'),
        ('uaht', 'uaht-prod-984057', 'uaht-prod-react'),
        ('ar-k12', 'ar-k12-prod-698683', 'ar-k12-react'),
    ]
    return {
        'name': 'agoge-shared-lb',
        'fingerprint': 'original-fingerprint',
        'description': 'Shared applications',
        'defaultService': DEFAULT_BACKEND,
        'hostRules': [{'hosts': [APP_HOST], 'pathMatcher': 'app-matcher'}],
        'pathMatchers': [{
            'name': 'app-matcher',
            'defaultService': DEFAULT_BACKEND,
            'pathRules': [
                tenant_rule([f'/{slug}/*'], f'projects/{project}/global/backendServices/{backend}')
                for slug, project, backend in tenants
            ],
        }],
    }


def merge(url_map, **kwargs):
    return merge_tenant_routes(
        url_map,
        project_path=kwargs.pop('project_path', 'test-dev'),
        backends=kwargs.pop('backends', {APP_HOST: APP_BACKEND, API_HOST: API_BACKEND}),
        **kwargs,
    )


def test_preserves_supplied_tenants_and_adds_app_and_api_routes(shared_url_map):
    original = deepcopy(shared_url_map)

    result = merge(shared_url_map)

    assert shared_url_map == original
    assert result['fingerprint'] == original['fingerprint']
    assert result['description'] == original['description']
    assert result['defaultService'] == DEFAULT_BACKEND
    app_matcher = result['pathMatchers'][0]
    assert app_matcher['pathRules'][:-1] == original['pathMatchers'][0]['pathRules']
    assert app_matcher['pathRules'][1]['service'].endswith('/cccau-prod-react')
    assert app_matcher['pathRules'][-1] == tenant_rule(['/test-dev', '/test-dev/*'])
    assert result['hostRules'] == original['hostRules'] + [
        {'hosts': [API_HOST], 'pathMatcher': 'api-matcher'},
    ]
    assert result['pathMatchers'][1] == {
        'name': 'api-matcher',
        'defaultService': DEFAULT_BACKEND,
        'pathRules': [tenant_rule(['/test-dev', '/test-dev/*'], API_BACKEND)],
    }
    assert merge(result) == result


@pytest.mark.parametrize('existing_paths,missing_paths', [
    (['/test-dev/*'], ['/test-dev']),
    (['/test-dev'], ['/test-dev/*']),
    (['/test-dev', '/test-dev/*'], []),
])
def test_preserves_existing_rules_and_adds_only_missing_patterns(shared_url_map, existing_paths, missing_paths):
    existing_rule = tenant_rule(existing_paths + ['/another-project/*'])
    shared_url_map['pathMatchers'][0]['pathRules'].append(existing_rule)
    original = deepcopy(shared_url_map)

    result = merge(shared_url_map, backends={APP_HOST: APP_BACKEND})

    expected_rules = original['pathMatchers'][0]['pathRules']
    if missing_paths:
        expected_rules.append(tenant_rule(missing_paths))
    assert result['pathMatchers'][0]['pathRules'] == expected_rules


def test_equivalent_full_backend_url_is_preserved(shared_url_map):
    existing_rule = tenant_rule(
        ['/test-dev', '/test-dev/*'],
        'https://www.googleapis.com/compute/v1/' + APP_BACKEND,
    )
    shared_url_map['pathMatchers'][0]['pathRules'].append(existing_rule)

    result = merge(shared_url_map, backends={APP_HOST: APP_BACKEND})

    assert result == shared_url_map


def test_accepts_canonical_compute_api_url_for_requested_backend(shared_url_map):
    result = merge(shared_url_map, backends={APP_HOST: 'https://compute.googleapis.com/compute/v1/' + APP_BACKEND})
    assert result['pathMatchers'][0]['pathRules'][-1]['service'] == APP_BACKEND


@pytest.mark.parametrize('project_path', ['test-dev', '/test-dev', '/test-dev/', '///test-dev///'])
def test_normalizes_outer_slashes(shared_url_map, project_path):
    result = merge(shared_url_map, project_path=project_path)
    assert result['pathMatchers'][0]['pathRules'][-1]['paths'] == ['/test-dev', '/test-dev/*']


@pytest.mark.parametrize('project_path', ['', '/', '///', '.', '..', 'a/b', 'a?b', 'a#b', 'a%2fb', ' a ', 'a\\b', None])
def test_rejects_invalid_project_paths(shared_url_map, project_path):
    with pytest.raises(ValueError, match='project_path'):
        merge(shared_url_map, project_path=project_path)


def test_allows_unreserved_slug_characters(shared_url_map):
    result = merge(shared_url_map, project_path='A_b.c~1-2')
    assert result['pathMatchers'][0]['pathRules'][-1]['paths'] == ['/A_b.c~1-2', '/A_b.c~1-2/*']


def test_rejects_existing_tenant_path_owned_by_another_backend(shared_url_map):
    shared_url_map['pathMatchers'][0]['pathRules'].append(tenant_rule(['/test-dev/*'], API_BACKEND))
    original = deepcopy(shared_url_map)
    with pytest.raises(ValueError, match='ownership conflict'):
        merge(shared_url_map)
    assert shared_url_map == original


@pytest.mark.parametrize('path', ['/test-dev/admin', '/test-dev/admin/*', '/test-dev/'])
def test_rejects_more_specific_existing_tenant_routes(shared_url_map, path):
    shared_url_map['pathMatchers'][0]['pathRules'].append(tenant_rule([path]))
    with pytest.raises(ValueError, match='more-specific'):
        merge(shared_url_map)


@pytest.mark.parametrize('action', [
    None,
    {'urlRewrite': {'pathPrefixRewrite': '/other/'}},
    {'urlRewrite': {'pathPrefixRewrite': '/', 'hostRewrite': 'other.example.com'}},
    {'urlRewrite': {'pathPrefixRewrite': '/'}, 'timeout': {'seconds': 60}},
])
def test_rejects_non_equivalent_rewrites_and_actions(shared_url_map, action):
    rule = tenant_rule(['/test-dev/*'])
    rule['routeAction'] = action
    shared_url_map['pathMatchers'][0]['pathRules'].append(rule)
    with pytest.raises(ValueError, match='different rewrite or action'):
        merge(shared_url_map)


def test_rejects_additional_rule_action(shared_url_map):
    rule = tenant_rule(['/test-dev/*'])
    rule['headerAction'] = {'requestHeadersToRemove': ['Authorization']}
    shared_url_map['pathMatchers'][0]['pathRules'].append(rule)
    with pytest.raises(ValueError, match='different rewrite or action'):
        merge(shared_url_map)


@pytest.mark.parametrize('same_host_rule', [True, False])
def test_rejects_matcher_shared_with_other_hosts(shared_url_map, same_host_rule):
    if same_host_rule:
        shared_url_map['hostRules'][0]['hosts'].append('another.example.com')
    else:
        shared_url_map['hostRules'].append({'hosts': ['another.example.com'], 'pathMatcher': 'app-matcher'})
    with pytest.raises(ValueError, match='shared with other hosts'):
        merge(shared_url_map)


def test_rejects_advanced_route_rules(shared_url_map):
    shared_url_map['pathMatchers'][0]['routeRules'] = [
        {'priority': 1, 'matchRules': [{'prefixMatch': '/'}], 'service': APP_BACKEND},
    ]
    with pytest.raises(ValueError, match='advanced routeRules'):
        merge(shared_url_map)


def test_rejects_duplicate_tenant_paths(shared_url_map):
    shared_url_map['pathMatchers'][0]['pathRules'].extend([
        tenant_rule(['/test-dev/*']), tenant_rule(['/test-dev/*']),
    ])
    with pytest.raises(ValueError, match='duplicate rules'):
        merge(shared_url_map)


def test_existing_host_uses_its_actual_matcher_name(shared_url_map):
    shared_url_map['hostRules'][0]['pathMatcher'] = 'production-apps'
    shared_url_map['pathMatchers'][0]['name'] = 'production-apps'
    result = merge(shared_url_map, backends={APP_HOST: APP_BACKEND})
    assert len(result['pathMatchers']) == 1
    assert result['pathMatchers'][0]['name'] == 'production-apps'
    assert result['pathMatchers'][0]['pathRules'][-1] == tenant_rule(['/test-dev', '/test-dev/*'])


def test_new_host_gets_unique_matcher_name(shared_url_map):
    shared_url_map['pathMatchers'].append({'name': 'api-matcher', 'defaultService': DEFAULT_BACKEND})
    result = merge(shared_url_map)
    assert result['hostRules'][-1]['pathMatcher'] == 'api-matcher-2'
    assert result['pathMatchers'][-1]['name'] == 'api-matcher-2'


def test_cannot_create_host_without_top_level_default_service(shared_url_map):
    del shared_url_map['defaultService']
    shared_url_map['defaultUrlRedirect'] = {'httpsRedirect': True}
    with pytest.raises(ValueError, match='no defaultService'):
        merge(shared_url_map)


@pytest.mark.parametrize('host', ['*.agoge-labs.com', 'https://app.agoge-labs.com', 'app.agoge-labs.com/path', 'app:443', ''])
def test_rejects_non_exact_hostnames(shared_url_map, host):
    with pytest.raises(ValueError, match='exact hostnames'):
        merge(shared_url_map, backends={host: APP_BACKEND})


@pytest.mark.parametrize('backend', ['test-dev-react', 'projects/test/regions/us-central1/backendServices/app', DEFAULT_BACKEND])
def test_requires_global_backend_service_resource(shared_url_map, backend):
    with pytest.raises(ValueError, match='backend service reference'):
        merge(shared_url_map, backends={APP_HOST: backend})


def test_failed_api_merge_does_not_modify_original_app_routes(shared_url_map):
    shared_url_map['hostRules'].append({'hosts': [API_HOST], 'pathMatcher': 'api-matcher'})
    shared_url_map['pathMatchers'].append({
        'name': 'api-matcher',
        'defaultService': DEFAULT_BACKEND,
        'pathRules': [tenant_rule(['/test-dev/*'], APP_BACKEND)],
    })
    original = deepcopy(shared_url_map)
    with pytest.raises(ValueError, match='ownership conflict'):
        merge(shared_url_map)
    assert shared_url_map == original
