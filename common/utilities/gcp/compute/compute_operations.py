import time
from typing import Any, Union

from google.api_core.exceptions import DeadlineExceeded, GoogleAPICallError, ServiceUnavailable
from google.cloud.compute_v1 import (
    Error,
    Operation,
    GlobalOperationsClient,
    ZoneOperationsClient,
    RegionOperationsClient,
    WaitGlobalOperationRequest,
    WaitRegionOperationRequest,
    WaitZoneOperationRequest
)
from googleapiclient.discovery import Resource

from common.constants.google import ClientType, OperationType
from common.utilities.gcp.cloud_logger import LoggerNames, Logger
from .quota_failure import ComputeQuotaFailure, classify_compute_api_error, classify_compute_operation_error


class ComputeOperationsAPI:
    def __init__(
        self,
        project: str,
        region: str,
        zone: str,
        log_name: str = LoggerNames.CLOUD_FN
    ) -> None:
        """Initializes the ComputeOperationsAPI.

        Args:
            log_name (str, optional): Name of the logger to use. Defaults to
                LoggerNames.CLOUD_FN.
        """
        self.class_name = self.__class__.__name__
        self.project = project
        self.region = region
        self.zone = zone
        self.operations_clients = {}
        self.client_type = ClientType.OPERATIONS
        self.logger = Logger(log_name=log_name, class_name=self.class_name)
        self.operations = {
            OperationType.GLOBAL: WaitGlobalOperationRequest,
            OperationType.REGION: WaitRegionOperationRequest,
            OperationType.ZONE: WaitZoneOperationRequest,
        }

    def client(self, operation_type: OperationType = OperationType.ZONE) -> Union[Resource, Any]:
        if operation_type not in self.operations_clients:
            client_types = {
                OperationType.GLOBAL: GlobalOperationsClient,
                OperationType.REGION: RegionOperationsClient,
                OperationType.ZONE: ZoneOperationsClient,
            }
            self.operations_clients[operation_type] = client_types[operation_type]()
        return self.operations_clients[operation_type]

    def wait(
        self,
        operation_id: Union[int, str],
        type_: OperationType = OperationType.ZONE,
        wait_seconds: int = 150,
        action: str = None,
        *,
        project: str = None,
        location: str = None,
    ) -> bool:
        """
        Args:
            operation_id (int): The operation being waited on
            type_ (OperationType): The type of wait, either zone, region, or global. Defaults to zone
            wait_seconds (int): The number of seconds to wait before returning.
            action (str): Optional descriptive string for verbose log messaging

        Returns: True if the operation complete, and False if there is a timeout.
        """
        client = self.client(operation_type=type_)
        request_project = project or self.project
        request_args = {'project': request_project}
        if type_ == OperationType.REGION:
            request_args['region'] = location or self.region
        elif type_ == OperationType.ZONE:
            request_args['zone'] = location or self.zone
        request = self.operations[type_](operation=str(operation_id), **request_args)
        context = {'project': request_project, 'operation_id': operation_id, 'operation_type': type_.name}
        deadline = time.monotonic() + wait_seconds
        self.logger.info(f'{self.class_name}:{operation_id} - Waiting for operation ID.', **context)
        last_error = None
        while (remaining := deadline - time.monotonic()) > 0:
            try:
                operation = client.wait(request=request, retry=None, timeout=min(30, remaining))
            except (DeadlineExceeded, ServiceUnavailable):
                pass
            except GoogleAPICallError as error:
                failure = classify_compute_api_error(error, action='wait', **context)
                if failure is None:
                    raise
                if failure.category != 'rate':
                    self.logger.error(str(failure), **failure.as_dict())
                    raise failure from error
                last_error = (failure, error)
            else:
                last_error = None
                if operation.status == Operation.Status.DONE.value:
                    try:
                        return self._parse_errors(operation, action=action, **context)
                    except ComputeQuotaFailure as failure:
                        self.logger.error(str(failure), **failure.as_dict())
                        raise
            # A nonterminal operation or a throttled poll may return immediately.
            # Polls are safe to repeat, but their deadline also bounds SDK retries.
            if (remaining := deadline - time.monotonic()) > 0:
                time.sleep(min(1, remaining))

        if last_error:
            failure, error = last_error
            self.logger.error(str(failure), **failure.as_dict())
            raise failure from error
        self.logger.error(
            f"{self.class_name}:{operation_id} - Operation timed out after {wait_seconds} seconds.",
            operation_id=operation_id,
            action=action
        )
        return False

    def _parse_errors(self, operation: Operation, **context) -> bool:
        """A DONE operation may contain structured errors without an HTTP message."""
        if failure := classify_compute_operation_error(operation, **context):
            raise failure
        error_messages = self._format_error_message(operation.error) or operation.http_error_message
        if error_messages or operation.http_error_status_code >= 400:
            raise RuntimeError(f'Operation failed with errors: {error_messages or operation.http_error_status_code}')
        return True

    @staticmethod
    def _format_error_message(error: Error) -> str:
        error_messages = [
            f'{err.code}: {err.message}'
            for err in error.errors
        ]
        return ", ".join(error_messages)
