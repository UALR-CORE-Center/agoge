from typing import Any, Union, List

from google.cloud.compute_v1 import (
    Route,
    RoutesClient,
    GetRouteRequest,
    ListRoutesRequest,
    DeleteRouteRequest,
    InsertRouteRequest,
)
from googleapiclient.discovery import Resource

from common.exceptions import BadRequest
from common.constants.google import OperationType
from common.utilities.gcp.cloud_logger import LoggerNames
from .base_compute_api import BaseComputeAPI
from .resources.routes_resource import RoutesResource


class ComputeRoutesAPI(BaseComputeAPI):
    def update(self, resource_name: str, wait: bool = True, **kwargs) -> bool:
        pass

    def __init__(
        self,
        project: str,
        region: str,
        zone: str,
        log_name: str = LoggerNames.CLOUD_FN
    ) -> None:
        super().__init__(project=project, region=region, zone=zone, log_name=log_name)
        self.default_operation = OperationType.GLOBAL

    def client(self, **kwargs) -> Union[Resource, Any]:
        if not self.routes_client:
            self.routes_client = RoutesClient()
        return self.routes_client

    def get(
        self,
        resource: str,
        project: str = None,
        **kwargs
    ) -> Any:
        client = self.client()

        if not project:
            project = self.project

        request = GetRouteRequest(project=project, route=resource)
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
    ) -> List[Route]:
        client = self.client()
        project = self.project

        if kwargs:
            if 'project' in kwargs:
                project = kwargs['project']

        list_request = ListRoutesRequest(project=project)

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
        route_resource: RoutesResource = None,
        **kwargs
    ) -> bool:
        client = self.client()
        project = self.project

        if kwargs:
            if 'project' in kwargs:
                project = kwargs['project']

        if not route_resource:
            raise ValueError('Missing required argument `route_resource`.')

        request = InsertRouteRequest(project=project, route_resource=route_resource)
        return self._make_request(
            client_request=client.insert,
            action='insert',
            resource=resource_name,
            wait=wait,
            request=request,
            operation_type=self.default_operation
        )

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

        request = DeleteRouteRequest(project=project, route=resource_name)
        return self._make_request(
            client_request=client.delete,
            resource=resource_name,
            action='delete',
            wait=wait,
            request=request,
            operation_type=self.default_operation
        )
