"""
TODO: Linux_harden_2.py is in good shape. Need to create a template. Also, this class needs to coordinate with the
    schema for the escape_room assessment.
Provides the startup scripts for each server based on the assessment questions in the build.

This module contains the following classes:
    - AssessmentManager: Supplies the build specification for dynamic assessment.
"""
import secrets
import string
from typing import Any

from common.constants.buckets import Buckets
from common.constants.build_constants import BuildConstants
from common.constants.database import DbCollections, DATABASE_NAME, DatabaseTypes
from common.document_database import DocumentDatabaseFactory
from common.utilities.gcp.cloud_logger import Logger, LoggerNames
from common.utilities.gcp.cloud_env import CloudEnv


class AssessmentManager:
    def __init__(
        self,
        build_id,
        build_type: str = BuildConstants.BuildType.WORKOUT,
        env_dict=None
    ) -> None:
        """

        Args:
            build_id (str): The build ID to query for and use for assessment.
        """
        self.class_name = self.__class__.__name__
        self.build_id = build_id
        self.logger = Logger(LoggerNames.CLOUD_FN)
        self.env = CloudEnv(env_dict=env_dict) if env_dict else CloudEnv()
        self.db = DocumentDatabaseFactory.create_db_object(
            db_type=DatabaseTypes.firestore,
            database_name=DATABASE_NAME
        )
        self.script_repository = (f"gs://{self.env.project}_{Buckets.BUILD_SPEC_BUCKET_SUFFIX}/"
                                  f"{Buckets.Folders.STARTUP_SCRIPTS.value}")
        if build_type == BuildConstants.BuildType.WORKOUT.value:
            workout = self.db.get(collection_name=DbCollections.WORKOUT, doc_id=self.build_id)
            self.workout = workout
            self.servers = workout.get('servers', []) if workout else []
            unit_id = workout['parent_id']
        else:
            unit_id = build_id
        self.unit = self.db.get(collection_name=DbCollections.UNIT, doc_id=unit_id)
        self.current_server_name = None
        if not self.unit:
            raise LookupError(f"The database record for {self.build_id} no longer exists!")
        self.url = self._get_url()
        self.assessment_questions = self._get_assessment_questions()
        self.assessment_script_spec = self._get_assessment_script_spec()

    def assessment_item(self, target_key: str) -> Any:
        assessment_types = ['assessment', 'lms_integration']
        for key in assessment_types:
            if assessment := self.unit.get(key):
                if target_key in assessment:
                    return assessment[target_key]
        return None

    def get_startup_scripts(self, server_name: str):
        """
        If this is the server running the assessment script, send it the script to include in meta data.

        Args:
            server_name (str): The name of the server to use for adding the script meta data.

        Returns: The startup script to include as meta-data
        """
        self.current_server_name = server_name
        if self.assessment_script_spec and server_name.endswith(self.assessment_script_spec['server']):
            self.logger.info(f"{self.class_name}:{server_name} - Adding the following script to server: "
                             f"{self.assessment_script_spec}")
            return self._create_startup_script()
        else:
            return None

    def _get_url(self):
        return f"{self.env.main_app_url}/workout/"

    def _get_assessment_questions(self):
        if escape_room := self.unit.get('escape_room'):
            return escape_room['puzzles']
        else:
            return self.assessment_item('questions')

    def _get_assessment_script_spec(self):
        return self.assessment_item('assessment_script')

    def _create_startup_script(self):
        """
        Creates the initial assessment script structure that will be built with additional question_key environment
        variables. The task string is also created at this point, and will be appended at the end of the script.
        """
        script_operating_system = self.assessment_script_spec['operating_system']
        script_path = self.assessment_script_spec['script']
        script_filename = script_path.split("/")[-1]
        script_params = {
            'SCRIPT_REPOSITORY': self.script_repository,
            'SCRIPT': script_filename,
            'SCRIPT_NAME': f"cyber-arena-assessment",
        }
        # Create operating system specific script pieces.
        if script_operating_system == BuildConstants.ScriptOperatingSystems.WINDOWS:
            key = 'windows-startup-script-bat'
            initial_script = StartupScripts.Windows.env.format(BUILD_ID=self.build_id, URL=self.url)
            if script_filename in ['randomized-passwords.ps1', 'randomized-passwords.sh']:
                self.username, self.password = self._load_username_and_update_password(self.current_server_name)
                if not self.username:
                    raise ValueError(f"Username missing for server {self.current_server_name}")
                initial_script += self._credential_env_windows()
                return {'key': key, 'value': initial_script}

            if self.assessment_script_spec['script_language'] == 'python':
                script_params['REOCCURRING_SCRIPT'] = f"python {script_filename}"
            elif self.assessment_script_spec['script_language'] == 'powershell':
                script_params['REOCCURRING_SCRIPT'] = f"powershell.exe -File .\\{script_filename}"
            else:
                script_params['REOCCURRING_SCRIPT'] = script_filename

            task = StartupScripts.Windows.task.format_map(script_params)
        else:
            key = 'startup-script'
            initial_script = StartupScripts.Linux.env.format(BUILD_ID=self.build_id, URL=self.url)
            if script_filename in ['randomized-passwords.ps1', 'randomized-passwords.sh']:
                self.username, self.password = self._load_username_and_update_password(self.current_server_name)
                if not self.username:
                    raise ValueError(f"Username missing for server {self.current_server_name}")
                initial_script += self._credential_env_linux()

            if self.assessment_script_spec['script_language'] == 'python':
                script_params['REOCCURRING_SCRIPT'] = f"python3 /usr/bin/{script_filename}"
            else:
                script_params['REOCCURRING_SCRIPT'] = f"/usr/bin/{script_filename}"

            task = StartupScripts.Linux.task.format_map(script_params)
        assessment_script = {'key': key, 'value': initial_script}
        # Add the question environment variables
        assessment_script['value'] = self._add_question_env(assessment_script['value'], script_operating_system)
        # Finally, add the reoccurring task at the end of the script.
        assessment_script['value'] += task
        return assessment_script

    def _add_question_env(self, assessment_script, script_operating_system):
        for i, question in enumerate(self.assessment_questions or []):
            if question and question.get('script_assessment'):
                question_key = question.get('question_key')
                if not question_key:
                    continue
                if script_operating_system == BuildConstants.ScriptOperatingSystems.WINDOWS:
                    assessment_script += StartupScripts.Windows.question.format(NUMBER=i, QUESTION_KEY=question_key)
                else:
                    assessment_script += StartupScripts.Linux.question.format(NUMBER=i, QUESTION_KEY=question_key)
        return assessment_script

    def _generate_password(self) -> str:
        safe_chars = (
                string.ascii_letters +
                string.digits +
                "!@#$*_+-=?:."
        )
        return ''.join(secrets.choice(safe_chars) for _ in range(20))

    def _credential_env_linux(self):
        return f"USERNAME={self.username}\nPASSWORD={self.password}\n"

    def _credential_env_windows(self):
        return (
            f"set USERNAME={self.username}\n"
            f"set PASSWORD={self.password}\n"
            f"setx /m USERNAME {self.username}\n"
            f"setx /m PASSWORD {self.password}\n"
            # Inline PowerShell user creation / password update
            "powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -Command \""
            "$u = $env:USERNAME; "
            "$p = $env:PASSWORD; "
            "$secure = ConvertTo-SecureString $p -AsPlainText -Force; "
            "$user = Get-LocalUser -Name $u -ErrorAction SilentlyContinue; "
            "if ($null -eq $user) { "
            "  New-LocalUser -Name $u -Password $secure -PasswordNeverExpires:$false -UserMayNotChangePassword:$false; "
            "  Add-LocalGroupMember -Group 'Administrators' -Member $u; "
            "} else { "
            "  Set-LocalUser -Name $u -Password $secure; "
            "} "
            "\"\n"
        )

    def _load_username_and_update_password(self, server_name: str):

        servers = self.workout.get("servers", [])

        for i, server in enumerate(servers):
            record_name = server.get("name")

            if server_name.endswith(record_name):
                hi = server.get("human_interaction", [])

                if not hi:
                    return None, None

                username = hi[0].get("username")
                if not username:
                    return None, None

                password = self._generate_password()

                # Update every protocol entry in hi
                for idx, entry in enumerate(hi):
                    entry["password"] = password

                server["human_interaction"] = hi
                servers[i] = server

                try:
                    self.db.update(
                        collection_name=DbCollections.WORKOUT,
                        doc_id=self.build_id,
                        data={"servers": servers}
                    )
                    self.logger.info(f"Successfully wrote randomized password to {self.build_id}!")
                except Exception as e:
                    self.logger.error(f"Writing randomized password to {self.build_id} failed: {e}")
                    raise
                self.workout["servers"] = servers
                return username, password
        return None, None

