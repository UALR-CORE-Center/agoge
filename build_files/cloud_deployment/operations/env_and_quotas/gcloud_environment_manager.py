import os
import shutil
import sys
import subprocess
from pathlib import Path
from typing import Sequence

from dotenv import load_dotenv

from common.exceptions import AgogeValidationError
from .project_menu import ProjectMenu

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

    def __init__(self, env_file=ENV_FILE, *, load_configurations: bool = True) -> None:
        self.env_file = env_file
        self.configurations = {}
        self._account_changed = False
        self._gcloud = shutil.which("gcloud") or shutil.which("gcloud.cmd")
        if load_configurations:
            self.load_configurations()

    def load_configurations(self) -> dict:
        """Load environment configurations"""
        projects = ProjectMenu().configurations()
        self.configurations = projects
        return projects

    def _run_gcloud(
        self,
        args: Sequence[str],
        *,
        interactive: bool = False,
        timeout: int | None = None,
    ) -> subprocess.CompletedProcess:
        """Run gcloud without hiding interactive authentication prompts."""
        if not self._gcloud:
            raise AgogeValidationError(
                "Google Cloud CLI was not found. Install it and ensure gcloud is on PATH."
            )

        command = [self._gcloud, *args]
        try:
            return subprocess.run(
                command,
                capture_output=not interactive,
                text=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise AgogeValidationError(
                f"Timed out while running: gcloud {' '.join(args)}"
            ) from exc

    @staticmethod
    def _gcloud_error(result: subprocess.CompletedProcess) -> str:
        return (result.stderr or result.stdout or "Unknown gcloud error").strip()

    def get_current_account(self):
        """Get the currently logged-in gcloud account."""
        result = self._run_gcloud(
            ["config", "get-value", "account"],
            timeout=30,
        )
        if result.returncode != 0:
            print(f"{RED}[!!] Error: {self._gcloud_error(result)}{NC}")
            return None
        account = result.stdout.strip()
        return account if account and account != "(unset)" else None

    def set_account(self):
        """Allow the user to set a different gcloud account."""
        current_account = self.get_current_account()
        print(f"{CYAN}\nAvailable Accounts:{NC}")
        result = self._run_gcloud(["auth", "list"], timeout=30)
        if result.returncode != 0:
            raise AgogeValidationError(
                f"Unable to list gcloud accounts: {self._gcloud_error(result)}"
            )
        print(f"{CYAN}{result.stdout}{NC}")
        new_account = input(
            f"{YELLOW}\nEnter the email of the account to use "
            f"(or press Enter to keep current): {NC}"
        ).strip()
        if not new_account:
            print(f"{CYAN}No changes made to the account.{NC}")
            return current_account

        result = self._run_gcloud(
            ["config", "set", "account", new_account],
            timeout=30,
        )
        if result.returncode != 0:
            raise AgogeValidationError(
                f"Unable to select account {new_account}: {self._gcloud_error(result)}"
            )
        self._account_changed = new_account != current_account
        print(f"{GREEN}[+] Successfully set account to: {new_account}{NC}")
        return new_account

    def ensure_credentials(
        self,
        *,
        account: str | None = None,
        quota_project: str | None = None,
        force: bool = False,
        synchronize: bool = False,
        prompt: bool = True,
    ) -> None:
        """Validate both gcloud credentials and ADC, refreshing when needed."""
        account = account or self.get_current_account()
        if force or synchronize:
            self.refresh_credentials(
                account=account,
                quota_project=quota_project,
                force=force,
            )
            return

        failures = self._credential_failures(account)
        if failures:
            reason = "; ".join(failures)
            if prompt:
                answer = input(
                    f"{YELLOW}Google Cloud credentials need attention ({reason}). "
                    f"Re-authenticate now? (Y/n): {NC}"
                ).strip().lower()
                if answer not in {"", "y", "yes"}:
                    raise AgogeValidationError(
                        "Google Cloud authentication is required. Run "
                        "`python setup.py --reauthenticate`."
                    )
                self.refresh_credentials(
                    account=account,
                    quota_project=quota_project,
                    force=True,
                )
                return
            raise AgogeValidationError(
                f"Google Cloud credentials are not usable ({reason}). Run "
                "`python setup.py --reauthenticate`."
            )

        if quota_project:
            self.set_adc_quota_project(quota_project)

    def refresh_credentials(
        self,
        *,
        account: str | None = None,
        quota_project: str | None = None,
        force: bool = True,
    ) -> None:
        """Refresh the CLI login and write the same identity to ADC."""
        adc_override = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        if adc_override:
            raise AgogeValidationError(
                "GOOGLE_APPLICATION_CREDENTIALS is set, so Python is using that "
                f"credential file instead of user ADC: {adc_override}. Unset it before "
                "running `python setup.py --reauthenticate`, or grant that service "
                "account the required permissions."
            )

        print(
            f"{CYAN}Refreshing gcloud and Application Default Credentials. "
            f"Complete the browser sign-in if prompted.{NC}"
        )
        args = ["auth", "login"]
        if account:
            args.append(account)
        if force:
            args.append("--force")
        if quota_project:
            args.append(f"--project={quota_project}")

        # Authentication must inherit stdin/stdout. Capturing this command's
        # output hides authorization URLs and password/security-key prompts.
        result = self._run_gcloud(args, interactive=True)
        if result.returncode != 0:
            raise AgogeValidationError(
                "gcloud login failed. Check the error above and retry "
                "`python setup.py --reauthenticate`."
            )

        active_account = self.get_current_account()
        if not active_account or (account and active_account.lower() != account.lower()):
            raise AgogeValidationError(
                "gcloud did not activate the selected account. ADC was not changed. "
                "Run `python setup.py --reauthenticate` and select the intended account."
            )
        account = active_account

        # A successful cached CLI login is not sufficient evidence that ADC was
        # written. Explicitly synchronize it even if an old ADC token is valid,
        # since that token could belong to another account. Passing ACCOUNT lets
        # gcloud reuse the selected user's login while writing the ADC file.
        print(f"{CYAN}Synchronizing Application Default Credentials for {account}.{NC}")
        adc_args = ["auth", "application-default", "login", account]
        if quota_project:
            adc_args.append(f"--project={quota_project}")
        result = self._run_gcloud(adc_args, interactive=True)
        if result.returncode != 0:
            raise AgogeValidationError(
                "gcloud login succeeded, but Application Default Credentials login failed. "
                "Check the error above and retry `python setup.py --reauthenticate`."
            )

        failures = self._credential_failures(account)
        if failures:
            raise AgogeValidationError(
                "Authentication completed, but credential validation failed: "
                + "; ".join(failures)
            )
        if quota_project:
            self.set_adc_quota_project(quota_project)
        self._account_changed = False
        print(f"{GREEN}[+] gcloud and Application Default Credentials are ready.{NC}")

    def _credential_failures(self, account: str | None) -> list[str]:
        failures = []
        if not account:
            failures.append("no active gcloud account")
        else:
            cli_token = self._run_gcloud(
                ["auth", "print-access-token", account],
                timeout=45,
            )
            if cli_token.returncode != 0 or not cli_token.stdout.strip():
                failures.append(self._token_failure(
                    "gcloud login", cli_token, "gcloud auth print-access-token"
                ))

        adc_token = self._run_gcloud(
            ["auth", "application-default", "print-access-token"],
            timeout=45,
        )
        if adc_token.returncode != 0 or not adc_token.stdout.strip():
            failures.append(self._token_failure(
                "Application Default Credentials", adc_token,
                "gcloud auth application-default print-access-token",
            ))
        return failures

    @staticmethod
    def _token_failure(label: str, result: subprocess.CompletedProcess, command: str) -> str:
        """Describe known token failures without echoing tokens or raw error bodies."""
        error = (result.stderr or "").lower()
        if result.returncode == 0:
            reason = "gcloud returned no access token"
        elif any(value in error for value in ("invalid_grant", "invalid_rapt", "reauth", "expired or revoked")):
            reason = "the stored login needs browser re-authentication; run `python setup.py --reauthenticate`"
        elif any(value in error for value in ("default credentials were not found", "could not automatically determine credentials")):
            reason = "the credential file was not found"
        elif any(value in error for value in ("connection", "proxy", "ssl", "certificate", "timed out", "name resolution")):
            reason = "a network, proxy, or TLS error prevented token validation"
        elif any(value in error for value in ("permission_denied", "permission denied", "serviceusage.services.use", "quota project")):
            reason = "a permission or quota-project error prevented validation"
        elif any(value in error for value in ("jsondecodeerror", "not a valid json")):
            reason = "the credential file could not be parsed"
        else:
            reason = f"gcloud exited with code {result.returncode}"
        redirect = "> $null" if os.name == "nt" else "> /dev/null"
        return (
            f"{label} validation failed ({reason}). "
            f"To see gcloud's error, run `{command} {redirect}` in "
            + ("PowerShell" if os.name == "nt" else "a terminal")
        )

    def set_adc_quota_project(self, project_id: str) -> None:
        """Set the quota project used by local Python client libraries."""
        if os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
            print(
                f"{YELLOW}[!] Skipping ADC quota-project update because "
                f"GOOGLE_APPLICATION_CREDENTIALS is set.{NC}"
            )
            return
        result = self._run_gcloud(
            [
                "auth",
                "application-default",
                "set-quota-project",
                project_id,
            ],
            timeout=45,
        )
        if result.returncode != 0:
            raise AgogeValidationError(
                f"Unable to set ADC quota project to {project_id}: "
                f"{self._gcloud_error(result)}. The selected account needs "
                "serviceusage.services.use on that project."
            )

    def display_menu(self):
        """Display a menu of environments for user selection."""
        if not self.configurations:
            self.load_configurations()
        print(f"{CYAN}\nAvailable Environments:{NC}")
        for index, env_name in enumerate(self.configurations.keys(), start=1):
            print(f"{index}. {env_name}")
        print()

    def select_environment(self):
        """Prompt the user to select an environment by number."""
        if not self.configurations:
            self.load_configurations()
        keys = list(self.configurations.keys())
        if not keys:
            raise AgogeValidationError('No visible environments. Use --show-environment PROJECT_ID to restore one.')
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
        if not self.configurations:
            self.load_configurations()
        env_config = self.configurations.get(env_name)
        return env_config["project_id"]


    def switch_environment(self, env_name) -> str:
        """Switch to the selected environment by configuring gcloud and updating .env."""
        env_config = self.configurations.get(env_name)
        if not env_config:
            print(f"{RED}[!!] Error: Configuration for environment '{env_name}' not found.{NC}")
            sys.exit(1)

        # Set both the gcloud target and the quota project used by ADC-backed
        # Python libraries. These are separate credential/configuration stores.
        project_id = env_config["project_id"]
        result = self._run_gcloud(
            ["config", "set", "project", project_id],
            timeout=30,
        )
        if result.returncode != 0:
            raise AgogeValidationError(
                f"Unable to select project {project_id}: {self._gcloud_error(result)}"
            )
        self.ensure_credentials(
            account=self.get_current_account(),
            quota_project=project_id,
            synchronize=self._account_changed,
        )
        print(f"{GREEN}[+] Successfully set gcloud project to: {project_id}{NC}")

        # Load .env file to set the impersonation account
        load_dotenv(self.env_file)
        print(f"{GREEN}[+] Successfully switched to environment: {env_name}{NC}")
        return project_id
