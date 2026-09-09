from pydantic import (
    AnyUrl,
    BaseModel,
    Field,
    HttpUrl,
    field_validator,
    model_validator,
)
from typing import List, Optional, Union, Any, Dict, Literal
from datetime import datetime
from ipaddress import ip_network
import re
import uuid

from common.constants.build_constants import BuildConstants
from common.constants.buckets import Buckets
from common.constants.enumerators import SnapshotTypes
from common.constants.states import ImageStatus, ServerStates
from common.models.wireguard import WireGuardEndpointModel
from common.utilities.gcp.shared_secrets import shared_api_secret_names


UnitTypeValue = Literal[
    BuildConstants.UnitType.SOLO.value,
    BuildConstants.UnitType.COMMUNITY.value,
]


class CloudEnvModel(BaseModel):
    @model_validator(mode='before')
    @classmethod
    def validate_shared_api_secrets(cls, values: Any) -> Any:
        if isinstance(values, dict):
            shared_api_secret_names(values)
        return values

    classroom_user: Optional[str] = Field(default=None, description="Email account of user to associate "
                                                                    "with Google Classroom")
    max_workspaces: Optional[int] = Field(default=300, le=1000, description="Max number of workspaces to allow")
    spec_bucket: Optional[str] = Field(default=None, description="Storage bucket for build specifications")
    student_workout_firewall: Optional[bool] = Field(default=False,
                                                     description="Whether student workout firewall is enabled")
    wireguard_dns_prefix: Optional[str] = Field(
        default="wg",
        description="DNS label prefix for public WireGuard gateway endpoints"
    )
    wireguard_dns_suffix: Optional[str] = Field(
        default=None,
        description="Public DNS suffix for WireGuard endpoints; defaults to parent_dns_suffix"
    )
    wireguard_port: Optional[int] = Field(
        default=51820,
        ge=1,
        le=65535,
        description="Public UDP port used by WireGuard gateways"
    )

    @field_validator('wireguard_port', mode='before')
    @classmethod
    def validate_wireguard_port(cls, value: Any) -> Optional[int]:
        if value is None:
            return None
        if isinstance(value, bool):
            raise ValueError('wireguard_port must be an integer from 1 through 65535')
        if isinstance(value, int):
            return value
        if isinstance(value, str) and re.fullmatch(r'[0-9]+', value.strip()):
            return int(value.strip())
        raise ValueError('wireguard_port must be an integer from 1 through 65535')

    @field_validator('wireguard_dns_prefix')
    @classmethod
    def validate_wireguard_dns_prefix(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        value = value.strip().lower().strip('-.')
        # The generated label is ``<prefix>-<five-digit-id>`` and DNS labels
        # cannot exceed 63 octets, leaving at most 57 for the prefix.
        if len(value) > 57 or not re.fullmatch(
            r'[a-z0-9](?:[a-z0-9-]{0,55}[a-z0-9])?', value
        ):
            raise ValueError('wireguard_dns_prefix must be a valid DNS label of at most 57 characters')
        return value

    @field_validator('wireguard_dns_suffix')
    @classmethod
    def validate_wireguard_dns_suffix(cls, value: Optional[str]) -> Optional[str]:
        if value is None or not value.strip():
            return None
        hostname = value.strip().lower().strip('.')
        if len(hostname) > 253:
            raise ValueError('wireguard_dns_suffix must be a valid DNS suffix')
        if any(
            not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', label)
            for label in hostname.split('.')
        ):
            raise ValueError('wireguard_dns_suffix must be a valid DNS suffix')
        return f'.{hostname}'

    @model_validator(mode='before')
    @classmethod
    def validate_wireguard_zone(cls, values: Any) -> Any:
        """Keep generated records inside the one configured public DNS zone."""
        if not isinstance(values, dict):
            return values
        wireguard_suffix = values.get('wireguard_dns_suffix')
        parent_suffix = values.get('parent_dns_suffix')
        if wireguard_suffix and parent_suffix:
            wireguard_suffix = str(wireguard_suffix).strip('.').lower()
            parent_suffix = str(parent_suffix).strip('.').lower()
            if not (
                wireguard_suffix == parent_suffix
                or wireguard_suffix.endswith(f'.{parent_suffix}')
            ):
                raise ValueError(
                    'wireguard_dns_suffix must equal or be a subdomain of parent_dns_suffix'
                )
        return values

    @model_validator(mode='before')
    @classmethod
    def set_spec_bucket(cls, values: Any) -> Any:
        if not values.get('spec_bucket'):
            project = values.get('project')
            if project:
                values['spec_bucket'] = f"{project}_{Buckets.BUILD_SPEC_BUCKET_SUFFIX}"
        return values

    class Config:
        extra = "ignore"


class TeachingConceptsModel(BaseModel):
    id: str = Field(..., description="ID of the teaching concept")
    name: str = Field(..., description="Name of the teaching concept")


class StandardMappingsModel(BaseModel):
    framework: str = Field(..., description="Framework of the standard mapping")
    mapping: str = Field(..., description="Mapping of the standard")


class SubNetworkModel(BaseModel):
    name: str = Field(..., description="Name of the subnetwork")
    ip_subnet: str = Field(..., description="IP subnet of the subnetwork")
    promiscuous_mode: Optional[bool] = Field(default=False, description="Toggle promiscuous mode for this subnetwork")


class NetworkModel(BaseModel):
    name: str = Field(..., description="Name of the network")
    subnets: Optional[List[SubNetworkModel]] = Field(default=None)
    reservations: List[str] = Field(
        default_factory=list,
        description="Unit-scoped IP addresses reserved from dynamic allocation"
    )

    @field_validator('reservations', mode='before')
    @classmethod
    def normalize_null_reservations(cls, value):
        return value or []


class NicModel(BaseModel):
    network: str = Field(..., description="Network of the NIC")
    internal_ip: Optional[str] = Field(default=None, description="Internal IP of the NIC")
    subnet_name: Optional[str] = Field(default="default", description="Subnet name of the NIC")
    external_nat: Optional[bool] = Field(default=False, description="Must be true if servers on network are intended to communicate outside of network.")
    external_ip_name: Optional[str] = Field(
        default=None,
        description="Optional reserved Google Compute Engine external address resource name"
    )
    ip_aliases: Optional[List[str]] = Field(default=None, description='Assign multiple IP values to NIC.')
    direct_connect: Optional[bool] = Field(default=False, description="Allow users to connect without using a proxy-machine.")


class HumanInteractionModel(BaseModel):
    display: Optional[bool] = Field(default=False)
    protocol: str = Field(..., description="Protocol of the human interaction")
    username: Optional[str] = Field(default=None)
    password: Optional[str] = Field(default=None)
    ssh_key: Optional[str] = Field(default=None)
    domain: Optional[str] = Field(default=None)
    security_mode: Optional[str] = Field(default=BuildConstants.Guacamole.SecurityModes.NLA,
                                         description="Security mode of the human interaction")


class ServerDetailsModel(BaseModel):
    description: Optional[str] = Field(default=None, description="Useful services and programs this image is providing related to the workout.")
    os: Optional[str] = Field(default=None, description="Operating system of the server")
    labels: Optional[List[str]] = Field(default=None, description="List of services and functionality provided on this server.")


class WebApplicationModel(BaseModel):
    name: str = Field(..., description="Display name of the container")
    host_name: str = Field(..., description="Host name for the URL")
    starting_directory: str = Field(..., description="The starting web directory for the container URL.")
    url: Optional[str] = Field(None, description="Full path of web application")


class FirewallModel(BaseModel):
    name: str = Field(..., description="Name of the firewall")
    type: str = Field(..., description="Type of the firewall")
    gateway: str = Field(..., description="Gateway of the firewall")
    networks: List[str] = Field(..., description="Networks of the firewall")
    allow_outbound: Optional[bool] = Field(default=True, description="If False, connections can still come in, but general outbound traffic will be denied")


class FirewallRuleModel(BaseModel):
    name: str = Field(..., description="Name of the firewall rule")
    network: str = Field(..., description="Network of the firewall rule")
    action: Optional[str] = Field(default=None, description="Action of the firewall rule")
    target_tags: Optional[List[str]] = Field(default_factory=list)
    protocol: Optional[str] = Field(default=None, description="Protocol of the firewall rule")
    ports: Optional[List[str]] = Field(default=None, description="List of ports to apply rule to.")
    ip_ranges: Optional[List[str]] = Field(default=["0.0.0.0/0"], description="Range of source or destination IPs to attach rule to.")
    direction: Optional[str] = Field(default=BuildConstants.Firewalls.TrafficDirection.INGRESS.value, description="Direction of flow of traffic.")
    priority: Optional[int] = Field(default=1000, description="Rule priority.")


class RouteModel(BaseModel):
    """A custom static route installed for a lab network."""

    name: str = Field(..., description="Name of the route, before the build ID prefix is added")
    network: str = Field(..., description="Specification network on which to install the route")
    dest_range: str = Field(..., description="Destination IPv4 or IPv6 range in CIDR notation")
    next_hop_instance: str = Field(..., description="Specification server name used as the route next hop")
    priority: int = Field(default=1000, ge=0, le=65535, description="Google Cloud route priority")
    tags: List[str] = Field(
        default_factory=list,
        description="Optional instance network tags that select which VMs use this route"
    )
    description: Optional[str] = Field(default=None, description="Optional route description")

    @field_validator('dest_range')
    @classmethod
    def validate_dest_range(cls, value: str) -> str:
        """Require a network address rather than silently masking host bits."""
        try:
            return str(ip_network(value, strict=True))
        except ValueError as error:
            raise ValueError('dest_range must be a valid CIDR network') from error

    @field_validator('tags', mode='before')
    @classmethod
    def normalize_null_tags(cls, value):
        return value or []


class ProxyConnectionModel(BaseModel):
    idx: Optional[int] = Field(default=None, description="Sorted index of connection")
    url: Optional[str] = Field(default=None, description="Full URL path to server connection")
    username: str = Field(..., description="Username for the proxy connection")
    internal_ip_address: str = Field(..., description="Internal IP address for the proxy connection")
    password: str = Field(..., description="Password for the proxy connection")
    server: str = Field(..., description="Server name for the proxy connection")


class ServerModel(BaseModel):
    """
    Servers used as part of a Unit or Unit Workout lab.
    Partially based on information stored in AgogeImageModel objects.
    """
    add_disk: Optional[int] = Field(default=0, description="Additional disk space of the server")
    build_type: Optional[str] = Field(default=None, description="Build type of the server")
    can_ip_forward: Optional[bool] = Field(default=False, description="Whether IP forwarding is enabled")
    community_server: Optional[bool] = Field(default=False, description="Whether this server should be a shared server in a community build unit.")
    wireguard_gateway: Optional[bool] = Field(
        default=False,
        description="Whether this shared server is the WireGuard gateway for a community unit"
    )
    wireguard_endpoint_id: Optional[str] = Field(
        default=None,
        pattern=r'^[1-9][0-9]{4}$',
        description="Runtime-assigned five-digit public WireGuard endpoint identifier"
    )
    details: Optional[ServerDetailsModel] = Field(default=None)
    firewall_rules: Optional[List[FirewallRuleModel]] = Field(default=None, description="List of firewall rules associated with server.")
    hidden: Optional[bool] = Field(default=False, description="Whether to display this server to students or not.")
    human_interaction: Optional[List[HumanInteractionModel]] = Field(default=None)
    hostname: Optional[str] = Field(default=None, description="Public DNS record associated with server.")
    image: str = Field(..., description="Image of the server")
    machine_type: Optional[str] = Field(default="e1-standard1", description="Machine type of the server")
    metadata: Optional[str] = Field(default=None, description="Metadata of the server")
    guacamole_startup_script: Optional[str] = Field(default=None, description="Optional startup script for Guacamole service")
    startup_script: Optional[str] = Field(default=None, description="Optional startup script to pass into server")
    min_cpu_platform: Optional[str] = Field(default="", description="Minimum CPU platform of the server")
    name: str = Field(..., description="Name of server.")
    nics: Optional[List[NicModel]] = Field(default=None)
    routes: Optional[List[RouteModel]] = Field(
        default=None,
        description="Static routes to create after this next-hop server is available"
    )
    parent_build_type: Optional[str] = Field(default=None, description="Build type of parent object (i.e. workout, unit, etc.).")
    parent_id: Optional[str] = Field(default=None, description="ID of parent object to associate with server.")
    shutoff_timestamp: Optional[float] = Field(default=None, description="Timestamp of when server will shut down.")
    sshkey: Optional[str] = Field(default=None, description="SSH key of the server")
    tags: List[str] = Field(
        default_factory=list,
        description="Optional field used for attaching specific firewall rules to machine"
    )
    state: Optional[int] = Field(default=None, description="Current build state of server")
    state_timestamp: Optional[str] = Field(default=None, description="Timestamp of the server state")

    @model_validator(mode='before')
    @classmethod
    def normalize_legacy_fields(cls, values: Any) -> Any:
        """Normalize nullable tags and the old plural startup-script field."""
        if not isinstance(values, dict):
            return values

        if values.get('tags') is None:
            values['tags'] = []

        if values.get('startup_script'):
            return values

        legacy_scripts = values.get('startup_scripts')
        if isinstance(legacy_scripts, str):
            values['startup_script'] = legacy_scripts
        elif isinstance(legacy_scripts, list):
            values['startup_script'] = '\n'.join(
                script for script in legacy_scripts if isinstance(script, str) and script
            ) or None
        return values


class AgogeSummaryModel(BaseModel):
    name: str = Field(..., description="Name of the Agoge summary")
    description: str = Field(..., description="Description of the Agoge summary")
    teacher_instructions_url: Optional[str] = Field(default=None, description="URL for teacher instructions")
    student_instructions_url: Optional[str] = Field(default=None, description="URL for student instructions")
    hourly_cost: Optional[float] = Field(default=None, description="Hourly cost of the Agoge summary")
    author: Optional[str] = Field(default=None, description="Author of the Agoge summary")
    standard_mappings: Optional[List[StandardMappingsModel]] = Field(default=None, description='Curriculum standard mappings for this lab')
    tags: Optional[List[TeachingConceptsModel]] = Field(default_factory=list, description='Key concepts that this build is intended to teach')


class AgogeWorkoutSummaryModel(BaseModel):
    name: str = Field(..., description="Name of the Agoge summary")
    description: str = Field(..., description="Description of the Agoge summary")
    student_instructions_url: Optional[str] = Field(
        default=None,
        description="URL for student instructions"
    )


class WorkspaceSettingsModel(BaseModel):
    count: int = Field(..., description='The number of distinct workstation builds to deploy')
    registration_required: Optional[bool] = Field(default=False, description='Whether students must login to access this build')
    student_emails: Optional[List[str]] = Field(default=None, description='Email addresses of students when registration is required')
    student_names: Optional[List[str]] = Field(default=None, description='Name of the student assigned to the workspaces')
    expires: float = Field(..., description="UTC timestamp of date when resources are available until.")


class AssessmentQuestionModel(BaseModel):
    id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()), description="An ID to use when referring to specific questions")
    name: Optional[str] = Field(default=None, description="The name of the question, which is also used for the workout-level assessment script.")
    type: str = Field(..., description="Type of the question")
    question: str = Field(..., description="Question text")
    key: Optional[str] = Field(default=None, description='The value used for decrypting individual cryptographic questions')
    answer: Optional[str] = Field(default=None, description="The answer to the question for questions of type input")
    script_assessment: Optional[bool] = Field(default=False)
    complete: Optional[bool] = Field(default=False)


