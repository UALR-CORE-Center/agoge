# agoge/cloud_deployment/operations/project_maintenance/extend_workout_expirations.py

import datetime

from cloud_fn_utilities.course_objects.unit.factory_unit import UnitFactory
from common.constants.database import DATABASE_NAME, DatabaseTypes, DbCollections
from common.document_database import DatabaseQueries, DocumentDatabaseFactory


class ExtendWorkoutExpirations:
    """
    Extends workout expiration timestamps by a user-specified number of days
    for workouts under a selected active unit.
    """

    SECONDS_PER_DAY = 86400

    def __init__(self):
        self.db = DocumentDatabaseFactory.create_db_object(
            db_type=DatabaseTypes.firestore,
            database_name=DATABASE_NAME,
        )
        self.db_queries = DatabaseQueries(db=self.db)
        self.unit = None
        self.days_to_extend = 0

    def run(self) -> None:
        eligible_units = self._get_eligible_units()

        if not eligible_units:
            print("[INFO] No active units found with expiration on or after today.")
            return

        selected_unit = self._prompt_for_unit_selection(eligible_units)
        self.days_to_extend = self._prompt_for_days()

        unit_id = str(selected_unit["id"])
        self.unit = self.db.get(collection_name=DbCollections.UNIT, doc_id=unit_id)

        old_unit_expiration = int(float(selected_unit["workspace_settings"]["expires"]))
        new_unit_expiration = old_unit_expiration + (
                self.days_to_extend * self.SECONDS_PER_DAY
        )

        old_unit_expiration_str = self._format_timestamp(old_unit_expiration)
        new_unit_expiration_str = self._format_timestamp(new_unit_expiration)

        print(f"\n[START] Extending expirations by {self.days_to_extend} day(s)")
        print(f"[UNIT] {unit_id}")
        print(f"  Old expiration: {old_unit_expiration_str} ({old_unit_expiration})")
        print(f"  New expiration: {new_unit_expiration_str} ({new_unit_expiration})")

        # Update unit expiration
        selected_unit["workspace_settings"]["expires"] = new_unit_expiration

        self.db.update(
            collection_name=DbCollections.UNIT,
            doc_id=unit_id,
            data=selected_unit,
        )

        print(f"[SUCCESS] Unit {unit_id} expiration updated")

        # Now update workouts
        total_workouts, updated_workouts = self._process_unit(unit_id)

        print("\n[SUMMARY]")
        print(f"  Unit processed: {unit_id}")
        print(f"  Total workouts scanned: {total_workouts}")
        print(f"  Workouts updated: {updated_workouts}")
        print("[END] Extension process complete")

    def _get_eligible_units(self) -> list[dict]:
        """
        Return active units whose expiration is today or in the future.
        """
        start_of_today_utc = self._get_start_of_current_utc_day_epoch()
        active_units = self.db_queries.get_active(collection_name=DbCollections.UNIT)

        eligible_units = []
        for unit in active_units:
            expiration_epoch = unit.get("workspace_settings", {}).get("expires")
            if expiration_epoch is None:
                continue

            expiration_epoch = int(float(expiration_epoch))
            if expiration_epoch >= start_of_today_utc:
                eligible_units.append(unit)

        return sorted(
            eligible_units,
            key=lambda unit: int(float(unit["workspace_settings"]["expires"]))
        )

    def _prompt_for_unit_selection(self, units: list[dict]) -> dict:
        """
        Display eligible units and prompt the user to select one.
        """
        print("[INFO] Eligible units:")
        for index, unit in enumerate(units, start=1):
            unit_id = str(unit["id"])
            expiration_epoch = int(float(unit["workspace_settings"]["expires"]))
            expiration_str = self._format_timestamp(expiration_epoch)
            print(f"{index}. {unit_id} - expires {expiration_str} ({expiration_epoch})")

        while True:
            raw_value = input("Select a unit by number: ").strip()

            try:
                selection = int(raw_value)
                if 1 <= selection <= len(units):
                    return units[selection - 1]
                print(f"[ERROR] Please enter a number between 1 and {len(units)}.")
            except ValueError:
                print("[ERROR] Invalid input. Please enter a whole number.")

    @staticmethod
    def _prompt_for_days() -> int:
        """
        Prompt the user for the number of days to extend workout expirations.
        """
        while True:
            raw_value = input("How many days do you want to extend the workouts by? ").strip()

            try:
                days = int(raw_value)
                if days <= 0:
                    print("[ERROR] Please enter a positive integer.")
                    continue
                return days
            except ValueError:
                print("[ERROR] Invalid input. Please enter a whole number.")

    def _process_unit(self, unit_id: str) -> tuple[int, int]:
        """
        Extend all workouts for a given unit.

        Returns:
            (total_workouts, updated_workouts)
        """
        workouts = self.db_queries.get_children(
            parent_id=unit_id,
            child_collection=DbCollections.WORKOUT
        )

        print(f"[INFO] Found {len(workouts)} workouts")

        updated_count = 0

        for workout in workouts:
            self._extend_workout(workout)
            updated_count += 1

        return len(workouts), updated_count

    def _extend_workout(self, workout: dict) -> None:
        """
        Extend a workout expiration by the configured number of days.
        """
        workout_id = str(workout["id"])
        old_expiration_epoch = int(float(workout["expires"]))
        new_expiration_epoch = old_expiration_epoch + (
            self.days_to_extend * self.SECONDS_PER_DAY
        )

        old_expiration_str = self._format_timestamp(old_expiration_epoch)
        new_expiration_str = self._format_timestamp(new_expiration_epoch)

        print(f"[WORKOUT] {workout_id}")
        print(f"  Old expiration: {old_expiration_str} ({old_expiration_epoch})")
        print(f"  New expiration: {new_expiration_str} ({new_expiration_epoch})")

        workout["expiration"] = new_expiration_epoch
        self.db.update(
            collection_name=DbCollections.WORKOUT,
            doc_id=workout_id,
            data=workout,
        )

        print(f"[SUCCESS] Workout {workout_id} updated")

    @staticmethod
    def _get_start_of_current_utc_day_epoch() -> int:
        """
        Return the epoch timestamp for the start of the current UTC day.
        """
        now_utc = datetime.datetime.utcnow()
        start_of_day_utc = datetime.datetime(
            year=now_utc.year,
            month=now_utc.month,
            day=now_utc.day,
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )
        return int(start_of_day_utc.timestamp())

    @staticmethod
    def _format_timestamp(epoch: int | float) -> str:
        """
        Convert epoch timestamp to UTC string.
        """
        return datetime.datetime.utcfromtimestamp(float(epoch)).strftime("%Y-%m-%d %H:%M:%S")