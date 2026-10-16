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
    AttachDiskInstanceRequest,
    Items,
    Metadata,
    SetMetadataInstanceRequest,
    GetGuestAttributesInstanceRequest
)
from google.api_core.exceptions import NotFound as GoogleNotFound
from googleapiclient.discovery import Resource

from common.constants.google import ResourceType, ClientType
from common.exceptions import NotFound, PreconditionFailed
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

    def set_metadata(
        self,
        resource_name: str,
        items: dict = None,
        remove: list = None,
        wait: bool = True,
        **kwargs
    ) -> bool:
        """Merges `items` into the instance metadata and drops the keys in `remove`.

        Every other existing key is preserved. The write is guarded by the
        instance's current metadata fingerprint; on a 412 (another writer got
        there first) the instance is re-read once and the merge retried.
        """
        client = self.client()
        project = kwargs.get('project', self.project)
        zone = kwargs.get('zone', self.zone)
        items = items or {}
        remove = set(remove or [])

        for attempt in range(2):
            instance = self.get(resource_name=resource_name, project=project, zone=zone)
            merged = {item.key: item.value for item in instance.metadata.items}
            merged.update(items)
            for key in remove:
                merged.pop(key, None)

            metadata_request = SetMetadataInstanceRequest(
                instance=resource_name,
                project=project,
                zone=zone,
                metadata_resource=Metadata(
                    fingerprint=instance.metadata.fingerprint,
                    items=[Items(key=key, value=value) for key, value in merged.items()]
                )
            )
            try:
                return self._make_request(
                    client_request=client.set_metadata,
                    action='set metadata',
                    resource=resource_name,
                    wait=wait,
                    request=metadata_request
                )
            except PreconditionFailed:
                if attempt:
                    raise
                self.logger.warning(
                    f'{self.class_name}:{resource_name} - metadata fingerprint stale; re-reading and retrying once'
                )

# [ eof ]

    def get_guest_attributes(
        self,
        resource_name: str,
        query_path: str,
        **kwargs
    ) -> dict:
        """Returns the guest attributes under `query_path` (e.g. `agoge-ctf/`) as `{key: value}`.

        Returns an empty dict when the VM has written nothing under the path yet. GCE answers that case
        with a 404, the same status as a missing instance, so on a 404 the instance is re-read: a missing
        instance still raises NotFound rather than looking like "no answer yet" to a poller.
        """
        client = self.client()
        project = kwargs.get('project', self.project)
        zone = kwargs.get('zone', self.zone)

        def fetch(request):
            # The 404 is caught here, not in _make_request, so routine polling of an empty path logs no error.
            try:
                return client.get_guest_attributes(request=request)
            except GoogleNotFound:
                return None

        request = GetGuestAttributesInstanceRequest(
            instance=resource_name,
            project=project,
            zone=zone,
            query_path=query_path
        )
        attributes = self._make_request(
            client_request=fetch,
            action='get guest attributes',
            resource=resource_name,
            wait=False,
            request=request
        )
        if attributes is None:
            self.get(resource_name=resource_name, project=project, zone=zone)
            return {}
        return {entry.key: entry.value for entry in attributes.query_value.items}