class AssessmentScriptModel(BaseModel):
    script: Optional[str] = Field(default=None, description="script name (e.g. attack.py)")
    script_language: Optional[str] = Field(default=None, description="e.g. python")
    server: Optional[str] = Field(default=None, description="Server that runs script.")
    operating_system: Optional[str] = Field(default=None, description="Target server operating system")


class AssessmentModel(BaseModel):
    questions: Optional[List[AssessmentQuestionModel]] = Field(default=None)
    assessment_script: Optional[AssessmentScriptModel] = Field(default=None, description="The assessment script for all indicated questions.")
    key: Optional[str] = Field(
        default=None,
        description='Key used for decrypting workout secrets in container applications'
    )


class LMSQuizAnswerModel(BaseModel):
    answer_text: Optional[str] = Field(default=None, description="Answer text")
    weight: Optional[float] = Field(default=0.0, description="Weight of the answer")


class LMSQuizQuestionsModel(BaseModel):
    name: Optional[str] = Field(default=None, description="Question name")
    question_name: Optional[str] = Field(default=None, description="Alternative field for question name (Canvas specific).")
    question_text: str = Field(..., description="Question text")
    question_type: Optional[str] = Field(default=None, description="Question type")
    points_possible: Optional[float] = Field(default=None, description="Points possible")
    script_assessment: Optional[bool] = Field(default=False)
    bonus: Optional[bool] = Field(default=None, description="Whether to count this question as a bonus")
    answers: Optional[List[LMSQuizAnswerModel]] = Field(default=None, description="Question answers")
    complete: Optional[bool] = Field(default=None, description="Used to mark completion for multi-step auto assessment scripts")


