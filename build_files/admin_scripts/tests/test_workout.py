from cloud_fn_utilities.globals import PubSub
from cloud_fn_utilities.gcp.cloud_env import CloudEnv
from cloud_fn_utilities.course_objects.workout.factory_workout import WorkoutFactory


class TestWorkout:
    def __init__(self, build_id=None, debug=True):
        self.env = CloudEnv()
        self.build_id = build_id if build_id else None
        self.debug = debug
        self.Workout = WorkoutFactory.create_workout_object(
            workout_id=self.build_id,
            debug=self.debug,
            env_dict=self.env.get_env()
        )

    def build(self):
        self.Workout.build()

    def start(self):
        self.Workout.start()

    def stop(self):
        self.Workout.stop()

    def delete(self):
        self.Workout.delete()


if __name__ == "__main__":
    print(f"Workout Tester.")

    test_workout_id = str(input(f"Which workout do you want to test? "))
    debug_response = str(input(f"Do you want to debug? Y/n "))
    debug = False if debug_response.upper() == "N" else True
    test_workout = TestWorkout(build_id=test_workout_id, debug=debug)
    while True:
        action = str(input(f"What action are you wanting to test [QUIT],{PubSub.Actions.BUILD.name}, "
                           f"{PubSub.Actions.START.name}, {PubSub.Actions.STOP.name}, or "
                           f"{PubSub.Actions.DELETE.name}?"))
        if not action or action.upper()[0] == "Q":
            break

        if action == PubSub.Actions.START.name:
            test_workout.start()
        elif action == PubSub.Actions.STOP.name:
            test_workout.stop()
        elif action == PubSub.Actions.DELETE.name:
            test_workout.delete()
        elif action == PubSub.Actions.BUILD.name:
            test_workout.build()
