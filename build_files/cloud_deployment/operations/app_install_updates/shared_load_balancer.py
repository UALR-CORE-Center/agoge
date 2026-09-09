"""Publish ready tenant applications through an existing shared URL map."""

import re
import time

from google.auth.exceptions import GoogleAuthError
from googleapiclient import discovery
from googleapiclient.errors import HttpError

from common.constants.database import ADMIN_INFO_DOCUMENT, DbCollections
from common.utilities.gcp.cloud_env import CloudEnv
from .shared_routing import _backend_reference, _tenant_path, merge_tenant_routes


COMPUTE_ROOT = 'https://www.googleapis.com/compute/v1/'
RESOURCE_NAME = r'[a-z](?:[-a-z0-9]{0,61}[a-z0-9])?'


class SharedLoadBalancer:
    """Create child backends first, then safely merge routes in the parent.

    All requests explicitly name their project. This never changes the active
    gcloud project, grants IAM roles, or exposes the Pub/Sub function over HTTP.
    """

    def __init__(self, project: str):
        self.project = project
        self.env = CloudEnv(project=project)
        self.config = dict(self.env.get_env().get('shared_load_balancer') or {})
        self.services = {
            'react': self.config.get('react_service', 'agoge-react'),
            'api': self.config.get('api_service', 'agoge-api'),
        }
        self.function = self.config.get('function', 'agoge')

    def run(self) -> bool:
        try:
            if self.env.project != self.project:
                raise ValueError('The selected project differs from its environment document.')
            self.path = _tenant_path(self.env.project_path)
            self.parent = self.env.parent_project
            self.region = self.env.region
            domain = self.env.parent_dns_suffix.strip('.').lower()
            if not self.parent or not domain:
                raise ValueError('Configure parent_project and parent_dns_suffix first.')
            self.hosts = {'react': f'app.{domain}', 'api': f'api.{domain}'}
            self.compute = discovery.build('compute', 'v1', cache_discovery=False)
            self.cloud_run = discovery.build('run', 'v2', cache_discovery=False)
            self.functions = discovery.build('cloudfunctions', 'v2', cache_discovery=False)
            if not self._ready():
                return False
            current = self._select_url_map()
            if current is None:
                return False
            self.url_map = current['name']

            plans = {
                role: self._plan_backend(self._backend_name(current, role), service)
                for role, service in self.services.items()
            }
            backends = {self.hosts[role]: plan['reference'] for role, plan in plans.items()}
            # Detect path ownership and unsupported routing before creating resources.
            merge_tenant_routes(current, project_path=self.path, backends=backends)
            print(f'Configuring shared URL map {self.parent}/{self.url_map}:')
            for host, backend in backends.items():
                print(f'  {host}{self.path} and {self.path}/* -> {backend} (rewrite to /)')
            for plan in plans.values():
                self._ensure_backend(plan)
            self._publish(current, backends)

            self.env.db.update(
                collection_name=DbCollections.ADMIN_INFO,
                doc_id=ADMIN_INFO_DOCUMENT,
                data={'shared_load_balancer': {
                    'url_map': self.url_map,
                    'react_service': self.services['react'],
                    'api_service': self.services['api'],
                    'function': self.function,
                }},
            )
            print('Shared routing configured. Allow time for load-balancer propagation.')
            for host in self.hosts.values():
                print(f'  https://{host}{self.path}/')
            return True
        except (HttpError, GoogleAuthError, ValueError, RuntimeError, TimeoutError, EOFError) as error:
            print(f'Shared routing did not finish: {error}')
            if isinstance(error, HttpError) and error.resp.status == 403:
                print(
                    'The setup identity needs URL-map read/validate/update access in the parent, '
                    'Cloud Run/Functions read access and Compute backend/NEG management in the tenant, '
                    'and compute.backendServices.use on the referenced tenant backends '
                    '(roles/compute.loadBalancerServiceUser). No IAM grants were changed.'
                )
            print(
                'Resources already created are retained. Resolve the reported issue and run '
                '"Configure Shared Load Balancer Routing" to retry without rebuilding.'
            )
            return False

    @staticmethod
    def _get_or_none(request):
        try:
            return request.execute()
        except HttpError as error:
            if error.resp.status == 404:
                return None
            raise

    @staticmethod
    def _run_service_ready(service: dict | None) -> bool:
        if not service or service.get('reconciling'):
            return False
        if service.get('terminalCondition', {}).get('state') != 'CONDITION_SUCCEEDED':
            return False
        if service.get('generation') is None or str(service.get('generation')) != str(service.get('observedGeneration')):
            return False
        latest = service.get('latestReadyRevision')
        if not latest or latest != service.get('latestCreatedRevision'):
            return False
        # An old revision can still serve while a newer deployment has failed.
        traffic = sum(
            target.get('percent', 0) for target in service.get('trafficStatuses', [])
            if target.get('revision', '').rsplit('/', 1)[-1] == latest.rsplit('/', 1)[-1]
        )
        return traffic == 100

    def _ready(self) -> bool:
        location = f'projects/{self.project}/locations/{self.region}'
        while True:
            pending = []
            for role, name in self.services.items():
                if not re.fullmatch(RESOURCE_NAME, name):
                    raise ValueError(f'Invalid Cloud Run service name: {name!r}')
                service = self._get_or_none(self.cloud_run.projects().locations().services().get(
                    name=f'{location}/services/{name}',
                ))
                if not self._run_service_ready(service):
                    pending.append(f'{role} Cloud Run service {name} (latest revision must be ready with 100% traffic)')
            if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,62}', self.function):
                raise ValueError(f'Invalid Cloud Function name: {self.function!r}')
            function = self._get_or_none(self.functions.projects().locations().functions().get(
                name=f'{location}/functions/{self.function}',
            ))
            if not function or function.get('state') != 'ACTIVE' or function.get('environment') != 'GEN_2' or (
                function.get('eventTrigger', {}).get('pubsubTopic') != f'projects/{self.project}/topics/agoge'
            ):
                pending.append(f'gen2 Pub/Sub function {self.function} (ACTIVE, using this project\'s agoge topic)')
            if not pending:
                return True
            print('Routing is waiting for deployed applications in ' + location + ':')
            for item in pending:
                print(f'  - {item}')
            print(
                f'Inspect Cloud Run: gcloud run services list --project={self.project} --region={self.region}\n'
                f'Inspect function: gcloud functions describe {self.function} --gen2 '
                f'--project={self.project} --region={self.region}\n'
                'Deploy/fix these resources in another terminal, or provide their actual service names. '
                'Use names, not run.app URLs. The function is a background dependency, not an HTTP backend.'
            )
            choice = input('[R]etry checks / [N] Enter resource names / [Enter] Defer routing: ').strip().upper()
            if choice == 'N':
                for role, name in self.services.items():
                    self.services[role] = input(f'{role} Cloud Run service [{name}]: ').strip() or name
                self.function = input(f'Cloud Function [{self.function}]: ').strip() or self.function
            elif choice != 'R':
                print('Shared routing deferred. Run Configure Shared Load Balancer Routing when ready.')
                return False

    def _select_url_map(self) -> dict | None:
        name = self.config.get('url_map')
        if not name:
            maps = []
            request = self.compute.urlMaps().list(project=self.parent)
            while request is not None:
                response = request.execute()
                maps.extend(response.get('items', []))
                request = self.compute.urlMaps().list_next(request, response)
            expected = set(self.hosts.values())
            placements = {
                host: {
                    item['name'] for item in maps
                    if any(host in [value.lower() for value in rule.get('hosts', [])]
                           for rule in item.get('hostRules', []))
                }
                for host in expected
            }
            if all(placements.values()) and not set.intersection(*placements.values()):
                raise ValueError(
                    'App and API hosts use separate URL maps. Configure those maps manually; '
                    'automatic shared routing requires both hosts on one URL map.'
                )
            candidates = [
                item for item in maps if expected.issubset({
                    host.lower() for rule in item.get('hostRules', []) for host in rule.get('hosts', [])
                })
            ]
            if len(candidates) == 1:
                name = candidates[0]['name']
                print(f'Discovered shared URL map: {self.parent}/{name}')
            else:
                print(f'Global URL maps in {self.parent}:')
                for item in maps:
                    hosts = ', '.join(host for rule in item.get('hostRules', []) for host in rule.get('hosts', []))
                    print(f'  {item["name"]}: {hosts or "no host rules"}')
                print(
                    'Use the URL map attached to the shared HTTPS load balancer for both app and API. '
                    'This is the URL-map name, not the app-matcher path-matcher name. '
                    'If app/API use separate URL maps, configure their routing manually. '
                    'Entering a map confirms both hosts use it; any missing exact host rules will be added.'
                )
                name = input('Shared URL-map name [Enter to defer]: ').strip()
                if not name:
                    return None
        if not re.fullmatch(RESOURCE_NAME, name):
            raise ValueError('Provide a global URL-map resource name, not a URL or path-matcher name.')
        return self.compute.urlMaps().get(project=self.parent, urlMap=name).execute()

    def _backend_name(self, url_map: dict, role: str) -> str:
        host = self.hosts[role]
        matcher_names = {
            rule.get('pathMatcher') for rule in url_map.get('hostRules', [])
            if host in [value.lower() for value in rule.get('hosts', [])]
        }
        references = {
            _backend_reference(rule.get('service'))
            for matcher in url_map.get('pathMatchers', []) if matcher.get('name') in matcher_names
            for rule in matcher.get('pathRules', [])
            if set(rule.get('paths', [])).intersection({self.path, self.path + '/*'})
        }
        if len(references) > 1:
            raise ValueError(f'{host}{self.path} uses conflicting backends; resolve these routes manually.')
        if references:
            reference = references.pop()
            if not reference.startswith(f'projects/{self.project}/global/backendServices/'):
                raise ValueError(f'{host}{self.path} belongs to another project; choose a different project_path.')
            return reference.rsplit('/', 1)[-1]
        return f'{self.project}-{role}'

    def _check_neg(self, neg: dict, service: str):
        target = neg.get('cloudRun', {})
        if neg.get('networkEndpointType') != 'SERVERLESS' or target.get('service') != service or (
            target.get('tag') or target.get('urlMask') or neg.get('cloudFunction') or neg.get('appEngine')
        ):
            raise ValueError(f'NEG {neg.get("name")} does not exclusively target Cloud Run service {service}.')

    def _plan_backend(self, name: str, service: str) -> dict:
        if not re.fullmatch(RESOURCE_NAME, name):
            raise ValueError(f'Invalid backend name: {name!r}')
        backend = self._get_or_none(self.compute.backendServices().get(project=self.project, backendService=name))
        neg_name = name + '-neg'
        if backend:
            if backend.get('loadBalancingScheme') != 'EXTERNAL_MANAGED' or len(backend.get('backends', [])) != 1:
                raise ValueError(f'Existing backend {name} must have one EXTERNAL_MANAGED serverless NEG; inspect it manually.')
            group = backend['backends'][0].get('group', '')
            prefix = f'{COMPUTE_ROOT}projects/{self.project}/regions/{self.region}/networkEndpointGroups/'
            if not group.startswith(prefix) or '/' in group[len(prefix):]:
                raise ValueError(f'Existing backend {name} targets a different project, region, or endpoint type.')
            neg_name = group[len(prefix):]
        neg = self._get_or_none(self.compute.regionNetworkEndpointGroups().get(
            project=self.project, region=self.region, networkEndpointGroup=neg_name,
        ))
        if neg:
            self._check_neg(neg, service)
        elif backend:
            raise ValueError(f'Existing backend {name} has a missing NEG; repair it manually.')
        return {
            'name': name,
            'reference': f'projects/{self.project}/global/backendServices/{name}',
            'backend_exists': backend is not None,
            'neg_name': neg_name,
            'neg_exists': neg is not None,
            'neg_link': f'{COMPUTE_ROOT}projects/{self.project}/regions/{self.region}/networkEndpointGroups/{neg_name}',
            'service': service,
        }

    def _ensure_backend(self, plan: dict):
        if not plan['neg_exists']:
            operation = self.compute.regionNetworkEndpointGroups().insert(
                project=self.project, region=self.region,
                body={'name': plan['neg_name'], 'networkEndpointType': 'SERVERLESS',
                      'cloudRun': {'service': plan['service']}},
            ).execute()
            self._wait_operation(operation, self.project, region=self.region)
        if not plan['backend_exists']:
            operation = self.compute.backendServices().insert(
                project=self.project,
                body={'name': plan['name'], 'loadBalancingScheme': 'EXTERNAL_MANAGED',
                      'backends': [{'group': plan['neg_link']}]},
            ).execute()
            self._wait_operation(operation, self.project)

    def _wait_operation(self, operation: dict, project: str, region: str | None = None):
        deadline = time.monotonic() + 300
        while operation.get('status') != 'DONE':
            if time.monotonic() >= deadline:
                raise TimeoutError(f'Compute operation {operation.get("name")} is still running; retry routing after it completes.')
            time.sleep(2)
            if region:
                operation = self.compute.regionOperations().get(
                    project=project, region=region, operation=operation['name'],
                ).execute()
            else:
                operation = self.compute.globalOperations().get(project=project, operation=operation['name']).execute()
        if operation.get('error'):
            raise RuntimeError(f'Compute operation failed: {operation["error"]}')

    def _validate(self, candidate: dict, backends: dict):
        probe_tests = [
            {'description': 'Agoge tenant routing preflight', 'host': host, 'path': self.path + suffix,
             'service': backend, 'expectedOutputUrl': f'https://{host}{rewritten}'}
            for host, backend in backends.items()
            for suffix, rewritten in [('', '/'), ('/', '/'), ('/__agoge_route_probe__', '/__agoge_route_probe__')]
        ]
        existing = candidate.get('tests', [])
        # The API allows at most 100 tests. Preserve every existing test in the
        # saved map; temporary rewrite probes are used only for validation.
        batches = [existing + probe_tests] if len(existing) + len(probe_tests) <= 100 else [existing, probe_tests]
        for tests in batches:
            resource = {**candidate, 'tests': tests}
            response = self.compute.urlMaps().validate(
                project=self.parent, urlMap=self.url_map,
                body={'resource': resource, 'loadBalancingSchemes': ['EXTERNAL_MANAGED']},
            ).execute().get('result', {})
            if not response.get('loadSucceeded') or not response.get('testPassed') or response.get('loadErrors') or response.get('testFailures'):
                raise ValueError(f'URL-map validation failed: {response}')

    def _publish(self, current: dict, backends: dict):
        for attempt in range(3):
            candidate = merge_tenant_routes(current, project_path=self.path, backends=backends)
            changed = candidate != current
            for key in ('id', 'kind', 'creationTimestamp', 'selfLink', 'region'):
                candidate.pop(key, None)
            self._validate(candidate, backends)
            if not changed:
                print('The tenant routes are already configured; no URL-map update needed.')
                return
            if not candidate.get('fingerprint'):
                raise ValueError('URL map has no fingerprint; refusing an unguarded update.')
            try:
                operation = self.compute.urlMaps().update(
                    project=self.parent, urlMap=self.url_map, body=candidate,
                ).execute()
            except HttpError as error:
                if error.resp.status != 412 or attempt == 2:
                    raise
                current = self.compute.urlMaps().get(project=self.parent, urlMap=self.url_map).execute()
                continue
            self._wait_operation(operation, self.parent)
            return