class LMSConnectionModel(BaseModel):
    lms_type: str = Field(..., description="The type of LMS this should integrate with.")
    api_key: Optional[str] = Field(default=None, description="The API key from the user profile needed for connecting to the LMS")
    url: Optional[str] = Field(default=None, description="The LMS API URL")
    course_code: int = Field(..., description="The course code to use for creating the LMS assignments")
    name: Optional[str] = Field(default=None, description="Name of LMS course")


class LMSIntegrationModel(BaseModel):
    lms_connection: Optional[LMSConnectionModel] = Field(default=None, description="The information needed to connect a lab to a course")
    course_work: Optional[str] = Field(default=BuildConstants.LMSCourseWork.ASSIGNMENT.value, description="Practice quiz or assignment")
    due_at: Optional[float] = Field(default=None, description="Due date for assignment")
    description: Optional[str] = Field(default=None, description="Description of assignment")
    allowed_attempts: Optional[float] = Field(default=-1.0, description="Attempts available for assignment, -1 is unlimited")
    assessment_script: Optional[AssessmentScriptModel] = Field(default=None, description="The assessment script for all indicated questions.")
    questions: Optional[List[LMSQuizQuestionsModel]] = Field(default=None)

    @field_validator('questions', mode='before')
    def default_questions(cls, value):
        return value or []


