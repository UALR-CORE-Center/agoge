import subprocess
import getpass
from googleapiclient import discovery

from common.utilities.gcp.cloud_env import CloudEnv
from common.constants.build_constants import BuildConstants
from cloud_deployment.utilities.globals import ShellCommands
from cloud_deployment.operations.env_and_quotas.environment_variables import EnvironmentVariables


class BaseBuild:
    """Project bootstrapper for Agoge / CyberArena deployments.

    This helper walks you through enabling APIs, creating a secure‑by‑default VPC
    (if your org skips the default), provisioning service accounts, Firebase
    auth, Pub/Sub topics, and other one‑time resources.
    """

    def __init__(self, project: str, suppress: bool = False):
        self.project = project
        self.project_number = self._get_project_number()
        self.suppress = suppress  # When True, auto‑accept every prompt (CI runs)
        self.service = discovery.build("iam", "v1")

    # ---------------------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------------------
    def _get_project_number(self) -> str:
        """Return the numeric project ID so we can construct IAM principals."""
        cmd = (
            f"gcloud projects describe {self.project} --format=""value(projectNumber)"""
        )
        result = subprocess.run(cmd, capture_output=True, shell=True, text=True, check=True)
        return result.stdout.strip()

    # ---------------------------------------------------------------------
    # Main driver
    # ---------------------------------------------------------------------
    def run(self) -> None:
        # 1. Enable required Google APIs ---------------------------------------------------
        confirmation = (
            str(input("Do you want to enable the necessary APIs at this time? (Y/n): ")).upper()
            if not self.suppress
            else "Y"
        )
        if confirmation != "N":
            for item in ShellCommands.EnableAPIs:
                print(f"Running: {item.value}")
                subprocess.run(item.value, capture_output=True, shell=True, text=True)

        # 2. Create the default VPC & firewall rules --------------------------------------
        confirmation = (
            str(
                input(
                    "Do you want to create the default VPC (and default firewall rules) "
                    "for this project? (Y/n): "
                )
            ).upper()
            if not self.suppress
            else "Y"
        )
        if confirmation != "N":
            for item in ShellCommands.CreateDefaultVPC:
                print(f"Running: {item.value}")
                subprocess.run(item.value, capture_output=True, shell=True, text=True)

        # 3. Service‑account impersonation setup -------------------------------------------
        confirmation = (
            str(
                input(
                    "Do you want to enable service account impersonation at this time? (Y/n): "
                )
            ).upper()
            if not self.suppress
            else "Y"
        )
        if confirmation != "N":
            for item in ShellCommands.Impersonation:
                cmd = item.value.format(project=self.project)
                print(f"Running: {cmd}")
                subprocess.run(cmd, capture_output=True, shell=True, text=True)

        # 4. Create service accounts -------------------------------------------------------
        confirmation = (
            str(input("Do you want to create the service accounts at this time? (Y/n): ")).upper()
            if not self.suppress
            else "Y"
        )
        if confirmation != "N":
            for item in ShellCommands.ServiceAccount:
                cmd = item.value.format(project=self.project, project_number=self.project_number)
                print(f"Running: {cmd}")
                subprocess.run(cmd, capture_output=True, shell=True, text=True)

        # 5. Firebase Authentication manual step ------------------------------------------
        firebase_prompt = f"""
        ──────────────────────────────────────────────────────────────────────────────
         Firebase Authentication setup for {self.project}
        ──────────────────────────────────────────────────────────────────────────────
         1️   Open your browser to:
               https://console.firebase.google.com/project/{self.project}/authentication/providers
        
         2️   If the project hasn’t been “upgraded” to Firebase yet:
               • Click **Add Firebase to an existing Google Cloud project**  
               • Follow the wizard to finish the upgrade.
        
         3   In Build ▸ Authentication ▸ Sign-in method  
               Enable every provider your app needs  
               (e.g. Email/Password, Google, OIDC, …).
        
         4   In Build ▸ Authentication ▸ Settings ▸ Authorized domains  
               Add the custom domain you’ll use for this project.
        
         5   In APIs & Services ▸ Credentials ▸ OAuth2 Client ID  
               • Add https://auth.<dns-suffix>/__/auth/handler to *Authorized redirect URIs*  
               • Add https://auth.<dns-suffix>, https://app.<dns-suffix>**, and https://<project-id>.web.app to
                 *Authorized JavaScript origins*.
        
         6   Create a DNS **CNAME** record:
               auth.<dns-suffix>  →  <project-id>.firebaseapp.com.
               
         7   Add the custom domain auth.<dns-suffix> to the Firebase project in Build ▸ Hosting.

         When all required providers show Enabled, type Y and press Enter
         (or N to skip this step).
        ──────────────────────────────────────────────────────────────────────────────
        """.rstrip()

        confirmation = input(firebase_prompt).strip().upper() if not self.suppress else "Y"
        if confirmation != "N":
            print("✔ Firebase authentication configuration confirmed.")

        # 6. Pub/Sub topics ---------------------------------------------------------------
        confirmation = (
            str(input("Do you want to create Pub/Sub topics at this time? (Y/n): ")).upper()
            if not self.suppress
            else "Y"
        )
        if confirmation != "N":
            for item in ShellCommands.PubSubTopics:
                print(f"Running: {item.value}")
                subprocess.run(item.value, capture_output=True, shell=True, text=True)

        # 7. Cloud Run / Functions env‑vars ----------------------------------------------
        confirmation = (
            str(
                input("Do you want to create the environmental variables at this time? (Y/n): ")
            ).upper()
            if not self.suppress
            else "Y"
        )
        if confirmation != "N":
            EnvironmentVariables(project=self.project).run()

        # 8. Shared‑resource IAM tweaks ----------------------------------------------------
        confirmation = (
            str(
                input(
                    "Do you want to update permissions for shared resources at this time? (Y/n): "
                )
            ).upper()
            if not self.suppress
            else "Y"
        )
        if confirmation != "N":
            env = CloudEnv()
            for item in ShellCommands.SharedResourcePermissions:
                cmd = item.value.format(
                    shared_resource_project=BuildConstants.SharedResourceProjects.MAIN_SHARED_RESOURCE_PROJECT,
                    dest_sa=f"agoge-service@{env.project}.iam.gserviceaccount.com",
                )
                print(f"Running: {cmd}")
                ret = subprocess.run(cmd, capture_output=True, shell=True)
                print(ret.stderr.decode())
                if ret.returncode != 0:
                    print(f"Error adding project permission to shared resources!")
