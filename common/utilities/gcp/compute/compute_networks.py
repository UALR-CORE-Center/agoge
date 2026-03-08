from typing import Any, Union, List

from google.cloud.compute_v1 import (
    Network,
    NetworksClient,
    GetNetworkRequest,
    InsertNetworkRequest,
    DeleteNetworkRequest,
    ListNetworksRequest,
    PatchNetworkRequest
)
from googleapiclient.discovery import Resource

from common.exceptions import BadRequest
from common.constants.google import ResourceType, ClientType, OperationType
from common.utilities.gcp.cloud_logger import LoggerNames
from .base_compute_api import BaseComputeAPI


class ComputeNetworksAPI(BaseComputeAPI):
    """Handles operations related to Compute Networks in Google Cloud.

    This class extends the base ComputeAPI to provide methods for creating,
    copying, deleting, and retrieving Compute Engine VCP networks.
    """

    def __init__(
        self,
        project: str,
        region: str,
        zone: str,
        log_name: str = LoggerNames.CLOUD_FN
    ) -> None:
        """Initializes the ComputeNetworksAPI.

        Args:
            log_name (str, optional): Name of the logger to use. Defaults to
                LoggerNames.CLOUD_FN.
        """
        super().__init__(project=project, region=region, zone=zone, log_name=log_name)
        self.resource_type = ResourceType.NETWORKS
        self.client_type = ClientType.NETWORKS
        self.default_operation = OperationType.GLOBAL

    def client(self) -> Union[Resource, Any]:
        if not self.networks_client:
            self.networks_client = NetworksClient()
        return self.networks_client

    def get(
        self,
        resource: str,
        project: str = None,
        **kwargs,
    ) -> Any:
        client = self.client()
        if not project:
            project = self.project

        request = GetNetworkRequest(network=resource, project=project)
        return self._make_request(
            client_request=client.get,
            resource=resource,
            action='get',
            wait=False,
            request=request,
            operation_type=self.default_operation
        )

    def list(
        self,
        filter_: str = None,
        **kwargs
    ) -> List[Network]:
        client = self.client()
        project = self.project

        if kwargs:
            if 'project' in kwargs:
                project = kwargs['project']

        list_request = ListNetworksRequest(project=project)

        if filter_:
            list_request.filter = filter_

        resp = self._make_request(
            client_request=client.list,
            action='list',
            resource=None,
            wait=False,
            request=list_request,
            operation_type=self.default_operation
        )
        return list(resp)

    def create(
        self,
        resource_name: str,
        wait: bool = True,
        network_resource: Network = None,
        **kwargs
    ) -> bool:
        client = self.client()
        project = self.project

        if kwargs:
            if 'project' in kwargs:
                project = kwargs['project']

        if not network_resource:
            raise BadRequest('Missing required argument `network_resource`.')

        request = InsertNetworkRequest(project=project, network_resource=network_resource)
        return self._make_request(
            client_request=client.insert,
            action='insert',
            resource=resource_name,
            wait=wait,
            request=request,
            operation_type=self.default_operation
        )

    def update(
        self,
        resource_name: str,
        wait: bool = True,
        **kwargs,
    ) -> bool:
        pass

    def delete(
        self,
        resource_name: str,
        wait: bool = True,
        **kwargs
    ) -> bool:
        client = self.client()
        project = self.project

        if kwargs:
            if 'project' in kwargs:
                project = kwargs['project']

        request = DeleteNetworkRequest(
            network=resource_name,
            project=project
        )

        return self._make_request(
            client_request=client.delete,
            resource=resource_name,
            action='delete',
            wait=wait,
            request=request,
            operation_type=self.default_operation
        )
