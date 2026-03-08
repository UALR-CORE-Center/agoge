from google.cloud.compute_v1 import Network


class NetworkResource:
    def __init__(
        self,
        region: str,
        project: str
    ) -> None:
        self.project = project
        self.region = region

    @staticmethod
    def network_path(network_name: str, project: str) -> str:
        return f'projects/{project}/global/networks/{network_name}'

    @staticmethod
    def default_network() -> str:
        return 'global/networks/default'

    def new(
        self,
        name: str,
        description: str = None,
        auto_create_subnetworks: bool = False,
    ) -> Network:
        if not description:
            description = f'Agoge {name} network'

        network_resource = Network(
            name=name,
            description=description,
            auto_create_subnetworks=auto_create_subnetworks,
        )

        return network_resource

