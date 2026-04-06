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
from cloud_deployment.operations.app_install_updates.agoge_app import AgogeApp
from cloud_deployment.operations.app_install_updates.classified_app import ClassifiedApp
from cloud_deployment._archive.build_specification import BuildSpecification
from cloud_deployment.operations.images_and_specs.default_server_image import DefaultServerImage
from cloud_deployment.operations.images_and_specs.local_to_cloud import LocalToCloud
from cloud_deployment.operations.env_and_quotas.increase_quotas import QuotaManager
from cloud_deployment.operations.project_manager import ProjectManager
from cloud_deployment.operations.images_and_specs.custom_image_import_manager import CustomImageImportManager
from cloud_deployment.operations.app_install_updates.install_update_manager import InstallUpdateManager
from .utilities.maintenance_menu_options import (display_project_maintenance_menu, get_project_maintenance_selection,
                                                 project_maintenance_menu)
from cloud_deployment.utilities.menu_options import get_user_selection

from .operations.project_maintenance.rebuild_guacamole_for_unit import RebuildGuacamoleForUnit

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
            SetupOptions.PROJECT_CREATION: lambda: ProjectManager().create(),
            SetupOptions.PROJECT_DELETE: lambda: ProjectManager().delete(),
            SetupOptions.PROJECT_MAINTENANCE: lambda: self._run_project_maintenance_menu(),
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

    def _run_project_maintenance_menu(self) -> None:
        """
        Display and execute the project maintenance submenu until the user selects Back.
        """
        while True:
            display_project_maintenance_menu()
            choice = get_user_selection(len(project_maintenance_menu["options"]))
            maintenance_selection = get_project_maintenance_selection(choice)

            if maintenance_selection == ProjectMaintenanceOptions.BACK:
                break

            self._run_project_maintenance_operation(maintenance_selection)

    def _run_project_maintenance_operation(
            self,
            selection: ProjectMaintenanceOptions,
    ) -> None:
        maintenance_operation_map = {
            ProjectMaintenanceOptions.REIMAGE_GUACAMOLE: (
                lambda: RebuildGuacamoleForUnit().run()
            ),
        }

        operation = maintenance_operation_map.get(selection)
        if operation:
            operation()
        else:
            print(f"Unsupported maintenance selection: {selection}")