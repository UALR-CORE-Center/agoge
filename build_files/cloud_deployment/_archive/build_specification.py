"""
Manage the build specification synchronization with the cloud.

This module contains the following classes:
    - BuildSpecification: Operations to sync local specifications with the cloud project.
"""
import datetime
import os

import googleapiclient.errors
import yaml
from google.cloud import storage
from googleapiclient import discovery
from google.api_core.exceptions import NotFound
from pydantic import ValidationError

from api.utilities.infrastructure_as_code.object_validators.unit import UnitValidator
from common.constants.build_constants import BuildConstants
from common.models.agoge import UnitModel
from common.utilities.gcp.cloud_env import CloudEnv
from cloud_functions.cloud_fn_utilities.gcp.datastore_manager import DataStoreManager, DatastoreKeyTypes
from cloud_deployment.operations.images_and_specs.computer_image_sync import ComputerImageSync


class BuildSpecification:
    BUILD_SPEC_BUCKET_SUFFIX = "build-specs"
    SPEC_FOLDER = 'specs/'
    ATTACK_FOLDER = 'attacks/'
    STARTUP_SCRIPT_FOLDER = "startup_scripts/"
    TEACHER_FOLDER = "teacher_instructions/"
    STUDENT_FOLDER = "student_instructions/"

    # List of directory names to exclude from the cloud sync process
    EXCLUDE = ['examples', 'fipte', 'old', 'agency', 'attacks', 'fixed_cyber_arenas', '']

    def __init__(self, sync=True, suppress=True):
        self.suppress = suppress
        self.env = CloudEnv()
        self.build_attacks_specs = os.path.join("build_files", "specs", "attacks")
        self.build_specs_plaintext = os.path.join("build_files", "specs")
        self.build_startup_scripts = os.path.join("build_files", "startup_scripts")
        self.build_student_instructions = os.path.join("build_files", "instructions", "student")
        self.build_teacher_instructions_plaintext = os.path.join("build_files", "instructions", "teacher")
        self._create_directories()

        self.storage_client = storage.Client()
        self.service = discovery.build('compute', 'v1')
        try:
            self.build_bucket = self.storage_client.get_bucket(f"{self.env.project}_{self.BUILD_SPEC_BUCKET_SUFFIX}")
        except NotFound as err:
            self.build_bucket = self.storage_client.create_bucket(f"{self.env.project}_{self.BUILD_SPEC_BUCKET_SUFFIX}")
        if sync:
            self.computer_image_sync = ComputerImageSync(suppress=self.suppress, env_dict=self.env.get_env())
        self.specs_to_upload = []

    def run(self):
        upload_specs = self._scan_specs_for_image_sync()
        self._upload_files_to_cloud(upload_specs, self.SPEC_FOLDER)
        self._sync_specs_to_datastore(upload_specs)
        self.sync_startup_scripts_and_instructions()

    def update_guacamole_images(self):
        guac_images = [BuildConstants.MachineImages.GUACAMOLE_SSL]
        for image in guac_images:
            print(f"\t...Beginning to SYNC the server image {image}")
            try:
                self.computer_image_sync.image_server(image)
            except googleapiclient.errors.HttpError:
                print(f'...Image not found on project. Copying over from base project')
                self.computer_image_sync.sync(image)

    def sync_single_spec(self):
        """
        Sync's a single specification file. This can be used by instructors after creating everything needed for the
        specification file. This functions will open the file and serialize the contents to ensure it is a valid
        specification. Then, it scans through the images. If the image does not exist, it will create new images based
        on the server name or return an error.
        Args:
            None

        Returns: None

        """
        spec_file = str(input(f"What is the directory and filename path to the spec file "
                              f"(do not include the specs/plaintext path)? "))
        filename = f"build_files/specs/{spec_file}"
        try:
            with open(filename) as f:
                spec = yaml.safe_load(f)
        except FileNotFoundError:
            print(f"Error: the file {filename} was not found!")
            return
        # If the spec is not a valid schema. This next function will throw an error.
        if not self._validate_spec(spec):
            return
        print(f"\t...Specification passed validation testing.")
        response = str(input(f"Do you want to image the specified servers at this time? "
                             f"If 'N', the source project will be used to sync images (y/N)"))
        image_first = True if str.upper(response) == "Y" else False
        source_project = None
        if not image_first:
            source_project = str(input(f"Enter the source project name you would like to use for copying over images "
                                       f"(or press enter if you want to use the default project)"))
        self._sync_computer_images(file=filename, image_first=image_first, source_project=source_project)
        print(f"\t...Completed processing computing images.")
        print(f"\t...Uploading the specification to the cloud.")
        # self._upload_file_to_cloud(file=filename, cloud_directory=self.SPEC_FOLDER)
        print(f"\t...The specification {spec_file} has been successfully uploaded to the cloud project "
              f"{self.env.project}.")
        #self._sync_specs_to_datastore(filename)

    def sync_startup_scripts_and_instructions(self):
        self._upload_folder_to_cloud(self.build_teacher_instructions_plaintext, self.TEACHER_FOLDER)
        self._upload_folder_to_cloud(self.build_student_instructions, self.STUDENT_FOLDER)
        self._upload_folder_to_cloud(self.build_startup_scripts, self.STARTUP_SCRIPT_FOLDER)
        self._upload_folder_to_cloud(self.build_attacks_specs, self.ATTACK_FOLDER)
        self._sync_attacks_to_cloud()

    def validate_specs(self):
        """
        Checks all specifications and returns list of specs that failed validation
        """
        # Load each spec in plaintext dir and generate the datastore entry to upload
        failed = []
        print('\t...Starting validation for all specifications')
        for item in os.scandir(self.build_specs_plaintext):
            if item.is_dir():
                if any(dir_name == item.name for dir_name in self.EXCLUDE):
                    continue
                else:
                    for file_entry in os.scandir(item.path):  # Use item.path instead of item
                        if validation_errors := self._validate_and_cont(file_entry):
                            # Validation failed, append file and errors
                            failed.append((file_entry.name, validation_errors))
            if item.is_file():
                # Start validation process
                if validation_errors := self._validate_and_cont(item):
                    failed.append((item.name, validation_errors))

        print('The following specifications failed validation: ')
        for spec in failed:
            print(spec[0])

        display_errors = str(input('View validation errors? (Y/n)')).lower()
        if display_errors == 'y':
            for spec in failed:
                print(f'{spec[0]} encountered the following validation errors:')
                for err in spec[1]:
                    print(f'\t{err}')
                print(f'___')
        return failed

    def _upload_files_to_cloud(self, files, cloud_directory):
        for file in files:
            self._upload_file_to_cloud(file, cloud_directory)

    def _upload_folder_to_cloud(self, local_directory, cloud_directory, extension=None):
        print(f"Uploading local {local_directory} to cloud {cloud_directory}...")
        for item in os.scandir(local_directory):
            if item.is_dir():
                for file in os.scandir(item.path):
                    if not extension or file.suffix == f".{extension}":
                        self._upload_file_to_cloud(file, cloud_directory)
            if item.is_file():
                if not extension or item.suffix == f".{extension}":
                    self._upload_file_to_cloud(item, cloud_directory)

    def _upload_file_to_cloud(self, file, cloud_directory):
        if isinstance(file, str):
            file_name = file.split('/')[-1]
        else:
            file_name = file.name
        new_blob = self.build_bucket.blob(f"{cloud_directory}{file_name}")
        with open(file, 'rb') as f:
            response = new_blob.upload_from_file(f, content_type='application/octet-stream')

    def _scan_specs_for_image_sync(self):
        specs_to_upload = []
        for item in os.scandir(self.build_specs_plaintext):
            if item.is_dir():
                if any(dir_name == item.name for dir_name in self.EXCLUDE):
                    continue
                else:
                    for file in os.scandir(item):
                        self._sync_computer_images(file)
                        specs_to_upload.append(file)
            if item.is_file():
                self._sync_computer_images(item)
                specs_to_upload.append(item)
        return specs_to_upload

    def _sync_computer_images(self, file, image_first=False, source_project=None):
        print(f"\t...Beginning to SYNC images from build specification {file}")
        with open(file) as f:
            spec = yaml.safe_load(f)
        server_list = []
        if 'servers' in spec:
            server_list = spec['servers']
        elif 'workspace_servers' in spec:
            server_list = spec['workspace_servers']
        for server_spec in server_list:
            if 'image' in server_spec:
                if image_first:
                    response = input(f"\t...Are you sure you want to IMAGE the server {server_spec['image']}? [Y/n] ")
                    if response.upper() != "N":
                        print(f"\t...Beginning to IMAGE the server image {server_spec['image']}")
                        self.computer_image_sync.image_server(server_spec['image'])
                    else:
                        print(f"\t...OK, Skipping {server_spec['image']}")
                else:
                    print(f"\t...Beginning to SYNC the server image {server_spec['image']}")
                    self.computer_image_sync.sync(server_spec['image'], source_project)
                print(f"\t...Finished processing {server_spec['image']}")

    def _sync_attacks_to_cloud(self):
        ds_manager = DataStoreManager()

        # First update files stored in Cloud buckets
        self._upload_folder_to_cloud(self.build_attacks_specs, self.ATTACK_FOLDER)
        # Load file into python objects and update each datastore entry
        for filename in os.listdir(self.build_attacks_specs):
            attack = yaml.safe_load(open(os.path.join(self.build_attacks_specs, filename)))
            ds_manager.set(key_type=DatastoreKeyTypes.CYBERARENA_ATTACK_SPEC.value, key_id=attack['id'])
            ds_manager.put(attack)

    def _sync_specs_to_datastore(self, specs):
        ds_manager = DataStoreManager()

        # Load each spec in plaintext dir and generate the datastore entry to upload
        if isinstance(specs, list):
            for file in specs:
                _, ext = os.path.splitext(file)
                if ext == ".yaml":
                    self._sync_specs_to_datastore(file)
        else:
            filename = os.path.basename(specs)
            _, ext = os.path.splitext(specs)
            print(f"\t...Beginning to SYNC the specification {filename} to Datastore")
            if ext == '.yaml':
                file = yaml.safe_load(open(specs))
                self._validate_spec(file)
                ds_manager.set(key_type=DatastoreKeyTypes.CATALOG.value, key_id=file['id'])
                ds_manager.put(file)

    def _create_directories(self):
        directories = [
            self.build_attacks_specs,
            self.build_specs_plaintext,
            self.build_startup_scripts,
            self.build_teacher_instructions_plaintext,
            self.build_student_instructions
        ]
        for directory in directories:
            if not os.path.exists(directory):
                os.makedirs(directory)

    @staticmethod
    def _validate_spec(spec):
        if 'build_type' not in spec:
            raise ValidationError("Spec does not contain a build_type")
        # Add the dynamic fields required for a spec to avoid throwing errors on these
        spec['creation_timestamp'] = datetime.datetime.now().timestamp()
        build_type = spec['build_type']
        try:
            if build_type in [BuildConstants.BuildType.UNIT.value, BuildConstants.BuildType.ESCAPE_ROOM.value]:
                spec['instructor_id'] = ['instructor@example.com']
                unit_model = UnitModel(**spec)
                spec = UnitValidator().load(unit_model.dict())
        except ValidationError as e:
            print(f"\t...Validation Error in the file: {e.messages}")
            return False
        return spec

    @staticmethod
    def _validate_and_cont(file):
        """
        Loads file, runs validations, and returns list of existing errors returned with validation
        """
        validation_errors = []
        with open(file, 'r') as f:
            spec = yaml.safe_load(f)
        if 'build_type' not in spec:
            error_msg = "Spec does not contain a build_type"
            validation_errors.append(error_msg)
        # Add the dynamic fields required for a spec to avoid throwing errors on these
        spec['creation_timestamp'] = datetime.datetime.now().timestamp()
        if build_type := spec.get('build_type', None):
            if build_type in [BuildConstants.BuildType.UNIT.value, BuildConstants.BuildType.ESCAPE_ROOM.value]:
                spec['instructor_id'] = ['instructor@example.com']
                unit_model = UnitModel(**spec)
                spec = UnitValidator().load(unit_model.dict())
        return validation_errors
