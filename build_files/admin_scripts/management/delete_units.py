from cloud_fn_utilities.periodic_maintenance.hourly_maintenance import HourlyMaintenance
from main_app.api.utilities.document_database.factory import DocumentDatabaseFactory
from main_app.api.core.unit import Unit
from main_app.api import CloudEnv
from main_app.api.models.users import AgogeUser
from main_app.api.utilities.globals import (
    DbCollections,
    DatabaseTypes,
    DATABASE_NAME,
    ValidTestProjects,
    UserGroups,
    BuildConstants
)
from main_app.api.utilities.common import DbOperators


class DeleteTestManager:
    def __init__(self, debug=False):
        self.env = CloudEnv()
        self.db = DocumentDatabaseFactory.create_db_object(
            db_type=DatabaseTypes.firestore,
            database_name=DATABASE_NAME
        )

        self.fake_user = AgogeUser(
            uid="admin-uid",
            email="admin@example.com",
            permissions={UserGroups.ADMIN.value: True},
            settings={
                BuildConstants.LMS.CANVAS.value: {
                    'api': None,
                    'url': None,
                    'secret': None
                }
            }
        )

    def run(self):
        # 1. Confirm deleting ALL units (only if the project is valid for testing).
        delete_all = input(
            f"Delete ALL units for the project '{self.env.project}'? "
            f"(Only valid for test projects.) (Y/n) "
        ).strip().lower()

        if (delete_all in ("", "y", "yes")) and \
           (self.env.project in {p.value for p in ValidTestProjects}):
            print("Deleting ALL units...")
            units = self.db.query(collection_name=DbCollections.UNIT)
            for unit in units:
                try:
                    Unit(env_dict=self.env.get_env()).delete(
                        requester=self.fake_user,
                        build_id=unit.get("id")
                    )
                    print(f"Deleted unit with ID: {unit.get('id')}")
                except Exception as ex:
                    print(f"Failed to delete unit with ID {unit.get('id')}: {ex}")
            return  # If all units are deleted, skip the rest of the script
        else:
            print("Skipping the deletion of ALL units.")

        # 2. Confirm deleting only those marked as 'test=True'.
        delete_tests = input(
            f"Delete all units marked as 'test=True' in the project '{self.env.project}'? (Y/n) "
        ).strip().lower()
        if delete_tests in ("", "y", "yes"):
            print("Deleting all test units...")
            units = self.db.query(
                collection_name=DbCollections.UNIT,
                filters=[("test", DbOperators.EQUAL, True)]
            )
            for unit in units:
                try:
                    Unit(env_dict=self.env.get_env()).delete(
                        requester=self.fake_user,
                        build_id=unit.get("id")
                    )
                    print(f"Deleted test unit with ID: {unit.get('id')}")
                except Exception as ex:
                    print(f"Failed to delete test unit with ID {unit.get('id')}: {ex}")
        else:
            print("Skipping the deletion of test units.")

        # 3. Confirm running routine for expired units.
        delete_expired = input(
            f"Run deletion routine for expired units in the project '{self.env.project}'? (Y/n) "
        ).strip().lower()
        if delete_expired in ("", "y", "yes"):
            print("Running HourlyMaintenance to delete expired units...")
            HourlyMaintenance().run()
        else:
            print("Skipping the deletion routine for expired units.")


if __name__ == "__main__":
    print("\n** Script to delete units in a test environment **\n")
    DeleteTestManager().run()
