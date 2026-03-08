from enum import Enum


class PubSub:
    class Topics(str, Enum):
        AGOGE = 'agoge'
        CYBER_ARENA = "cyber-arena"
        AGENT_TELEMETRY = 'agency-telemetry'

    class Handlers(str, Enum):
        BUDGET = "BUDGET"
        BUILD = "BUILD"
        MAINTENANCE = "MAINTENANCE"
        CONTROL = "CONTROL"
        ADMIN = "ADMIN"
        IOT = "IOT"
        AGENCY = "AGENCY"

    class Actions(Enum):
        BUILD = 1
        START = 2
        DELETE = 3
        STOP = 4
        REBUILD = 5
        SNAPSHOT = 6
        RESTORE = 7
        NUKE = 8
        SYNC = 9
        CANCEL = 10
        UPDATE = 11
        RESET_EXPIRATION = 12
        EXTEND_RUNTIME = 13
        CHECK_IN = 16
        CHECK_OUT = 17

    class CourseObjects(Enum):
        """Course Lab objects"""
        DISK = 1
        DISPLAY_PROXY = 2
        FIREWALL_SERVER = 3
        IMAGE = 4
        INSTANCE = 5
        LAB_SERVER = 6
        PUBLIC_IMAGE = 7
        SNAPSHOT = 8
        TEMPLATE_SERVER = 9
        UNIT = 10
        WORKOUT = 11
        GOOGLE_IMAGES = 12
        NVD = 13
        LMS = 14

    class EventAttributes:
        HANDLER = 'handler'
        ACTION = 'action'
        BUILD_ID = 'build_id'
        CHILD_ID = 'child_id'
        CLAIMED_BY = 'claimed_by'
        COURSE_OBJECT = 'course_object'
        DURATION = 'duration'
        EXPIRES = 'expires'
        IMAGE_NAME = 'image_name'
        KEY_TYPE = 'key_type'
        NETWORK_PREFIX = 'network_prefix'
        SERVER_NAME = 'server_name'
        SERVER_TYPE = 'server_type'
        SNAPSHOT_LATEST = 'snapshot_latest'
        SNAPSHOT_NAME = 'snapshot_name'
        SNAPSHOT_TYPE = 'snapshot_type'
        USER = 'user'
