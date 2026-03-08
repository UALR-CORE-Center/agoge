import copy
import re
from typing import Type
from pydantic import BaseModel, HttpUrl
from datetime import datetime
from enum import Enum

from common.constants.build_constants import BuildConstants
from common.constants.database import DbCollections
from common.constants.states import SpecificationStates
from common.exceptions import AgogeValidationError
from common.models.agoge import NetworkModel, FirewallRuleModel, ServerModel
from common.models.users import AgogeUser
from common.utilities.id_generator import IdGenerator

from utilities.infrastructure_as_code.object_validators import (
    AssessmentValidator,
    FirewallRulesValidator,
    NetworksValidator,
    ServersValidator,
    SummaryValidator,
    WebApplicationsValidator
)
from .language_lookup import LanguageLookup
from .lab_spec_base import LabSpecBase


class FormTypes(str, Enum):
    ASSESSMENT = 'assessment'
    NETWORKS = 'networks'
    REVIEW = 'review'
    SUMMARY = 'summary'
    SERVERS = 'servers'
    WEB_APPS = 'web_applications'
    FIREWALL_RULES = 'firewall_rules'


# TODO: This should be reworked to use Pydantic Models as much as possible

class SpecEditManager(LabSpecBase):
    """Handles temporary storing of specifications"""

    def __init__(self, env_dict: dict) -> None:
        super().__init__(env_dict=env_dict)
        self.class_name = self.__class__.__name__
        self.spec_form = None
        self.catalog = False

    @property
    def edit_id(self) -> str:
        """Retrieve specification edit id.

        Returns (str): edit_id
        """
        return self.spec.get('edit_id') if self.spec else None

    @staticmethod
    def generate_edit_id() -> str:
        return IdGenerator.build_id()

    @staticmethod
    def _map_concepts(tags) -> list[dict]:
        if tags:
            concept_map = {concept.name: concept.value for concept in BuildConstants.TeachingConcepts}
            return [{'id': tag.lower(), 'name': concept_map[tag]} for tag in tags]
        return []

    @staticmethod
    def _generate_schema(objects, model: Type[BaseModel]):
        for obj in objects:
            model(**obj)
            yield obj

    @staticmethod
    def _get_form_type(form: dict) -> str:
        form_key = form.get('form_type')
        if form_key not in [form_type.value for form_type in FormTypes]:
            raise ValueError("Could not determine form type")

        return form_key

    @staticmethod
    def _extract_image_id_from_name(image: str) -> str:
        if isinstance(image, str):
            if image.startswith('image-'):
                return image.split('image-')[1]
            return image
        raise ValueError(f"SpecEditManager:_extract_image_id_from_name - Expected str got {type(image)}")

    @staticmethod
    def _default_author(requester: AgogeUser) -> str:
        invalid_name_chars = set('?;:._-')
        name = requester.name
        if '@' in name:
            name = name.split('@')[0]

        return ''.join(c for c in name if c not in invalid_name_chars)

    def load(
        self,
        edit_id: str = None,
        spec: dict = None,
        form=None
    ) -> None:
        self.spec = self.db.get(collection_name=DbCollections.SPECIFICATION_EDITS, doc_id=edit_id)
        if form:
            self.spec_form = self._form_to_dict(form)
        elif spec:
            self.spec = spec
        else:
            self.logger.error(f"Missing values for edit_id or spec. At least one required!")
            raise ValueError

    def is_valid(self) -> tuple[bool, str]:
        if not self.validated:
            try:
                self._validate_spec()
            except AgogeValidationError as e:
                print(e)
                return False, str(e)
            self.validated = True
        return True, "Spec is valid"

    def save(self) -> None:
        if self.catalog:
            edit_id = self.edit_id

            # Save to Catalog
            self.spec = self.clean()
            spec_id = self.spec.get('id')

            self.logger.info(f'publishing specification edit to id {spec_id}', spec_id=spec_id)
            self.db.update(
                collection_name=self.catalog_collection,
                doc_id=spec_id,
                data=self.spec
            )

            # Delete Edit
            self.db.delete(collection_name=self.edit_collection, doc_id=edit_id)
        else:
            self.logger.info(f'saving changes to specification edit with id {self.edit_id}', edit_id=self.edit_id)
            self.db.update(
                collection_name=self.edit_collection,
                doc_id=self.edit_id,
                data=self.spec
            )

        if not self.is_valid()[0]:
            raise AgogeValidationError("Cannot save invalid spec")
        return

    def delete(
        self,
        edit_id: str
    ) -> None:
        self.db.delete(collection_name=self.edit_collection, doc_id=edit_id)

    def clean(self) -> dict:
        """Prepares specification to be saved to project catalog.
        returns: Cleaned specification object to use in future builds
        """
        cleaned = {}
        ignore_keys = ['edit_id', 'promiscuous_mode', 'network_map', 'parent_id', 'status']
        for key, val in self.spec.items():
            if key not in ignore_keys:
                cleaned[key] = val
            elif key == 'id':
                # Make sure that the Catalog ID is updated to match possible name changes
                spec_id = self._get_id_from_name(
                    self.spec['summary']['name'],
                    self.spec['discriminator']
                )
                cleaned[key] = self.spec['id'] = spec_id
        return cleaned

    def create_spec_copy(
        self,
        spec_db: dict,
        action: SpecificationStates,
        requester: AgogeUser
    ) -> None:
        """Takes input Datastore specification record and creates a temporary copy
        to use for edits
        """
        # Create temporary copy to save future spec changes
        self.spec = copy.deepcopy(spec_db)
        self.spec['edit_id'] = self.generate_edit_id()
        self.spec['parent_id'] = spec_db['id']
        self.spec['summary']['author'] = self._default_author(requester)
        if action == SpecificationStates.COPY:
            discriminator = self.generate_discriminator()
            self.spec['discriminator'] = discriminator
            self.spec['id'] = self._get_id_from_name(spec_db['summary']['name'], discriminator)
            self.spec['status'] = action

        # If we are editing a spec, mark base with edit state to prevent multiple users
        # modifying the same base
        if action == SpecificationStates.EDIT:
            self.spec['status'] = action
            spec_db['status'] = SpecificationStates.EDIT
            self.db.update(collection_name=self.catalog_collection, doc_id=spec_db['id'], data=spec_db)
        self.db.update(collection_name=self.edit_collection, doc_id=self.spec['edit_id'], data=self.spec)

    def create_base_spec(self, requester: AgogeUser) -> None:
        if requester.name:
            author = self._default_author(requester)
        else:
            author = 'Agoge Author'
        self.spec = {
            'assessment': {},
            'build_type': BuildConstants.BuildType.UNIT.value,
            'discriminator': self.generate_discriminator(),
            'edit_id': self.generate_edit_id(),
            'firewall_rules': [],
            'id': 'temp-id',
            'instructor_id': ['instructor@example.com'],
            'networks': [BuildConstants.Networks.WORKOUT_DEFAULT_NETWORK_CONFIG],
            'status': SpecificationStates.EDIT,
            'servers': [],
            'summary': {
                "name": "New Agoge Lab",
                "description": "Agoge Lab Description",
                "author": author,
            },
            'version': '1',
        }
        self.db.update(collection_name=self.edit_collection, doc_id=self.spec['edit_id'], data=self.spec)

    def _validate_spec(self) -> None:
        if not (build_type := self.spec.get('build_type')):
            raise AgogeValidationError("Spec does not contain a build_type")

        # Set default placeholder values
        self.spec.setdefault('creation_timestamp', datetime.now().timestamp())
        if build_type in [BuildConstants.BuildType.UNIT.value, BuildConstants.BuildType.ESCAPE_ROOM.value]:
            instructor_id = self.spec.get('instructor_id', ['instructor@example.com'])
            if not isinstance(instructor_id, list):
                instructor_id = [instructor_id]
            self.spec['instructor_id'] = instructor_id

            # Validate individual specification components
            if summary := self.spec.get('summary'):
                SummaryValidator(self.spec).load(summary)
            if networks := self.spec.get('networks'):
                list(self._generate_schema(networks, NetworkModel))
                network_validator = NetworksValidator(self.spec)
                self.spec.update(network_validator.load())
            if servers := self.spec.get('servers'):
                list(self._generate_schema(servers, ServerModel))
                server_validator = ServersValidator(self.spec).load()
                self.spec.update(server_validator)
            if 'firewall_rules' in self.spec or servers:
                if firewall_rules := self.spec.get('firewall_rules'):
                    list(self._generate_schema(firewall_rules, FirewallRuleModel))
                firewall_validator = FirewallRulesValidator(self.spec).load()
                self.spec.update(firewall_validator)
            if self.spec.get('assessment'):
                assessment_validator = AssessmentValidator(self.spec).load()
                self.spec.update(assessment_validator)
            if self.spec.get('web_applications'):
                web_apps = WebApplicationsValidator(self.spec).load()
                self.spec.update(web_apps)

    def _form_to_dict(
        self,
        form: dict
    ) -> dict:
        ignore = ['build_id', 'form_type', 'spec_type', 'unit_type']
        form_type = self._get_form_type(form)
        if form_type:
            form_methods = {
                FormTypes.SUMMARY.value: self._parse_summary_form,
                FormTypes.ASSESSMENT.value: self._parse_assessment_form,
                FormTypes.NETWORKS.value: self._parse_networks_form,
                FormTypes.SERVERS.value: self._parse_servers_form,
                FormTypes.FIREWALL_RULES.value: self._parse_firewall_rules_form,
                FormTypes.WEB_APPS.value: self._parse_web_applications_form,
            }
            parse_form = form_methods.get(form_type)
            if parse_form:
                parse_form(form=form, ignore=ignore)
                return self.spec
            elif form_type == 'review':
                self.catalog = True
                return self.spec
        raise AgogeValidationError(f'Missing or invalid form_type: {form_type}')

    def _parse_summary_form(
        self,
        form: dict,
        **kwargs
    ) -> None:
        if 'version' not in self.spec:
            self.spec['version'] = 1

        # spec.id is the key used in catalog kind once changes are submitted.
        # It does not imply immutability in the specifications_edit kind.
        self.spec['id'] = self._get_id_from_name(form.get('name'), self.spec['discriminator'])

        # If URLs are not explicitly set to None, validation will fail as "" is still
        # considered to be of type str
        teacher_instructions_url = form.get('teacher_instructions_url')
        if not str(teacher_instructions_url):
            teacher_instructions_url = None
        student_instructions_url = form.get('student_instructions_url')
        if not str(student_instructions_url):
            student_instructions_url = None

        self.spec['summary'].update({
            'name': form.get('name'),
            'author': form.get('author'),
            'teacher_instructions_url': teacher_instructions_url,
            'student_instructions_url': student_instructions_url,
            'description': form.get('description'),
            'tags': BuildConstants.TeachingConcepts.map(form.get('tags')),
        })

    def _parse_assessment_form(
        self,
        form: dict,
        ignore: list
    ) -> None:
        if questions := form.get('questions'):
            if 'assessment' in self.spec:
                self.spec['assessment']['questions'] = questions
            else:
                self.spec['assessment'] = {'questions': questions}
        if assessment_script := form.get('assessment_script'):
            script_name = assessment_script.get('script')
            if script_name:
                language = LanguageLookup.get_language(filename=script_name)
                self.spec['assessment']['assessment_script'] = {
                    'script': script_name,
                    'script_language': language.lower(),
                    'server': assessment_script.get('server'),
                    'operating_system': assessment_script.get('operating_system'),
                }

    def _parse_networks_form(
        self,
        form: dict,
        **kwargs
    ) -> None:
        submitted_networks = form.get('networks')
        if not submitted_networks:
            raise AgogeValidationError('Could not find valid network objects')

        networks = []
        for network in submitted_networks:
            subnet = network.get('subnets', [])
            serialized_network = {
                'name': network.get('name'),
                'subnets': []
            }

            if len(subnet) > 0:
                serialized_network['subnets'].append({
                    'name': 'default',
                    'ip_subnet': subnet[0].get('ip_subnet'),
                    'promiscuous_mode': self._parse_boolean_field(
                        subnet[0].get('promiscuous_mode')
                    )
                })

            networks.append(serialized_network)

        # As long as the generated format above is correct, we can safely replace
        # the stored values with the generated values
        self.spec['networks'] = networks

    def _parse_servers_form(
        self,
        form: dict,
        ignore: list
    ) -> None:
        submitted_servers = form.get('servers')
        if not submitted_servers:
            raise AgogeValidationError('Could not find valid server objects')

        servers = []
        images_db = self.db.query(collection_name=DbCollections.IMAGE)
        images = {image['name']: image for image in images_db}
        for server in submitted_servers:
            image_name = server.get('image')
            if isinstance(image_name, dict):
                image_name = image_name.get('value')
            image_id = self._extract_image_id_from_name(image_name)
            if not (image := images.get(image_id)):
                raise AgogeValidationError(f"Could not find image with given name {image_id}.")

            human_interaction = image.get('human_interaction')
            processed_human_interaction = []
            if human_interaction:
                if isinstance(human_interaction, list):
                    for conn in human_interaction:
                        if 'ssh_key' in conn:
                            del conn['ssh_key']
                        processed_human_interaction.append(conn)
                elif isinstance(human_interaction, dict):
                    if 'ssh_key' in human_interaction:
                        del human_interaction['ssh_key']
                    processed_human_interaction = [human_interaction]

            machine_type = server.get('machine_type')
            processed_machine_type = ""
            if machine_type is not None:
                processed_machine_type = machine_type
            else:
                processed_machine_type = image.get('machine_type', 'e1-standard1')

            processed_server = {
                'name': server.get('name'),
                'image': f"image-{image_id}",
                'hidden': bool(server.get('hidden', False)),
                'community_server': bool(server.get('community_server', False)),
                'machine_type': processed_machine_type,
                'details': {
                    "os": image.get('os'),
                    "description": image.get("description", "Agoge managed server"),
                    "labels": image.get('labels', [])
                },
                'human_interaction': processed_human_interaction,
                'tags': [],
                'nics': [],
            }
            for nic in server.get('nics', []):
                processed_nic = {
                    'subnet_name': 'default',
                    'internal_ip': nic.get('internal_ip'),
                    'external_nat': nic.get('external_nat', False),
                    'direct_connect': nic.get('direct_connect', False),
                    'network': nic.get('network'),
                }
                if (ip_aliases := nic.get('ip_aliases')) and ip_aliases != "":
                    if isinstance(ip_aliases, str):
                        cleaned_ip_aliases = re.sub(r"\s+", "", ip_aliases)
                        ip_aliases = cleaned_ip_aliases.split(',')
                    processed_nic['ip_aliases'] = ip_aliases
                processed_server['nics'].append(processed_nic)

            if server.get('deny_outbound'):
                processed_server['tags'].append('deny-outbound')
            servers.append(processed_server)
        self.spec['servers'] = servers

    def _parse_web_applications_form(
        self,
        form: dict,
        ignore: list,
    ) -> None:
        submitted_apps = form.get('web_applications')
        if not submitted_apps:
            raise AgogeValidationError("Could not find valid web application objects")

        web_apps = []
        for web_app in submitted_apps:
            hostname = web_app.get('host_name')
            name = web_app.get('name')
            starting_directory = web_app.get('starting_directory')
            if not hostname and not starting_directory and not name:
                raise AgogeValidationError("Missing or invalid values for web application")

            # Validate starting_directory
            if not starting_directory.startswith("/"):
                starting_directory = f"/{starting_directory}"

            web_apps.append({
                'host_name': hostname,
                'name': name,
                'starting_directory': starting_directory,
                'url': f"{hostname}{starting_directory}"
            })

        self.spec['web_applications'] = web_apps

    def _parse_firewall_rules_form(
        self,
        form: dict,
        ignore: list
    ) -> None:
        pass

    @staticmethod
    def _parse_boolean_field(value) -> bool:
        return str(value).lower() in ['true', '1', 'on']


# [ eof ]
