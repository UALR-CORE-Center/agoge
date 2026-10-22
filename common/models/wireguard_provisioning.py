"""Validated, credential-free contracts for enrolled WireGuard kits and leases."""
import base64
import ipaddress
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class WireGuardKitCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str = Field(pattern=r'^[a-z][a-z0-9-]{0,39}$')
    device_id: str = Field(min_length=1, max_length=128)
    equipment_subnet: str
    peer_public_key: str
    authorized_instructors: list[str] = Field(min_length=1, max_length=100)

    @field_validator('device_id')
    @classmethod
    def clean_device_id(cls, value):
        if value != value.strip() or any(ord(c) < 32 for c in value):
            raise ValueError('device_id must be a nonempty printable identifier')
        return value

    @field_validator('equipment_subnet')
    @classmethod
    def subnet(cls, value):
        network = ipaddress.ip_network(value, strict=True)
        private_ranges = [ipaddress.ip_network(value) for value in ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16')]
        if network.version != 4 or not any(network.subnet_of(private) for private in private_ranges):
            raise ValueError('equipment_subnet must be an RFC1918 private IPv4 network')
        return str(network)

    @field_validator('peer_public_key')
    @classmethod
    def public_key(cls, value):
        try:
            decoded = base64.b64decode(value, validate=True)
        except Exception as error:
            raise ValueError('peer_public_key must be a WireGuard public key') from error
        if len(decoded) != 32 or not any(decoded):
            raise ValueError('peer_public_key must be a nonzero 32-byte WireGuard public key')
        return base64.b64encode(decoded).decode('ascii')

    @field_validator('authorized_instructors')
    @classmethod
    def instructors(cls, values):
        normalized = sorted({v.strip().lower() for v in values})
        if any(not v or '@' not in v or len(v) > 254 for v in normalized):
            raise ValueError('authorized_instructors must contain email addresses')
        return normalized


class WireGuardKitModel(WireGuardKitCreate):
    enabled: bool = True
    assigned_unit_id: str | None = None


class WireGuardLeaseModel(BaseModel):
    """Only public keys and non-secret runtime information may enter Unit records."""
    model_config = ConfigDict(extra='ignore')
    unit_id: str
    kit_id: str
    device_id: str
    endpoint_id: str
    equipment_subnet: str
    student_subnets: list[str]
    gateway_public_key: str
    peer_public_key: str
    gateway_address: str = '10.254.254.1/30'
    peer_address: str = '10.254.254.2/32'
    secret_version_name: str
    expires: float
    status: Literal['reserved', 'released'] = 'reserved'
    boot_id: str | None = None
    service_ready: bool = False
    tunnel_ready: bool = False
    health_timestamp: float | None = None
    latest_handshake: int = 0
    health_error: str | None = None

    def is_ready(self, now: float, max_age: int = 120) -> bool:
        return bool(self.status != 'released' and self.service_ready and self.health_timestamp
                    and 0 <= now - self.health_timestamp <= max_age and self.expires > now)


class WireGuardHealthReport(BaseModel):
    model_config = ConfigDict(extra='forbid')
    boot_id: str = Field(min_length=16, max_length=128)
    service_ready: bool
    tunnel_ready: bool = False
    latest_handshake: int = Field(default=0, ge=0)
    # Errors are codes, never arbitrary shell output/configuration/credentials.
    error: str | None = Field(default=None, max_length=80, pattern=r'^[a-zA-Z0-9_. -]*$')
