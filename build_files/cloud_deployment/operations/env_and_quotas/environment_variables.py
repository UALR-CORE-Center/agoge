import uuid
import string
import random
from enum import Enum
from getpass import getpass
import zoneinfo
import subprocess
from google.cloud import secretmanager, compute_v1
from google.api_core.exceptions import NotFound

from common.document_database.factory import DocumentDatabaseFactory
from common.constants.database import DatabaseTypes, DATABASE_NAME, DbCollections, ADMIN_INFO_DOCUMENT
from common.models.agoge import CloudEnvModel
from common.utilities.gcp.shared_secrets import SHARED_API_SECRET_NAMES, shared_api_secret_names

from cloud_deployment.utilities.globals import ShellCommands
from .shared_api_secrets import enabled_api_secret_version


class EnvironmentVariables:
    DEFAULT_REGION = "us-central1"
    DEFAULT_ZONE = "us-central1-a"
    DEFAULT_TIMEZONE = "America/Chicago"
    VARIABLES = ['admin_email', 'project_number', 'max_workspaces',
                 'default_server_image_project', 'parent_project',
                 'parent_dnszone', 'parent_dns_suffix', 'wireguard_dns_prefix',
                 'wireguard_dns_suffix', 'wireguard_port', 'project_path']
    SECRET_VARIABLES = ['api_key', 'sendgrid_api_key', 'shodan_api_key', 'openai_api_key', 'jwt_private_key','jwt_public_key']
    WIREGUARD_DEFAULTS = {
        'wireguard_dns_prefix': 'wg',
        'wireguard_port': 51820,
    }

    def __init__(self, project):
        self.project = project
        self.region_client = compute_v1.RegionsClient()
        self.zone_client = compute_v1.ZonesClient()
        self._create_firestore()
        self.db = DocumentDatabaseFactory.create_db_object(
            db_type=DatabaseTypes.firestore,
            project_id=self.project
        )
        self.env = self.db.get(collection_name=DbCollections.ADMIN_INFO, doc_id=ADMIN_INFO_DOCUMENT) or {}
        self.secret_client = secretmanager.SecretManagerServiceClient()

    def run(self):
        reply = str(input(f"Do you want to update a specific environment variable or ALL environmental variables "
                          f"for {self.project}? [s]pecific/[A]ll ")).upper()
        if reply in ["S", "SPECIFIC"]:
            print('Use shared_api_secrets to choose parent, copied, or local API keys. '
                  'Legacy domain overrides remain editable here for existing deployments.')
            while True:
                var = str(input(f"Which variable do you want to update? "))
                self.set_variable(var)
                response = str(input("Would you like to set another variable? (y/N) ")).upper()
                if not response or response == "N":
                    self.db.update(collection_name=DbCollections.ADMIN_INFO, doc_id=ADMIN_INFO_DOCUMENT,
                                   data=self.env)
                    break
        else:
            print(
                "Configure parent_project, parent_dnszone, parent_dns_suffix, and project_path for shared hosting.\n"
                "App URLs and DNS settings are derived from the parent; Firebase defaults to this project's firebaseapp.com domain.\n"
                f"🔑  For `api_key`, open Firebase Project Settings → General for {self.project}.\n"
                "    Copy apiKey from that project's Web app SDK configuration.\n"
                "    A Firebase key selects exactly one project. Do not copy it from the parent or another tenant."
            )
            self.set_variable("project", self.project)
            self._set_region()
            self._set_zone()
            self._set_timezone()
            self._set_guacamole_variables()
            for var in self.VARIABLES + self.SECRET_VARIABLES:
                self.set_variable(var)

    def ensure_wireguard_defaults(self) -> dict:
        """Backfill non-secret WireGuard settings for an existing installation.

        Updates must be non-interactive so the normal application upgrade path
        can safely migrate projects that predate WireGuard support.
        """
        updates = {}
        if not self.env.get('wireguard_dns_prefix'):
            updates['wireguard_dns_prefix'] = self.WIREGUARD_DEFAULTS['wireguard_dns_prefix']
        if not self.env.get('wireguard_port'):
            updates['wireguard_port'] = self.WIREGUARD_DEFAULTS['wireguard_port']
        if not self.env.get('wireguard_dns_suffix'):
            parent_suffix = self.env.get('parent_dns_suffix')
            if not parent_suffix:
                raise ValueError(
                    'parent_dns_suffix must be configured before enabling WireGuard DNS'
                )
            updates['wireguard_dns_suffix'] = parent_suffix

        # Validate both migrated defaults and truthy pre-existing values. Keep
        # the stored representation canonical so update and runtime paths use
        # exactly the same port, prefix, and suffix.
        effective = {**self.env, **updates}
        validated = CloudEnvModel.model_validate(effective)
        for setting in (
            'wireguard_dns_prefix',
            'wireguard_dns_suffix',
            'wireguard_port',
        ):
            canonical = getattr(validated, setting)
            if effective.get(setting) != canonical:
                updates[setting] = canonical

        if updates:
            self.env.update(updates)
            self.db.update(
                collection_name=DbCollections.ADMIN_INFO,
                doc_id=ADMIN_INFO_DOCUMENT,
                data=updates,
            )
        return updates

    def set_variable(self, var, new_value=None):
        if var == 'shared_api_secrets':
            for secret_name in SHARED_API_SECRET_NAMES:
                self._set_api_secret(secret_name)
            return
        if var in SHARED_API_SECRET_NAMES:
            self._set_api_secret(var, new_value)
            return
        self._set_variable(var, new_value)

    def _set_variable(self, var, new_value=None):
        if var in self.SECRET_VARIABLES:
            # Show metadata only; never display an existing or proposed key.
            current_val = 'configured' if self._secret_exists(var) else 'not configured'
            prompt = f'{var} is {current_val}. Do you wish to set it? (Y/n)'
        else:
            current_val = self.env.get(var, None)
            if current_val and current_val == new_value:
                print("Given value is the same as the set value. No change is needed.")
                return False
            elif new_value:
                prompt = f"The current value of {var} is {current_val}. Do you wish to set it to {new_value}? (Y/n)"
            else:
                prompt = f"The current value of {var} is {current_val}. Do you wish to set it? (Y/n)"
        reply = str(input(prompt)).upper()
        if not reply or reply == "Y":

            if var in self.SECRET_VARIABLES:
                if var in ("jwt_private_key", "jwt_public_key"):
                    new_value = self._read_multiline(f"Paste the full PEM for {var}")
                    # Convert escaped "\n" sequences into actual newline characters
                    if "\\n" in new_value:
                        new_value = new_value.replace("\\n", "\n")
                else:
                    if not new_value:
                        if var == 'api_key':
                            print(
                                f'Use the Firebase Web API key from {self.project}: '
                                f'https://console.firebase.google.com/project/{self.project}/settings/general\n'
                                'After saving, rebuild React to update the key embedded in the frontend.'
                            )
                        new_value = getpass(f"What value would you like to set for {var}? ")
                if not new_value.strip():
                    print('Empty secret skipped; the existing value and source are unchanged.')
                    return None
                self.store_secret(var, new_value)
            else:
                if not new_value:
                    default_value = self.WIREGUARD_DEFAULTS.get(var)
                    if var == 'wireguard_dns_suffix':
                        default_value = self.env.get('parent_dns_suffix')
                    default_hint = f" [{default_value}]" if default_value else ""
                    new_value = str(
                        input(f"What value would you like to set for {var}?{default_hint} ")
                    ).strip() or default_value
                if var == 'wireguard_port':
                    try:
                        new_value = int(new_value)
                    except (TypeError, ValueError) as error:
                        raise ValueError('wireguard_port must be an integer from 1 through 65535') from error
                    if not 1 <= new_value <= 65535:
                        raise ValueError('wireguard_port must be an integer from 1 through 65535')
                if var in ('dns_suffix', 'parent_dns_suffix', 'wireguard_dns_suffix'):
                    if not new_value:
                        raise ValueError(f'{var} cannot be empty')
                    if not new_value.startswith("."):
                        new_value = f'.{new_value}'
                self.env[var] = new_value
                if var == 'admin_email':
                    self._create_admin_user(user_email=new_value)
                self.db.update(collection_name=DbCollections.ADMIN_INFO, doc_id=ADMIN_INFO_DOCUMENT, data=self.env)
            return True
        return False

    def _set_api_secret(self, secret_name, new_value=None):
        shared = list(shared_api_secret_names(self.env))
        current_source = 'parent' if secret_name in shared else 'local'
        choice = input(
            f'{secret_name} currently uses {current_source}. '
            '[Enter] Keep / [P] Parent reference / [C] Copy parent / [L] Local: '
        ).strip().upper()
        if not choice:
            return
        if choice not in ('P', 'C', 'L'):
            raise ValueError('Choose P, C, L, or Enter to keep the current secret source')
        if choice in ('P', 'C'):
            parent = self.env.get('parent_project')
            if not parent or parent == self.project:
                raise ValueError('Choose a different parent_project before sharing or copying API secrets')
            version_name = enabled_api_secret_version(self.secret_client, parent, secret_name)
            if choice == 'C':
                response = self.secret_client.access_secret_version(request={'name': version_name})
                self.store_secret(secret_name, response.payload.data.decode('UTF-8'))
            elif secret_name not in shared:
                shared.append(secret_name)
        else:
            changed = self._set_variable(secret_name, new_value)
            if changed is None:
                return
            if not changed and not self._secret_exists(secret_name):
                print('No local secret exists; keeping the current source.')
                return
            if not changed:
                enabled_api_secret_version(self.secret_client, self.project, secret_name)
        if choice != 'P' and secret_name in shared:
            shared.remove(secret_name)
        # Explicit source selection avoids using an old tenant copy when the
        # administrator has selected a parent key. This never enables rubrics.
        self.env['shared_api_secrets'] = shared
        self.db.update(
            collection_name=DbCollections.ADMIN_INFO, doc_id=ADMIN_INFO_DOCUMENT,
            data={'shared_api_secrets': shared},
        )
        print(f'{secret_name} now uses {"parent reference" if choice == "P" else "local storage"}.')

    def _secret_exists(self, secret_name):
        try:
            self.secret_client.get_secret(name=f'projects/{self.project}/secrets/{secret_name}')
            return True
        except NotFound:
            return False

    def remove_variable(self):
        current_vars = list(self.env.items())
        print('Environment Variables::')
        for i in enumerate(current_vars):
            print(f'\t[{i[0]}] {current_vars[i[0]][0]}')

        idx = int(input('Which variable would you like to remove? '))
        var = current_vars[idx]
        if var[0] in self.env:
            del self.env[var[0]]
            print(f'Removed {var[0]} from environment')
            self.db.update(collection_name=DbCollections.ADMIN_INFO, doc_id=ADMIN_INFO_DOCUMENT, data=self.env)
        else:
            print(f'Could not find variable with name: {var[0]}')

    def store_secret(self, secret_name, secret_value):
        """Store the secret value in Google Secret Manager"""
        parent = f"projects/{self.project}"
        secret_id = secret_name

        if not self._secret_exists(secret_id):
            # If secret does not exist, create it
            self.secret_client.create_secret(
                request={
                    "parent": parent,
                    "secret_id": secret_id,
                    "secret": {"replication": {"automatic": {}}},
                }
            )

        # Add a new secret version
        self.secret_client.add_secret_version(
            request={"parent": f"{parent}/secrets/{secret_id}", "payload": {"data": secret_value.encode("UTF-8")}}
        )

    def get_secret(self, secret_name):
        """Retrieve the secret value from Google Secret Manager"""
        secret_version = "latest"
        secret_name = f"projects/{self.project}/secrets/{secret_name}/versions/{secret_version}"

        try:
            response = self.secret_client.access_secret_version(name=secret_name)
            return response.payload.data.decode("UTF-8")
        except NotFound:
            # Return None if the secret does not exist
            return None

    def _create_firestore(self):
        command = ShellCommands.FireStore.CHECK_FIRESTORE.value.format(project=self.project, database=DATABASE_NAME)
        ret = subprocess.run(command, capture_output=True, shell=True)
        if ret.returncode != 0:
            print(f"Firestore database {DATABASE_NAME} does not exist in {self.project}. Creating one now.")

            region_options, options_string = self.__list_regions()
            reply = input(f"Region options for Firestore database:\n{options_string}"
                          f"Enter the number beside the region in which you like to "
                          f"run the project's database? Default is {self.DEFAULT_REGION}")
            region = region_options[int(reply)] if reply.isnumeric() else self.DEFAULT_REGION

            command = ShellCommands.FireStore.CREATE_FIRESTORE.value.format(region=region, database=DATABASE_NAME)
            print(f"Running: {command}")
            ret = subprocess.run(command, capture_output=True, shell=True)
            print(ret.stderr.decode())
            if ret.returncode != 0:
                print(f"Error creating firestore database. See message above.")
                raise

    def _read_multiline(self, prompt: str) -> str:
        print(prompt + " (end input with an empty line):")
        lines = []
        while True:
            try:
                line = input()
            except EOFError:
                break
            if line == "":
                break
            lines.append(line)
        return "\n".join(lines) + "\n"

    def _set_region(self):
        region_options, options_string = self.__list_regions()

        reply = input(f"Region options:\n{options_string}Enter the number beside the region in which you like to "
                      f"run the Agoge app? Default is {self.DEFAULT_REGION}")
        region = region_options[int(reply)] if reply.isnumeric() else self.DEFAULT_REGION
        self.set_variable("region", region)

    def _set_zone(self):
        """
        Prompts the user to select a zone from the list of available zones in the project.

        Sets the selected zone as the active zone for operations.
        """
        zones = self.zone_client.list(project=self.project)
        zone_options = {}
        options_string = "\n"

        for i, zone in enumerate(zones):
            zone_options[i] = zone.name
            options_string += f"[{i}] {zone.name}\n"

        reply = input(f"Zone options:\n{options_string}Enter the number beside the zone in which you like to "
                      f"run the Agoge app? Default is {self.DEFAULT_ZONE}: ")
        self.zone = zone_options[int(reply)] if reply.isnumeric() else self.DEFAULT_ZONE
        self.set_variable("zone", self.zone)

    def _set_timezone(self):
        reply = input(f"What timezone do you want to set for the project? Use the IANA Timezone identifier. "
                      f"The default is {self.DEFAULT_TIMEZONE}")
        timezone = reply if reply else self.DEFAULT_TIMEZONE
        try:
            zoneinfo.ZoneInfo(timezone)
        except zoneinfo.ZoneInfoNotFoundError:
            print(f"Unknown timezone entered! Setting the timezone to {self.DEFAULT_TIMEZONE}")
            timezone = self.DEFAULT_TIMEZONE
        self.set_variable("timezone", timezone)

    def _create_admin_user(
            self,
            user_email: str
    ) -> None:
        uid = str(uuid.uuid4().hex)
        user = {
            'uid': uid,
            'email': user_email.strip(" ").lower(),
            'permissions': {
                'admin': True,
                'instructor': True,
                'student': True,
            },
            'settings': {
                "canvas": {
                    "secret": None,
                    "api": None,
                    "url": None
                }
            },
            'timezone': self.env.get('timezone', 'America/Chicago')
        }
        self.db.update(collection_name=DbCollections.USERS, doc_id=uid, data=user)

    def _set_guacamole_variables(self):
        """
        Sets the guacamole-related environment variables.

        - Generates 15-character random passwords for:
          guac_sql_root_password, guac_sql_password, guac_admin_password.
        - Prompts the user for multi-line input for google_dns_service_key,
          which is then stored as a secret.
        """
        # Generate random passwords
        print("Creating random passwords for Guacamole variables...")
        self.store_secret("guac_sql_root_password", self.__generate_random_password())
        self.store_secret("guac_sql_password", self.__generate_random_password())
        self.store_secret("guac_admin_password", self.__generate_random_password())
        print("Random passwords have been set.")

        # Prompt for the multi-line JSON key
        print("Download a JSON DNS key from the Agoge Certbot DNS Service Account. "
              "Copy the key and delete the key file. "
              "Then, enter the contents of the google_dns_service_key JSON file (end input with an empty line):")
        lines = []
        while True:
            line = input()
            if line == "":
                break
            lines.append(line)
        key_contents = "\n".join(lines)

        # Store the secret using your store_secret method
        self.store_secret("google_dns_service_key", key_contents)

        print("Guacamole variables have been set:")
        print("  - guac_sql_root_password, guac_sql_password, guac_admin_password: 15-character random passwords")
        print("  - google_dns_service_key: stored as a secret")

    def __list_regions(self):
        """
        Lists all regions in the given Google Cloud project.

        Returns:
            Tuple[dict, str]: A dictionary of region options and a formatted string for display.
        """
        regions = self.region_client.list(project=self.project)
        region_options = {}
        options_string = "\n"

        for i, region in enumerate(regions):
            region_options[i] = region.name
            options_string += f"[{i}] {region.name}\n"

        return region_options, options_string

    class Variables(str, Enum):
        DNS_SUFFIX = "dns_suffix"
        API_KEY = "api_key"
        MAIN_APP_URL = "main_app_url"
        ADMIN_EMAIL = "admin_email"

    import random
    import string

    @staticmethod
    def __generate_random_password(length=15):
        """Generates a random alphanumeric password of a given length."""
        characters = string.ascii_letters + string.digits
        return ''.join(random.choice(characters) for _ in range(length))
