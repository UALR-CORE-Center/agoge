from enum import Enum


DATABASE_BASE_NAME = "agoge"
DATABASE_VERSION = "v1"
DATABASE_NAME = f"{DATABASE_BASE_NAME}-{DATABASE_VERSION}"
ADMIN_INFO_DOCUMENT = 'project'


class DatabaseTypes(Enum):
    firestore = 'firestore'


class DbOperationTypes(Enum):
    GET = 'get'
    SET = 'set'
    UPDATE = 'update'
    DELETE = 'delete'


class DbFilterTypes(Enum):
    WHERE = 0,
    OR = 1
    AND = 2


class DbOperators(Enum):
    IN = "in"
    NOT_IN = 'not-in'
    LESS_THAN = '<'
    LESS_THAN_EQ = '<='
    GREATER_THAN = '>'
    GREATER_THAN_EQ = '>='
    NOT_EQUAL = '!='
    EQUAL = '=='
    ARRAY_CONTAINS = 'array_contains'


class DbCollections(str, Enum):
    ADMIN_INFO = 'admin-info'
    CLASSROOM = 'classroom'
    FIXED_ARENA = 'fixed-arena'
    FIXED_ARENA_CLASS = 'fixed-arena-class'
    FIXED_ARENA_WORKSPACE = 'fixed-arena-workspace'
    CATALOG = 'catalog'
    UNIT = 'unit'
    WORKOUT = 'workout'
    WEBXR='web-xr'
    SERVER = 'agoge-server'
    SPECIFICATION_EDITS = 'specification-edits'
    SNAPSHOTS = 'snapshots'
    CYBERARENA_ATTACK = 'agoge-attack'
    CYBERARENA_ATTACK_SPEC = 'agoge-attack-spec'
    IOT_DEVICE = 'agoge-iot-device'
    PUZZLE = 'agoge-puzzle'
    USERS = 'agoge-user'
    NVD_DATA = 'nvd_data'
    IMAGE = 'image'
    GOOGLE_IMAGES = 'google-images'
    GOOGLE_IMAGE_UPDATES = 'google-image-updates'
    UPDATES = 'agoge-updates'
    INSTRUCTIONS = 'instructions'
    LLM_AGENT = 'llm_agent'
    RUBRIC = 'rubric'
    PROJECT_INFO = 'project-info'
