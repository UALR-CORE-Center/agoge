from typing import Any, List, Union, Tuple

from google.cloud.compute_v1 import (
    GetInstanceRequest,
    ListInstancesRequest,
    StartInstanceRequest,
    StopInstanceRequest,
    DeleteInstanceRequest,
    Instance,
    InstancesClient,
    InsertInstanceRequest,
    ResetInstanceRequest,
    DetachDiskInstanceRequest,
    Disk,
    AttachDiskInstanceRequest
)
from googleapiclient.discovery import Resource

from common.constants.google import ResourceType, ClientType
from common.exceptions import NotFound
from common.utilities.gcp.cloud_logger import LoggerNames
from .base_compute_api import BaseComputeAPI


class ComputeInstanceAPI(BaseComputeAPI):
    """Handles operations related to Compute Engine instances in Google Cloud.

    This class extends the base ComputeAPI to provide methods for creating,
    copying, deleting, and retrieving Compute Engine images.
    """

    def __init__(
        self,
        project: str,
        region: str,
        zone: str,
        log_name: str = LoggerNames.CLOUD_FN
    ) -> None:
        """Initializes the ComputeImageAPI.

        Args:
            log_name (str, optional): Name of the logger to use. Defaults to
                LoggerNames.CLOUD_FN.
        """
        super().__init__(project=project, region=region, zone=zone, log_name=log_name)
        self.resource_type = ResourceType.INSTANCE
        self.client_type = ClientType.INSTANCE

    def client(self) -> Union[Resource, Any]:
        if not self.instance_client:
            self.instance_client = InstancesClient()
        return self.instance_client

    def get(
        self,
        resource_name: str,
        project: str = None,
        zone: str = None,
        **kwargs
    ) -> Any:
        client = self.client()
        if not project:
            project = self.project
        if not zone:
            zone = self.zone

        get_request = GetInstanceRequest(
            instance=resource_name,
            project=project,
            zone=zone
        )
        return self._make_request(
            client_request=client.get,
            action='get',
            resource=resource_name,
            wait=False,
            request=get_request
        )

    def list(
        self,
        wait: bool = True,
        **kwargs
    ) -> List:
        client = self.client()
        project = self.project
        zone = self.zone

        if kwargs:
            if 'project' in kwargs:
                project = kwargs['project']
            if 'zone' in kwargs:
                zone = kwargs['zone']

        list_request = ListInstancesRequest(
            project=project,
            zone=zone,
        )

        resp = self._make_request(
            client_request=client.list,
            action='list',
            resource=None,
            wait=wait,
            request=list_request
        )
        return list(resp)

    def create(
        self,
        resource_name: str,
        wait: bool = True,
        instance_resource: Instance = None,
        **kwargs
    ) -> bool:
        client = self.client()
        project = self.project
        zone = self.zone

        if kwargs:
            if 'project' in kwargs:
                project = kwargs['project']
            if 'zone' in kwargs:
                zone = kwargs['zone']

        if not instance_resource:
            raise ValueError('Missing required Instance object in create request.')

        insert_request = InsertInstanceRequest(
            project=project,
            zone=zone,
            instance_resource=instance_resource
        )
        return self._make_request(
            client_request=client.insert,
            action='create',
            resource=resource_name,
            wait=wait,
            request=insert_request
        )

    def delete(
        self,
        resource_name: str,
        wait: bool = True,
        **kwargs
    ) -> bool:
        client = self.client()
        project = self.project
        zone = self.zone

        if kwargs:
            if 'project' in kwargs:
                project = kwargs['project']
            if 'zone' in kwargs:
                zone = kwargs['zone']

        delete_request = DeleteInstanceRequest(
            instance=resource_name,
            project=project,
            zone=zone
        )
        return self._make_request(
            client_request=client.delete,
            action='delete',
            resource=resource_name,
            wait=wait,
            request=delete_request
        )

    def update(self, resource_name: str, wait: bool = True, **kwargs) -> bool:
        raise NotImplemented("Method not yet implemented")

    def start(
        self,
        resource_name: str,
        wait: bool = True,
        **kwargs
    ) -> bool:
        client = self.client()
        project = self.project
        zone = self.zone

        if kwargs:
            if 'project' in kwargs:
                project = kwargs['project']
            if 'zone' in kwargs:
                zone = kwargs['zone']

        start_request = StartInstanceRequest(
            instance=resource_name,
            project=project,
            zone=zone
        )

        return self._make_request(
            client_request=client.start,
            action='start',
            resource=resource_name,
            wait=wait,
            request=start_request
        )

    def stop(
        self,
        resource_name: str,
        wait: bool = True,
        **kwargs
    ) -> bool:
        client = self.client()
        project = self.project
        zone = self.zone

        if kwargs:
            if 'project' in kwargs:
                project = kwargs['project']
            if 'zone' in kwargs:
                zone = kwargs['zone']

        stop_request = StopInstanceRequest(
            instance=resource_name,
            project=project,
            zone=zone,
        )

        return self._make_request(
            client_request=client.stop,
            action='stop',
            resource=resource_name,
            wait=wait,
            request=stop_request
        )

    def detach_boot_disk(
        self,
        resource_name: str,
        wait: bool = True,
        instance_resource: Instance = None
    ) -> tuple[str, bool]:
        """Finds and detaches boot disk from instance

        Returns:
            tuple[str, bool]: diskName, operation status
        """
        client = self.client()
        project = self.project
        zone = self.zone

        device_name, disk_name = self.get_boot_disk_name(resource_name)
        detach_request = DetachDiskInstanceRequest(
            device_name=device_name,
            instance=resource_name,
            project=project,
            zone=zone
        )
        return disk_name, self._make_request(
            client_request=client.detach_disk,
            action='detach disk',
            resource=resource_name,
            wait=wait,
            request=detach_request
        )

    def attach_boot_disk(
        self,
        resource_name: str,
        wait: bool = True,
        disk_resource: Disk = None
    ) -> bool:
        """Attach boot disk to instance"""
        client = self.client()
        project = self.project
        zone = self.zone

        attach_disk_request = AttachDiskInstanceRequest(
            instance=resource_name,
            attached_disk_resource=disk_resource,
            project=project,
            zone=zone
        )
        return self._make_request(
            client_request=client.attach_disk,
            action='attach disk',
            resource=resource_name,
            wait=wait,
            request=attach_disk_request
        )

    def get_boot_disk_name(
        self,
        resource_name: str,
    ) -> Tuple[str, str]:
        """Extracts boot disk from `Instance.disks` and returns deviceName and diskName

        Return:
            tuple[str, str]: deviceName, diskName
        """
        instance_resource = self.get(resource_name=resource_name)
        attached_disks = instance_resource.disks
        if attached_disks:
            for disk in attached_disks:
                if disk.boot:
                    disk_name = disk.source.split("/")[-1]
                    return disk.device_name, disk_name
            raise NotFound(f'No boot disk found for server instance {resource_name}. Does it exist?')
        raise NotFound(f'No attached disks found for server instance {resource_name}.')

    def reset(
        self,
        resource_name: str,
        wait: bool = True,
        **kwargs
    ) -> bool:
        client = self.client()
        project = self.project
        zone = self.zone

        if kwargs:
            if 'project' in kwargs:
                project = kwargs['project']
            if 'zone' in kwargs:
                zone = kwargs['zone']

        reset_request = ResetInstanceRequest(
            instance=resource_name,
            project=project,
            zone=zone,
        )
        return self._make_request(
            client_request=client.reset,
            action='reset',
            resource=resource_name,
            wait=wait,
            request=reset_request
        )

# [ eof ]
