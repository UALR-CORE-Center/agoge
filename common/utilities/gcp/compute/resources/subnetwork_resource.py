from google.cloud.compute_v1 import (
    Subnetwork,
)


class SubnetworkResource:
    def __init__(
        self,
        region: str,
        project: str
    ) -> None:
        self.project = project
        self.region = region

    def new(
        self,
        name: str,
        network: str,
        ip_cidr_range: str,
        description: str = None,
        region: str = None
    ) -> Subnetwork:
        if not description:
            description = f'Agoge {name} subnetwork for network, {network}'
        if not region:
            region = self.region

        subnet_resource = Subnetwork(
            name=name,
            description=description,
            network=network,
            region=region,
            ip_cidr_range=ip_cidr_range
        )

        return subnet_resource
