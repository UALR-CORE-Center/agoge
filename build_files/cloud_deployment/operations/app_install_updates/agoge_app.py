import subprocess
from googleapiclient import discovery
from pathlib import Path
import shutil


from common.utilities.gcp.cloud_env import CloudEnv


class Commands:
    BASE_BUILD_CLOUD_RUN_COMMAND = "gcloud builds submit {target_dir} --tag {image_path}"
    BUILD_API_CLOUD_RUN_COMMAND = "gcloud builds submit . --tag {image_path}"
    BASE_DEPLOY_CLOUD_RUN_COMMAND = (
        "gcloud run deploy agoge-{app_type} "
        "--image {image_path} "
        "--memory=4096Mi " 
        "--cpu 4 "
        "--platform=managed "
        "--region={region} "
        "--allow-unauthenticated " 
        "--service-account={service_account}"
    )
    ADD_DEFAULT_COMPUTE_EDITOR_ROLE = (
        "gcloud projects add-iam-policy-binding {project} "
        "--member=serviceAccount:{project_number}-compute@developer.gserviceaccount.com "
        "--condition=None "
        "--role=\"roles/editor\""
    )
    DEPLOY_CLOUD_FUNCTION_COMMAND = (
        "gcloud functions deploy --quiet agoge "
        "--gen2 "
        "--region={region} "
        "--memory=2048Mi "
        "--entry-point=agoge_cloud_function "
        "--runtime=python311 "
        "--source=\"./.staging/\" "
        "--service-account={project_number}-compute@developer.gserviceaccount.com "
        "--run-service-account={service_account} "
        "--timeout=540s "
        "--trigger-topic=agoge "
    )
    CLOUD_SCHEDULER_NAME = "agoge-hourly-maintenance"
    SCHEDULE = "*/15 * * * *"
    CLOUD_SCHEDULER_COMMAND = (
        f"gcloud scheduler jobs create pubsub {CLOUD_SCHEDULER_NAME} "
        f"--schedule=\"{SCHEDULE}\" "
        f"--topic=agoge "
        f"--message-body=Hello! "
        f"--attributes=handler=MAINTENANCE "
        f"--location=us-central1"
    )

    class ServiceAccounts:
        REACT = "agoge-react-service@{project}.iam.gserviceaccount.com"
        AGOGE = "agoge-service@{project}.iam.gserviceaccount.com"

    class AppType:
        REACT = 'react'
        API = 'api'
        CLOUD_FN = 'cloud_fn'

    class AppDirectories:
        REACT = 'frontend/'
        API = 'api/'
        STAGING = '.staging/'

    def __init__(self, env):
        self.env = env

    def image_path(
        self,
        app_type: str
    ) -> str:
        return f"gcr.io/{self.env.project}/agoge-{app_type}"

    def build_cloud_run(
        self,
        app_type: str,
        target_dir: str
    ) -> str:
        image_path = self.image_path(app_type)
        print(f"Submitting build for agoge-{app_type} in {self.env.project}")
        if app_type == self.AppType.REACT:
            return self.BASE_BUILD_CLOUD_RUN_COMMAND.format(target_dir=target_dir, image_path=image_path)
        elif app_type == self.AppType.API:
            return self.BASE_BUILD_CLOUD_RUN_COMMAND.format(target_dir=target_dir, image_path=image_path)

    def deploy_cloud_run(
        self,
        app_type: str,
        image_path: str,
        min_instance: bool = False
    ) -> str:
        if app_type == self.AppType.REACT:
            service_account = self.ServiceAccounts.REACT.format(project=self.env.project)
        else:
            service_account = self.ServiceAccounts.AGOGE.format(project=self.env.project)

        print(f"Deploying agoge-{app_type} in {self.env.project} using service account {service_account}")
        cmd = self.BASE_DEPLOY_CLOUD_RUN_COMMAND.format(
            app_type=app_type,
            image_path=image_path,
            region=self.env.region,
            service_account=service_account
        )
        if min_instance:
            return f"{cmd} --min-instances=1"
        return cmd

    def deploy_cloud_function(self):
        service_account = self.ServiceAccounts.AGOGE.format(project=self.env.project)
        return self.DEPLOY_CLOUD_FUNCTION_COMMAND.format(
            project=self.env.project,
            region=self.env.region,
            service_account=service_account,
            project_number=self.env.project_number
        )


