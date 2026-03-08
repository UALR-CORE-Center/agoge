from typing import Any, Union
from google.api_core.exceptions import DeadlineExceeded
from google.api_core.exceptions import ResourceExhausted as GoogleResourceExhausted
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

from common.exceptions import ResourceExhausted
from common.constants.google import ClientType, OperationType, OperationStatus
from common.utilities.gcp.cloud_logger import LoggerNames, Logger


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
        self.operations_client = None
        self.client_type = ClientType.OPERATIONS
        self.logger = Logger(log_name=log_name, class_name=self.class_name)
        self.operations = {
            OperationType.GLOBAL: WaitGlobalOperationRequest,
            OperationType.REGION: WaitRegionOperationRequest,
            OperationType.ZONE: WaitZoneOperationRequest,
        }

    def client(self, operation_type: OperationType = OperationType.ZONE) -> Union[Resource, Any]:
        if not self.operations_client:
            if operation_type == OperationType.GLOBAL:
                self.operations_client = GlobalOperationsClient()
            elif operation_type == OperationType.REGION:
                self.operations_client = RegionOperationsClient()
            else:
                self.operations_client = ZoneOperationsClient()
        return self.operations_client

    def wait(
        self,
        operation_id: Union[int, str],
        type_: OperationType = OperationType.ZONE,
        wait_seconds: int = 150,
        action: str = None
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
        request_method = self.operations.get(type_)

        request_args = {'project': self.project}
        if type_ == OperationType.REGION:
            request_args['region'] = self.region
        elif type_ == OperationType.ZONE:
            request_args['zone'] = self.zone

        i = 0
        max_wait_iteration = round(wait_seconds / 30)
        while i < max_wait_iteration:
            try:
                self.logger.info(
                    f"{self.class_name}:{operation_id} - Waiting for operation ID.",
                    attempt=i,
                    operation_id=operation_id
                )
                request = request_method(operation=operation_id, **request_args)
                operation = client.wait(request=request)
                if operation.status != Operation.Status.DONE.value:
                    continue
                return self._parse_errors(operation)
            except (GoogleResourceExhausted, ResourceExhausted) as e:
                if isinstance(e, ResourceExhausted):
                    self.logger.error(e.message, operation_id=operation_id)
                    raise

                self.logger.error(str(e), operation_id=operation_id)
                raise ResourceExhausted(str(e))
            except DeadlineExceeded as e:
                i += 1
                if not action:
                    msg = (f"{self.class_name}:{operation_id} - Response timeout for operation ID. "
                           f"Trying again")
                else:
                    msg = (f"{self.class_name}:{operation_id} - Response timeout {action} for operation"
                           f"ID. Trying again")
                self.logger.warning(msg, operation_id=operation_id, details=str(e))
                pass
            except RuntimeError as e:
                self.logger.error(f'{self.class_name}:{operation_id} - {e}')
                raise
            except Exception as e:
                i += 1
                self.logger.error(f"{self.class_name}:{operation_id} - Exception caught when "
                                  f"attempting to wait for operation completion. {e}",
                                  attempt=i)
                pass

        self.logger.error(
            f"{self.class_name}:{operation_id} - Operation timed out after {wait_seconds} seconds.",
            operation_id=operation_id,
            action=action
        )
        return False

    def _parse_errors(self, operation: Operation) -> bool:
        """Check for any exceptions that might need to be manually thrown"""
        if not operation.http_error_message:
            return True

        error_messages = self._format_error_message(operation.error)
        if 'QUOTA_EXCEEDED' in error_messages:
            raise ResourceExhausted(error_messages)
        else:
            raise RuntimeError(f'Operation failed with errors: {error_messages}')

    @staticmethod
    def _format_error_message(error: Error) -> str:
        error_messages = [
            f'{err.code}: {err.message}'
            for err in error.errors
        ]
        return ", ".join(error_messages)
