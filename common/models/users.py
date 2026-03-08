from pydantic import BaseModel, Field, HttpUrl, field_validator
from typing import Any, Dict, Optional

from ..constants.users import LMSConnection, UserGroups


class APISettings(BaseModel):
    api: Optional[str] = None
    url: Optional[str] = None
    secret: Optional[str] = None

    @field_validator('url')
    @classmethod
    def validate_url(cls, url: Optional[str]) -> Optional[str]:
        if url is not None:
            try:
                HttpUrl(url=url)
            except ValueError:
                raise ValueError("Must contain a valid URL")
        return url


class UserPermissions(BaseModel):
    instructor: bool = Field(default=False, description="Whether a user is an instructor")
    admin: bool = Field(default=False, description="Whether a user is an admin")
    student: bool = Field(default=True, description="Whether a user is an student")


class AgogeUser(BaseModel):
    uid: str
    email: str
    name: Optional[str] = None
    permissions: Optional[Dict[str, bool]] = None
    settings: Dict[str, APISettings] = Field(
        default_factory=lambda: {
            lms.value: APISettings()
            for lms in LMSConnection
        }
    )
    timezone: str = "America/Chicago"

    @property
    def is_instructor(self) -> bool:
        if self.permissions:
            return self.permissions.get(UserGroups.INSTRUCTOR.value, False)
        return False

    @property
    def is_admin(self) -> bool:
        if self.permissions:
            return self.permissions.get(UserGroups.ADMIN.value, False)
        return False

    @property
    def is_authorized(self) -> bool:
        return self.is_instructor or self.is_admin

    def set_default_name_or_email(self, name: str = None) -> None:
        if name:
            self.name = name
        else:
            self.name = self.name or self.email

    def get_settings_overview(self) -> Dict[str, bool]:
        return {
            lms: bool(settings.api)
            for lms, settings in self.settings.items()
        }


class SafeAgogeUser(BaseModel):
    uid: str
    email: str
    name: Optional[str] = None
    permissions: Dict[str, bool]
    settings: Dict[str, bool]
    timezone: str = "America/Chicago"

    @classmethod
    def from_agoge_user(cls, user: AgogeUser):
        return cls(
            uid=user.uid,
            name=user.name,
            email=user.email,
            permissions=user.permissions,
            settings=user.get_settings_overview(),
            timezone=user.timezone
        )

    @classmethod
    def from_dict(cls, user: Dict[str, Any]):
        settings = user.get("settings", {})
        cleaned_settings = {
            k: bool(v.get('api'))
            for k, v in settings.items()
        }
        email = user.get('email')
        return cls(
            uid=user.get("uid"),
            name=user.get("name", email),
            email=email,
            permissions=user.get("permissions", {}),
            settings=cleaned_settings,
            timezone=user.get('timezone')
        )


class AnonymousAppUser(AgogeUser):
    def __init__(self):
        super().__init__(
            uid=None,
            email=None,
            name='Anonymous User',
            permissions={},
            settings=None
        )
        self.set_default_name_or_email()

    @property
    def is_authenticated(self) -> bool:
        return False

    @property
    def is_anonymous(self) -> bool:
        return True