class EscapeRoomModel(BaseModel):
    question: str = Field(..., description="The door to open in the escape room")
    answer: Optional[str] = Field(default=None, description="Answer from the top level-question")
    responses: Optional[List[str]] = Field(default_factory=list, description="Records the team's attempts to answer the question and escape")
    escaped: Optional[bool] = Field(default=False, description="Whether or not the team has successfully escaped")
    time_limit: Optional[int] = Field(default=3600, description="Number of seconds the team has to escape from the room")
    start_time: Optional[float] = Field(default=0.0, description="When the escape room started.")
    remaining_time: Optional[float] = Field(default=None)
    puzzles: Optional[List['PuzzleModel']] = Field(default=None)


class PuzzleModel(BaseModel):
    id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()), description="An ID to use when referring to specific puzzles")
    instructions_url: Optional[Union[AnyUrl, str]] = Field(default=None, description="URL for puzzle instructions")
    entry_type: Optional[str] = Field(default=None, description="The type of entry to present to the user for solving the question")
    entry_name: Optional[str] = Field(default=None, description="A name based on the entry_type to help build a URL for the student to click on.")
    type: Optional[str] = Field(default=BuildConstants.QuestionTypes.INPUT, description="Type of the puzzle question")
    summary: Optional[str] = Field(default=None, description='Brief outline of what the puzzle is about')
    question: str = Field(..., description="Question text")
    name: str = Field(..., description="Name of the puzzle")
    answer: Optional[str] = Field(default=None, description="The answer to the question for questions of type input")
    script: Optional[str] = Field(default=None, description="script name (e.g. attack.py)")
    script_language: Optional[str] = Field(default=None, description="e.g. python")
    server: Optional[str] = Field(default=None, description="Server that runs script.")
    operating_system: Optional[str] = Field(default=None, description="Target server operating system")
    responses: Optional[List[str]] = Field(default_factory=list, description="Records the team's attempts to answer the question and escape")
    correct: Optional[bool] = Field(default=False, description="Whether the puzzle response is correct")
    reveal: Optional[str] = Field(default=None, description="Information to reveal if they have the right answer")

    @field_validator('instructions_url', mode='before')
    def allow_empty_string_for_url(cls, v):
        if v == "":
            return None
        return v


