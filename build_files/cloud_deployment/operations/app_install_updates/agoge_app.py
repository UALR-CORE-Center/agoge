import threading
from googleapiclient import discovery
from pathlib import Path
import shutil


from common.utilities.gcp.cloud_env import CloudEnv
from common.exceptions import AgogeValidationError
from cloud_deployment.operations.app_install_updates.firebase_build import prepare_firebase_auth
from cloud_deployment.operations.env_and_quotas.shared_api_secrets import ensure_shared_api_secret_access
from cloud_deployment.utilities import console as ui

CLOUD_BUILD_CONFIGS = Path(__file__).resolve().parent / 'cloudbuild'

# Uploaded with neither image nor function source; .env is kept on purpose.
# gcloud's per-minute API rate limits (e.g. Resource Manager reads) clear on their own.
QUOTA_ERROR_PATTERN = r'status=\[429\]|Quota exceeded|RESOURCE_EXHAUSTED'

STAGING_IGNORE = ('__pycache__', '*.pyc', '.DS_Store', '*.bak', 'tests', 'unit_tests', '*.http')


class Commands:
    # Layer-cached Docker builds; see cloudbuild/*.yaml.
    BASE_BUILD_CLOUD_RUN_COMMAND = (
        "gcloud builds submit {target_dir} --config={config} "
        "--substitutions=_IMAGE={image_path} --project={project}"
    )
    BASE_DEPLOY_CLOUD_RUN_COMMAND = (
        "gcloud run deploy agoge-{app_type} "
        "--image {image_path} "
        "--memory=4096Mi " 
        "--cpu 4 "
        "--platform=managed "
        "--project={project} "
        "--region={region} "
        "--allow-unauthenticated " 
        "--service-account={service_account}"
    )
    # The default TCP probe passes as soon as gunicorn binds the port, before the workers have imported
    # the app; a min instance then idles half-loaded with throttled CPU and its first request waits ~25 s.
    # An HTTP probe (api/health.py) keeps startup CPU until a worker actually answers.
    API_STARTUP_PROBE = (
        "--startup-probe=httpGet.path=/health/ready,httpGet.port=8080,"
        "periodSeconds=3,timeoutSeconds=3,failureThreshold=60"
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
        "--project={project} "
        "--region={region} "
        "--memory=2048Mi "
        "--entry-point=agoge_cloud_function "
        "--runtime=python311 "
        "--source=\"{source}\" "
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
        "--location={region} "
        "--project={project}"
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

    BUILD_CONFIGS = {
        AppType.API: CLOUD_BUILD_CONFIGS / 'cached_image.yaml',
        AppType.REACT: CLOUD_BUILD_CONFIGS / 'cached_multistage_image.yaml',
    }

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
        if app_type in (self.AppType.REACT, self.AppType.API):
            return self.BASE_BUILD_CLOUD_RUN_COMMAND.format(
                target_dir=target_dir, config=self.BUILD_CONFIGS[app_type],
                image_path=image_path, project=self.env.project,
            )

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

        cmd = self.BASE_DEPLOY_CLOUD_RUN_COMMAND.format(
            app_type=app_type,
            image_path=image_path,
            region=self.env.region,
            project=self.env.project,
            service_account=service_account
        )
        if app_type == self.AppType.API:
            cmd = f"{cmd} {self.API_STARTUP_PROBE}"
        if min_instance:
            return f"{cmd} --min-instances=1"
        return cmd

    def deploy_cloud_function(self, source: str = f'./{AppDirectories.STAGING}{AppType.CLOUD_FN}/'):
        service_account = self.ServiceAccounts.AGOGE.format(project=self.env.project)
        return self.DEPLOY_CLOUD_FUNCTION_COMMAND.format(
            source=source,
            project=self.env.project,
            region=self.env.region,
            service_account=service_account,
            project_number=self.env.project_number
        )


class AgogeApp:
    staging_dir = Path(".staging")

    def __init__(
        self,
        suppress: bool = True,
        *,
        project: str | None = None,
    ) -> None:
        self.suppress = suppress
        self.env = CloudEnv(project=project)
        if project and self.env.project != project:
            raise AgogeValidationError(
                f'The environment document project ({self.env.project}) does not match '
                f'the selected project ({project}). Correct its project field before deploying.'
            )
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

    def select_main_app_targets(self) -> tuple[str, ...]:
        """Ask which Cloud Run apps to deploy, before any long-running work starts."""
        confirm_all = int(ui.prompt("Deploy  [0] All   [1] Specific  ›"))
        if confirm_all not in (0, 1):
            raise AgogeValidationError('Choose 0 for All or 1 for Specific.')
        if confirm_all == 0:
            return Commands.AppType.API, Commands.AppType.REACT
        api_or_frontend = int(ui.prompt("App     [0] API   [1] React     ›"))
        if api_or_frontend not in (0, 1):
            raise AgogeValidationError('Choose 0 for API or 1 for React.')
        return (Commands.AppType.API,) if api_or_frontend == 0 else (Commands.AppType.REACT,)

    def deploy_main_app(self, targets: tuple[str, ...] | None = None, *, with_cloud_function: bool = False) -> bool:
        """Deploy the selected Cloud Run apps, optionally alongside the Cloud Function.

        Everything prepares concurrently, but when the API is part of the
        deploy, React and the Cloud Function go live only after the API
        deployment succeeds, so a failed API never sits behind a newer UI or
        a function built against newer shared code.
        """
        targets = targets or self.select_main_app_targets()
        include_frontend = Commands.AppType.REACT in targets
        if include_frontend:
            prepare_firebase_auth(self.env)

        self._backup_env_files()

        try:
            self._write_env_files(include_frontend=include_frontend)
            # Grant parent-secret access once, up front: concurrent grants from
            # the API and function tasks race on the same IAM policy etag.
            deploys_api = Commands.AppType.API in targets
            if deploys_api or with_cloud_function:
                with ui.status('Checking shared API secret access'):
                    ensure_shared_api_secret_access(self.env)
            tasks = []
            wait_for_api = None
            if deploys_api:
                api_finished, api_result = threading.Event(), []

                def deploy_api() -> bool:
                    deployed = False
                    try:
                        deployed = self._deploy_api(preflight=False)
                        return deployed
                    finally:
                        api_result.append(deployed)
                        api_finished.set()

                def wait_for_api() -> bool:
                    ui.set_phase('Waiting for API deployment')
                    api_finished.wait()
                    return api_result[0]

                tasks.append(('API', deploy_api))
            if include_frontend:
                tasks.append(('React', (
                    (lambda: self._deploy_react(wait_for=wait_for_api)) if wait_for_api else self._deploy_react
                )))
            if with_cloud_function:
                tasks.append(('Cloud Function', lambda: self.deploy_cloud_functions(
                    preflight=False, wait_for=wait_for_api,
                )))

            results = ui.run_tasks(f'Deploying to {self.env.project}', tasks)
            return all(results.values())
        finally:
            self._restore_env_files()
            self._remove_empty_staging_root()

    def _deploy_api(self, preflight: bool = True):
        if preflight:
            ensure_shared_api_secret_access(self.env)
        staging = self._stage_build(app_type=Commands.AppType.API)
        try:
            return self._deploy_cloud_run(
                app_type=self.commands.AppType.API,
                target_dir=str(staging),
                min_instance=True
            )
        finally:
            self._remove_staging(staging)

    def _deploy_react(self, wait_for=None):
        return self._deploy_cloud_run(
            app_type=self.commands.AppType.REACT,
            target_dir=self.commands.AppDirectories.REACT,
            wait_for=wait_for,
        )

    def _stage_build(self, app_type: str) -> Path:
        """
        In order to utilize the shared 'common' code, we need to first build the directory
        in a format that resembles the dev environment. Each app gets its own
        .staging/<app_type>/ so the API and Cloud Function can stage concurrently.
        """
        if app_type == Commands.AppType.CLOUD_FN:
            directory = self.cloud_fn_dir
        elif app_type == Commands.AppType.API:
            directory = self.api_dir
        else:
            raise ValueError(f"Invalid app_type {app_type}")

        ui.set_phase(f'Staging {directory}/ + common/')
        staging = self.staging_dir / app_type
        if staging.exists():
            # First clean up any residual files from previous staging
            shutil.rmtree(staging)
        staging.mkdir(parents=True)

        ignore = shutil.ignore_patterns(*STAGING_IGNORE)
        for item in directory.iterdir():
            if ignore(str(directory), [item.name]):
                continue
            dest = staging / item.name
            if item.is_dir():
                shutil.copytree(item, dest, ignore=ignore)
            else:
                shutil.copy2(item, dest)

        shutil.copytree(self.common_dir, staging / "common", ignore=ignore)
        return staging

    @staticmethod
    def _remove_staging(staging) -> None:
        """Remove one app's staging dir. The shared .staging/ root stays, since
        another task may be staging into it concurrently."""
        if isinstance(staging, Path) and staging.exists():
            shutil.rmtree(staging)

    def _remove_empty_staging_root(self) -> None:
        """Call only once no task is running."""
        try:
            self.staging_dir.rmdir()
        except OSError:
            pass  # missing, or still holds a directory

    def _deploy_cloud_run(
        self,
        app_type: str,
        target_dir: str,
        min_instance: bool = False,
        wait_for=None,
    ) -> bool:
        image_path = self.commands.image_path(app_type=app_type)
        build_cmd = self.commands.build_cloud_run(app_type=app_type, target_dir=target_dir)

        if not self._stream_command_output(build_cmd, phase='Building image (Cloud Build)'):
            ui.note(f"Cloud Build failed for agoge-{app_type}; the service was not deployed")
            return False

        if wait_for is not None and not wait_for():
            ui.skip('Built, not deployed: API deploy failed')
            return False

        deploy_cmd = self.commands.deploy_cloud_run(
            app_type=app_type,
            image_path=image_path,
            min_instance=min_instance
        )

        if not self._stream_command_output(deploy_cmd, phase='Deploying Cloud Run revision'):
            ui.note(f"Cloud Run rejected the agoge-{app_type} deployment")
            return False

        return True

    def deploy_cloud_functions(self, preflight: bool = True, wait_for=None) -> bool:
        if preflight:
            ensure_shared_api_secret_access(self.env)
        # This does not need to be run everytime, but this is here temporarily to make sure it gets set up correctly.
        command = self.commands.ADD_DEFAULT_COMPUTE_EDITOR_ROLE.format(project=self.env.project,
                                                                       project_number=self.env.project_number)

        if not self._stream_command_output(command, phase='Granting function service account'):
            ui.note("Could not grant the default compute service account its role; function not deployed")
            return False

        # Build cloud_function directory
        staging = self._stage_build(app_type=Commands.AppType.CLOUD_FN)
        try:
            if wait_for is not None and not wait_for():
                ui.skip('Not deployed: API deploy failed')
                return False
            command = self.commands.deploy_cloud_function(source=f'./{staging}/')
            if not self._stream_command_output(command, phase='Building & deploying function',
                                               retry_on=QUOTA_ERROR_PATTERN, attempts=4):
                ui.note("Cloud Function deployment failed")
                return False
            return self._set_scheduler()
        finally:
            self._remove_staging(staging)

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
            else:
                self.backup_files[env_file] = None

    def _restore_env_files(self):
        """
        Restore the original environment files from backups.
        """
        for original, backup in self.backup_files.items():
            if backup is None:
                original.unlink(missing_ok=True)
            elif backup.exists():
                shutil.move(backup, original)

    def _set_scheduler(self) -> bool:
        parent = f'projects/{self.env.project}/locations/{self.env.region}'
        response = self.service.projects().locations().jobs().list(parent=parent).execute()
        job_exists = False
        for job in response.get('jobs', []):
            if job.get('name', None) == self.job_name:
                job_exists = True
        if not job_exists:
            command = self.commands.CLOUD_SCHEDULER_COMMAND.format(
                project=self.env.project, region=self.env.region
            )
            if not self._stream_command_output(command, phase='Creating maintenance scheduler'):
                ui.note("Could not create the Cloud Scheduler job")
                return False
        return True

    @staticmethod
    def _stream_command_output(command: str, phase: str | None = None, **retry) -> bool:
        """Run a command on the live task board; its full output goes to the task log."""
        return ui.run_command(command, phase=phase, **retry)

    def _write_env_files(self, *, include_frontend: bool = True):
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
                    # Existing standalone deployments may retain explicit
                    # overrides. Shared projects need only PARENT_DOMAIN.
                    "DOMAIN": (self.env.env_dict.get('dns_suffix') or '').strip('.') or None,
                    "SUB_DOMAIN": self.env.env_dict.get('app_sub_domain'),
                }
            ),
            remove_variables=('DOMAIN', 'SUB_DOMAIN'),
        )

        if not include_frontend:
            return

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
                    "VITE_PROJECT_PATH": f"/{self.env.project_path}/" if self.env.project_path else '/',
                }
            ),
        )

    def _update_env_file(self, env_file: Path, new_variables: dict, remove_variables=()):
        """
        Update or create an environment file with the given variables.
        Preserves existing variables not explicitly updated.
        """
        try:
            env_variables = self._read_env_file(env_file)
            for key in remove_variables:
                env_variables.pop(key, None)
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
