import json
import logging
import random
import string
import requests
import yaml
from datetime import datetime, timedelta, timezone

from cloud_fn_utilities.common import IdGenerator
from utilities.globals import PubSub, DatastoreKeyTypes
from utilities.gcp.cloud_env import CloudEnv
from cloud_fn_utilities.gcp.datastore_manager import DataStoreManager
from utilities.infrastructure_as_code.build_spec_to_cloud import BuildSpecToCloud
from utilities.lms.lms_canvas import LMSSpecCanvas
from cloud_fn_utilities.course_objects.unit.factory_unit import UnitFactory
from cloud_fn_utilities.course_objects.workout.factory_workout import WorkoutFactory


class TestUnit:
    def __init__(self, build_id=None, debug=True, yaml_file='test_unit.yaml'):
        """
        Initializes the TestUnit class.

        Args:
            build_id (str): The build ID of the unit.
            debug (bool): Flag to enable debug logging.
            yaml_file (str): Path to the YAML configuration file.
        """
        self.env = CloudEnv()
        self.env_dict = self.env.get_env()
        self.build_id = build_id
        self.debug = debug
        self.yaml_file = yaml_file

        # Set up logging
        self.logger = logging.getLogger(self.__class__.__name__)
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        if debug:
            self.logger.setLevel(logging.DEBUG)
        else:
            self.logger.setLevel(logging.INFO)

        # Load YAML configuration
        try:
            with open(self.yaml_file, 'r') as f:
                self.yaml = yaml.safe_load(f)
                self.logger.debug(f"Loaded YAML configuration from '{self.yaml_file}'.")
        except FileNotFoundError:
            self.logger.error(f"YAML configuration file '{self.yaml_file}' not found.")
            self.yaml = {}

    def build(self):
        """
        Builds the unit based on the configuration.
        """
        build_spec = self._prepare_build_spec()
        if not build_spec:
            self.logger.error("Failed to prepare build specification.")
            return

        build_spec_to_cloud = BuildSpecToCloud(cyber_arena_spec=build_spec, env_dict=self.env_dict)
        build_spec_to_cloud.commit(publish=False)
        self.build_id = build_spec_to_cloud.build_id

        if self.debug:
            self.logger.info(f"Beginning to build a new unit with ID {self.build_id}")
            self._build_single_workout(build_spec)
            self.logger.info("Finished building.")

    def start(self):
        """
        Starts the unit.
        """
        unit = UnitFactory.create_unit_object(unit_id=self.build_id, debug=self.debug)
        if unit:
            unit.start()
        else:
            self.logger.error(f"Failed to create unit object for unit ID '{self.build_id}'.")

    def stop(self):
        """
        Stops the unit.
        """
        unit = UnitFactory.create_unit_object(unit_id=self.build_id, debug=self.debug)
        if unit:
            unit.stop()
        else:
            self.logger.error(f"Failed to create unit object for unit ID '{self.build_id}'.")

    def delete(self):
        """
        Deletes the unit.
        """
        unit = UnitFactory.create_unit_object(unit_id=self.build_id, debug=self.debug)
        if unit:
            unit.delete()
        else:
            self.logger.error(f"Failed to create unit object for unit ID '{self.build_id}'.")

    def question_completion(self):
        """
        Simulates question completion for the unit's workouts.
        """
        ds_unit = DataStoreManager(key_type=DatastoreKeyTypes.UNIT, key_id=self.build_id)
        unit = ds_unit.get()
        if not unit:
            self.logger.error(f"Unit with ID '{self.build_id}' not found in datastore.")
            return

        workouts = ds_unit.get_children(child_key_type=DatastoreKeyTypes.WORKOUT, parent_id=self.build_id)
        if not workouts:
            self.logger.warning(f"No workouts found for unit ID '{self.build_id}'.")
            return

        for workout in workouts:
            workout_id = workout['id']
            for question in unit.get('lms_quiz', {}).get('questions', []):
                question_key = question.get('question_key')
                if question_key:
                    data = {"question_key": question_key}
                    response = requests.put(f"http://localhost:8080/api/unit/workout/{workout_id}", json=data)
                    if response.status_code == 200:
                        self.logger.debug(f"Successfully completed question '{question_key}' for workout '{workout_id}'.")
                    else:
                        self.logger.error(f"Failed to complete question '{question_key}' for workout '{workout_id}': {response.status_code}")

    def _prepare_build_spec(self):
        """
        Prepares the build specification from the YAML configuration.

        Returns:
            dict: The build specification, or None if preparation failed.
        """
        unit_name = self.yaml.get('unit_name')
        if not unit_name:
            self.logger.error("No 'unit_name' specified in YAML configuration.")
            return None

        datastore_manager = DataStoreManager(key_type=DatastoreKeyTypes.CATALOG.value, key_id=unit_name)
        build_spec = datastore_manager.get()
        if not build_spec:
            self.logger.error(f"Invalid build spec name '{unit_name}' passed.")
            return None

        build_spec['instructor_id'] = self.yaml.get('instructor_id', 'default_instructor@example.com')
        build_spec['test'] = True
        expires_in_days = self.yaml.get('expires_in_days', 1)
        build_spec['workspace_settings'] = {
            'count': 2,
            'registration_required': False,
            'student_emails': [],
            'expires': (datetime.now(timezone.utc) + timedelta(days=expires_in_days)).timestamp()
        }
        build_spec['join_code'] = ''.join(random.choices(string.digits, k=6))

        if self.yaml.get('lms_integration'):
            lms_type = self.yaml.get('lms_type')
            if lms_type == 'canvas':
                lms_spec_decorator = LMSSpecCanvas(
                    env_dict=self.env_dict,
                    build_spec=build_spec,
                    course_code=self.yaml.get('lms_course_code'),
                    due_at=self.yaml.get('lms_due_at'),
                    time_limit=self.yaml.get('lms_time_limit'),
                    allowed_attempts=self.yaml.get('lms_allowed_attempts'),
                    lms_type=lms_type
                )
                build_spec = lms_spec_decorator.decorate()
                self.logger.debug("LMS specification decorated with Canvas integration.")
            else:
                self.logger.warning(f"LMS type '{lms_type}' is not supported.")
        else:
            self.logger.info("LMS integration is disabled.")

        return build_spec

    def _build_single_workout(self, build_spec):
        """
        Builds a single workout for the unit.

        Args:
            build_spec (dict): The build specification.
        """
        workout_id = ''.join(random.choices(string.ascii_lowercase, k=10))
        claimed_by = json.dumps({'student_email': 'example@ualr.edu'})
        unit = UnitFactory.create_unit_object(
            unit_id=self.build_id,
            workout_id=workout_id,
            form_data=claimed_by,
            debug=self.debug,
            force=True,
            env_dict=self.env_dict
        )
        if unit:
            unit.build()
            self._prompt_build_one_workout()
        else:
            self.logger.error(f"Failed to create unit object for workout ID '{workout_id}'.")

    def _prompt_build_one_workout(self):
        """
        Prompts the user to test the workout build.
        """
        build_one = input("Would you like to test the workout build at this time? (y/N): ").strip()
        if build_one.upper().startswith('Y'):
            ds_unit = DataStoreManager(key_type=DatastoreKeyTypes.UNIT, key_id=self.build_id)
            workouts = ds_unit.get_children(child_key_type=DatastoreKeyTypes.WORKOUT, parent_id=self.build_id)
            if workouts:
                workout_id = workouts[0]['id']
                self.logger.info(f"Beginning to build workout {workout_id}...")
                workout = WorkoutFactory.create_workout_object(workout_id=workout_id, debug=self.debug)
                if workout:
                    workout.build()
                    self.logger.info(f"Finished building workout {workout_id}.")
                else:
                    self.logger.error(f"Failed to create workout object for workout ID '{workout_id}'.")
            else:
                self.logger.warning(f"No workouts found for unit ID '{self.build_id}'.")
        else:
            self.logger.info("Skipping workout build.")


