"""Validated, credential-free remote peer contracts with legacy kit compatibility."""
import base64
import ipaddress
from typing import Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, StrictBool, computed_field, field_validator, model_validator


class WireGuardKitCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str = Field(pattern=r'^[a-z][a-z0-9-]{0,39}$')
    device_id: str = Field(min_length=1, max_length=128)
    equipment_subnet: str
    peer_public_key: str
    authorized_instructors: list[str] = Field(min_length=1, max_length=100)
    name: str = Field(default='', max_length=128)
    description: str = Field(default='', max_length=2048)

    @field_validator('name', 'description')
    @classmethod
    def readable_text(cls, value):
        if any(ord(char) < 32 and char not in '\n\t' for char in value):
            raise ValueError('Use printable text')
        return value.strip()

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


class WireGuardRemotePeerCreate(WireGuardKitCreate):
    """Canonical API language; legacy equipment_subnet remains the storage key."""
    equipment_subnet: str = Field(
        validation_alias=AliasChoices('remote_network_cidr', 'equipment_subnet'),
        serialization_alias='remote_network_cidr',
        description='Private IPv4 LAN reachable through the remote WireGuard peer',
    )

    @model_validator(mode='before')
    @classmethod
    def reject_conflicting_network_aliases(cls, values):
        if not isinstance(values, dict) or 'remote_network_cidr' not in values or 'equipment_subnet' not in values:
            return values
        if values['remote_network_cidr'] != values['equipment_subnet']:
            raise ValueError('remote_network_cidr conflicts with legacy equipment_subnet')
        return {key: value for key, value in values.items() if key != 'equipment_subnet'}

    @property
    def remote_network_cidr(self) -> str:
        return self.equipment_subnet


class WireGuardRemotePeerModel(WireGuardRemotePeerCreate):
    enabled: bool = True
    assigned_unit_id: str | None = None


class WireGuardRemotePeerUpdate(BaseModel):
    """Administrator edits keep enrollment identity and token unchanged."""
    model_config = ConfigDict(extra='forbid')
    name: str | None = Field(default=None, max_length=128)
    description: str | None = Field(default=None, max_length=2048)
    remote_network_cidr: str | None = None
    peer_public_key: str | None = None
    authorized_instructors: list[str] | None = Field(default=None, min_length=1, max_length=100)
    enabled: StrictBool | None = None

    @model_validator(mode='after')
    def no_null_settings(self):
        if not self.model_fields_set or any(getattr(self, key) is None for key in self.model_fields_set):
            raise ValueError('Supply at least one non-null setting')
        return self


class WireGuardLabSettingsUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    remote_peer_id: str = Field(pattern=r'^[a-z][a-z0-9-]{0,39}$')
    remote_network_cidr: str

    @field_validator('remote_network_cidr')
    @classmethod
    def subnet(cls, value):
        return WireGuardKitCreate.subnet(value)


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
    configuration_revision: str | None = None
    configuration_pending: bool = False
    previous_secret_version_name: str | None = None
    secret_history: list[str] = Field(default_factory=list)

    @computed_field
    @property
    def remote_peer_id(self) -> str:
        return self.kit_id

    @computed_field
    @property
    def remote_network_cidr(self) -> str:
        return self.equipment_subnet

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