class StartupScripts:
    """
    The Startup Scripts are either Windows or Linux based. Windows runs individual command prompt commands, but
    Linux has a single script file and builds the script file through concatenation.
    """
    class Windows:
        env = 'setx /m BUILD_ID {BUILD_ID}\n' \
              'setx /m URL {URL}\n'
        question = 'setx /m Q_{NUMBER}_KEY {QUESTION_KEY}\n'
        task = 'call gsutil cp {SCRIPT_REPOSITORY}{SCRIPT} .\n' \
               'schtasks /Create /SC MINUTE /TN {SCRIPT_NAME} /RU System /TR {REOCCURRING_SCRIPT}'

    class Linux:
        env = '#! /bin/bash\n' \
              'cat >> /etc/environment << EOF\n' \
              'BUILD_ID={BUILD_ID}\n' \
              'URL={URL}\n'
        question = 'Q_{NUMBER}_KEY={QUESTION_KEY}\n'
        task = 'EOF\n' \
               'gsutil cp {SCRIPT_REPOSITORY}{SCRIPT} /usr/bin\n' \
               'if [[ "{SCRIPT}" == *.sh ]]; then chmod +x /usr/bin/{SCRIPT}; fi\n/usr/bin/{SCRIPT}\n' \
               '(crontab -l 2>/dev/null; echo "* * * * * {REOCCURRING_SCRIPT}") | crontab -'