class AgogeApp:
    def __init__(
        self,
        suppress: bool = True
    ) -> None:
        self.suppress = suppress
        self.env = CloudEnv()
        self.service = discovery.build('cloudscheduler', 'v1')
        self.commands = Commands(env=self.env)
        self.job_name = (f"projects/{self.env.project}/locations/{self.env.region}/jobs/"
                         f"{self.commands.CLOUD_SCHEDULER_NAME}")
        # Paths for environment files
        self.fastapi_env_file = Path("api/.env")
        self.react_vite_env_file = Path("frontend/.env.production")
        self.backup_files = {}

        # Paths for build staging
        self.staging_dir = Path(".staging")
        self.common_dir = Path("common")
        self.cloud_fn_dir = Path("cloud_functions")
        self.api_dir = Path("api")

    def deploy_main_app(self) -> bool:
        confirm_all = int(input("Deploy\n - [0] All\n - [1] Specific\nSelection: "))

        self._backup_env_files()

        try:
            self._write_env_files()
            if confirm_all == 0:
                if not self._deploy_api():
                    return False
                return self._deploy_react()
            else:
                api_or_frontend = int(input("Select an app to deploy:\n - [0] API\n - [1] React\nSelection: "))
                if api_or_frontend == 0:
                    return self._deploy_api()
                else:
                    return self._deploy_react()
        finally:
            self._restore_env_files()

    def _deploy_api(self):
        self._stage_build(app_type=Commands.AppType.API)

        return self._deploy_cloud_run(
            app_type=self.commands.AppType.API,
            target_dir=self.commands.AppDirectories.STAGING,
            min_instance=True
        )

    def _deploy_react(self):
        return self._deploy_cloud_run(
            app_type=self.commands.AppType.REACT,
            target_dir=self.commands.AppDirectories.REACT
        )

    def _stage_build(self, app_type: str) -> None:
        """
        In order to utilize the shared 'common' code, we need to first build the directory
        in a format that resembles the dev environment
        """
        print(f'Staging build for {app_type} in {self.env.project}')
        if self.staging_dir.exists():
            # First clean up any residual files from previous staging
            shutil.rmtree(self.staging_dir)

        self.staging_dir.mkdir()
        if app_type == Commands.AppType.CLOUD_FN:
            print('... copying cloud_functions/ into .staging/')
            directory = self.cloud_fn_dir
        elif app_type == Commands.AppType.API:
            print('... copying api/ into .staging/')
            directory = self.api_dir
        else:
            raise ValueError(f"Invalid app_type {app_type}")

        for item in directory.iterdir():
            dest = self.staging_dir / item.name
            if item.is_dir():
                shutil.copytree(item, dest)
            else:
                shutil.copy2(item, dest)

        print('...copying common/ into .staging/')
        shutil.copytree(self.common_dir, self.staging_dir / "common")

    def _deploy_cloud_run(
        self,
        app_type: str,
        target_dir: str,
        min_instance: bool = False
    ) -> bool:
        image_path = self.commands.image_path(app_type=app_type)

        print(f"Beginning to package Agoge apps. This operation may take a few minutes...")
        build_cmd = self.commands.build_cloud_run(app_type=app_type, target_dir=target_dir)

        if not self._stream_command_output(build_cmd):
            print(f"Error packaging the Cloud Run App! Exiting without deploying the Cloud Run App")
            return False

        deploy_cmd = self.commands.deploy_cloud_run(
            app_type=app_type,
            image_path=image_path,
            min_instance=min_instance
        )

        if not self._stream_command_output(deploy_cmd):
            print(f"Error deploying the Cloud Run {app_type.upper()} app! Exiting without deploying the Cloud Run app")
            return False

        return True

    def deploy_cloud_functions(self) -> bool:
        # This does not need to be run everytime, but this is here temporarily to make sure it gets set up correctly.
        print(f"Setting the default cloud function service account permissions to the editor role.")
        command = self.commands.ADD_DEFAULT_COMPUTE_EDITOR_ROLE.format(project=self.env.project,
                                                                       project_number=self.env.project_number)

        if not self._stream_command_output(command):
            print(f"Error deploying the cloud function! See messages above. Exiting without deploying the "
                  f"cloud function")
            return False

        # Build cloud_function directory
        self._stage_build(app_type=Commands.AppType.CLOUD_FN)

        # Deploy function
        print(f"Beginning to deploy cloud function. This operation may take a few minutes...")
        command = self.commands.deploy_cloud_function()
        if not self._stream_command_output(command):
            print(f"Error deploying the cloud function! See messages above. Exiting without deploying the "
                  f"cloud function")
            return False
        self._set_scheduler()

        if self.staging_dir.exists():
            print('... removing temporary .staging directory ')
            shutil.rmtree(self.staging_dir)
        return True

    def _backup_env_files(self):
        """
        Create backups of the existing environment files.
        """
        self.backup_files = {}
        for env_file in [self.fastapi_env_file, self.react_vite_env_file]:
            if env_file.exists():
                backup_path = env_file.with_suffix(env_file.suffix + ".bak")
                shutil.copy(env_file, backup_path)
                self.backup_files[env_file] = backup_path

    def _restore_env_files(self):
        """
        Restore the original environment files from backups.
        """
        for original, backup in self.backup_files.items():
            if backup.exists():
                shutil.move(backup, original)
                print(f"Restored original file: {original}")

    def _set_scheduler(self) -> None:
        parent = f'projects/{self.env.project}/locations/{self.env.region}'
        response = self.service.projects().locations().jobs().list(parent=parent).execute()
        job_exists = False
        for job in response.get('jobs', []):
            if job.get('name', None) == self.job_name:
                job_exists = True
        if not job_exists:
            if not self._stream_command_output(self.commands.CLOUD_SCHEDULER_COMMAND):
                print(f"Error setting up the cloud scheduler! See messages above.")

    @staticmethod
    def _stream_command_output(command: str) -> bool:
        """Helper method to stream the output of a subprocess command"""
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, text=True)

        for line in process.stdout:
            print(line, end="")

        for line in process.stderr:
            print(line, end="")

        process.wait()
        return process.returncode == 0

    def _write_env_files(self):
        """
        Write variables to the environment files for FastAPI and React Vite.
        """
        if not self.env:
            raise ValueError("Environment variables are not properly initialized.")

        # Write to FastAPI environment file
        self._update_env_file(
            self.fastapi_env_file,
            self._filter_valid_variables(
                {
                    "DEVELOPMENT": "false",
                    "PARENT_DOMAIN": self.env.parent_dns_suffix.lstrip('.'),
                    "DOMAIN": self.env.dns_suffix.lstrip('.'),
                    "SUB_DOMAIN": self.env.app_sub_domain,
                }
            ),
        )

        # Write to React Vite environment file
        self._update_env_file(
            self.react_vite_env_file,
            self._filter_valid_variables(
                {
                    "VITE_ENV": "production",
                    "VITE_AGOGE_API_URL": (
                        f"https://api{self.env.parent_dns_suffix}/"
                        if self.env.parent_dns_suffix
                        else (
                            f"https://api{self.env.dns_suffix}/"
                            if self.env.dns_suffix
                            else None
                        )
                    ),
                    "VITE_FIREBASE_KEY": self.env.api_key,
                    "VITE_FIREBASE_AUTH_DOMAIN": self.env.firebase_auth_domain,
                    "VITE_PROJECT_ID": self.env.project,
                    "VITE_PROJECT_PATH": f"/{self.env.project_path}/",
                }
            ),
        )

    def _update_env_file(self, env_file: Path, new_variables: dict):
        """
        Update or create an environment file with the given variables.
        Preserves existing variables not explicitly updated.
        """
        try:
            env_variables = self._read_env_file(env_file)
            env_variables.update(new_variables)  # Update or add new variables
            with open(env_file, "w") as file:
                for key, value in env_variables.items():
                    file.write(f"{key}={value}\n")
        except Exception as e:
            raise IOError(f"Error updating environment file {env_file}: {e}")

    def _read_env_file(self, env_file: Path) -> dict:
        """
        Read existing variables from the given .env file.
        Returns an empty dictionary if the file doesn't exist.
        """
        variables = {}
        if env_file.exists():
            try:
                with open(env_file, "r") as file:
                    for line in file:
                        line = line.strip()
                        if line and not line.startswith("#"):
                            key, sep, value = line.partition("=")
                            if sep:
                                variables[key.strip()] = value.strip()
            except Exception as e:
                raise IOError(f"Error reading environment file {env_file}: {e}")
        return variables

    def _filter_valid_variables(self, variables: dict) -> dict:
        """
        Filter out variables with None values.
        """
        return {key: value for key, value in variables.items() if value is not None}
