import time
from datetime import datetime, timezone
import subprocess
import pathlib

from common.constants.database import DatabaseTypes, DATABASE_NAME, DbCollections
from common.constants.build_constants import BuildConstants
from common.document_database import DocumentDatabaseFactory

from cloud_deployment.utilities.menu_options import SetupOptions, ProjectMaintenanceOptions
from cloud_deployment.operations.app_install_updates.base_build import BaseBuild
from cloud_deployment.operations.env_and_quotas.environment_variables import EnvironmentVariables
from cloud_deployment.operations.env_and_quotas.gcloud_environment_manager import GcloudEnvironmentManager
from cloud_deployment.operations.app_install_updates.agoge_app import AgogeApp
from cloud_deployment.operations.app_install_updates.classified_app import ClassifiedApp
from cloud_deployment._archive.build_specification import BuildSpecification
from cloud_deployment.operations.images_and_specs.default_server_image import DefaultServerImage
from cloud_deployment.operations.images_and_specs.local_to_cloud import LocalToCloud
from cloud_deployment.operations.env_and_quotas.increase_quotas import QuotaManager
from cloud_deployment.operations.project_manager import ProjectManager
from cloud_deployment.operations.images_and_specs.custom_image_import_manager import CustomImageImportManager
from cloud_deployment.operations.app_install_updates.install_update_manager import InstallUpdateManager
from cloud_deployment.utilities.menu_options import (
    SetupOptions,
    ProjectMaintenanceOptions,
    display_project_maintenance_menu,
    get_project_maintenance_selection,
    get_project_maintenance_operation,
    get_project_maintenance_menu_length,
    get_user_selection,
)
from cloud_deployment.utilities.menu_options import get_user_selection

from cloud_deployment.operations.guacamole_image_management.guacamole_image_manager import (
    GuacamoleImageManager,
)

from .operations.project_maintenance.rebuild_guacamole_for_unit import RebuildGuacamoleForUnit
from .operations.project_maintenance.extend_project_expiration import ExtendWorkoutExpirations

class SetupManager:
    """
    Handles the execution of selected setup operations (e.g., full updates, environment variable syncs, etc.)
    based on the user's choice from the menu system.
    """

    def __init__(self, selection, project) -> None:
        """
        :param selection: A SetupOptions enum value indicating which operation to run.
        :param project: The GCP project ID to apply operations to.
        """
        self.selection = selection
        self.project = project

    def run(self, new_selection: SetupOptions = None) -> None:
        """
        Executes the selected operation. In case of missing environment variables (KeyError),
        attempts to synchronize environment variables before retrying or exiting.
        """
        self.selection = new_selection or self.selection
        # Create a map of selection values to the corresponding operations
        operation_map = {
            SetupOptions.FULL: lambda: InstallUpdateManager(self.project).run_full_install(),
            SetupOptions.UPDATE: lambda: InstallUpdateManager(self.project).run_update(),
            SetupOptions.CLOUD_FUNCTION: lambda: AgogeApp().deploy_cloud_functions(),
            SetupOptions.MAIN_APP: lambda: AgogeApp().deploy_main_app(),
            SetupOptions.DEFAULT_SERVER_IMAGES: lambda: DefaultServerImage().run(),
            SetupOptions.CLASSIFIED_APP: lambda: ClassifiedApp().deploy(),
            SetupOptions.ENV: lambda: EnvironmentVariables(project=self.project).run(),
            SetupOptions.IMPORT_CUSTOM_IMAGES: lambda: CustomImageImportManager().run(),
            SetupOptions.IMPORT_LOCAL_IMAGE: lambda: LocalToCloud().run(),
            SetupOptions.STARTUP_SCRIPTS_AND_INSTRUCTIONS: lambda: BuildSpecification().sync_startup_scripts_and_instructions(),
            SetupOptions.INCREASE_QUOTAS: lambda: QuotaManager(project=self.project).request_all(),
            SetupOptions.REFRESH_GCP_CREDENTIALS: self._refresh_gcp_credentials,
            SetupOptions.PROJECT_CREATION: lambda: ProjectManager().create(),
            SetupOptions.PROJECT_DELETE: lambda: ProjectManager().delete(),
            SetupOptions.PROJECT_MAINTENANCE: lambda: self._run_project_maintenance_menu(),
            SetupOptions.REFRESH_GUACAMOLE_IMAGE_AND_CERT: (
                lambda: GuacamoleImageManager(
                    project=self.project
                ).create_guac_project_image()
            ),
        }

        try:
            # Retrieve the operation based on the current selection
            operation = operation_map.get(self.selection)
            if operation:
                operation()  # execute

        except KeyError as e:
            print(f"A KeyError occurred, possibly due to a missing environment variable: {e}")
            print(f"Attempting to synchronize environment variables for project '{self.project}' before retrying.")
            EnvironmentVariables(project=self.project).run()

    def _refresh_gcp_credentials(self) -> None:
        auth_manager = GcloudEnvironmentManager(load_configurations=False)
        auth_manager.refresh_credentials(
            account=auth_manager.get_current_account(),
            quota_project=self.project,
            force=True,
        )

    def _run_project_maintenance_menu(self) -> None:
        while True:
            display_project_maintenance_menu()
            choice = get_user_selection(get_project_maintenance_menu_length())
            selection = get_project_maintenance_selection(choice)

            if selection == ProjectMaintenanceOptions.BACK:
                break

            operation_class = get_project_maintenance_operation(choice)
            if operation_class:
                operation_kwargs = {}
                if getattr(operation_class, "REQUIRES_PROJECT", False):
                    operation_kwargs["project"] = self.project
                operation_class(**operation_kwargs).run()
            else:
                print(f"Unsupported maintenance selection: {selection}")
