import time

from cloud_fn_utilities.course_objects.compute.factory import ComputeManagerFactory
from cloud_fn_utilities.course_objects.unit.factory_unit import UnitFactory
from common.constants.database import DATABASE_NAME, DatabaseTypes, DbCollections
from common.document_database import DatabaseQueries, DocumentDatabaseFactory


class RebuildGuacamoleForUnit:
    """
    Rebuilds Guacamole display servers for every workout in a unit by
    loading each matching server and destroying it so it can be recreated
    through the normal provisioning flow.
    """

    GUACAMOLE_SERVER_MARKER = "display-guacamole"

    def __init__(self):
        self.db = DocumentDatabaseFactory.create_db_object(
            db_type=DatabaseTypes.firestore,
            database_name=DATABASE_NAME,
        )
        self.db_queries = DatabaseQueries(db=self.db)
        self.compute_manager = ComputeManagerFactory.create_manager_object()
        self.unit = None

    def run(self) -> None:
        """
        Rebuild all Guacamole servers associated with the unit.
        """
        unit_id = input("Which unit do you want to rebuild the guacamole server for? ").strip()
        self.unit = UnitFactory.create_unit_object(unit_id=unit_id)
        print(f"[START] Rebuilding Guacamole servers for unit: {unit_id}")

        workouts = self.db_queries.get_children(
            parent_id=unit_id,
            child_collection=DbCollections.WORKOUT
        )
        print(f"[INFO] Found {len(workouts)} workouts")

        total_servers = 0
        rebuilt_servers = 0

        for workout in workouts:
            workout_id = str(workout['id'])
            print(f"\n[WORKOUT] Processing workout_id={workout_id}")

            servers, rebuilt = self._rebuild_guacamole_servers_for_workout(workout_id)
            total_servers += servers
            rebuilt_servers += rebuilt

        print("\n[SUMMARY]")
        print(f"  Total servers scanned: {total_servers}")
        print(f"  Guacamole servers rebuilt: {rebuilt_servers}")
        print("[END] Rebuild process complete")

    def _rebuild_guacamole_servers_for_workout(self, workout_id: str) -> tuple[int, int]:
        """
        Find and rebuild matching Guacamole servers for a single workout.
        Returns:
            (total_servers, rebuilt_servers)
        """
        servers = self.db_queries.get_servers(parent_id=workout_id)
        print(f"[INFO] Found {len(servers)} servers for workout")

        rebuilt_count = 0

        for server in servers:
            server_name = self._build_server_name(server)

            if self._is_guacamole_server(server_name):
                self._rebuild_server(server_name)
                rebuilt_count += 1
        return len(servers), rebuilt_count

    @staticmethod
    def _build_server_name(server: dict) -> str:
        """
        Build the server name from the stored server record.
        """
        return f'{server["parent_id"]}-{server["name"]}'

    def _is_guacamole_server(self, server_name: str) -> bool:
        """
        Determine whether the server is a Guacamole display server.
        """
        return self.GUACAMOLE_SERVER_MARKER in server_name

    def _rebuild_server(self, server_name: str) -> None:
        """
        Load and destroy the server so it can be rebuilt.
        """
        print(f"[ACTION] Rebuilding server: {server_name}")

        try:
            self.compute_manager.load(server_name=server_name)

            print(f"[NUKE] Nuking server: {server_name}")
            self.compute_manager.nuke()
            time.sleep(30)
            self.compute_manager.stop()

            print(f"[SUCCESS] Rebuild triggered for: {server_name}")

        except Exception as e:
            print(f"[ERROR] Failed to rebuild {server_name}: {e}")
