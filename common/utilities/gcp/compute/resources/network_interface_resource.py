from typing import List
from google.cloud.compute_v1 import (
    NetworkInterface,
    AccessConfig,
    AliasIpRange
)


class NetworkInterfaceResource:
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

    @staticmethod
    def _subnetwork(
        subnet_name: str,
        region: str
    ) -> str:
        return f'regions/{region}/subnetworks/{subnet_name}'

    def new(
        self,
        network: str = None,
        network_name: str = None,
        subnetwork: str = None,
        subnetwork_name: str = None,
        internal_ip: str = None,
        access_configs: List[AccessConfig] | None = None,
        alias_ip_ranges: List[AliasIpRange] = None,
    ) -> NetworkInterface:

        if network_name:
            network = self.network_path(network_name, self.project)
        if not network:
            raise ValueError('Missing value for network or network_name. Must provide one')

        nic = NetworkInterface(network=network)
        if subnetwork_name:
            subnetwork = self._subnetwork(subnetwork_name, self.region)
        if subnetwork:
            nic.subnetwork = subnetwork
        if access_configs:
            nic.access_configs = access_configs
        if alias_ip_ranges:
            nic.alias_ip_ranges = alias_ip_ranges
        if internal_ip:
            nic.network_i_p = internal_ip

        return nic

    def access_config(
        self,
        type_: str,
        name: str
    ) -> AccessConfig:
        return AccessConfig(type_=type_, name=name)

    def alias_ip_range(
        self,
        ip_cidr_range: str,
    ) -> AliasIpRange:
        return AliasIpRange(ip_cidr_range=ip_cidr_range)
