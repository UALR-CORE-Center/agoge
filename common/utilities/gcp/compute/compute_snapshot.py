from typing import Any, List, Union

from google.cloud.compute_v1 import (
    Snapshot,
    SnapshotsClient,
    InsertSnapshotRequest,
    DeleteSnapshotRequest,
    GetSnapshotRequest,
    ListSnapshotsRequest
)
from googleapiclient.discovery import Resource

from common.constants.google import ResourceType, ClientType, OperationType
from common.utilities.gcp.cloud_logger import LoggerNames
from .base_compute_api import BaseComputeAPI


class ComputeSnapshotAPI(BaseComputeAPI):
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
        self.resource_type = ResourceType.SNAPSHOT
        self.client_type = ClientType.SNAPSHOT

    def client(self) -> Union[Resource, Any]:
        if not self.snapshot_client:
            self.snapshot_client = SnapshotsClient()
        return self.snapshot_client

    def get(
        self,
        resource_name: str,
        **kwargs
    ) -> dict:
        client = self.client()
        project = self.project

        if kwargs:
            if 'project' in kwargs:
                project = kwargs['project']

        get_request = GetSnapshotRequest(
            project=project,
            snapshot=resource_name
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
        filters: str = None,
        **kwargs
    ) -> List:
        client = self.client()

        project = self.project

        if kwargs:
            if 'project' in kwargs:
                project = kwargs['project']

        list_request = ListSnapshotsRequest(project=project)
        if filters:
            list_request.filter = filters

        return self._make_request(
            client_request=client.list,
            action='list',
            wait=False,
            request=list_request
        )

    def create(
        self,
        resource_name: str,
        wait: bool = True,
        source: str = None,
        **kwargs
    ) -> bool:
        client = self.client()
        project = self.project

        if kwargs:
            if 'project' in kwargs:
                project = kwargs['project']

        if not source:
            raise ValueError("Missing value for snapshot source")

        snapshot = Snapshot(name=resource_name, source_disk=source)
        insert_request = InsertSnapshotRequest(
            project=project,
            snapshot_resource=snapshot
        )

        # Make the request
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

        if kwargs:
            if 'project' in kwargs:
                project = kwargs['project']

        delete_request = DeleteSnapshotRequest(
            project=project,
            snapshot=resource_name
        )

        return self._make_request(
            client_request=client.delete,
            action='delete',
            resource=resource_name,
            wait=wait,
            operation_type=OperationType.GLOBAL,
            request=delete_request
        )

    def update(self, resource_name: str, wait: bool = True, **kwargs) -> bool:
        raise NotImplemented

    @staticmethod
    def get_source(project: str, snapshot_name: str) -> str:
        return f'projects/{project}/global/snapshots/{snapshot_name}'
