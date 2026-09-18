import time

from common.exceptions import Conflict, NotFound
from common.utilities.gcp.cloud_env import CloudEnv
from common.utilities.gcp.cloud_logger import Logger, LoggerNames
from common.utilities.gcp.compute.compute_routes import ComputeRoutesAPI
from common.utilities.gcp.compute.resources.routes_resource import RoutesResource


class RouteManager:
    def __init__(
        self,
        build_id: str,
        env_dict: dict = None
    ) -> None:
        self.class_name = self.__class__.__name__
        self.log_name = LoggerNames.CLOUD_FN
        self.env = CloudEnv(env_dict=env_dict) if env_dict else CloudEnv()
        self.build_id = build_id
        self.logger = Logger(self.log_name, class_name=self.class_name)
        self.routes_resource = RoutesResource(project=self.env.project, zone=self.env.zone)
        self.routes_client = ComputeRoutesAPI(
            project=self.env.project,
            region=self.env.region,
            zone=self.env.zone,
            log_name=self.log_name
        )

    def route_name(self, name: str) -> str:
        return name if name.startswith(f"{self.build_id}-") else f"{self.build_id}-{name}"

    def build(self, routing_spec):
        """Build routes after their next-hop VM is available.

        Route specifications can be dictionaries or Pydantic models. The
        existing ``dest_range``/``next_hop_instance`` names remain canonical,
        while descriptive aliases are accepted for imported specifications.
        """
        for route in routing_spec or []:
            route_name = self.route_name(self._get(route, 'name'))
            next_hop_name = self._get(route, 'next_hop_instance', 'next_hop_server')
            destination = self._get(route, 'dest_range', 'destination_cidr', 'destination_range')
            network_name = self._get(route, 'network')
            next_hop_instance = self.routes_resource.next_hop_instance(self.build_id, next_hop_name)
            route_body = self.routes_resource.new(
                name=route_name,
                network=self.routes_resource.network_path(self._prefixed_name(network_name)),
                priority=self._get(route, 'priority', default=1000),
                next_hop_instance=next_hop_instance,
                dest_range=destination,
                tags=self._get(route, 'tags', default=[]),
                description=self._get(route, 'description', default=None),
            )
            try:
                created = self.routes_client.create(
                    resource_name=route_name,
                    route_resource=route_body,
                    wait=True,
                )
                if not created:
                    raise ConnectionError(
                        f'Timed out creating route {route_name}'
                    )
            except Conflict as error:
                existing_route = self.routes_client.get(resource=route_name)
                if not self._routes_match(existing_route, route_body):
                    raise Conflict(
                        f'Existing route {route_name} does not match the requested configuration'
                    ) from error
                self.logger.info(
                    f"{self.class_name}:{route_name} - Matching route already exists"
                )

    def delete(self, routing_spec=None):
        self.logger.info(f"{self.class_name}:{self.build_id} - Deleting routes for Workout")
        if routing_spec is not None:
            for route in routing_spec:
                route_name = self.route_name(self._get(route, 'name'))
                try:
                    deleted = self.routes_client.delete(resource_name=route_name)
                    if not deleted:
                        raise ConnectionError(
                            f'Timed out deleting route {route_name}'
                        )
                except NotFound:
                    self.logger.info(f"{self.class_name}:{route_name} - Route already deleted")
            return True

        existing_routes_list = self._list_build_routes()
        if existing_routes_list:
            for route in existing_routes_list:
                try:
                    deleted = self.routes_client.delete(resource_name=route.name)
                    if not deleted:
                        raise ConnectionError(
                            f'Timed out deleting route {route.name}'
                        )
                except NotFound:
                    self.logger.info(f"{self.class_name}:{route.name} - Route already deleted")
            self._wait_for_deletion()
        return True

    def _wait_for_deletion(self):
        # TODO: Might not need this method since we are waiting for each request to finish prior to calling
        i = 0
        success = False
        while not success and i < 10:
            existing_routes_list = self._list_build_routes()
            if existing_routes_list:
                i += 1
                time.sleep(10)
            else:
                success = True

        if not success:
            self.logger.error(f'{self.class_name}:{self.build_id} - Timeout in deleting routes')
            raise ConnectionError

    def _list_build_routes(self) -> list:
        """List routes owned by this build without relying on GCE wildcard filters."""
        prefix = f'{self.build_id}-'
        return [
            route
            for route in self.routes_client.list()
            if getattr(route, 'name', '').startswith(prefix)
        ]

    def _prefixed_name(self, name: str) -> str:
        return name if name.startswith(f'{self.build_id}-') else f'{self.build_id}-{name}'

    @classmethod
    def _routes_match(cls, existing, desired) -> bool:
        """Compare every caller-controlled field on immutable GCE routes."""
        return (
            cls._resource_path(cls._field(existing, 'network'))
            == cls._resource_path(cls._field(desired, 'network'))
            and cls._field(existing, 'dest_range') == cls._field(desired, 'dest_range')
            and cls._resource_path(cls._field(existing, 'next_hop_instance'))
            == cls._resource_path(cls._field(desired, 'next_hop_instance'))
            and cls._field(existing, 'priority') == cls._field(desired, 'priority')
            and sorted(cls._field(existing, 'tags', []) or [])
            == sorted(cls._field(desired, 'tags', []) or [])
            and cls._field(existing, 'description') == cls._field(desired, 'description')
        )

    @staticmethod
    def _field(resource, name: str, default=None):
        if isinstance(resource, dict):
            return resource.get(name, default)
        return getattr(resource, name, default)

    @staticmethod
    def _resource_path(resource_url: str | None) -> str:
        value = str(resource_url or '')
        marker = '/compute/v1/'
        return value.split(marker, 1)[-1].lstrip('/')

    @staticmethod
    def _get(route, key: str, *aliases: str, default=None):
        keys = (key, *aliases)
        if isinstance(route, dict):
            for candidate in keys:
                if candidate in route and route[candidate] is not None:
                    return route[candidate]
        else:
            for candidate in keys:
                value = getattr(route, candidate, None)
                if value is not None:
                    return value
        if default is not None or key in ('description', 'tags', 'priority'):
            return default
        raise ValueError(f"Route is missing required field '{key}'")
