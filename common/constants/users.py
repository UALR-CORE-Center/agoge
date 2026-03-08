from enum import Enum


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


class LMSConnection(Enum):
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
