import time

from common.constants.build_constants import BuildConstants
from common.constants.database import DbCollections
from common.constants.pub_sub import PubSub
from common.constants.states import UnitStates
from common.models.agoge import UnitModel

from ...course_objects.workout.factory_workout import WorkoutFactory
from ...state_managers.unit_states import UnitStateManager
from .base_unit import BaseUnit


class SoloUnit(BaseUnit):
    def __init__(
        self,
        unit_model: UnitModel,
        workout_id=None,
        form_data=None,
        debug=False,
        force=False,
        env_dict=None
    ) -> None:
        """
        Args:
            unit_model (UnitModel): The Unit to manage
            workout_id (str): A Workout ID if the intent is to build a new workout
            form_data (str): Use associated with web form. This includes keys for student_name, student_email and
                        team_name (for escape rooms)
            debug (bool): Avoids pubsub messages and builds synchronously
            force (bool): Unused
            env_dict (dict):
        """
        super().__init__(
            unit_model=unit_model,
            workout_id=workout_id,
            form_data=form_data,
            debug=debug,
            force=force,
            env_dict=env_dict
        )

    def _build_unit(self):
        """There is nothing to build in a solo unit. All components are built in the workouts."""
        pass

    def start(self):
        workouts = self.db_queries.get_children(
            parent_id=self.unit_id,
            child_collection=DbCollections.WORKOUT
        )

        for workout in workouts:
            workout_id = str(workout['id'])
            if self.debug:
                workout = WorkoutFactory.create_workout_object(
                    workout_id=workout_id,
                    debug=self.debug,
                    env_dict=self.env_dict
                )
                workout.start()
            else:
                if self.debug:
                    print(workout_id)
                self.pubsub_manager.msg(
                    handler=str(PubSub.Handlers.CONTROL.value),
                    action=str(PubSub.Actions.START.value),
                    course_object=str(PubSub.CourseObjects.WORKOUT.value),
                    build_id=workout_id
                )
            time.sleep(2)

    def stop(self):
        workouts = self.db_queries.get_children(
            parent_id=self.unit_id,
            child_collection=DbCollections.WORKOUT
        )
        for workout in workouts:
            workout_id = str(workout['id'])

            if self.debug:
                workout = WorkoutFactory.create_workout_object(
                    workout_id=workout_id,
                    debug=self.debug,
                    env_dict=self.env_dict
                )
                workout.stop()
            else:
                self.pubsub_manager.msg(
                    handler=str(PubSub.Handlers.CONTROL.value),
                    action=str(PubSub.Actions.STOP.value),
                    course_object=str(PubSub.CourseObjects.WORKOUT.value),
                    build_id=workout_id
                )

    def delete(self):
        workouts = self.db_queries.get_children(
            parent_id=self.unit_id,
            child_collection=DbCollections.WORKOUT
        )
        for workout in workouts:
            workout_id = str(workout['id'])
            if self.debug:
                print(f"Deleting workout {workout_id}")
                workout = WorkoutFactory.create_workout_object(
                    workout_id=workout_id,
                    debug=self.debug,
                    env_dict=self.env_dict
                )
                workout.delete()
            else:
                self.pubsub_manager.msg(
                    handler=str(PubSub.Handlers.CONTROL.value),
                    action=str(PubSub.Actions.DELETE.value),
                    course_object=str(PubSub.CourseObjects.WORKOUT.value),
                    build_id=workout_id
                )
        unit_state_manager = UnitStateManager(build_id=self.unit_id)
        if unit_state_manager.are_workouts_deleted():
            unit_state_manager.state_transition(new_state=UnitStates.DELETED)
        else:
            self.logger.error(f"{self.class_name}:{self.unit_id} - Unit is not deleted!")

    def nuke(self):
        workouts = self.db_queries.get_children(
            parent_id=self.unit_id,
            child_collection=DbCollections.WORKOUT
        )
        for workout in workouts:
            workout = WorkoutFactory.create_workout_object(
                workout_id=str(workout['id']),
                debug=self.debug,
                env_dict=self.env_dict
            )
            workout.nuke()

    def _wait_until_unit_is_ready_for_servers(self):
        pass
