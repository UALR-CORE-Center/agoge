import time
from datetime import datetime, timezone
from enum import Enum
import random
import subprocess
from typing import Callable, List, Optional

from colorama import Fore, Style, init
from google.api_core.exceptions import GoogleAPICallError, RetryError
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
    _PRODUCTION_FOLDER_ID = "267924026470"
    _DEVELOPMENT_FOLDER_ID = "997842458280"
    _BILLING_ACCOUNT_ID = "01DA03-A4053E-869DE5"

    # ---------------------------------------------------------------------
    # Construction helpers
    # ---------------------------------------------------------------------
    def __init__(self, *, db_project: str | None = None) -> None:
        self.resource_client = resourcemanager_v3.ProjectsClient()
        self.billing_client = billing_v1.CloudBillingClient()
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
        folder = self._PRODUCTION_FOLDER_ID if env is Environment.PROD else self._DEVELOPMENT_FOLDER_ID
        project = resourcemanager_v3.Project(
            project_id=project_id,
            display_name=f"{tenant}-{env.value}",
            parent=f"folders/{folder}",
        )
        labels = {"customer": tenant, "env": env.value}
        try:
            op = self.resource_client.create_project(
                request=resourcemanager_v3.CreateProjectRequest(project=project),
                metadata=[("labels", str(labels))],
            )
            op.result()
            print(f"{Fore.GREEN}[SUCCESS] Project '{project_id}' created.{Style.RESET_ALL}")
        except (GoogleAPICallError, RetryError) as exc:
            raise AgogeValidationError(f"GCP project creation failed: {exc}") from exc

    def _enable_billing(self, project_id: str) -> None:
        print(f"{Fore.GREEN}[INFO] Linking billing…{Style.RESET_ALL}")
        self._run_gcloud(f"gcloud config set project {project_id}")
        self._run_gcloud("gcloud services enable cloudbilling.googleapis.com")
        try:
            self.billing_client.update_project_billing_info(
                name=f"projects/{project_id}",
                project_billing_info={
                    "billing_account_name": f"billingAccounts/{self._BILLING_ACCOUNT_ID}",
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
    def _generate_project_id(client: str, env: Environment) -> str:
        return f"{client}-{env.value}-{random.randint(100_000, 999_999)}"

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
