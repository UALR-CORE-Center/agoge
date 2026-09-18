from typing import List
from google.cloud.compute_v1 import Route


class RoutesResource:
    def __init__(
        self,
        project: str,
        zone:  str
    ) -> None:
        self.project = project
        self.zone = zone

    def network_path(self, network_name: str) -> str:
        return f'projects/{self.project}/global/networks/{network_name}'

    def next_hop_instance(self, build_id: str, server_name: str) -> str:
        if server_name.startswith('projects/'):
            return server_name
        instance_name = server_name if server_name.startswith(f'{build_id}-') else f'{build_id}-{server_name}'
        return f'projects/{self.project}/zones/{self.zone}/instances/{instance_name}'

    def new(
        self,
        name: str,
        network: str,
        dest_range: str,
        next_hop_instance: str = None,
        next_hop_ilb: str = None,
        priority: int = 1000,
        tags: List = None,
        description: str = None,
    ) -> Route:
        if not description:
            description = f'Agoge {network} network route, {name}'
        if not tags:
            tags = []

        route_resource = Route(
            name=name,
            description=description,
            network=network,
            priority=priority,
            tags=tags,
            dest_range=dest_range
        )
        if next_hop_instance:
            route_resource.next_hop_instance = next_hop_instance
        elif next_hop_ilb:
            route_resource.next_hop_ilb = next_hop_ilb
        else:
            raise ValueError('Missing value for next_hop_ilb and next_hop_instance. Must provide one!')
        return route_resource
