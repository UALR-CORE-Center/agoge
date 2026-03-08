from enum import Enum, StrEnum, auto


class ImageScopes(Enum):
    PROJECT = 'project'
    GLOBAL = 'global'


class SnapshotTypes(StrEnum):
    AUTO = auto()
    MANUAL = auto()


class WorkoutInternetFirewallAction(Enum):
    ADD_IP_ADDRESS = 0
    DISABLE_INTERNET_ACCESS = 1


class LLMAgentTypes(Enum):
    openai = 'openai'


class ValidTestProjects(Enum):
    AGOGE_PRODUCTION = 'agoge-ualr'
    AGOGE_TEST = 'agoge-test-427119'
