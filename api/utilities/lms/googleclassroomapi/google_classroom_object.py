import random
import time
import googleapiclient.discovery
from abc import ABC, abstractmethod
from googleapiclient.errors import HttpError

from common.utilities.gcp.cloud_logger import LoggerNames, Logger
from .exceptions import *


class GoogleClassroomObject(ABC):
    """Manages API requests with exceptions handling and Timeout backoffs

    Attributes:
        _client: The Google API service client
        max_attempts: Max number of request attempts to make in case of Timeout errors
    """
    def __init__(self, client) -> None:
        self.class_name = self.__class__.__name__
        self.max_attempts = 5
        if not isinstance(client, googleapiclient.discovery.Resource):
            raise ValueError(f'Invalid object type for client: {type(client)}.')
        self._client = client
        self.logger = Logger(LoggerNames.API, class_name=self.class_name)

    @abstractmethod
    def create(self, *args, **kwargs):
        pass

    @abstractmethod
    def delete(self, *args, **kwargs):
        pass

    @abstractmethod
    def get(self, *args, **kwargs):
        pass

    @abstractmethod
    def list(self, *args, **kwargs):
        pass

    @abstractmethod
    def update(self, *args, **kwargs):
        pass

    def _make_request(self, request, method):
        """
        Takes formatted API request object and handles any exceptions and Timeout errors
        """
        backoff = 1
        for attempt in range(self.max_attempts):
            try:
                response = request.execute()
                return response
            except TimeoutError:
                # Exponential backoff with jitter
                sleep_time = backoff + random.uniform(0, 1)
                log_msg = (f'{self.class_name} - Attempt {attempt + 1}: Timeout calling {method}. '
                           f'Retrying in {sleep_time} seconds...')
                self.logger.debug(log_msg)
                time.sleep(sleep_time)
                backoff *= 2  # Double the backoff interval for the next attempt
            except HttpError as e:
                if e.status_code == 400:
                    raise BadRequest(e.reason)
                elif e.status_code == 403:
                    raise Unauthorized(e.reason)
                elif e.status_code == 404:
                    raise ResourceNotFound(e.reason)
                elif e.status_code == 409:
                    raise Conflict(e.reason)
                raise GoogleClassroomException(e)
            except Exception as e:
                GoogleClassroomObject(f'{self.class_name} - Reqeust {method} failed with error: {e}')
        raise GoogleClassroomException(f"{self.class_name} - Request {method} "
                                       f"failed after several attempts due to timeout.")

# [ eof ]