if __name__ == "__main__":
    print("Unit v2 Tester.")
    workout_id = IdGenerator.build_id()
    idx = 7
    unit = UnitFactory.create_unit_object(
        unit_id='oqqxfnbqfs',
        workout_id=workout_id,
        form_data=json.dumps({'student_email': f'test{idx}@bastazo.com'}),
        debug=True,
    )
    unit.stop()

    # delete_first = input("Do you want to delete a test unit first? (y/N): ").strip()
    # if delete_first.upper().startswith('Y'):
    #     delete_unit = input("What is the unit ID that you want to delete? ").strip()
    #     test_unit = TestUnit(build_id=delete_unit, debug=False)
    #     test_unit.delete()
    #     print("Unit deletion was successful!")
    #
    # build_first = input("Build the test unit described in test_unit.yaml? (Y/n): ").strip()
    # if not build_first or build_first.upper().startswith('Y'):
    #     test_unit = TestUnit()
    #     test_unit.build()
    # else:
    #     test_unit_id = input("Which unit ID do you want to test? ").strip()
    #     test_unit = TestUnit(build_id=test_unit_id, debug=False)
    #
    # while True:
    #     action = input(f"What action are you wanting to test [QUIT], {PubSub.Actions.BUILD.name}, {PubSub.Actions.START.name}, "
    #                    f"{PubSub.Actions.STOP.name}, {PubSub.Actions.DELETE.name}, or ASSESS? ").strip()
    #     if not action or action.upper().startswith('Q'):
    #         break
    #     elif action.upper() == PubSub.Actions.BUILD.name:
    #         test_unit.build()
    #     elif action.upper() == PubSub.Actions.START.name:
    #         test_unit.start()
    #     elif action.upper() == PubSub.Actions.STOP.name:
    #         test_unit.stop()
    #     elif action.upper() == PubSub.Actions.DELETE.name:
    #         test_unit.delete()
    #         break
    #     elif action.upper().startswith('A'):
    #         test_unit.question_completion()
    #     else:
    #         print("Invalid action. Please try again.")
