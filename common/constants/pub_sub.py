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
        CTF = "CTF"

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
        # 18-20 were unused; a CTF reset is CTF_HOST_RESET because RESET_EXPIRATION already exists
        CTF_ARM_BOARD = 18   # plant every flag on one board, then aggregate
        CTF_PLANT = 19       # plant one board's flags on one server (or all its servers)
        CTF_HOST_RESET = 20  # reset one server of one board in a ResetMode
        NESTED_FINALIZE = 21  # shut a nested template server's guests down and snapshot them, then CHECK_IN

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
        CTF_ID = 'ctf_id'
        WORKOUT_ID = 'workout_id'
        RESET_MODE = 'reset_mode'
        # Nested guest slug for a CTF host reset that targets one guest, not the parent server
        GUEST = 'guest'
        # CTF messages reuse SERVER_NAME for the target server
