import time

from common.exceptions import BaseAgogeException
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
        return f"{self.build_id}-{name}"

    def build(self, routing_spec):
        for route in routing_spec:
            next_hop_instance = self.routes_resource.next_hop_instance(self.build_id, route['next_hop_instance'])
            route_body = self.routes_resource.new(
                name=self.route_name(route['name']),
                network=self.routes_resource.network_path(f'{self.build_id}-{route["network"]}'),
                priority=0,
                next_hop_instance=next_hop_instance,
                dest_range=route['dest_range'],
            )
            self.routes_client.create(
                resource_name=self.route_name(route['name']),
                route_resource=route_body,
                wait=False
            )

    def delete(self):
        self.logger.info(f"{self.class_name}:{self.build_id} - Deleting routes for Workout")
        existing_routes_list = self.routes_client.list(filter_=f"name = {self.build_id}*")
        if existing_routes_list:
            for route in existing_routes_list:
                try:
                    self.routes_client.delete(resource_name=route.name)
                except BaseAgogeException:  # TODO: Determine appropriate exception to catch here
                    self.logger.info(f"{self.class_name}:{self.build_id} - Timeout when deleting routes")
                    return
            self._wait_for_deletion()

    def _wait_for_deletion(self):
        # TODO: Might not need this method since we are waiting for each request to finish prior to calling
        i = 0
        success = False
        while not success and i < 10:
            existing_routes_list = self.routes_client.list(filter_=f"name = {self.build_id}*")
            if existing_routes_list:
                i += 1
                time.sleep(10)
            else:
                success = True

        if not success:
            self.logger.error(f'{self.class_name}:{self.build_id} - Timeout in deleting routes')
            raise ConnectionError
