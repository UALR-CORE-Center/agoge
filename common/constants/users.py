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

    @classmethod
    def exists(cls, name):
        return name in cls.__members__

    @classmethod
    def has_value(cls, value):
        return value in cls._value2member_map_
