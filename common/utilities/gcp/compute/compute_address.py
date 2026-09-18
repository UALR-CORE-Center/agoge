from typing import Any, List, Union

from google.cloud.compute_v1 import (
    Address,
    AddressesClient,
    DeleteAddressRequest,
    GetAddressRequest,
    InsertAddressRequest,
    ListAddressesRequest,
)
from googleapiclient.discovery import Resource

from common.constants.google import ClientType, OperationType, ResourceType
from common.exceptions import BadRequest
from common.utilities.gcp.cloud_logger import LoggerNames

from .base_compute_api import BaseComputeAPI


class ComputeAddressesAPI(BaseComputeAPI):
    """Compute Engine regional static external-address operations."""

    def __init__(
        self,
        project: str,
        region: str,
        zone: str,
        log_name: str = LoggerNames.CLOUD_FN,
    ) -> None:
        super().__init__(project=project, region=region, zone=zone, log_name=log_name)
        self.resource_type = ResourceType.ADDRESSES
        self.client_type = ClientType.ADDRESSES
        self.default_operation = OperationType.REGION

    def client(self, **kwargs) -> Union[Resource, Any]:
        if not self.addresses_client:
            self.addresses_client = AddressesClient()
        return self.addresses_client

    def get(
        self,
        resource: str,
        project: str = None,
        region: str = None,
        **kwargs,
    ) -> Address:
        project = project or self.project
        region = region or self.region
        request = GetAddressRequest(address=resource, project=project, region=region)
        return self._make_request(
            client_request=self.client().get,
            resource=resource,
            action="get",
            wait=False,
            request=request,
            operation_type=self.default_operation,
        )

    def list(
        self,
        filter_: str = None,
        project: str = None,
        region: str = None,
        **kwargs,
    ) -> List[Address]:
        request = ListAddressesRequest(
            project=project or self.project,
            region=region or self.region,
        )
        if filter_:
            request.filter = filter_
        response = self._make_request(
            client_request=self.client().list,
            resource=None,
            action="list",
            wait=False,
            request=request,
            operation_type=self.default_operation,
        )
        return list(response)

    def create(
        self,
        resource_name: str,
        wait: bool = True,
        address_resource: Address = None,
        project: str = None,
        region: str = None,
        **kwargs,
    ) -> bool:
        if not address_resource:
            raise BadRequest(message="Missing required argument `address_resource`.")
        request = InsertAddressRequest(
            project=project or self.project,
            region=region or self.region,
            address_resource=address_resource,
        )
        return self._make_request(
            client_request=self.client().insert,
            resource=resource_name,
            action="insert",
            wait=wait,
            request=request,
            operation_type=self.default_operation,
        )

    def delete(
        self,
        resource_name: str,
        wait: bool = True,
        project: str = None,
        region: str = None,
        **kwargs,
    ) -> bool:
        request = DeleteAddressRequest(
            address=resource_name,
            project=project or self.project,
            region=region or self.region,
        )
        return self._make_request(
            client_request=self.client().delete,
            resource=resource_name,
            action="delete",
            wait=wait,
            request=request,
            operation_type=self.default_operation,
        )

    def update(self, resource_name: str, wait: bool = True, **kwargs) -> bool:
        raise NotImplementedError("Regional external addresses are immutable")
