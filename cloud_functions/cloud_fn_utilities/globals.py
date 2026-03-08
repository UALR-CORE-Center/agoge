from enum import Enum
from datetime import datetime, timezone, timedelta


class UserGroups(Enum):
    INSTRUCTOR = "instructor"
    ADMIN = "admin"
    STUDENT = "student"
    PENDING = "pending"
    ALL_GROUPS = [INSTRUCTOR, ADMIN, STUDENT]
    BASE = {
        f'{ADMIN}': False,
        f'{STUDENT}': True,
        f'{INSTRUCTOR}': False
    }


class LMS(Enum):
    CANVAS = 'canvas'
    ALL = [CANVAS]

    @classmethod
    def _value_to_member_map(cls):
        _value2member_map_ = {v.value: v for v in cls.__members__.values()}

    @classmethod
    def exists(cls, name):
        return name in cls.__members__

    @classmethod
    def has_value(cls, value):
        if not hasattr(cls, '_value2member_map_'):
            cls._value_to_member_map()
        return value in cls._value2member_map_


class DatastoreKeyTypes(str, Enum):
    ADMIN_INFO = 'admin-info'
    CLASSROOM = 'classroom'
    CATALOG = 'catalog'
    UNIT = 'unit'
    WORKOUT = 'workout'
    SERVER = 'agoge-server'
    SPECIFICATION_EDITS = 'specification-edits'
    SNAPSHOTS = 'snapshots'  # TODO: I don't think this is used anywhere
    CYBERARENA_ATTACK = 'agoge-attack'
    CYBERARENA_ATTACK_SPEC = 'agoge-attack-spec'
    IOT_DEVICE = 'agoge-iot-device'
    USERS = 'agoge-user'
    NVD_DATA = 'nvd_data'
    IMAGE = 'image'
    SNAPSHOT = 'snapshot'
    INSTRUCTIONS = 'instructions'
    GOOGLE_IMAGES = 'google-images'
    GOOGLE_IMAGES_UPDATES = 'google-image-updates'


