import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from cloud_fn_utilities.course_objects.compute.factory import ComputeManagerFactory
from common.constants.build_constants import BuildConstants
from common.constants.database import DATABASE_NAME, DatabaseTypes, DbCollections
from common.constants.states import ServerStates, UnitStates, WorkoutStates
from common.document_database import DocumentDatabaseFactory
from common.utilities.gcp.cloud_env import CloudEnv


class RebuildGuacamoleForProject:
    """Reimage the selected project's existing Guacamole lab proxies."""

    REQUIRES_PROJECT = True
    MAX_WORKERS = 4
    STOP_GRACE_SECONDS = 30
    SERVER_STATES = {
        ServerStates.READY.value, ServerStates.RUNNING.value,
        ServerStates.STOPPED.value, ServerStates.BROKEN.value,
    }
    UNIT_STATES = {UnitStates.READY.value, UnitStates.RUNNING.value, UnitStates.BROKEN.value}
    WORKOUT_STATES = {
        WorkoutStates.READY.value, WorkoutStates.RUNNING.value, WorkoutStates.BROKEN.value,
        WorkoutStates.GUACAMOLE_SERVER_LOAD_TIMEOUT.value,
    }

    def __init__(self, project: str) -> None:
        if not project:
            raise ValueError("A GCP project is required for Guacamole maintenance.")
        self.project = project
        self.db = DocumentDatabaseFactory.create_db_object(
            db_type=DatabaseTypes.firestore, database_name=DATABASE_NAME, project_id=project,
        )
        env = CloudEnv(project=project)
        if env.project != project:
            raise ValueError(f"Agoge environment belongs to {env.project}, expected {project}.")
        self.env_dict = env.get_env()

    def run(self) -> None:
        targets = sorted({
            f"{server['parent_id']}-{server['name']}"
            for server in self.db.query(collection_name=DbCollections.SERVER)
            if self._is_rebuildable_proxy(server)
        })
        if not targets:
            print(f"[INFO] No Guacamole lab proxies eligible for reimage in {self.project}.")
            return

        workers = min(self.MAX_WORKERS, len(targets))
        print(f"[INFO] Found {len(targets)} Guacamole lab proxies in {self.project}.")
        print(f"Reimaging up to {workers} at a time will disconnect active Guacamole sessions.")
        if input(f"Type REBUILD to start reimaging in {self.project}: ").strip() != "REBUILD":
            print("[INFO] Guacamole reimage cancelled.")
            return

        rebuilt = 0
        skipped = 0
        failed = []
        with ThreadPoolExecutor(max_workers=workers) as executor:
            pending = {executor.submit(self._rebuild, target): target for target in targets}
            for future in as_completed(pending):
                target = pending[future]
                try:
                    if future.result():
                        rebuilt += 1
                        print(f"[REBUILT] {target}")
                    else:
                        skipped += 1
                        print(f"[SKIP] {target} or its lab is ineligible for reimage.")
                except Exception as error:
                    failed.append(target)
                    print(f"[ERROR] Failed to reimage {target}: {error}")

        print(f"[SUMMARY] {self.project} — {rebuilt} rebuilt, {skipped} skipped, {len(failed)} failed.")
        if failed:
            print(f"Failed Guacamole servers: {', '.join(sorted(failed))}")

    @classmethod
    def _is_rebuildable_proxy(cls, server: dict) -> bool:
        if (
            not server or not server.get("parent_id") or not server.get("name")
            or server.get("state") not in cls.SERVER_STATES
            or (server.get("parent_build_type") or None) not in {
                None, BuildConstants.BuildType.UNIT.value, BuildConstants.BuildType.WORKOUT.value,
                BuildConstants.BuildType.ESCAPE_ROOM.value,
            }
            or server.get("wireguard_gateway") or server.get("wireguard_endpoint_id")
        ):
            return False
        image_name = (server.get("image") or "").rsplit("/", 1)[-1]
        return bool(
            server["name"] in {"display-guacamole-server", "display-guacamole"}
            or server.get("guacamole_startup_script")
            or image_name.startswith("image-guac-")
        )

    def _rebuild(self, server_name: str) -> bool:
        server = self.db.get(collection_name=DbCollections.SERVER, doc_id=server_name)
        if not self._is_rebuildable_proxy(server) or server_name != f"{server['parent_id']}-{server['name']}":
            return False

        parent_id = server["parent_id"]
        parent_type = server.get("parent_build_type") or None
        workout = None
        network_prefix = parent_id
        if parent_type in {None, BuildConstants.BuildType.WORKOUT.value}:
            workout = self.db.get(collection_name=DbCollections.WORKOUT, doc_id=parent_id)
            if workout and (not workout.get("parent_id") or workout.get("state") not in self.WORKOUT_STATES):
                return False
            if not workout and parent_type == BuildConstants.BuildType.WORKOUT.value:
                return False

        unit_id = workout["parent_id"] if workout else parent_id
        unit = self.db.get(collection_name=DbCollections.UNIT, doc_id=unit_id)
        if not unit:
            return False
        unit_type = unit.get("unit_type")
        solo_unit = unit_type in {None, BuildConstants.UnitType.SOLO.value}
        if (
            unit.get("state") not in self.UNIT_STATES
            and not (workout and solo_unit and unit.get("state") == UnitStates.START.value)
        ):
            return False

        if workout:
            if unit_type == BuildConstants.UnitType.COMMUNITY.value:
                network_prefix = unit_id
            # Older records may omit the type needed for assessment lookup.
            server = {**server, "parent_build_type": BuildConstants.BuildType.WORKOUT.value}

        manager = ComputeManagerFactory.create_manager_object(env_dict=self.env_dict)
        manager.load(server_name=server_name, network_prefix=network_prefix, server_spec=server)
        initial_state = manager.state_manager.get_state()
        if initial_state not in self.SERVER_STATES:
            return False

        if server.get("build_type") != BuildConstants.ServerBuildType.MACHINE_IMAGE:
            # Resolve through the same local/shared lookup used for the boot disk.
            image = manager.get_boot_image()
            if image.status != "READY":
                raise RuntimeError(f"Boot image {server.get('image')} is {image.status}.")

        print(f"[REIMAGING] {server_name}")
        manager.nuke()
        if manager.state_manager.get_state() != ServerStates.RUNNING.value:
            raise RuntimeError("The replacement VM did not reach RUNNING.")

        parent_running = (workout or unit)["state"] == WorkoutStates.RUNNING.value
        if initial_state != ServerStates.RUNNING.value and not (
            initial_state == ServerStates.BROKEN.value and parent_running
        ):
            # Let the guest persist first-boot configuration before stopping it.
            time.sleep(self.STOP_GRACE_SECONDS)
            manager.stop()
            if manager.state_manager.get_state() != ServerStates.STOPPED.value:
                raise RuntimeError("The replacement VM did not reach STOPPED.")
        return True
