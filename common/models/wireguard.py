from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


WireGuardEndpointStatus = Literal[
    "reserved",
    "active",
    "releasing",
    "released",
    "error",
]


class WireGuardEndpointModel(BaseModel):
    """Instructor-visible information for a Unit's WireGuard gateway."""

    id: str = Field(..., pattern=r"^[1-9][0-9]{4}$")
    hostname: str
    server_name: str
    port: int = Field(default=51820, ge=1, le=65535)
    external_ip_name: Optional[str] = None
    public_ip: Optional[str] = None
    status: WireGuardEndpointStatus = "reserved"

    @field_validator("hostname")
    @classmethod
    def validate_hostname(cls, value: str) -> str:
        """Normalize the hostname as an absolute Cloud DNS name."""
        hostname = value.strip().lower().rstrip(".")
        if not hostname or len(hostname) > 253:
            raise ValueError("hostname must be a valid DNS name")

        labels = hostname.split(".")
        for label in labels:
            if (
                not label
                or len(label) > 63
                or not label[0].isalnum()
                or not label[-1].isalnum()
                or any(not (character.isalnum() or character == "-") for character in label)
            ):
                raise ValueError("hostname must be a valid DNS name")
        return f"{hostname}."


class WireGuardEndpointRecordModel(WireGuardEndpointModel):
    """Private registry record. Never return this model from the public API."""

    unit_id: str
    created_timestamp: float
    updated_timestamp: float
    released_timestamp: Optional[float] = None
    expires: Optional[float] = None

    def public_endpoint(self) -> WireGuardEndpointModel:
        return WireGuardEndpointModel(
            **self.model_dump(
                include={
                    "id",
                    "hostname",
                    "server_name",
                    "port",
                    "external_ip_name",
                    "public_ip",
                    "status",
                }
            )
        )


class WireGuardPublicEndpointModel(BaseModel):
    """The deliberately small response returned without authentication."""

    id: str = Field(..., pattern=r"^[1-9][0-9]{4}$")
    hostname: str
    port: int = Field(default=51820, ge=1, le=65535)
    status: WireGuardEndpointStatus

    @classmethod
    def from_record(cls, record: WireGuardEndpointRecordModel):
        return cls(
            id=record.id,
            hostname=record.hostname,
            port=record.port,
            status=record.status,
        )