class UnitModel(BaseModel):
    id: str = Field(..., description="ID of the unit")
    creation_timestamp: Optional[float] = Field(default=None)
    version: str = Field(..., description="Version of the unit")
    class_id: Optional[str] = Field(default=None)
    instructor_id: Union[str, List[str]] = Field(..., description="List of instructor IDs")
    workspace_settings: Optional[WorkspaceSettingsModel] = Field(default=None)
    build_type: str = Field(..., description="Build type of the unit")
    unit_type: UnitTypeValue = Field(
        default=BuildConstants.UnitType.SOLO.value,
        description="Defines the type of unit setup."
    )
    summary: AgogeSummaryModel = Field(..., description="Summary of the Agoge unit")
    networks: Optional[List[NetworkModel]] = Field(default=None)
    wireguard_endpoint: Optional[WireGuardEndpointModel] = Field(
        default=None,
        description="Runtime public endpoint allocated for this community Unit's WireGuard gateway"
    )
    routes: Optional[List[RouteModel]] = Field(default=None, description="Custom static routes for the unit")
    servers: Optional[List[ServerModel]] = Field(default=None)
    web_applications: Optional[List[WebApplicationModel]] = Field(default=None, description="Used for cloud container labs")
    firewalls: Optional[List[FirewallModel]] = Field(default=None)
    firewall_rules: Optional[List[FirewallRuleModel]] = Field(default=None, description="These are ONLY set by the program to allow all internal traffic")
    assessment: Optional[AssessmentModel] = Field(default=None, description="Use Agoge to provide grading support")
    lms_integration: Optional[LMSIntegrationModel] = Field(default=None, description="Use connected LMS to provide grading support and distribution functionality")
    escape_room: Optional[EscapeRoomModel] = Field(default=None, description="Escape room units include additional specification of the escape room puzzles associated with each workout")
    test: Optional[bool] = Field(default=None, description="Whether the unit is a test. This helps in cleaning the datastore.")
    join_code: Optional[str] = Field(default=None, description='Used to invite students to claim a unit workspace')
    workout_duration_days: Optional[int] = Field(default=None, description='For asynchronous workout builds, specify to add an expiration timestamp for the workout.')
    accessibility_features: Optional[bool] = Field(default=False, description="Whether accessibility features are enabled or not")
    state: Optional[int] = Field(default=None, description="Current build state of unit")
    state_timestamp: Optional[str] = Field(default=None, description="Timestamp of the unit state")

    class Config:
        from_attributes = True


