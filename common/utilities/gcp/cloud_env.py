from typing import List, Optional
from google.cloud import secretmanager

from ...constants.buckets import Buckets
from ...constants.database import DbCollections, DatabaseTypes, DATABASE_NAME, ADMIN_INFO_DOCUMENT
from ...document_database import DocumentDatabaseFactory
from .cloud_logger import Logger, LoggerNames
from .shared_secrets import shared_api_secret_names


class CloudEnv:
    def __init__(
        self,
        log_name: str = LoggerNames.CLOUD_FN,
        env_dict: dict = None,
        project: str = None,
    ) -> None:
        """Initialize CloudEnv by loading environment variables and secrets."""
        self.project = project
        self.logger = Logger(log_name)
        self.secret_client = secretmanager.SecretManagerServiceClient()

        if env_dict:
            self.env_dict = env_dict
        else:
            self.db = DocumentDatabaseFactory.create_db_object(
                db_type=DatabaseTypes.firestore,
                database_name=DATABASE_NAME,
                log_name=log_name,
                project_id=self.project,
            )

            # Load environment variables
            self.env_dict = self.db.get(collection_name=DbCollections.ADMIN_INFO, doc_id=ADMIN_INFO_DOCUMENT)
            if not self.env_dict:
                raise ValueError('Missing Cloud Environment Database object')

        # Assign variables from env_dict
        self._assign_variables()

        # Secrets variables
        self._api_key = None
        self._auth_config = None
        self._openai_api_key = None
        self._sendgrid_api_key = None
        self._shodan_api_key = None

        # Guacamole Variables
        self._guac_sql_root_password = None
        self._guac_sql_password = None
        self._guac_admin_password = None
        self._google_dns_service_key = None

    @property
    def api_key(self):
        if self._api_key is None:
            self._api_key = self.get_secret('api_key')
        return self._api_key

    @property
    def auth_config(self):
        if self._auth_config is None:
            """Generate authentication configuration."""
            api_key = self.api_key
            self._auth_config = {
                'api_key': api_key,
                'auth_domain': self.firebase_auth_domain,
                'project_id': self.project
            }
        return self._auth_config

    @property
    def guac_sql_root_password(self):
        if self._guac_sql_root_password is None:
            self._guac_sql_root_password = self.get_secret('guac_sql_root_password')
        return self._guac_sql_root_password

    @property
    def guac_sql_password(self):
        if self._guac_sql_password is None:
            self._guac_sql_password = self.get_secret('guac_sql_password')
        return self._guac_sql_password

    @property
    def guac_admin_password(self):
        if self._guac_admin_password is None:
            self._guac_admin_password = self.get_secret('guac_admin_password')
        return self._guac_admin_password

    @property
    def google_dns_service_key(self):
        if self._google_dns_service_key is None:
            self._google_dns_service_key = self.get_secret('google_dns_service_key')
        return self._google_dns_service_key

    @property
    def openai_api_key(self):
        if self._openai_api_key is None:
            self._openai_api_key = self.get_secret('openai_api_key')
        return self._openai_api_key

    @property
    def sendgrid_api_key(self):
        if self._sendgrid_api_key is None:
            self._sendgrid_api_key = self.get_secret('sendgrid_api_key')
        return self._sendgrid_api_key

    @property
    def shodan_api_key(self):
        if self._shodan_api_key is None:
            self._shodan_api_key = self.get_secret('shodan_api_key')
        return self._shodan_api_key

    @property
    def groove_api_key(self):
        if not hasattr(self, "_groove_api_key"):
            self._groove_api_key = self.get_secret("groove_api_key")
        return self._groove_api_key

    def get_env(self) -> dict:
        """Return the environment dictionary."""
        return self.env_dict

    def _assign_variables(self):
        """Assign environment variables to instance attributes."""
        env = self.env_dict
        get = env.get

        # General Variables
        self.admin_email = get('admin_email')
        self.classroom_user = get('classroom_user')
        self.timezone = get('timezone', 'America/Chicago')
        self.max_workspaces = get('max_workspaces')
        self.rubric_support = get('rubric_support', False)

        # GCP Project Variables
        self.project = get('project')
        self.project_path = (get('project_path') or '').strip('/')
        self.project_number = get('project_number')
        self.region = env['region']
        self.zone = env['zone']
        self.custom_dnszone = get('custom_dnszone')
        # Shared installations need only the parent DNS settings. Keep legacy
        # overrides readable for projects that still use their own domains.
        parent_domain = (get('parent_dns_suffix') or get('dns_suffix') or '').strip('.')
        self.parent_dns_suffix = f'.{parent_domain}' if parent_domain else ''
        domain = (get('dns_suffix') or self.parent_dns_suffix).strip('.')
        self.dns_suffix = f'.{domain}' if domain else ''
        self.dnszone = get('dnszone') or get('dns_zone') or get('parent_dnszone')
        self.wireguard_dns_prefix = get('wireguard_dns_prefix', 'wg')
        self.wireguard_dns_suffix = get('wireguard_dns_suffix') or self.parent_dns_suffix
        self.wireguard_port = int(get('wireguard_port') or 51820)
        self.parent_project = get('parent_project') or self.project
        self.parent_zone = get('parent_dnszone') or self.dnszone
        self.app_sub_domain = get('app_sub_domain') or 'app'
        app_url = get('main_app_url')
        if not app_url:
            if not parent_domain:
                raise ValueError('parent_dns_suffix must be configured to derive the shared app URL')
            app_url = f'https://app.{parent_domain}'
            if self.project_path:
                app_url += f'/{self.project_path}'
        self.main_app_url = (
            app_url if app_url.startswith(('https://', 'http://')) else f'https://{app_url}'
        ).rstrip('/')
        # Firebase remains tenant-specific even when the app shares a hostname.
        self.firebase_auth_domain = get('firebase_auth_domain') or f'{self.project}.firebaseapp.com'
        self.shared_api_secrets = shared_api_secret_names(env)
        self.student_workout_firewall = get('student_workout_firewall', False)
        self.default_server_image_project = get('default_server_image_project')

        # Buckets
        default_spec_bucket = f"{self.project}_{Buckets.BUILD_SPEC_BUCKET_SUFFIX}"
        self.spec_bucket = get('spec_bucket', default_spec_bucket)
        if not self.spec_bucket:
            self.logger.warning(
                f"{self.__class__.__name__} - The environment variable 'spec_bucket' is not set for the project. "
                f"This should occur as part of the build process when synchronizing the specs."
            )

    def _get_auth_config(self) -> dict:
        """Generate authentication configuration."""
        return {
            'api_key': self.get_secret("api_key"),
            'auth_domain': self.firebase_auth_domain,
            'project_id': self.project
        }

    def get_secret(self, secret_name: str) -> Optional[str]:
        """Retrieves the secret value from Google Secret Manager.

        Args:
            secret_name: The name of the secret.

        Returns:
            The secret value if found, else None.
        """
        # Parent selection is explicit and authoritative, even when an older
        # tenant-local copy exists. Never fall back across billing accounts.
        shared = secret_name in self.shared_api_secrets
        project = self.parent_project if shared else self.project
        secret_version = 'latest'
        secret_path = (
            f'projects/{project}/secrets/{secret_name}/versions/{secret_version}'
        )
        try:
            response = self.secret_client.access_secret_version(name=secret_path)
            secret_value = response.payload.data.decode('UTF-8')
            return secret_value
        except Exception as e:
            if shared:
                raise RuntimeError(f"Cannot access shared API secret '{secret_path}'") from e
            self.logger.debug(f"Error accessing secret '{secret_name}': {e}")
            return None
