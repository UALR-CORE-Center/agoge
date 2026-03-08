import subprocess
import sys


class AccountImpersonation:
    SET_WORKLOAD_IDENTITY_POOL = 'gcloud iam workload-identity-pools create {project}-labs-pool --location="global" ' \
                                 '--description="Workload Identity Pool for local development" ' \
                                 '--display-name="LocalDevPool"'

    CREATE_OIDC_PROVIDER = 'gcloud iam workload-identity-pools providers create-oidc {project}-labs-provider ' \
                           '--location="global" ' \
                           '--workload-identity-pool={project}-labs-pool ' \
                           '--display-name="LocalDevProvider" ' \
                           '--attribute-mapping="google.subject=assertion.sub,attribute.email=assertion.email" ' \
                           '--issuer-uri="https://accounts.google.com"'

    GRANT_IAM_ROLE = 'gcloud iam service-accounts add-iam-policy-binding ' \
                     '{service_account_name}@{project}.iam.gserviceaccount.com ' \
                     '--role="roles/iam.workloadIdentityUser" ' \
                     '--member="principalSet://iam.googleapis.com/projects/{project_number}' \
                     '/locations/global/workloadIdentityPools/{project}-pool/attribute.email/{user_email}"'
    SERVICE_ACCOUNT_ADDRESS = '{service_account_name}@{project}.iam.gserviceaccount.com'

    def __init__(
        self,
        project: str,
        project_number: str
    ) -> None:
        self.project = project
        self.project_number = project_number

    def run(self):
        try:
            workload_identity_cmd = self.SET_WORKLOAD_IDENTITY_POOL.format(project=self.project)
            self._run_command(workload_identity_cmd)
        except Exception as e:
            if 'ALREADY_EXISTS' not in str(e):
                raise Exception(f"Failed to create Workout Identity Pool. {e}")
            pass

        try:
            create_oidc_cmd = self.CREATE_OIDC_PROVIDER.format(project=self.project)
            self._run_command(create_oidc_cmd)
        except Exception as e:
            if 'ALREADY_EXISTS' not in str(e):
                raise Exception(f"Failed to create workout identity OIDC. {e}")
            pass

        user_email = str(input("Email associated with project: ")).strip(" ")
        service_account_name = str(input("Target Service Account Name (String preceding '@' in service account): ")).strip(" ")
        if user_email != '' and service_account_name != '':
            try:
                grant_iam = self.GRANT_IAM_ROLE.format(
                    service_account_name=service_account_name,
                    project=self.project,
                    project_number=self.project_number,
                    user_email=user_email
                )
                self._run_command(grant_iam)
            except Exception as e:
                raise Exception(f"Failed to grant IAM Role to user, {user_email}. {e}")

            service_acc_addr = self.SERVICE_ACCOUNT_ADDRESS.format(
                service_account_name=service_account_name,
                project=self.project
            )
            print(f"Impersonation successful! Set the following environment variable and run the script again: "
                  f"`GOOGLE_IMPERSONATED_SERVICE_ACCOUNT={service_acc_addr}`")
            sys.exit()
        else:
            raise Exception("Cannot create IAM permissions with empty values")

    @staticmethod
    def _run_command(command: str) -> bool:
        ret = subprocess.run(command, capture_output=True, shell=True, text=True)
        ret_msg = ret.stderr.strip() or ret.stdout.strip()  # Log stderr if available, else stdout
        if ret.returncode != 0:
            raise Exception(f"{ret_msg}")
        return True