class CriteriaModel(BaseModel):
    category: str = Field(..., description="The title of the category, such as 'Configuration' or 'Documentation'.")
    index: int = Field(..., description="The position of the performance level within the rubric criteria array, starting at 0. For example, 0 could represent 'Exemplary'.")
    description: str = Field(..., description="Detailed description of the expectations for this performance level.")


class RubricModel(BaseModel):
    build_id: str = Field(..., description="ID of the rubric")
    headers: List[str] = Field(..., description="Performance level headers, ordered by proficiency level")
    categories: List[str] = Field(..., description="List of rubric categories such as 'Configuration', 'Documentation', etc.")
    criteria: List[CriteriaModel] = Field(..., description="List of rubric criteria")

    class Config:
        from_attributes = True


class CatalogModel(BaseModel):
    discriminator: str = Field(..., description="Discriminator field")
    networks: Optional[List[NetworkModel]] = None
    routes: Optional[List[RouteModel]] = None
    servers: Optional[List[ServerModel]] = None
    summary: AgogeSummaryModel = Field(...)
    firewall_rules: Optional[List[FirewallRuleModel]] = None
    instructor_id: Union[str, List[str]] = Field(..., description="List of instructor IDs")
    creation_timestamp: Optional[float] = None
    build_type: str = Field(..., description="Build type of the unit")
    unit_type: UnitTypeValue = Field(
        default=BuildConstants.UnitType.SOLO.value,
        description="Defines the type of unit setup."
    )
    version: str = Field(..., description="Version of the unit")
    id: str = Field(..., description="ID of the unit")
    assessment: Optional[AssessmentModel] = Field(default=None, description="Use Agoge to provide grading support")
    lms_quiz: Optional[LMSIntegrationModel] = Field(default=None, description="Use connected LMS to provide grading support and distribution functionality")

    class Config:
        from_attributes = True


