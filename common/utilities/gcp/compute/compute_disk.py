from typing import Any, Union

from google.cloud.compute_v1 import (
    GetDiskRequest,
    DeleteDiskRequest,
    ResizeDiskRequest,
    Snapshot,
    DisksClient,
    Disk
)
from googleapiclient.discovery import Resource

from common.constants.google import ResourceType, ClientType
from common.utilities.gcp.cloud_logger import LoggerNames
from .base_compute_api import BaseComputeAPI


class ComputeDiskAPI(BaseComputeAPI):
    """Handles operations related to Compute Engine images in Google Cloud.

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
        self.resource_type = ResourceType.DISK
        self.client_type = ClientType.DISK

    @staticmethod
    def get_source(
        project_id: str,
        zone: str,
        disk_name: str
    ) -> str:
        return f'projects/{project_id}/zones/{zone}/disks/{disk_name}'

    def client(self) -> Union[Resource, Any]:
        if not self.disk_client:
            self.disk_client = DisksClient()
        return self.disk_client

    def get(
        self,
        resource_name: str,
        **kwargs
    ) -> Any:
        client = self.client()

        request = GetDiskRequest(disk=resource_name, project=self.project, zone=self.zone)
        return self._make_request(
            client_request=client.get,
            resource=resource_name,
            action='get',
            wait=False,
            request=request
        )

    def create(
        self,
        resource_name: str,
        wait: bool = True,
        disk_size: int = None,
        source_snapshot: str = None,
        source_image: str = None,
        disk: Disk = None
    ) -> bool:
        client = self.client()

        # Build the request
        if not disk:
            disk = Disk(name=resource_name)
            if disk_size:
                disk.size_gb = disk_size
            if source_snapshot:
                disk.source_snapshot = source_snapshot
            elif source_image:
                disk.source_image = source_image
            else:
                raise ValueError(
                    f"Insert disk request for {resource_name} but no source given. "
                    f"Requires `source_snapshot` or `source_image`"
                )

        request_args = {
            'project': self.project,
            'zone': self.zone,
            'disk_resource': disk,
        }
        return self._make_request(
            client_request=client.insert,
            resource=resource_name,
            action="create",
            wait=wait,
            **request_args
        )

    def create_snapshot(
        self,
        disk_name: str,
        snapshot_name: str,
        project: str = None,
        wait: bool = True,
        zone: str = None
    ) -> bool:
        client = self.client()

        if not project:
            project = self.project
        if not zone:
            zone = self.zone

        snapshot = Snapshot(name=snapshot_name)
        request_args = {
            'project': project,
            'zone': zone,
            'disk': disk_name,
            'snapshot_resource': snapshot
        }
        return self._make_request(
            client_request=client.create_snapshot,
            resource=disk_name,
            action='create snapshot',
            wait=wait,
            **request_args
        )

    def delete(
        self,
        resource_name: str,
        wait: bool = True,
        **kwargs
    ) -> bool:
        client = self.client()

        request = DeleteDiskRequest(disk=resource_name, project=self.project, zone=self.zone)
        return self._make_request(
            client_request=client.delete,
            resource=resource_name,
            action='delete',
            wait=wait,
            request=request
        )

    def update(
        self,
        resource_name: str,
        wait: bool = True,
        **kwargs
    ) -> bool:
        raise NotImplemented

    def resize(
        self,
        resource_name: str,
        wait: bool = True
    ) -> bool:
        client = self.client()
        request = ResizeDiskRequest(disk=resource_name, project=self.project, zone=self.zone)
        return self._make_request(
            client_request=client.resize,
            resource=resource_name,
            action='resize',
            wait=wait,
            request=request
        )
