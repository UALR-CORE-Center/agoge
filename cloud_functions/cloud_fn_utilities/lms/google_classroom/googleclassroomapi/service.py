import json
from google.oauth2 import service_account
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from google.auth import exceptions
from google.cloud import secretmanager

from .exceptions import (
    GoogleClassroomException,
    Unauthorized
)


class Service:
    """Handles authentication and client creation for Google Classroom API.

    This class provides functionalities to authenticate a user and create a
    client for interacting with the Google Classroom API.

    Attributes:
        project: A GCP project id to authenticate to
        user: A string representing the user email.
        scopes: A list of strings representing the authentication scopes.
        __credentials: Credentials object for the authenticated user.
    """
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(Service, cls).__new__(cls)
        return cls._instance

    @classmethod
    def get_instance(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = cls(*args, **kwargs)
        return cls._instance

    def __init__(self, project, scope, user=None, debug=False):
        """Initializes the Service with scope and user.

        Args:
            project: A GCP project id to authenticate to
            scope: A list of strings representing the authentication scopes.
            user: A string representing the user email.
        """
        if not hasattr(self, 'initialized'):
            self.initialized = True
            self.project = project
            self.scopes = scope
            self.user = user
            self.debug = debug
            self._secret_name = 'classroom_api'
            self._secret_version = 'latest'
            self._resource_name = f"projects/{self.project}/secrets/{self._secret_name}/versions/{self._secret_version}"
            self.__credentials = None
            self.__service_account_info = None
            self.client = self.get_client()

    def _authenticate(self):
        """Authenticates with API and sets credentials.

        This method authenticates with the Google Classroom API using stored service
        account info in SecretsManager and sets the credentials for further API
        interactions. It raises exceptions if authentication fails.

        Raises:
            Unauthorized: If default credentials could not be loaded.
            GoogleClassroomException: For other exceptions during authentication.
        """
        service_account_info = self._get_service_account_info()
        try:
            if self.user:
                self.__credentials = (
                    service_account.Credentials.from_service_account_info(
                        service_account_info,
                        scopes=self.scopes,
                        subject=str(self.user)
                    )
                )
            else:
                self.__credentials = (
                    service_account.Credentials.from_service_account_info(
                        service_account_info,
                        scopes=self.scopes,
                    )
                )
        except exceptions.DefaultCredentialsError as e:
            raise Unauthorized(f"Could not load default credentials: {e}")
        except Exception as e:
            raise GoogleClassroomException(e)

    def _get_service_account_info(self):
        if not self.__service_account_info:
            secrets_client = secretmanager.SecretManagerServiceClient()
            response = secrets_client.access_secret_version(request={"name": self._resource_name})
            self.__service_account_info = json.loads(response.payload.data.decode("UTF-8"))
        return self.__service_account_info

    def get_client(self):
        """Creates and returns the Google Classroom API client.

        This method creates a client for the Google Classroom API using the
        authenticated credentials.

        Returns:
            The Google Classroom service client.

        Raises:
            GoogleClassroomException: If credentials are not set.
        """
        if self.__credentials is None or not self.__credentials.valid:
            if self.__credentials and self.__credentials.expired:
                self.__credentials.refresh(Request())
            else:
                self._authenticate()
        return build('classroom', 'v1', credentials=self.__credentials)

# [ eof ]