class CatalogEditModel(BaseModel):
    assessment: Optional[AssessmentModel] = Field(default=None, description="Use Agoge to provide grading support")
    build_type: str = Field(..., description="Build type of the unit")
    creation_timestamp: Optional[float] = None
    discriminator: str = Field(..., description="Discriminator field")
    edit_id: str = Field(..., description="ID of edit")
    firewall_rules: Optional[List[FirewallRuleModel]] = None
    firewalls: Optional[List[FirewallModel]] = Field(default=None)
    id: Optional[str] = Field(..., description="Catalog ID to save final edit.")
    instructor_id: Union[str, List[str]] = Field(..., description="List of instructor IDs")
    lms_quiz: Optional[LMSIntegrationModel] = Field(default=None, description="Use connected LMS to provide grading support and distribution functionality")
    networks: Optional[List[NetworkModel]] = Field(default=None)
    routes: Optional[List[RouteModel]] = Field(default=None)
    parent_id: Optional[str] = Field(default=None, description="ID of Catalog object used for copy or edits")
    promiscuous_mode: bool = Field(default=False, description="Enable network mirroring")
    servers: Optional[List[ServerModel]] = Field(default=None)
    status: Optional[str] = Field(default=None, description="Current status identifier")
    summary: Optional[AgogeSummaryModel] = Field(..., description="Summary of the Agoge unit")
    unit_type: UnitTypeValue = Field(
        default=BuildConstants.UnitType.SOLO.value,
        description="Defines the type of unit setup."
    )
    version: str = Field(..., description="Version of the unit")
    web_applications: Optional[List[WebApplicationModel]] = Field(default=None, description="Used for cloud container labs")
    workout_duration_days: Optional[int] = Field(default=None, description='For asynchronous workout builds, specify to add an expiration timestamp for the workout.')


class WorkoutModel(BaseModel):
    active: bool = Field(default=False, description="Whether the workout is in available for interaction.")
    accessibility_features: Optional[bool] = Field(default=False, description="Whether or not accessibility features are enabled")
    assessment: Optional[AssessmentModel] = Field(default=None, description="Use Agoge to provide grading support")
    build_type: str = Field(..., description="Build type of the workout")
    action: Optional[int] = Field(default=None, description="Action identifier")
    creation_timestamp: Optional[float] = Field(default=None, description="Creation timestamp of the workout")
    expires: Optional[float] = Field(default=None, description="Timestamp of workout expiration")
    firewall_rules: Optional[List[FirewallRuleModel]] = Field(default=None, description="List of firewall rules")
    firewalls: Optional[List[FirewallModel]] = Field(default=None)
    lms_integration: Optional[LMSIntegrationModel] = Field(
        default=None,
        description="Use connected LMS to provide grading support and distribution functionality"
    )
    id: str = Field(..., description="ID of the workout")
    networks: Optional[List[NetworkModel]] = Field(default=None, description="List of networks")
    parent_build_type: str = Field(..., description="Parent build type")
    parent_id: str = Field(..., description="Parent ID")
    prev_state: Optional[int] = Field(default=None, description="Previous state identifier")
    proxy_connections: Optional[List[ProxyConnectionModel]] = Field(
        default=None,
        description="List of proxy connections"
    )
    servers: Optional[List[ServerModel]] = Field(default=None, description="List of servers")
    web_applications: Optional[List[WebApplicationModel]] = Field(
        default=None,
        description="Used for cloud container labs"
    )
    shutoff_timestamp: Optional[float] = Field(default=None, description="Shutoff timestamp of the running workout")
    state: Optional[int] = Field(default=None, description="Current state identifier")
    state_timestamp: Optional[str] = Field(default=None, description="Timestamp of the workout state")
    student_email: Optional[str] = Field(default=None, description="Student email associated with the workout")
    summary: Optional[AgogeWorkoutSummaryModel] = Field(None, description="Summary of the Agoge unit")
    team_name: Optional[str] = Field(
        default=None,
        description="Name of team associated with workout. Used in case of EscapeRoom workouts"
    )
    student_external_ip_addresses: Optional[List[str]] = Field(
        default=None,
        description='A list of external IP addresses used by student clients to access the lab. This '
                    'list is used to manage cloud firewall rules for interactive access.'
    )

    @field_validator('state_timestamp', mode='before')
    def validate_state_timestamp(cls, value):
        if value is not None:
            try:
                datetime.fromisoformat(value)
            except ValueError:
                raise ValueError("state_timestamp must be a valid ISO 8601 datetime string")
        return value

    class Config:
        from_attributes = True


class DiskInitializeParamsModel(BaseModel):
    sourceImage: str
    diskSizeGb: int
    type: str


class DiskModel(BaseModel):
    boot: bool
    autoDelete: bool
    initializeParams: DiskInitializeParamsModel


