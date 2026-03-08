from google.cloud.compute_v1 import (
    ImagesClient,
    ImageFamilyViewsClient,
    ListImagesRequest,
    GetImageRequest,
    GetImageFamilyViewRequest,
    InsertImageRequest,
    DeleteImageRequest,
    Image
)
from googleapiclient.discovery import Resource
from typing import Any, List, Union

from common.constants.google import ResourceType, ClientType, ImageSource, OperationType
from common.exceptions import OperationTimeout, NotFound
from common.utilities.gcp.cloud_logger import LoggerNames
from common.constants.build_constants import BuildConstants
from .base_compute_api import BaseComputeAPI


class ComputeImageAPI(BaseComputeAPI):
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
        self.resource_type = ResourceType.IMAGE
        self.client_type = ClientType.IMAGE

    def client(
        self,
        client_type: ClientType = ClientType.IMAGE,
    ) -> Union[Resource, ImagesClient, ImageFamilyViewsClient]:
        if client_type == ClientType.IMAGE_FAMILY:
            if not self.family_views_client:
                self.family_views_client = ImageFamilyViewsClient()
            return self.family_views_client
        else:
            if not self.images_client:
                self.images_client = ImagesClient()
            return self.images_client

    @staticmethod
    def self_link(image_name: str, project: str) -> str:
        return (
            f"https://www.googleapis.com/compute/v1/projects/{project}/global/images/{image_name}"
        )

    def copy(
        self,
        resource_name: str,
        source_image_project: str,
        delete_previous: bool = False
    ) -> None:
        """Copies an image from the specified source project to the current project.

        Optionally deletes a previously existing image with the same name before
        creating the new image.

        Args:
            resource_name (str): The name of the image to create or overwrite.
            source_image_project (str): The project ID from where the source
                image is copied.
            delete_previous (bool, optional): If True, attempts to delete any
                existing image with the same name prior to copying. Defaults to False.

        Raises:
            OperationTimeout: If the deletion of an existing image times out,
                or the new image creation times out.
        """
        if delete_previous:
            if not self.delete(resource_name, wait=True):
                msg = f"{self.class_name}:{resource_name} - Timeout waiting for image to delete."
                self.logger.error(msg)
                raise OperationTimeout(message=msg)

        image = self.get(resource=resource_name, project=source_image_project)

        if not self.create(resource_name, source=image.selfLink, source_type=ImageSource.IMAGE):
            raise OperationTimeout

    def list(
        self,
        project: str = None,
        request_filter: str = None
    ) -> List:
        """
        List images in the project. If any error occurs during the list request,
        an empty list is returned instead of raising an exception.
        """
        client = self.client(ClientType.IMAGE)

        # Construct ListImageRequest object
        project = project or self.project
        list_request = ListImagesRequest(project=project)
        if request_filter:
            list_request.filter = request_filter

        images = self._make_request(
            client_request=client.list,
            resource=None,
            action='list',
            wait=False,
            request=list_request
        )
        return list(images)

    def get(
        self,
        resource: str,
        project: str = None,
        zone: str = None,
        **kwargs
    ) -> Any:
        """Retrieves a Compute Engine image from a specific project.

        Args:
            resource (str): The name of the image to retrieve.
            project (str, optional): The project ID from which the image is
                retrieved. If None, defaults to the project in the environment
                configuration.
            zone (str, optional): The zone ID for the image. If None, defaults to the zone
                in the environment configuration

        Returns:
            Any: A dictionary representing the image resource.

        Raises:
            NotFound: If the requested image could not be found.
        """
        project = project or self.project
        zone = zone or self.zone

        def _build_request(p: str):
            if kwargs.get("family"):
                return GetImageFamilyViewRequest(family=resource, project=p, zone=zone)
            return GetImageRequest(image=resource, project=p)

        client_type = (
            ClientType.IMAGE_FAMILY if "family" in kwargs else self.client_type
        )
        client = self.client(client_type=client_type)

        try:
            self.logger.debug(f"First attempt: image request for {resource} in project {project}.")
            return self._make_request(
                client_request=client.get,
                resource=resource,
                action="get",
                wait=False,
                request=_build_request(project),
            )
        except NotFound as primary_exc:
            # Try the shared resource project
            self.logger.debug(f"Second attempt: image request for {resource} "
                              f"in project {BuildConstants.SharedResourceProjects.MAIN_SHARED_RESOURCE_PROJECT}.")
            shared_resource_project = BuildConstants.SharedResourceProjects.MAIN_SHARED_RESOURCE_PROJECT
            try:
                return self._make_request(
                    client_request=client.get,
                    resource=resource,
                    action="get",
                    wait=False,
                    request=_build_request(shared_resource_project),
                )
            except NotFound:
                # still not found – fall through to re-raise original
                self.logger.error(f"Could not find the compute image {resource} in either project {project} or the "
                                  f"shared resource project {shared_resource_project}.")
                pass
            raise primary_exc

    def create(
        self,
        resource_name: str,
        wait: bool = True,
        source: str = None,
        source_type: ImageSource = ImageSource.SNAPSHOT,
        image_resource: Image = None,
        **kwargs
    ) -> bool:
        """Creates a new Compute Engine image.

        This method attempts to create an image up to MAX_IMAGE_BUILD_RETRY times.
        If the image already exists (HTTP 409), it raises a Conflict exception.

        Args:
            resource_name (str): Name of the image to create.
            wait (bool, optional): Whether to wait for the creation operation
                to complete before returning. Defaults to True.
            source: (str, optional): Source of compute resource to create the image.
            source_type: (ImageSource): Enumerator to define what type of source to expect.
            image_resource: (Image, optional): Image Proto object to use instead

        Returns:
            bool: True if the image was successfully created (and optionally
            waited for), False otherwise.

        Raises:
            Conflict: If the image already exists.
        """
        client = self.client(ClientType.IMAGE)
        disk_size_gb = None
        description = f"{str(self.project).capitalize()} production image"
        project = self.project

        if kwargs:
            if 'disk_size_gb' in kwargs:
                disk_size_gb = kwargs['disk_size_gb']
            if 'description' in kwargs:
                description = kwargs['description']
            if 'project' in kwargs:
                project = kwargs['project']

        if not image_resource:
            # Build Image object
            image_resource = Image(name=resource_name, description=description)

            if disk_size_gb:
                image_resource.disk_size_gb = disk_size_gb
            if source:
                if source_type == ImageSource.IMAGE:
                    image_resource.source_image = str(source)
                elif source_type == ImageSource.SNAPSHOT:
                    image_resource.source_snapshot = str(source)
                elif source_type == ImageSource.DISK:
                    image_resource.source_disk = str(source)
                else:
                    raise ValueError(
                        f"Unsupported source for image object {source}. Must be one of "
                        f"[{ImageSource.SNAPSHOT.name}, {ImageSource.IMAGE.name}, {ImageSource.DISK.name}"
                    )

        # Build request object
        image_request = InsertImageRequest(
            project=project,
            image_resource=image_resource
        )

        # Send image insert request
        for attempt in range(self.MAX_IMAGE_BUILD_RETRY):
            try:
                return self._make_request(
                    client_request=client.insert,
                    action='create',
                    resource=resource_name,
                    wait=wait,
                    request=image_request
                )
            except BrokenPipeError:
                continue
        self.logger.error(
            f'{self.class_name}:{resource_name} - Failed to create image after '
            f'{self.MAX_IMAGE_BUILD_RETRY} attempts.'
        )
        return False

    def update(
        self,
        resource_name: str,
        wait: bool = True,
        **kwargs
    ) -> bool:
        """Updates an existing Compute Engine image.

        Currently not implemented.

        Args:
            resource_name (str): The name of the image to update.
            wait (bool, optional): Whether to wait for the update operation
                to complete before returning. Defaults to True.

        Returns:
            bool: False by default (indicating not implemented).
        """
        pass

    def delete(
        self,
        resource_name: str,
        **kwargs
    ) -> bool:
        """Deletes a Compute Engine image.

        Attempts to delete the specified image up to MAX_RETRY_COUNT times.

        Args:
            resource_name (str): The name of the image to delete.
            **kwargs: Additional arguments.

        Returns:
            bool: True if the image was successfully deleted, False otherwise.

        Raises:
            NotFound: If the image does not exist.
        """
        client = self.client(client_type=self.client_type)
        max_retry_count = self.MAX_RETRY_COUNT
        project = self.project

        if kwargs:
            if 'max_retry_count' in kwargs:
                max_retry_count = kwargs['max_retry_count']
            if 'project' in kwargs:
                project = kwargs['project']

        delete_request = DeleteImageRequest(
            image=resource_name,
            project=project
        )

        for attempt in range(max_retry_count):
            try:
                return self._make_request(
                    client_request=client.delete,
                    action='delete',
                    resource=resource_name,
                    wait=True,
                    operation_type=OperationType.GLOBAL,
                    request=delete_request
                )
            except BrokenPipeError:
                continue

        self.logger.error(
            f"{self.class_name}:{resource_name} - Failed to delete image after "
            f"{self.MAX_RETRY_COUNT} attempts.",
            resource=resource_name
        )
        return False
