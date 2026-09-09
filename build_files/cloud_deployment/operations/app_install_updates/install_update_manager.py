import time
from datetime import datetime, timezone
import subprocess
import pathlib

from common.constants.database import DatabaseTypes, DATABASE_NAME, DbCollections
from common.constants.build_constants import BuildConstants
from common.constants.project_constants import CURRENT_VERSION
from common.document_database import DocumentDatabaseFactory
from cloud_deployment.operations.app_install_updates.base_build import BaseBuild
from cloud_deployment.operations.app_install_updates.agoge_app import AgogeApp
from cloud_deployment.operations.app_install_updates.shared_load_balancer import SharedLoadBalancer
from cloud_deployment.operations.guacamole_image_management.guacamole_image_manager import GuacamoleImageManager
from cloud_deployment.operations.lab_management.shared_lab_manager import SharedLabManager

class InstallUpdateManager:
    def __init__(self, project_id: str):
        self.project_id = project_id

    def run_full_install(self) -> None:
        """
        Executes a full Cyber Arena installation, including building the base environment,
        deploying the main app, and deploying cloud functions.
        """
        BaseBuild(project=self.project_id).run()
        agoge_app = AgogeApp(project=self.project_id)
        if not agoge_app.deploy_main_app():
            return
        if not agoge_app.deploy_cloud_functions():
            return
        if not SharedLoadBalancer(project=self.project_id).run():
            return
        GuacamoleImageManager(
            project=self.project_id
        ).create_guac_project_image()
        SharedLabManager().run()

        self._create_update_record(action="initial install")
        print("🎉 Setup complete! Your new Agoge project is ready with shared app/API routing.")

    def run_update(self) -> None:
        """
        Updates the main application and cloud functions.
        """
        # Existing projects did not run the WireGuard DNS bootstrap that was
        # added to full installs. Perform the same idempotent migration before
        # deploying code that depends on it.
        BaseBuild(project=self.project_id, suppress=True).ensure_wireguard_prerequisites()
        agoge_app = AgogeApp(project=self.project_id)
        if not agoge_app.deploy_main_app():
            return
        if not agoge_app.deploy_cloud_functions():
            return
        if not SharedLoadBalancer(project=self.project_id).run():
            return
        self._create_update_record(action="update")

    def _create_update_record(self, action: str) -> None:
        """
        Persist an update event and bump the project's version in both the
        child project and the shared-resource project.
        """
        git_commit = self._get_git_commit()
        update_doc_id = str(int(time.time()))
        update_time = datetime.now(tz=timezone.utc).isoformat()
        update_info = {
            'version': CURRENT_VERSION,
            'action': action,
            'update_time': update_time,
            'git_commit': git_commit,
        }

        # 1️  store the event in the child project's UPDATES collection
        db = DocumentDatabaseFactory.create_db_object(
            db_type=DatabaseTypes.firestore,
            database_name=DATABASE_NAME,
            project_id=self.project_id,
        )
        db.update(
            collection_name=DbCollections.UPDATES,
            doc_id=update_doc_id,
            data=update_info
        )

        # 2️ patch ProjectInfo in both places (shared & child)
        project_info_patch = {
            "deployed_version": CURRENT_VERSION,
            "last_modified": update_time,
            "git_commit": git_commit,
        }

        db_shared_resource_project = DocumentDatabaseFactory.create_db_object(
            db_type=DatabaseTypes.firestore,
            database_name=DATABASE_NAME,
            project_id=BuildConstants.SharedResourceProjects.MAIN_SHARED_RESOURCE_PROJECT
        )

        project_info = db_shared_resource_project.get(collection_name=DbCollections.PROJECT_INFO, doc_id=self.project_id)
        project_info.update(project_info_patch)

        db_shared_resource_project.update(collection_name=DbCollections.PROJECT_INFO, doc_id=self.project_id, data=project_info)
        db.update(collection_name=DbCollections.PROJECT_INFO, doc_id=self.project_id, data=project_info)

    @staticmethod
    def _get_git_commit(short: bool = False) -> str | None:
        """
        Return the current commit hash for the repo that contains this file.
        • `short=True` → 7-char abbreviation (git's default for --short)
        • Returns None if the code isn't inside a Git repo.
        """
        repo_root = pathlib.Path(__file__).resolve().parent
        try:
            # Let Git walk up directories to find .git
            rev_cmd = ["git", "rev-parse", "--short" if short else "HEAD"]
            commit = subprocess.check_output(rev_cmd, cwd=repo_root,
                                             stderr=subprocess.STDOUT,
                                             text=True).strip()
            return commit
        except subprocess.CalledProcessError:
            return None
