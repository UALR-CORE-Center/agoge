from typing import Any, Union, List
from google.cloud.compute_v1 import (
    Subnetwork,
    SubnetworksClient,
    GetSubnetworkRequest,
    InsertSubnetworkRequest,
    DeleteSubnetworkRequest,
    ListSubnetworksRequest,
)
from googleapiclient.discovery import Resource

from common.exceptions import BadRequest
from common.constants.google import ResourceType, ClientType, OperationType
from common.utilities.gcp.cloud_logger import LoggerNames
from .base_compute_api import BaseComputeAPI


class ComputeSubnetworksAPI(BaseComputeAPI):
    """Handles operations related to Compute Subnetworks in Google Cloud.

    This class extends the base ComputeAPI to provide methods for creating,
    copying, deleting, and retrieving Compute Engine VCP subnetworks.
    """

    def __init__(
        self,
        project: str,
        region: str,
        zone: str,
        log_name: str = LoggerNames.CLOUD_FN
    ) -> None:
        """Initializes the ComputeSubNetworksAPI.

        Args:
            log_name (str, optional): Name of the logger to use. Defaults to
                LoggerNames.CLOUD_FN.
        """
        super().__init__(project=project, region=region, zone=zone, log_name=log_name)
        self.resource_type = ResourceType.SUBNETWORKS
        self.client_type = ClientType.SUBNETWORKS
        self.default_operation = OperationType.REGION

    def client(self) -> Union[Resource, Any]:
        if not self.subnetworks_client:
            self.subnetworks_client = SubnetworksClient()
        return self.subnetworks_client

    def get(
        self,
        resource: str,
        project: str = None,
        region: str = None,
        **kwargs,
    ) -> Any:
        client = self.client()
        if not project:
            project = self.project
        if not region:
            region = self.region

        request = GetSubnetworkRequest(subnetwork=resource, project=project, region=region)
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
    ) -> List[Subnetwork]:
        client = self.client()
        project = self.project
        region = self.region

        if kwargs:
            if 'project' in kwargs:
                project = kwargs['project']
            if 'region' in kwargs:
                region = kwargs['region']

        list_request = ListSubnetworksRequest(project=project, region=region)

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
        subnet_resource: Subnetwork = None,
        **kwargs
    ) -> bool:
        client = self.client()
        project = self.project
        region = self.region

        if kwargs:
            if 'project' in kwargs:
                project = kwargs['project']
            if 'region' in kwargs:
                region = kwargs['region']

        if not subnet_resource:
            raise BadRequest('Missing required argument `subnet_resource`.')

        request = InsertSubnetworkRequest(project=project, region=region, subnetwork_resource=subnet_resource)
        return self._make_request(
            client_request=client.insert,
            action='insert',
            resource=resource_name,
            wait=wait,
            request=request,
            operation_type=self.default_operation
        )

    def update(self, resource_name: str, wait: bool = True, **kwargs) -> bool:
        pass

    def delete(
        self,
        resource_name: str,
        wait: bool = True,
        **kwargs
    ) -> bool:
        client = self.client()
        project = self.project
        region = self.region

        if kwargs:
            if 'project' in kwargs:
                project = kwargs['project']
            if 'region' in kwargs:
                region = kwargs['region']

        request = DeleteSubnetworkRequest(
            project=project,
            region=region,
            subnetwork=resource_name
        )

        return self._make_request(
            client_request=client.delete,
            resource=resource_name,
            action='delete',
            wait=wait,
            request=request,
            operation_type=self.default_operation
        )
