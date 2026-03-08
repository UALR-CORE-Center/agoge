from enum import Enum, auto, StrEnum


class ImageProjects:
    COS = 'cos-cloud'
    DEBIAN = 'debian-cloud'
    FEDORA = 'fedora-coreos-cloud'
    RHEL = 'rhel-cloud'
    ROCKY_LINUX = 'rocky-linux-cloud'
    SQL_SERVER = 'windows-sql-cloud'
    SUSE_LINUX = 'suse-cloud'
    UBUNTU = 'ubuntu-os-cloud'
    UBUNTU_PRO = 'ubuntu-os-pro-cloud'
    WINDOWS = 'windows-cloud'

    ALL = [
        COS, DEBIAN, FEDORA, RHEL,
        ROCKY_LINUX, SQL_SERVER, SUSE_LINUX,
        UBUNTU, UBUNTU_PRO, WINDOWS
    ]


class ResourceType(Enum):
    """Enumerates resource types used in Compute operations."""
    INSTANCE = auto()
    IMAGE = auto()
    SNAPSHOT = auto()
    DISK = auto()
    MACHINE_TYPE = auto()
    FIREWALLS = auto()
    NETWORKS = auto()
    SUBNETWORKS = auto()


class ImageSource(Enum):
    """Enumerates the types of compute objects to use as
    a source for a new compute image"""
    IMAGE = auto()
    SNAPSHOT = auto()
    DISK = auto()
    RAW_DISK = auto()


class SnapshotSource(Enum):
    """Enumerates the types of compute objects to use as
    a source for a new compute image"""
    IMAGE = auto()
    SNAPSHOT = auto()
    DISK = auto()


class AttachedDiskMode(Enum):
    READ_WRITE = 'READ_WRITE'
    READ_ONLY = 'READ_ONLY'


class RequestType(Enum):
    GET_DISK_REQUEST = auto()
    INSERT_DISK_REQUEST = auto()
    DELETE_DISK_REQUEST = auto()
    RESIZE_DISK_REQUEST = auto()
    CREATE_SNAPSHOT_DISK_REQUEST = auto()
    GET_INSTANCE_REQUEST = auto()
    INSERT_INSTANCE_REQUEST = auto()
    DELETE_INSTANCE_REQUEST = auto()
    UPDATE_INSTANCE_REQUEST = auto()


class ClientType(Enum):
    DISCOVERY = 'discovery'
    FIREWALLS = 'firewalls'
    IMAGE = 'image'
    IMAGE_FAMILY = 'image-family'
    SNAPSHOT = 'snapshot'
    DISK = 'disk'
    INSTANCE = 'instance'
    MACHINE_TYPES_CLIENT = 'machine-types-client'
    NETWORKS = 'networks'
    SUBNETWORKS = 'subnetworks'
    OPERATIONS = 'operations'


class OperationType(Enum):
    ZONE = 0
    REGION = 1
    GLOBAL = 2

class OperationStatus(StrEnum):
    PENDING = 'PENDING'
    RUNNING = 'RUNNING'
    DONE = 'DONE'


class FirewallDirection(StrEnum):
    INGRESS = 'INGRESS'
    EGRESS = 'EGRESS'


class IpProtocol(StrEnum):
    TCP = auto()
    UDP = auto()
    ICMP = auto()


class AddressTypes:
    IPv4 = 'ipv4'
    IPv6 = 'ipv6'


class FirewallRuleAction(Enum):
    ALLOW = auto()
    DENY = auto()
