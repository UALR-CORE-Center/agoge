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

    @staticmethod
    def _command_error(command: str, result: subprocess.CompletedProcess) -> RuntimeError:
        stderr = result.stderr.decode() if isinstance(result.stderr, bytes) else result.stderr
        return RuntimeError(
            f"Command failed ({result.returncode}): {command}\n{(stderr or '').strip()}"
        )

    def _enable_apis(self, api_commands=None) -> None:
        """Enable APIs in the requested tenant project and fail closed."""
        for item in api_commands or ShellCommands.EnableAPIs:
            command = f"{item.value} --project={self.project}"
            print(f"Running: {command}")
            result = subprocess.run(command, capture_output=True, shell=True, text=True)
            if result.returncode != 0:
                raise self._command_error(command, result)

    def ensure_wireguard_prerequisites(self) -> None:
        """Idempotently migrate and validate prerequisites used by gateways."""
        self._enable_apis((
            ShellCommands.EnableAPIs.COMPUTE,
            ShellCommands.EnableAPIs.DNS,
        ))
        settings = EnvironmentVariables(project=self.project)
        settings.ensure_wireguard_defaults()
        required = {
            'parent_project': settings.env.get('parent_project'),
            'parent_dnszone': settings.env.get('parent_dnszone'),
            'wireguard_dns_suffix': settings.env.get('wireguard_dns_suffix'),
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ValueError(
                f"Missing WireGuard DNS prerequisite(s): {', '.join(missing)}"
            )
        env = CloudEnv(project=self.project)

        dns_service = discovery.build('dns', 'v1', cache_discovery=False)
        zone = dns_service.managedZones().get(
            project=env.parent_project,
            managedZone=env.parent_zone,
        ).execute()
        if str(zone.get('visibility') or 'public').lower() != 'public':
            raise ValueError(
                f"Managed zone '{env.parent_zone}' must be public for remote WireGuard peers"
            )
        zone_suffix = str(zone.get('dnsName') or '').strip().lower().rstrip('.')
        wireguard_suffix = str(env.wireguard_dns_suffix).strip().lower().strip('.')
        if not zone_suffix or not (
            wireguard_suffix == zone_suffix
            or wireguard_suffix.endswith(f'.{zone_suffix}')
        ):
            raise ValueError(
                f"wireguard_dns_suffix '{env.wireguard_dns_suffix}' is not in managed "
                f"zone '{zone.get('dnsName')}'"
            )

        managed_zones = dns_service.managedZones()
        zone_resource = (
            f"projects/{env.parent_project}/managedZones/{env.parent_zone}"
        )
        policy = managed_zones.getIamPolicy(
            resource=zone_resource,
            body={'options': {'requestedPolicyVersion': 3}},
        ).execute()
        member = f"serviceAccount:agoge-service@{env.project}.iam.gserviceaccount.com"
        bindings = policy.setdefault('bindings', [])
        dns_admin = next(
            (
                binding
                for binding in bindings
                if binding.get('role') == 'roles/dns.admin'
                and not binding.get('condition')
            ),
            None,
        )
        if dns_admin is None:
            dns_admin = {'role': 'roles/dns.admin', 'members': []}
            bindings.append(dns_admin)
        members = dns_admin.setdefault('members', [])
        if member not in members:
            members.append(member)
            managed_zones.setIamPolicy(
                resource=zone_resource,
                body={'policy': policy},
            ).execute()

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
            self._enable_apis()

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
               Add the shared app hostname (app.<parent-dns-suffix>).
        
         5   In APIs & Services ▸ Credentials ▸ OAuth2 Client ID  
               • Add https://{self.project}.firebaseapp.com/__/auth/handler to *Authorized redirect URIs*
               • Add https://{self.project}.firebaseapp.com and https://app.<parent-dns-suffix> to
                 *Authorized JavaScript origins*.

         Firebase auth defaults to {self.project}.firebaseapp.com; tenant DNS records are not required.
         Existing firebase_auth_domain overrides remain supported.

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

        # 8. Shared-resource and parent-DNS IAM permissions -------------------------------
        confirmation = (
            str(
                input(
                    "Do you want to update shared-resource and parent-DNS permissions at this time? (Y/n): "
                )
            ).upper()
            if not self.suppress
            else "Y"
        )
        if confirmation != "N":
            env = CloudEnv(project=self.project)
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

            self.ensure_wireguard_prerequisites()
