import sys
import json
import subprocess
from pathlib import Path
from dotenv import load_dotenv

from common.constants.build_constants import BuildConstants
from common.constants.database import DATABASE_NAME, DbCollections, DatabaseTypes
from common.document_database.factory import DocumentDatabaseFactory

# ANSI Colors
CYAN = '\033[0;36m'
GREEN = '\033[0;32m'
RED = '\033[0;31m'
NC = '\033[0m'
YELLOW = '\033[0;33m'

ENV_FILE = Path("main_app/api/.env")
SHARED_RESOURCE_PROJECT = {
    "agoge-shared-resources": {
        "impersonation_account": "agoge-service@agoge-shared-resources.iam.gserviceaccount.com",
        "project_id": "agoge-shared-resources"
    }
}


class GcloudEnvironmentManager:
    """
    Manages environment switching, account setting, and .env file updates.
    """

    def __init__(self, env_file=ENV_FILE) -> None:
        self.env_file = env_file
        self.configurations = self.load_configurations()

    def load_configurations(self) -> dict:
        """Load environment configurations"""
        db = DocumentDatabaseFactory.create_db_object(
            db_type=DatabaseTypes.firestore,
            database_name=DATABASE_NAME,
            project_id=BuildConstants.SharedResourceProjects.MAIN_SHARED_RESOURCE_PROJECT,
        )

        environments = db.query(collection_name=DbCollections.PROJECT_INFO)
        projects = {}
        for environment in environments:
            projects[environment["tenant_name"]] = {
                "impersonation_account": environment["impersonation_account"],
                "project_id": environment["project_name"]
            }
        return projects

    def get_current_account(self):
        """Get the currently logged-in gcloud account."""
        try:
            result = subprocess.run(
                "gcloud config get-value account",
                capture_output=True, shell=True
            )
            return result.stdout.strip().decode()
        except subprocess.CalledProcessError:
            print(f"{RED}[!!] Error: Unable to fetch current account.{NC}")
            return None

    def set_account(self):
        """Allow the user to set a different gcloud account."""
        try:
            print(f"{CYAN}\nAvailable Accounts:{NC}")
            result = subprocess.run("gcloud auth list", capture_output=True, shell=True)
            print(f"{CYAN}{result.stdout.decode()}{NC}")
            new_account = input(f"{YELLOW}\nEnter the email of the account to use (or press Enter to keep current): {NC}").strip()
            if new_account:
                subprocess.run(f"gcloud config set account {new_account}", capture_output=True, shell=True)
                print(f"{GREEN}[+] Successfully set account to: {new_account}{NC}")
            else:
                print(f"{CYAN}No changes made to the account.{NC}")
        except subprocess.CalledProcessError:
            print(f"{RED}[!!] Error: Unable to set the account.{NC}")

    def display_menu(self):
        """Display a menu of environments for user selection."""
        print(f"{CYAN}\nAvailable Environments:{NC}")
        for index, env_name in enumerate(self.configurations.keys(), start=1):
            print(f"{index}. {env_name}")
        print()

    def select_environment(self):
        """Prompt the user to select an environment by number."""
        keys = list(self.configurations.keys())
        while True:
            try:
                choice = int(
                    input(f"{YELLOW}Select an env (1-{len(keys)}): {NC}")
                ) - 1
                if 0 <= choice < len(keys):
                    return keys[choice]
                print(
                    f"{RED}[!!] Invalid choice. Pick 1-{len(keys)}.{NC}"
                )
            except ValueError:
                print(f"{RED}[!!] Invalid input. Enter a number.{NC}")

    def read_env_file(self):
        """Read existing variables from the .env file."""
        if self.env_file is None:
            return {}  # shared-resource mode: nothing to read

        variables = {}
        if self.env_file.exists():
            with open(self.env_file, "r") as file:
                for line in file:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        key, sep, value = line.partition("=")
                        if sep:
                            variables[key.strip()] = value.strip()
        else:
            print(f"{YELLOW}[!] No existing .env file found. A new one will be created.{NC}")
        return variables

    def write_env_file(self, variables):
        """Write all variables to the .env file."""
        if self.env_file is None:
            return  # shared-resource mode: nothing to write

        with open(self.env_file, "w") as file:
            for key, value in variables.items():
                file.write(f"{key}={value}\n")

    def get_project_id(self, env_name) -> str:
        """Use when you just need the project_id and don't need to switch projects."""
        env_config = self.configurations.get(env_name)
        return env_config["project_id"]


    def switch_environment(self, env_name) -> str:
        """Switch to the selected environment by configuring gcloud and updating .env."""
        env_config = self.configurations.get(env_name)
        if not env_config:
            print(f"{RED}[!!] Error: Configuration for environment '{env_name}' not found.{NC}")
            sys.exit(1)

        try:
            # Set gcloud project
            project_id = env_config["project_id"]
            subprocess.run(f"gcloud config set project {project_id}", capture_output=True, shell=True)
            print(f"{GREEN}[+] Successfully set gcloud project to: {project_id}{NC}")

            # Prompting the user to refresh the API token
            refresh_token = input(
                f"{YELLOW}Would you like to refresh your API token? This is necessary when switching accounts (y/N): {NC}"
            ).strip().lower()

            if refresh_token == 'y':
                # Ensuring credentials used for API login are set to the new account
                subprocess.run("gcloud auth application-default login", capture_output=True, shell=True)
                print(f"{GREEN}[+] Successfully logged in with new user account{NC}")

                # Set application-default quota project
                subprocess.run(f"gcloud auth application-default set-quota-project {project_id}",
                               capture_output=True, shell=True)
                print(f"{GREEN}[+] Successfully set application-default quota project to: {project_id}{NC}")

            # Load .env file to set the impersonation account
            load_dotenv(self.env_file)
            print(f"{GREEN}[+] Successfully switched to environment: {env_name}{NC}")
            return project_id

        except subprocess.CalledProcessError as e:
            print(f"{RED}[!!] Error while configuring environment: {e}{NC}")
            sys.exit(1)