class BuildConstants:
    class BuildType(str, Enum):
        AGENT_SERVER = 'agent'
        FIXED_ARENA = "fixed_arena"
        FIXED_ARENA_CLASS = "fixed_arena_class"
        FIXED_ARENA_WORKSPACE = "fixed_arena_workspace"
        UNIT = "unit"
        WORKOUT = "workout"
        IMAGE = 'image'
        FIXED_ARENA_WEAKNESS = 'fixed_arena_weakness'
        FIXED_ARENA_ATTACK = 'fixed_arena_attack'
        ESCAPE_ROOM = 'escape_room'

    class UnitType(str, Enum):
        SOLO = 'solo'
        COMMUNITY = 'community'

    class Frameworks(Enum):
        NICE = "NICE"

    class Guacamole:
        class Protocols(str, Enum):
            RDP = "rdp"
            VNC = "vnc"
            SSH = "ssh"

        class SecurityModes(str, Enum):
            RDP = 'rdp'
            NLA = 'nla'
            ANY = 'any'
            TLS = 'tls'

    class Firewalls:
        class FirewallTypes(str, Enum):
            FORTINET = "fortinet"
            VYOS = "vyos"
            VPC = 'vpc'

        class TransportProtocols(str, Enum):
            TCP = "tcp"
            UDP = "udp"
            ICMP = "icmp"

        class TrafficDirection(str, Enum):
            INGRESS = 'INGRESS'
            EGRESS = 'EGRESS'

        class Action(str, Enum):
            ALLOW = 'allow'
            DENY = 'deny'

    class Networks:
        class Reservations:
            DISPLAY_SERVER = '10.1.0.3'
            WORKSPACE_PROXY_SERVER = '10.1.0.4'
            WORKOUT_PROXY_SERVER = "10.1.1.3"
            PACKET_MIRROR_DESTINATION = '10.1.1.4'
            WORKSPACE_FIREWALL_SERVER = "10.1.0.100"
            FIXED_ARENA_WORKOUT_SERVER_RANGE = ('10.1.0.10', '10.1.0.200')
        GATEWAY_NETWORK_NAME = 'gateway'
        GATEWAY_NETWORK_CONFIG = {
            'name': GATEWAY_NETWORK_NAME,
            'subnets': [
                {
                    'name': 'default',
                    'ip_subnet': '10.1.0.0/24'
                }
            ]
        }
        WORKOUT_EXTERNAL_NAME = 'external'

    class MachineTypes(Enum):
        VERY_SMALL = 0
        SMALL = 1
        MEDIUM = 2
        LARGE = 3
        VERY_LARGE = 4
        ROUTER = 5

    class GoogleMachineTypes(Enum):
        E2_MICRO = 'e2-micro'
        E2_MEDIUM = 'e2-medium'
        E2_STANDARD_2 = 'e2-standard-2'
        E2_STANDARD_4 = 'e2-standard-4'
        E2_STANDARD_8 = 'e2-standard-8'

    class MachineImages:
        GUACAMOLE_SSL = "image-cyberarena-labentry-ssl"
        GUACAMOLE = "image-cyberarena-labentry"  ## Old image
        FORTIMANAGER = "image-fortimanager"
        AGENT = 'image-cybergym-kali'

    class ServerBuildType:
        MACHINE_IMAGE = "machine-image"

    class ServerBuildSource(Enum):
        UNIT = 1
        IMAGE = 2

    class Servers:
        FIXED_ARENA_WORKSPACE_PROXY = "display-workspace-server"

    class EscapeRoomEntryTypes(str, Enum):
        SERVER = 'server'
        WEB_APPLICATION = 'web_application'

    class CyberArenaObjects(Enum):
        FIXED_ARENA = 1
        FIXED_ARENA_CLASS = 2
        FIXED_ARENA_WORKSPACE = 3
        SERVER = 4
        CYBER_ARENA_AGENT = 5
        UNIT = 6
        WORKOUT = 7
        SNAPSHOT = 8

    class Reports:
        ATTACK = 2

    class ScriptOperatingSystems:
        WINDOWS = 'windows'
        LINUX = 'linux'

    class QuestionTypes(str, Enum):
        AUTO = "auto"
        INPUT = "input"
        UPLOAD = "upload"
        PERCENTAGE = 'percentage'

    class LMS(str, Enum):
        CANVAS = 'canvas'
        BLACKBOARD = 'blackboard'
        GOOGLE_CLASSROOM = 'classroom'

    class LMSCourseWork(str, Enum):
        QUIZ = 'quiz'
        ASSIGNMENT = 'assignment'


class UnitStates(Enum):
    START = 0
    BUILDING_ASSESSMENT = 1
    BUILDING_NETWORKS = 2
    COMPLETED_NETWORKS = 3
    BUILDING_SERVERS = 4
    COMPLETED_SERVERS = 5
    BUILDING_FIREWALL = 6
    COMPLETED_FIREWALL = 7
    BUILDING_ROUTES = 8
    COMPLETED_ROUTES = 9
    BUILDING_FIREWALL_RULES = 10
    COMPLETED_FIREWALL_RULES = 11
    BUILDING_STUDENT_ENTRY = 12
    COMPLETED_STUDENT_ENTRY = 13
    GUACAMOLE_SERVER_LOAD_TIMEOUT = 28
    RUNNING = 50
    STOPPING = 51
    STARTING = 52
    READY = 53
    EXPIRED = 60
    MISFIT = 61
    BROKEN = 62
    DELETING_SERVERS = 70
    COMPLETED_DELETING_SERVERS = 71
    DELETED = 72


