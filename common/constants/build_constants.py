from enum import Enum


class BuildConstants:
    class BuildType(str, Enum):
        IMAGE = 'image'
        AGENT_SERVER = 'agent'
        FIXED_ARENA = "fixed_arena"
        FIXED_ARENA_CLASS = "fixed_arena_class"
        FIXED_ARENA_WORKSPACE = "fixed_arena_workspace"
        UNIT = "unit"
        WORKOUT = "workout"
        FIXED_ARENA_WEAKNESS = 'fixed_arena_weakness'
        FIXED_ARENA_ATTACK = 'fixed_arena_attack'
        ESCAPE_ROOM = 'escape_room'

    class UnitType(str, Enum):
        SOLO = 'solo'
        COMMUNITY = 'community'

    class InstructionsType(str, Enum):
        TEACHER = 'teacher'
        STUDENT = 'student'

    class Frameworks(Enum):
        NICE = "NICE"

    class TeachingConcepts(Enum):
        ETHICS = 'Ethics'
        ESTABLISHING_TRUST = 'Establishing Trust'
        UBIQUITOUS_COMPUTING = 'Ubiquitous Computing'
        DATA_SECURITY = 'Data Security'
        SYSTEM_SECURITY = 'System Security'
        ADVERSARIAL_THINKING = 'Adversarial Thinking'
        RISK = 'Risk'
        IMPLICATIONS = 'Implications'
        COURSES = 'Courses'
        TRAINING = 'Training'
        PREREQUISITES = 'Prerequisites'
        EVALUATION = 'Evaluation'
        EXERCISE = 'Exercise'

        @staticmethod
        def map(tags):
            if tags:
                concept_map = {concept.name.lower(): concept.value for concept in BuildConstants.TeachingConcepts}
                return [{'id': tag.lower(), 'name': concept_map[tag.lower()]} for tag in tags]
            return []

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
            AGENT_MACHINE = '10.1.0.210'

        SUBNET_NAME = 'default'
        GATEWAY_NETWORK_NAME = 'gateway'
        GATEWAY_NETWORK_CONFIG = {
            'name': GATEWAY_NETWORK_NAME,
            'subnets': [
                {
                    'name': SUBNET_NAME,
                    'ip_subnet': '10.1.0.0/24'
                }
            ]
        }
        WORKOUT_EXTERNAL_NAME = 'external'
        WORKOUT_SUBNET_IP_SUBNET = '10.1.1.0/24'
        WORKOUT_DEFAULT_NETWORK_CONFIG = {
            'name': WORKOUT_EXTERNAL_NAME,
            'subnets': [
                {
                    'name': SUBNET_NAME,
                    'ip_subnet': WORKOUT_SUBNET_IP_SUBNET
                }
            ]
        }

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
        N1_STANDARD_1 = 'n1-standard-1'
        N1_STANDARD_2 = 'n1-standard-2'
        N1_STANDARD_4 = 'n1-standard-4'
        N2_STANDARD_2 = 'n2-standard-2'
        N2_STANDARD_4 = 'n2-standard-4'

        ALL = [
            E2_MICRO, E2_MEDIUM,
            E2_STANDARD_2, E2_STANDARD_4,
            E2_STANDARD_8, N1_STANDARD_1,
            N1_STANDARD_2, N1_STANDARD_4,
            N2_STANDARD_2, N2_STANDARD_4
        ]

    class MachineImages:
        GUACAMOLE_SSL = "image-guac-{project}"
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

    class AgogeObjects(Enum):
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

    class SpecSource(str, Enum):
        FILE = 'file'
        FORM = 'form'

    class SharedResourceProjects:
        MAIN_SHARED_RESOURCE_PROJECT = "agoge-shared-resources"
