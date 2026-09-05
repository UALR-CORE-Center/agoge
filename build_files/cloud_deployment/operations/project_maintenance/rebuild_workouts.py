import time
from collections.abc import Callable
from typing import Any

from cloud_fn_utilities.course_objects.workout.factory_workout import WorkoutFactory

from common.constants.build_constants import BuildConstants
from common.constants.database import DATABASE_NAME, DatabaseTypes, DbCollections
from common.constants.states import UnitStates, WorkoutStates
from common.document_database import DatabaseQueries, DocumentDatabaseFactory
from common.utilities.gcp.cloud_env import CloudEnv


class RebuildWorkouts:
    """Synchronously rebuild all or selected Workouts in a Unit."""

    REQUIRES_PROJECT = True
    REBUILD_STOP_GRACE_SECONDS = 30
    REBUILDABLE_STATES = frozenset(
        {
            WorkoutStates.READY.value,
            WorkoutStates.RUNNING.value,
            WorkoutStates.BROKEN.value,
        }
    )
    REBUILDABLE_UNIT_STATES = frozenset(
        {
            UnitStates.READY.value,
            UnitStates.RUNNING.value,
            UnitStates.BROKEN.value,
        }
    )

    def __init__(
        self,
        project: str,
        db=None,
        db_queries: DatabaseQueries | None = None,
        cloud_env: CloudEnv | None = None,
        input_func: Callable[[str], str] | None = None,
        workout_factory=WorkoutFactory,
        rebuild_func: Callable[[str], bool] | None = None,
        sleep_func: Callable[[float], None] | None = None,
    ) -> None:
        if not project:
            raise ValueError("A GCP project is required for Workout maintenance.")

        self.project = project
        self.input = input_func or input
        self.db = db or DocumentDatabaseFactory.create_db_object(
            db_type=DatabaseTypes.firestore,
            database_name=DATABASE_NAME,
            project_id=project,
        )
        self.db_queries = db_queries or DatabaseQueries(db=self.db)

        env = cloud_env or CloudEnv(project=project)
        if env.project != project:
            raise ValueError(
                "The selected GCP project does not match the project stored "
                f"in its Agoge environment: selected={project}, stored={env.project}."
            )
        self.env_dict = env.get_env()
        self.workout_factory = workout_factory
        self.rebuild = rebuild_func or self._rebuild_workout
        self.sleep = sleep_func or time.sleep

    def run(self) -> None:
        units = self._get_units()
        if not units:
            print(f"[INFO] No rebuildable Units were found in project {self.project}.")
            return

        selected_unit = self._prompt_for_unit_selection(units)
        if selected_unit is None:
            print("[INFO] Workout rebuild cancelled.")
            return

        unit_id = str(selected_unit["id"])
        workouts = sorted(
            self.db_queries.get_children(
                parent_id=unit_id,
                child_collection=DbCollections.WORKOUT,
            ),
            key=lambda workout: str(workout.get("id", "")),
        )
        if not workouts:
            print(f"[INFO] Unit {unit_id} has no Workouts to rebuild.")
            return

        self._display_workouts(workouts)
        scope = self._prompt_for_scope()
        if scope is None:
            print("[INFO] Workout rebuild cancelled.")
            return

        if scope == "all":
            requested_workouts = workouts
        else:
            requested_workouts = self._prompt_for_workout_selection(workouts)
            if not requested_workouts:
                print("[INFO] No Workouts selected; rebuild cancelled.")
                return

        rebuildable, skipped = self._partition_rebuildable(requested_workouts)
        self._display_skipped_workouts(skipped)
        if not rebuildable:
            print("[INFO] None of the selected Workouts are in a rebuildable state.")
            return

        self._display_rebuild_warning(unit_id, rebuildable)
        if self.input("Type REBUILD to start these rebuilds: ").strip() != "REBUILD":
            print("[INFO] Confirmation did not match; rebuild cancelled.")
            return

        rebuilt, failed, changed_state = self._rebuild_workouts(unit_id, rebuildable)
        skipped.extend(changed_state)
        print("\n[SUMMARY]")
        print(f"  Unit: {unit_id}")
        print(f"  Workouts rebuilt: {len(rebuilt)}")
        print(f"  Workouts skipped: {len(skipped)}")
        print(f"  Rebuild failures: {len(failed)}")
        if rebuilt:
            print(f"  Rebuilt Workout IDs: {', '.join(rebuilt)}")
        if failed:
            print(f"  Failed Workout IDs: {', '.join(failed)}")
        if rebuilt:
            print("[END] Direct Workout rebuild processing is complete.")
        else:
            print("[END] No Workouts were rebuilt.")

    def _get_units(self) -> list[dict]:
        units = self.db_queries.get_active(collection_name=DbCollections.UNIT)
        return sorted(
            (
                unit
                for unit in units
                if unit.get("id") and self._unit_is_rebuildable(unit)
            ),
            key=lambda unit: str(unit["id"]),
        )

    def _prompt_for_unit_selection(self, units: list[dict]) -> dict | None:
        print(f"\n[INFO] Rebuildable Units in project {self.project}:")
        units_by_id = {}
        for index, unit in enumerate(units, start=1):
            unit_id = str(unit["id"])
            units_by_id[unit_id] = unit
            summary = unit.get("summary") or {}
            name = summary.get("name") if isinstance(summary, dict) else None
            unit_type = unit.get("unit_type", "unknown")
            state = self._state_name(unit.get("state"), UnitStates)
            name_suffix = f" - {name}" if name else ""
            print(
                f"  [{index:>2}] {unit_id}{name_suffix} "
                f"(type={unit_type}, state={state})"
            )
        print("  [ 0] Back")

        while True:
            raw_value = self.input(
                "Select a Unit by number or enter its exact ID: "
            ).strip()
            if raw_value in {"", "0"}:
                return None
            if raw_value in units_by_id:
                return units_by_id[raw_value]
            if raw_value.isdigit():
                index = int(raw_value)
                if 1 <= index <= len(units):
                    return units[index - 1]
            print("[ERROR] Select a listed Unit number or enter its exact ID.")

    def _prompt_for_scope(self) -> str | None:
        print("\nChoose the rebuild scope:")
        print(
            "  1. Full Unit (all eligible Workouts; shared Community "
            "infrastructure is preserved)"
        )
        print("  2. Individual Workout(s)")
        print("  0. Back")
        while True:
            selection = self.input("Select rebuild scope [0-2]: ").strip()
            if selection == "1":
                return "all"
            if selection == "2":
                return "selected"
            if selection in {"", "0"}:
                return None
            print("[ERROR] Enter 1, 2, or 0.")

    def _display_workouts(self, workouts: list[dict]) -> None:
        print("\n[INFO] Workouts in the selected Unit:")
        for index, workout in enumerate(workouts, start=1):
            owner = (
                workout.get("student_email") or workout.get("team_name") or "unassigned"
            )
            state = self._state_name(workout.get("state"), WorkoutStates)
            print(
                f"  [{index:>2}] {workout.get('id', '<missing-id>')} "
                f"(owner={owner}, state={state})"
            )

    def _prompt_for_workout_selection(
        self,
        workouts: list[dict],
    ) -> list[dict]:
        workouts_by_id = {
            str(workout["id"]): workout for workout in workouts if workout.get("id")
        }
        while True:
            raw_value = self.input(
                "Enter Workout numbers or exact IDs (comma/space-separated), "
                "or press Enter to cancel: "
            ).strip()
            if not raw_value:
                return []

            selected = []
            selected_ids = set()
            invalid_tokens = []
            for token in raw_value.replace(",", " ").split():
                workout = workouts_by_id.get(token)
                if workout is None and token.isdigit():
                    index = int(token)
                    if 1 <= index <= len(workouts):
                        workout = workouts[index - 1]
                if workout is None:
                    invalid_tokens.append(token)
                    continue

                workout_id = str(workout["id"])
                if workout_id not in selected_ids:
                    selected.append(workout)
                    selected_ids.add(workout_id)

            if invalid_tokens:
                print(
                    "[WARNING] Ignored unknown Workout selections: "
                    + ", ".join(invalid_tokens)
                )
            if selected:
                return selected
            print(
                "[ERROR] No valid Workouts selected. Try again or press Enter to cancel."
            )

    def _partition_rebuildable(
        self,
        workouts: list[dict],
    ) -> tuple[list[dict], list[dict]]:
        rebuildable = []
        skipped = []
        for workout in workouts:
            if (
                workout.get("id")
                and self._state_value(workout.get("state")) in self.REBUILDABLE_STATES
            ):
                rebuildable.append(workout)
            else:
                skipped.append(workout)
        return rebuildable, skipped

    def _display_skipped_workouts(self, skipped: list[dict]) -> None:
        for workout in skipped:
            state = self._state_name(workout.get("state"), WorkoutStates)
            print(
                f"[SKIP] Workout {workout.get('id', '<missing-id>')} is in "
                f"state {state}; only READY, RUNNING, or BROKEN can be rebuilt."
            )

    def _display_rebuild_warning(
        self,
        unit_id: str,
        workouts: list[dict],
    ) -> None:
        print("\n[WARNING] This action deletes and recreates each selected Workout VM.")
        print("Data stored only on VM boot disks will be lost.")
        print(
            "The Unit, its networks, and shared Community servers (including "
            "a shared gateway) will be preserved."
        )
        print("This runs directly; keep this terminal open until processing completes.")
        print(
            "RUNNING Workouts remain running. READY or BROKEN Workouts finish "
            "in READY with their servers stopped."
        )
        print(f"GCP project: {self.project}")
        print(f"Unit: {unit_id}")
        print(
            "Workouts to rebuild: "
            + ", ".join(str(workout["id"]) for workout in workouts)
        )

    def _rebuild_workouts(
        self,
        unit_id: str,
        workouts: list[dict],
    ) -> tuple[list[str], list[str], list[dict]]:
        rebuilt = []
        failed = []
        changed_state = []
        for index, workout in enumerate(workouts):
            workout_id = str(workout["id"])
            current_unit = self.db.get(
                collection_name=DbCollections.UNIT,
                doc_id=unit_id,
            )
            if not self._unit_is_rebuildable(current_unit):
                changed_state.extend(workouts[index:])
                state = self._state_name(
                    current_unit.get("state") if current_unit else None,
                    UnitStates,
                )
                print(
                    f"[SKIP] Unit {unit_id} is no longer eligible "
                    f"(state={state}); remaining Workouts were not rebuilt."
                )
                break
            current_workout = self.db.get(
                collection_name=DbCollections.WORKOUT,
                doc_id=workout_id,
            )
            if (
                not current_workout
                or str(current_workout.get("parent_id")) != unit_id
                or self._state_value(current_workout.get("state"))
                not in self.REBUILDABLE_STATES
            ):
                changed_state.append(current_workout or workout)
                state = self._state_name(
                    current_workout.get("state") if current_workout else None,
                    WorkoutStates,
                )
                print(
                    f"[SKIP] Workout {workout_id} changed or is no longer "
                    f"eligible (state={state}); it was not rebuilt."
                )
                continue
            try:
                print(f"[REBUILDING] Workout {workout_id}")
                if not self.rebuild(workout_id):
                    raise RuntimeError("the Workout rebuild did not complete")
                rebuilt.append(workout_id)
                print(f"[REBUILT] Workout {workout_id}")
            # A failure for one Workout must not prevent independent rebuilds
            # for the remaining selected Workouts.
            except Exception as error:  # noqa: BLE001
                failed.append(workout_id)
                print(f"[ERROR] Failed to rebuild Workout {workout_id}: {error}")
        return rebuilt, failed, changed_state

    def _rebuild_workout(self, workout_id: str) -> bool:
        workout = self.workout_factory.create_workout_object(
            workout_id=workout_id,
            debug=True,
            env_dict=self.env_dict,
        )
        initial_state = self._state_value(workout.workout.state)
        if not workout.nuke():
            return False

        if initial_state == WorkoutStates.RUNNING.value:
            return workout.state_manager.get_state() == WorkoutStates.RUNNING.value

        # Give newly created guests, especially Guacamole, time to persist
        # first-boot configuration before issuing a stop operation.
        self.sleep(self.REBUILD_STOP_GRACE_SECONDS)
        workout.stop()
        return workout.state_manager.get_state() == WorkoutStates.READY.value

    @classmethod
    def _unit_is_rebuildable(cls, unit: dict | None) -> bool:
        if not unit:
            return False

        state = cls._state_value(unit.get("state"))
        if state in cls.REBUILDABLE_UNIT_STATES:
            return True

        unit_type = getattr(unit.get("unit_type"), "value", unit.get("unit_type"))
        return state == UnitStates.START.value and unit_type in {
            None,
            BuildConstants.UnitType.SOLO.value,
        }

    @staticmethod
    def _state_value(state: Any) -> int | None:
        try:
            return int(state)
        except (TypeError, ValueError):
            return None

    @classmethod
    def _state_name(cls, state: Any, state_enum) -> str:
        state_value = cls._state_value(state)
        if state_value is None:
            return "UNKNOWN"
        try:
            return state_enum(state_value).name
        except ValueError:
            return f"UNKNOWN({state_value})"
