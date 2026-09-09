from datetime import datetime, timezone
from enum import Enum
import os
import random
import re
import subprocess
from typing import Callable, List

from colorama import Fore, Style, init
from google.api_core.exceptions import (
    GoogleAPICallError,
    NotFound,
    PermissionDenied,
    RetryError,
    Unauthenticated,
)
from google.auth.exceptions import DefaultCredentialsError, RefreshError
from google.cloud import billing_v1, resourcemanager_v3

from common.constants.build_constants import BuildConstants
from common.constants.database import DATABASE_NAME, DbCollections, DatabaseTypes
from common.document_database.factory import DocumentDatabaseFactory
from common.exceptions import AgogeValidationError
from common.models.project_info import ProjectContact, ProjectInfo
from cloud_deployment.operations.app_install_updates.install_update_manager import InstallUpdateManager

init(autoreset=True)

class Environment(str, Enum):
    """Deployment environment the project is created for."""
    PROD = "prod"
    DEV = "dev"


class ProjectManager:  # pylint: disable=too-many-public-methods
    """Handles GCP project creation/deletion and metadata storage."""
    _PRODUCTION_FOLDER_ID = "506220203180"
    _DEVELOPMENT_FOLDER_ID = "507606816058"
    _BILLING_ACCOUNT_ID = "01364F-67A93E-94E45E"

    # ---------------------------------------------------------------------
    # Construction helpers
    # ---------------------------------------------------------------------
    def __init__(
        self,
        *,
        db_project: str | None = None,
        resource_client=None,
        folder_client=None,
        billing_client=None,
    ) -> None:
        try:
            self.resource_client = resource_client or resourcemanager_v3.ProjectsClient()
            self.folder_client = folder_client or resourcemanager_v3.FoldersClient()
            self.billing_client = billing_client or billing_v1.CloudBillingClient()
        except DefaultCredentialsError as exc:
            raise AgogeValidationError(
                "Application Default Credentials are unavailable. Run "
                "`python setup.py --reauthenticate`."
            ) from exc
        self.production_folder_id = os.environ.get(
            "AGOGE_PRODUCTION_FOLDER_ID",
            self._PRODUCTION_FOLDER_ID,
        )
        self.development_folder_id = os.environ.get(
            "AGOGE_DEVELOPMENT_FOLDER_ID",
            self._DEVELOPMENT_FOLDER_ID,
        )
        self.billing_account_id = os.environ.get(
            "AGOGE_BILLING_ACCOUNT_ID",
            self._BILLING_ACCOUNT_ID,
        )
        self.db = DocumentDatabaseFactory.create_db_object(
            db_type=DatabaseTypes.firestore,
            database_name=DATABASE_NAME,
            project_id=db_project or BuildConstants.SharedResourceProjects.MAIN_SHARED_RESOURCE_PROJECT,
        )

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------
    def create(self) -> None:
        """Interactive flow to create a project and store its metadata."""
        tenant_name = self._prompt(
            prompt=f"{Fore.CYAN}Enter the entity's name: {Style.RESET_ALL}",
            error="Entity name cannot be empty.",
            validator=lambda s: bool(s.strip()),
        )
        env = self._prompt_env()

        # 1️. Create the GCP project ------------------------------------------------
        project_id = self._generate_project_id(tenant_name, env)
        self._create_gcp_project(project_id, tenant_name, env)
        self._enable_billing(project_id)

        # 2️. Collect and persist metadata -----------------------------------------
        info_dict = self._collect_project_info(project_id, tenant_name)
        self._store_project_info(project_id, info_dict)

        # 3. Bootstrap the new project -------------------------------------------
        InstallUpdateManager(project_id=project_id).run_full_install()

    def delete(self) -> None:  # pragma: no cover
        """Interactive deletion with safety prompt."""
        project_id = input(f"{Fore.CYAN}Enter the project ID to delete: {Style.RESET_ALL}").strip()
        confirm = input(f"Type '{project_id}' to confirm deletion: ").strip()
        if confirm != project_id:
            print("Project ID mismatch — deletion cancelled.")
            return

        try:
            op = self.resource_client.delete_project(name=f"projects/{project_id}")
            op.result()
            print(f"{Fore.GREEN}Project '{project_id}' scheduled for deletion.{Style.RESET_ALL}")
        except GoogleAPICallError as exc:  # network/permission issues
            print(f"{Fore.RED}GCP error deleting project: {exc}{Style.RESET_ALL}")
        except Exception as exc:  # noqa: BLE001
            print(f"{Fore.RED}Unexpected error: {exc}{Style.RESET_ALL}")

    # ------------------------------------------------------------------
    # Internals – GCP plumbing
    # ------------------------------------------------------------------
    def _create_gcp_project(self, project_id: str, tenant: str, env: Environment) -> None:
        folder = (
            self.production_folder_id
            if env is Environment.PROD
            else self.development_folder_id
        )
        self._verify_project_creation_access(folder, env)
        labels = {
            "customer": self._slugify(tenant, max_length=63) or "customer",
            "env": env.value,
        }
        project = resourcemanager_v3.Project(
            project_id=project_id,
            display_name=self._project_display_name(tenant, env),
            parent=f"folders/{folder}",
            labels=labels,
        )
        try:
            op = self.resource_client.create_project(
                request=resourcemanager_v3.CreateProjectRequest(project=project),
            )
            op.result()
            print(f"{Fore.GREEN}[SUCCESS] Project '{project_id}' created.{Style.RESET_ALL}")
        except (NotFound, PermissionDenied) as exc:
            raise AgogeValidationError(
                self._project_parent_error(folder, env)
            ) from exc
        except (Unauthenticated, RefreshError) as exc:
            raise AgogeValidationError(
                "GCP credentials expired during project creation. Run "
                "`python setup.py --reauthenticate` and retry."
            ) from exc
        except (GoogleAPICallError, RetryError) as exc:
            raise AgogeValidationError(f"GCP project creation failed: {exc}") from exc

    def _verify_project_creation_access(self, folder: str, env: Environment) -> None:
        """Fail early when ADC cannot create projects under the configured folder."""
        if not re.fullmatch(r"\d+", folder):
            raise AgogeValidationError(
                f"Invalid {env.value} folder ID: {folder!r}. Set "
                f"{self._folder_environment_variable(env)} to a numeric GCP folder ID."
            )

        permission = "resourcemanager.projects.create"
        try:
            response = self.folder_client.test_iam_permissions(
                resource=f"folders/{folder}",
                permissions=[permission],
            )
        except (NotFound, PermissionDenied) as exc:
            raise AgogeValidationError(
                self._project_parent_error(folder, env)
            ) from exc
        except (Unauthenticated, RefreshError) as exc:
            raise AgogeValidationError(
                "Application Default Credentials are missing or expired. Run "
                "`python setup.py --reauthenticate`."
            ) from exc
        except (GoogleAPICallError, RetryError) as exc:
            raise AgogeValidationError(
                f"Unable to verify project creation access on folders/{folder}: {exc}"
            ) from exc

        if permission not in set(response.permissions):
            raise AgogeValidationError(
                f"The Application Default Credentials do not have {permission} on "
                f"folders/{folder}. Grant roles/resourcemanager.projectCreator on "
                "that folder, or select an account that already has it."
            )

    @staticmethod
    def _project_parent_error(folder: str, env: Environment) -> str:
        variable = ProjectManager._folder_environment_variable(env)
        return (
            f"Cannot access the configured {env.value} project parent, folders/{folder}. "
            "Google returns NOT_FOUND when a folder is missing or hidden from the "
            "credential identity. Run `python setup.py --reauthenticate`, select the "
            "correct account, and verify that it has "
            "roles/resourcemanager.projectCreator on the folder. If the folder was "
            f"replaced, set {variable} to its current numeric ID."
        )

    @staticmethod
    def _folder_environment_variable(env: Environment) -> str:
        return (
            "AGOGE_PRODUCTION_FOLDER_ID"
            if env is Environment.PROD
            else "AGOGE_DEVELOPMENT_FOLDER_ID"
        )

    @staticmethod
    def _project_display_name(tenant: str, env: Environment) -> str:
        suffix = f"-{env.value}"
        cleaned = re.sub(r"[^A-Za-z0-9' !-]+", "-", tenant.strip()).strip(" -")
        cleaned = cleaned or "Agoge"
        return f"{cleaned[:30 - len(suffix)].rstrip()}{suffix}"

    def _enable_billing(self, project_id: str) -> None:
        print(f"{Fore.GREEN}[INFO] Linking billing…{Style.RESET_ALL}")
        self._run_gcloud(f"gcloud config set project {project_id}")
        self._run_gcloud("gcloud services enable cloudbilling.googleapis.com")
        try:
            self.billing_client.update_project_billing_info(
                name=f"projects/{project_id}",
                project_billing_info={
                    "billing_account_name": f"billingAccounts/{self.billing_account_id}",
                    "billing_enabled": True,
                },
            )
        except GoogleAPICallError as exc:
            raise AgogeValidationError("Failed to enable billing") from exc
        print(f"{Fore.GREEN}[SUCCESS] Billing enabled.{Style.RESET_ALL}")

    # ------------------------------------------------------------------
    # Internals – Firestore metadata
    # ------------------------------------------------------------------
    def _collect_project_info(self, project_id: str, tenant_name: str) -> dict:
        print(f"\n{Fore.CYAN}── Project metadata ──{Style.RESET_ALL}")
        contacts: List[ProjectContact] = []
        while input("Add a contact? (y/N): ").strip().lower() == "y":
            contacts.append(
                ProjectContact(
                    contact_name=input("  Name  : ").strip(),
                    contact_email=input("  Email : ").strip() or None,
                    contact_phone=input("  Phone : ").strip() or None,
                    primary_contact=input("  Primary? (y/N): ").lower() == "y",
                )
            )
        now = datetime.now(timezone.utc)
        info = ProjectInfo(
            project_name=project_id,
            impersonation_account=f"agoge-service@{project_id}.iam.gserviceaccount.com",
            tenant_name=tenant_name,
            created_date=now,
            last_modified=now,
            contacts=contacts or None,
        )
        return info.model_dump(exclude_none=True)

    def _store_project_info(self, project_id: str, info_dict: dict) -> None:
        try:
            ProjectInfo.model_validate(info_dict)  # second line of defence
            self.db.update(DbCollections.PROJECT_INFO, doc_id=project_id, data=info_dict)
            print(f"{Fore.GREEN}[SUCCESS] Metadata stored.{Style.RESET_ALL}")
        except (AgogeValidationError, ValueError) as exc:
            raise AgogeValidationError("Invalid project metadata") from exc

    # ------------------------------------------------------------------
    # Internals – Misc helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _run_gcloud(cmd: str) -> None:
        """Run a gcloud command and stream stderr in yellow if non‑fatal."""
        proc = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if proc.stderr:
            print(f"{Fore.YELLOW}{proc.stderr.strip()}{Style.RESET_ALL}")
        if proc.returncode != 0:
            raise AgogeValidationError(f"gcloud command failed: {cmd}")

    @staticmethod
    def _slugify(value: str, *, max_length: int) -> str:
        slug = re.sub(r"[^a-z0-9-]+", "-", value.strip().lower())
        slug = re.sub(r"-+", "-", slug).strip("-")
        return slug[:max_length].rstrip("-")

    @classmethod
    def _generate_project_id(cls, client: str, env: Environment) -> str:
        suffix = f"-{env.value}-{random.randint(100_000, 999_999)}"
        client_slug = cls._slugify(client, max_length=30 - len(suffix))
        if not client_slug or not client_slug[0].isalpha():
            client_slug = cls._slugify(
                f"agoge-{client_slug}",
                max_length=30 - len(suffix),
            )
        project_id = f"{client_slug}{suffix}"
        if not re.fullmatch(r"[a-z][a-z0-9-]{4,28}[a-z0-9]", project_id):
            raise AgogeValidationError(
                f"Unable to generate a valid GCP project ID from {client!r}."
            )
        return project_id

    # Interactive prompt wrappers -------------------------------------------------
    @staticmethod
    def _prompt(*, prompt: str, error: str, validator: Callable[[str], bool]) -> str:
        for _ in range(3):
            val = input(prompt).strip()
            if validator(val):
                return val
            print(f"{Fore.RED}{error}{Style.RESET_ALL}")
        raise AgogeValidationError("Too many invalid attempts.")

    def _prompt_env(self) -> Environment:
        mapping = {"1": Environment.PROD, "2": Environment.DEV}
        while True:
            choice = input(
                f"{Fore.CYAN}Select environment (1 = Production, 2 = Development): {Style.RESET_ALL}"
            ).strip()
            if choice in mapping:
                return mapping[choice]
            print(f"{Fore.RED}Invalid selection.{Style.RESET_ALL}")