class WorkoutStates(Enum):
    NOT_BUILT = -1
    START = 0
    BUILDING_ASSESSMENT = 1
    BUILDING_NETWORKS = 2
    COMPLETED_NETWORKS = 3
    BUILDING_SERVERS = 4
    COMPLETED_SERVERS = 5
    BUILDING_FIREWALL = 6
    COMPLETED_FIREWALL = 7
    BUILDING_ROUTES = 8
    COMPLETED_ROUTES = 9
    BUILDING_FIREWALL_RULES = 10
    COMPLETED_FIREWALL_RULES = 11
    BUILDING_STUDENT_ENTRY = 12
    COMPLETED_STUDENT_ENTRY = 13
    GUACAMOLE_SERVER_LOAD_TIMEOUT = 28
    RUNNING = 50
    STOPPING = 51
    STARTING = 52
    READY = 53
    EXPIRED = 60
    MISFIT = 61
    BROKEN = 62
    DELETING_SERVERS = 70
    COMPLETED_DELETING_SERVERS = 71
    DELETED = 72


class ServerStates(Enum):
    START = 0
    BUILDING = 1
    READY = 2
    STARTING = 3
    RUNNING = 4
    STOPPING = 5
    STOPPED = 6
    EXPIRED = 7
    MISFIT = 8
    RESETTING = 9
    RELOADING = 10
    BROKEN = 11
    DELETING = 12
    DELETED = 13


class ImageStates(Enum):
    CHECKED_IN = 0
    CHECKED_OUT = 1


class LoggerNames:
    MAIN_APP = 'main_app.api'
    CLOUD_FN = 'cloud_functions'


class Buckets:
    BUILD_SPEC_BUCKET_SUFFIX = "build-specs"

    class Folders(str, Enum):
        SPECS = "specs/"
        ATTACKS = 'attacks/'
        STARTUP_SCRIPTS = "startup_scripts/"
        TEACHER_FOLDER = "teacher_instructions/"
        STUDENT_FOLDER = "student_instructions/"


class PubSub:
    class Topics(str, Enum):
        AGOGE = "agoge"
        AGENT_TELEMETRY = 'agency-telemetry'
        CYBER_ARENA = "cyber-arena"

    class Handlers(str, Enum):
        BUDGET = "BUDGET"
        BUILD = "BUILD"
        MAINTENANCE = "MAINTENANCE"
        CONTROL = "CONTROL"
        ADMIN = "ADMIN"
        IOT = "IOT"
        AGENCY = "AGENCY"

    class BuildActions(Enum):
        WORKOUT = 0
        UNIT = 1
        FIXED_ARENA = 2
        FIXED_ARENA_CLASS = 3
        SERVER = 4
        DISPLAY_PROXY = 5
        FIREWALL_SERVER = 6
        FIXED_ARENA_WORKSPACE_PROXY = 7
        CYBER_ARENA_AGENT = 9
        CYBER_ARENA_ATTACK = 10
        CYBER_ARENA_WEAKNESS = 11

    class Actions(Enum):
        BUILD = 1
        START = 2
        DELETE = 3
        STOP = 4
        REBUILD = 5
        SNAPSHOT = 6
        RESTORE = 7
        NUKE = 8
        START_ESCAPE_ROOM_TIMER = 9
        EXTEND_RUNTIME = 10
        RESET_EXPIRATION = 11
        IMAGE_CREATE = 12
        IMAGE_SYNC = 13
        IMAGE_SERVER_CREATE = 14
        IMAGE_DELETE = 15
        IMAGE_CHECK_IN = 16
        IMAGE_CHECK_OUT = 17
        DELETE_SNAPSHOT = 18
        INSTANCE_DELETE = 19
        IMAGE_CANCEL_CHANGES = 20
        GLOBAL_IMAGE_SYNC = 21

    class CyberArenaObjects(Enum):
        FIXED_ARENA = 1
        FIXED_ARENA_CLASS = 2
        FIXED_ARENA_WORKSPACE = 3
        SERVER = 4
        AGENT_MACHINE = 5
        UNIT = 6
        WORKOUT = 7
        SNAPSHOT = 8


def get_current_timestamp_utc(add_seconds: int = 0) -> float:
    # Ensure add_seconds is an integer; if not, default to 0
    try:
        add_seconds = add_seconds if isinstance(add_seconds, int) else int(add_seconds)
    except ValueError:
        add_seconds = 0
    return (datetime.now(timezone.utc) + timedelta(seconds=add_seconds)).timestamp()
