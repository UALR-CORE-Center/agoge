"""Conservative, side-effect-free updates to shared load-balancer URL maps."""

from copy import deepcopy
import re


_COMPUTE_URL_PREFIXES = (
    'https://www.googleapis.com/compute/v1/',
    'https://compute.googleapis.com/compute/v1/',
)
_TENANT_REWRITE = {'urlRewrite': {'pathPrefixRewrite': '/'}}


def _tenant_path(project_path: str) -> str:
    if not isinstance(project_path, str):
        raise ValueError('project_path must be a single, nonempty URL path segment.')
    path = project_path.strip('/')
    if not re.fullmatch(r'[A-Za-z0-9._~-]+', path) or path in {'.', '..'}:
        raise ValueError(
            'project_path must be one nonempty URL path segment using only letters, '
            'numbers, "-", "_", ".", or "~"; do not include a query, fragment, or nested path.'
        )
    return '/' + path


def _backend_reference(reference: str) -> str:
    if not isinstance(reference, str):
        raise ValueError('Each routing backend must name a global backend service.')
    for prefix in _COMPUTE_URL_PREFIXES:
        if reference.startswith(prefix):
            reference = reference[len(prefix):]
            break
    if not re.fullmatch(r'projects/[^/]+/global/backendServices/[^/]+', reference):
        raise ValueError(
            f'Invalid backend service reference {reference!r}; expected '
            'projects/PROJECT/global/backendServices/SERVICE.'
        )
    return reference


def _new_matcher_name(host: str, matchers: list[dict]) -> str:
    label = re.sub(r'[^a-z0-9-]', '-', host.split('.')[0].lower()).strip('-') or 'host'
    if not label[0].isalpha():
        label = 'host-' + label
    base = label[:51].rstrip('-') + '-matcher'
    names = {matcher.get('name') for matcher in matchers}
    candidate = base
    suffix = 2
    while candidate in names:
        candidate = f'{base}-{suffix}'
        suffix += 1
    return candidate


def _matcher_for_host(url_map: dict, host: str) -> dict:
    host_rules = url_map.setdefault('hostRules', [])
    matchers = url_map.setdefault('pathMatchers', [])
    matching_rules = [
        rule for rule in host_rules
        if host in [value.lower() for value in rule.get('hosts', [])]
    ]
    if len(matching_rules) > 1:
        raise ValueError(f'Host {host} has multiple host rules; resolve them manually before retrying.')
    if matching_rules:
        name = matching_rules[0].get('pathMatcher')
        matching_matchers = [matcher for matcher in matchers if matcher.get('name') == name]
        if len(matching_matchers) != 1:
            raise ValueError(
                f'Host {host} does not have one valid path matcher; repair its host rule manually.'
            )
        other_hosts = {
            value for rule in host_rules if rule.get('pathMatcher') == name
            for value in rule.get('hosts', []) if value.lower() != host
        }
        if other_hosts:
            raise ValueError(
                f'Path matcher {name!r} for {host} is shared with other hosts '
                f'({", ".join(sorted(other_hosts))}); create a dedicated host matcher manually '
                'before retrying.'
            )
        return matching_matchers[0]

    if not url_map.get('defaultService'):
        raise ValueError(
            f'Cannot add host {host}: the URL map has no defaultService. '
            'Create this host and its default backend manually before retrying.'
        )
    name = _new_matcher_name(host, matchers)
    matcher = {'name': name, 'defaultService': url_map['defaultService'], 'pathRules': []}
    matchers.append(matcher)
    host_rules.append({'hosts': [host], 'pathMatcher': name})
    return matcher


def merge_tenant_routes(url_map: dict, *, project_path: str, backends: dict[str, str]) -> dict:
    """Return a copied URL map routing a tenant's exact and wildcard paths.

    ``backends`` maps exact app/API hostnames to global backend service resource
    names. Existing tenant rules must already have the requested backend and a
    simple ``/`` prefix rewrite. Conflicts and advanced routing require manual
    resolution; this function never repoints another tenant's existing rules.
    """
    tenant_path = _tenant_path(project_path)
    desired_paths = (tenant_path, tenant_path + '/*')
    result = deepcopy(url_map)
    seen_hosts = set()
    for supplied_host, supplied_backend in backends.items():
        if not isinstance(supplied_host, str) or not re.fullmatch(
            r'[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?', supplied_host
        ):
            raise ValueError('Routing requires exact hostnames without a scheme, port, path, or wildcard.')
        host = supplied_host.lower()
        if host in seen_hosts:
            raise ValueError(f'Host {host} was provided more than once; supply one backend per host.')
        seen_hosts.add(host)
        backend = _backend_reference(supplied_backend)
        matcher = _matcher_for_host(result, host)
        if matcher.get('routeRules'):
            raise ValueError(
                f'Path matcher {matcher["name"]!r} for {host} uses advanced routeRules; '
                'configure the tenant route manually or use a dedicated pathRules matcher.'
            )

        present_paths = set()
        rules = matcher.setdefault('pathRules', [])
        for rule in rules:
            paths = rule.get('paths', [])
            children = [
                path for path in paths
                if path.startswith(tenant_path + '/') and path not in desired_paths
            ]
            if children:
                raise ValueError(
                    f'Host {host} already has more-specific tenant paths ({", ".join(children)}); '
                    'review and resolve those routes manually before retrying.'
                )
            matching_paths = [path for path in paths if path in desired_paths]
            if not matching_paths:
                continue
            try:
                same_backend = _backend_reference(rule.get('service')) == backend
            except ValueError:
                same_backend = False
            if not same_backend:
                raise ValueError(
                    f'Host {host} already routes {matching_paths[0]} to another backend or action; '
                    'resolve this tenant-path ownership conflict manually before retrying.'
                )
            if rule.get('routeAction') != _TENANT_REWRITE or set(rule) - {
                'paths', 'service', 'routeAction', 'description',
            }:
                raise ValueError(
                    f'Host {host} has a different rewrite or action for {matching_paths[0]}; '
                    'review this rule manually before retrying. Expected only a "/" path-prefix rewrite.'
                )
            for path in matching_paths:
                if path in present_paths:
                    raise ValueError(
                        f'Host {host} has duplicate rules for {path}; remove the duplicate manually before retrying.'
                    )
                present_paths.add(path)

        missing_paths = [path for path in desired_paths if path not in present_paths]
        if missing_paths:
            rules.append({
                'paths': missing_paths,
                'service': backend,
                'routeAction': deepcopy(_TENANT_REWRITE),
            })
    return result
