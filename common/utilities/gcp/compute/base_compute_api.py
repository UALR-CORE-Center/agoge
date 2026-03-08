from typing import List, Union, Any

from abc import abstractmethod

from google.api_core.exceptions import GoogleAPICallError, AlreadyExists
from google.api_core.exceptions import ResourceExhausted as GoogleResourceExhausted
from google.api_core.exceptions import Conflict as GoogleConflict
from google.api_core.exceptions import NotFound as GoogleNotFound
from google.api_core.exceptions import BadRequest as GoogleBadRequest
from googleapiclient.discovery import Resource

from common.constants.google import ResourceType, OperationType
from common.constants.build_constants import BuildConstants
from common.exceptions import Conflict, BaseAgogeException, NotFound, BadRequest, ResourceExhausted
from .compute_operations import ComputeOperationsAPI
from ..cloud_logger import LoggerNames, Logger


class BaseComputeAPI:
    """Base class for interacting with Google Compute Engine resources.

    This class provides common functionality for creating, deleting, updating,
    and retrieving Compute Engine resources. Subclasses should provide concrete
    implementations for resource-specific operations.
    """

    ALLOWED_GOOGLE_MACHINE_TYPES = ["n1", "n2", "e2"]
    GOOGLE_MACHINE_TYPES = BuildConstants.GoogleMachineTypes.ALL.value
    SOURCE_IMAGE_PROJECT = "ualr-cybersecurity"
    INITIAL_TIMESTAMP = '2000-01-01T00:00:00.000'
    DEFAULT_MAX_SNAPSHOTS = 5
    DEFAULT_MAX_AUTO = 3
    MAX_RETRY_COUNT = 5
    MAX_TIMEOUT_ITERATIONS = 5
    MAX_IMAGE_BUILD_RETRY = 10
    SERVICE_ACCOUNT_CONFIG = [{
        'email': 'default',
        'scopes': [
            'https://www.googleapis.com/auth/devstorage.read_write',
            'https://www.googleapis.com/auth/logging.write'
        ]
    }]

    def __init__(
        self,
        project: str,
        region: str,
        zone: str,
        log_name: str = LoggerNames.CLOUD_FN
    ) -> None:
        """Initializes the ComputeAPI base class.

        Args:
            log_name (str, optional): The name of the logger to use. Defaults to
                LoggerNames.CLOUD_FN.
        """
        self.class_name = self.__class__.__name__
        self.log_name = log_name
        self.operation_types = OperationType
        self.resource_type = ResourceType.INSTANCE
        self.project = project
        self.region = region
        self.zone = zone
        self.cloud_ops_mgr = ComputeOperationsAPI(self.project, self.region, self.zone, log_name=self.log_name)
        self.logger = Logger(log_name=self.log_name, class_name=self.class_name)

        self.disk_client = None
        self.family_views_client = None
        self.instance_client = None
        self.images_client = None
        self.snapshot_client = None
        self.machine_type_client = None
        self.firewalls_client = None
        self.networks_client = None
        self.subnetworks_client = None
        self.routes_client = None
        self.operations_client = None

    @abstractmethod
    def client(self, **kwargs) -> Union[Resource, Any]:
        raise NotImplemented

    @abstractmethod
    def get(
        self,
        resource: str,
        project: str = None,
        **kwargs,
    ) -> dict:
        """Abstract method to retrieve a GCE resource.

        Subclasses must implement this method to provide the actual retrieval
        logic using the Google Compute client.

        Args:
            resource (str): The name of the resource to retrieve.
            project (str, optional): The project ID from which to retrieve
                the resource. If None, uses the default from the environment.
            **kwargs: Additional parameters that subclasses may require.

        Returns:
            dict: The resource data.
        """
        raise NotImplemented

    @abstractmethod
    def create(
        self,
        resource_name: str,
        wait: bool = True,
        **kwargs
    ) -> bool:
        """Abstract method to create a GCE resource.

        Subclasses must implement this method to provide the actual creation
        logic using the Google Compute client.

        Args:
            resource_name (str): The name of the resource to create.
            body (dict): A dictionary containing the resource configuration.
            wait (bool, optional): Whether to wait for the operation to complete.

        Returns:
            bool: True if the resource creation was successful, False otherwise.
        """
        raise NotImplemented

    @abstractmethod
    def delete(
        self,
        resource_name: str,
        wait: bool = True,
        **kwargs
    ) -> bool:
        """Abstract method to delete a GCE resource.

        Subclasses must implement this method to provide the actual deletion
        logic using the Google Compute client.

        Args:
            resource_name (str): The name of the resource to delete.
            wait (bool, optional): Whether to wait for the operation to
                complete. Defaults to True.
            **kwargs: Additional parameters that subclasses may require.

        Returns:
            bool: True if deletion was successful, False otherwise.
        """
        raise NotImplemented

    @abstractmethod
    def update(
        self,
        resource_name: str,
        wait: bool = True,
        **kwargs,
    ) -> bool:
        """Updates a GCE resource.

        This is a public wrapper around the abstract `_update` method, adding
        logging and pre-processing where needed.

        Args:
            resource_name (str): The name of the resource to update.
            wait (bool, optional): Whether to wait for the update operation
                to complete. Defaults to True.

        Returns:
            bool: True if the update operation succeeded (and optionally
            finished), False otherwise.
        """
        raise NotImplemented

    def _make_request(
        self,
        client_request: Any,
        action: str,
        resource: str = None,
        wait: bool = True,
        operation_type: OperationType = OperationType.ZONE,
        **kwargs
    ) -> Any:
        resource_type = self.resource_type.name
        log_args = {
            'resource': str(resource),
            'operation_type': operation_type.name,
            'action': action,
            'resource_type': resource_type
        }

        self.logger.info(
            f'{self.class_name}:{resource} - action ({action}) called for {resource_type} {resource}',
            **log_args
        )
        try:
            operation = client_request(**kwargs)
            if wait:
                return self.wait_for_operation(operation.name, operation_type)
            return operation
        except AlreadyExists:
            self.logger.error(f'Error {action} for {resource_type} {resource}', **log_args)
            raise Conflict(f"Attempt to {action} {resource_type} failed. {resource_type}, {resource}, already exists!")
        except GoogleNotFound:
            if resource:
                self.logger.error(
                    f'Error {action} for {resource_type}, {resource}, in project {self.project}.',
                    **log_args
                )
                raise NotFound(message=f"The requested resource or endpoint, {resource}, was not found.")
            else:
                self.logger.error(f'Error {action} for {resource_type}', **log_args)
                raise NotFound(message=f"The requested resource/s not found.")
        except GoogleBadRequest as e:
            self.logger.error(
                f"{self.class_name}:{resource} - {resource_type} is still building or request is malformed. "
                f"Details: {str(e)}",
                **log_args
            )
            raise BadRequest
        except GoogleResourceExhausted as e:
            self.logger.error(f'QUOTA exceeded for {resource_type}', details=str(e), **log_args)
            raise ResourceExhausted
        except GoogleAPICallError as e:
            if '409' in str(e):
                self.logger.error(f'Error {action} for {resource_type} {resource}', resource=resource)
                raise Conflict(f"Attempt to {action} {resource_type} failed. "
                               f"{resource_type}, {resource}, already exists!")
            else:
                self.logger.error(f"Error {action}: {e}", **log_args)
                raise BaseAgogeException(str(e))

    def wait_for_operation(
        self,
        operation_id,
        operation_type: OperationType = OperationType.ZONE,
        wait_seconds: int = 150
    ) -> bool:
        """Waits for a long-running operation to complete.

        Uses the CloudOperationsManager to poll for completion of the specified
        Compute Engine operation.

        Args:
            operation_id: The ID of the operation to wait on.
            operation_type (OperationType, optional): The scope of the
                operation (e.g., ZONE, REGION, GLOBAL). Defaults to OperationType.ZONE.
            wait_seconds (int, optional): Maximum time in seconds to wait for
                completion. Defaults to 150.

        Returns:
            bool: True if the operation completed successfully within the
            specified time, False otherwise.
        """
        return self.cloud_ops_mgr.wait(operation_id, type_=operation_type, wait_seconds=wait_seconds)
