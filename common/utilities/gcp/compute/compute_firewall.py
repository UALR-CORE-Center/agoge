from typing import Any, Union, List

from google.cloud.compute_v1 import (
    Firewall,
    FirewallsClient,
    GetFirewallRequest,
    InsertFirewallRequest,
    DeleteFirewallRequest,
    ListFirewallsRequest,
    PatchFirewallRequest
)
from googleapiclient.discovery import Resource

from common.exceptions import BadRequest
from common.constants.google import ResourceType, ClientType, OperationType
from common.utilities.gcp.cloud_logger import LoggerNames
from .base_compute_api import BaseComputeAPI


class ComputeFirewallsAPI(BaseComputeAPI):
    """Handles operations related to Compute Firewalls in Google Cloud.

    This class extends the base ComputeAPI to provide methods for creating,
    copying, deleting, and retrieving Compute Engine firewall rules.
    """

    def __init__(
        self,
        project: str,
        region: str,
        zone: str,
        log_name: str = LoggerNames.CLOUD_FN
    ) -> None:
        """Initializes the ComputeFirewallsAPI.

        Args:
            log_name (str, optional): Name of the logger to use. Defaults to
                LoggerNames.CLOUD_FN.
        """
        super().__init__(project=project, region=region, zone=zone, log_name=log_name)
        self.resource_type = ResourceType.FIREWALLS
        self.client_type = ClientType.FIREWALLS

    def network(self, network: str) -> str:
        return f'projects/{self.project}/global/networks/{network}'

    def client(self) -> Union[Resource, Any]:
        if not self.firewalls_client:
            self.firewalls_client = FirewallsClient()
        return self.firewalls_client

    def get(
        self,
        resource_name: str,
        **kwargs
    ) -> Any:
        client = self.client()

        request = GetFirewallRequest(firewall=resource_name, project=self.project)
        return self._make_request(
            client_request=client.get,
            resource=resource_name,
            action='get',
            wait=False,
            request=request,
            operation_type=OperationType.GLOBAL
        )

    def list(
        self,
        wait: bool = False,
        filter_: str = None,
        **kwargs
    ) -> List:
        client = self.client()
        project = self.project

        if kwargs:
            if 'project' in kwargs:
                project = kwargs['project']

        list_request = ListFirewallsRequest(
            project=project,
        )

        if filter_:
            list_request.filter = filter_

        resp = self._make_request(
            client_request=client.list,
            action='list',
            resource='firewall',
            wait=wait,
            request=list_request,
            operation_type=OperationType.GLOBAL
        )
        return list(resp)

    def create(
        self,
        resource_name: str,
        wait: bool = True,
        firewall_resource: Firewall = None,
        **kwargs
    ) -> bool:
        if not firewall_resource:
            raise BadRequest('Missing required firewall_resource argument')

        client = self.client()
        project = self.project

        if kwargs:
            if 'project' in kwargs:
                project = kwargs['project']

        request = InsertFirewallRequest(firewall_resource=firewall_resource, project=project)
        return self._make_request(
            client_request=client.insert,
            resource=resource_name,
            action='insert',
            wait=wait,
            request=request,
            operation_type=OperationType.GLOBAL
        )

    def delete(
        self,
        resource_name: str,
        wait: bool = True,
        **kwargs
    ) -> bool:
        client = self.client()

        request = DeleteFirewallRequest(firewall=resource_name, project=self.project)
        return self._make_request(
            client_request=client.delete,
            resource=resource_name,
            action='delete',
            wait=wait,
            request=request,
            operation_type=OperationType.GLOBAL
        )

    def update(
        self,
        resource_name: str,
        wait: bool = True,
        **kwargs
    ) -> bool:
        raise NotImplemented

    def patch(
        self,
        resource_name: str,
        wait: bool = True,
        firewall_body: Any = None,
        **kwargs
    ) -> bool:
        client = self.client()
        project = self.project

        if kwargs:
            if 'project' in kwargs:
                project = kwargs['project']

        if not firewall_body:
            raise BadRequest('Missing value for required arg `firewall_body`!')

        request = PatchFirewallRequest(
            firewall=resource_name,
            project=project,
            firewall_resource=firewall_body
        )
        return self._make_request(
            client_request=client.patch,
            resource=resource_name,
            action='patch',
            wait=wait,
            request=request,
            operation_type=OperationType.GLOBAL
        )