class AgogeImageModel(BaseModel):
    """
    Agoge generated compute images ready to be used by CatalogModel instances
    """
    name: str
    machine_type: str
    description: str
    tags: List[str]
    image: str
    os: str
    add_disk: str
    human_interaction: Union[List[HumanInteractionModel], HumanInteractionModel]
    status: Union[ImageStatus, int]
    labels: Optional[List[str]] = None
    # TODO: Temporarily make `disks` optional until it is safe to completely remove
    disks: Optional[List[DiskModel]] = None
    self_link: Optional[str] = None
    startup_script: Optional[str] = None
    dns_record: Optional[str] = None
    in_use_by: Optional[str] = None
    state: Optional[Union[ServerStates, int]] = Field(
        default=int(ServerStates.START.value),
        description="State of image server"
    )
    state_timestamp: Optional[str] = Field(default=None, description="Timestamp of image state")
    base_family: Optional[str] = None,
    image_exists: Optional[bool] = False


class SnapshotModel(BaseModel):
    name: str = Field(..., description="Name of snapshot.")
    creation_timestamp: int = Field(..., description="Timestamp of when snapshot was created.")
    source: str = Field(..., description="URL to snapshot resource.")
    type_: Optional[str] = Field(default=SnapshotTypes.AUTO.value, description="Type of snapshot")


class SnapshotsModel(BaseModel):
    server_id: str = Field(..., description="ID of snapshot server.")
    parent_build_id: Optional[str] = Field(
        None,
        description="Optional 10 character parent build ID (i.e. workout or unit id)."
    )
    server_type: int = Field(..., description="Type of server to create snapshot of.")
    expiration_date: Optional[int] = Field(
        default=None,
        description="Expiration date timestamp. Defaults to 2 weeks after parent build expiration."
    )
    snapshots: Optional[List[SnapshotModel]] = Field(
        None,
        description="List of existing snapshot resources"
    )


class AgogeInstructionsModel(BaseModel):
    uid: str
    instructions_type: Union[BuildConstants.InstructionsType, str]
    modified: float
    name: Optional[str] = None
    content: Optional[str] = None


class AgogeInstructionMinimal(BaseModel):
    uid: str
    instructions_type: Union[BuildConstants.InstructionsType, str]
    name: Optional[str] = None


class CVEModel(BaseModel):
    cve_id: str = Field(..., alias='cve_id', description='The unique identifier for the CVE')
    vendor: Optional[str] = Field(None, description='Vendor of the affected product')
    product: Optional[str] = Field(None, description='Affected product name')
    attack_vector: Optional[str] = Field(None, description='Attack vector type')
    complexity: Optional[str] = Field(None, description='Complexity of the attack')
    privileges_required: Optional[str] = Field(None, alias='priv', description='Privileges required to exploit')
    user_interaction: Optional[str] = Field(None, alias='ui', description='User interaction required')
    confidentiality: Optional[str] = Field(None, description='Impact on confidentiality')
    integrity: Optional[str] = Field(None, description='Impact on integrity')
    availability: Optional[str] = Field(None, description='Impact on availability')
    description: Optional[str] = Field(None, description='Description of the CVE')

    class Config:
        populate_by_name = True

class PuzzleQuestionModel(BaseModel):
    id: Optional[str] = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="ID of the question document"
    )
    title: str = Field(..., description="Question text shown to the player")
    answer: Optional[str] = Field(default=None, description="Canonical answer (if applicable)")
    answer_normalized: Optional[str] = Field(
        default=None,
        description="Optional pre-normalized answer for fuzzy comparison"
    )
    hint: Optional[str] = Field(default=None, description="Hint text shown to the player")
    fuzzy: Optional[bool] = Field(default=False, description="If True, compare answers loosely")

class PuzzleTestModel(BaseModel):
    id: Optional[str] = Field(
        default=lambda: str(uuid.uuid4()),
        description="ID of the test document"
    )
    title: str = Field(..., description="Test text shown to the player")
    questions: List[PuzzleQuestionModel] = Field(default=list, description="Ordered list of questions")
    created_at: Optional[float] = Field(default=None, description="UTC epoch seconds when created")
    join_code: Optional[str] = Field(default=None, description="Short unique join code for sharing or joining")
    sku: Optional[str] = Field(default=None, description="Lighting SKU (e.g., Govee)")
    device: Optional[str] = Field(default=None, description="Lighting device identifier")

UnitModel.model_rebuild()
AssessmentModel.model_rebuild()
LMSIntegrationModel.model_rebuild()
