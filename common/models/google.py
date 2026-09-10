# One-to-one Google-defined enumerations
from pydantic import BaseModel, Field, field_validator
from typing import Optional, Union, List


class DiskInitializeParamsModel(BaseModel):
    sourceImage: str
    diskSizeGb: int
    type: str


class DiskModel(BaseModel):
    boot: bool
    autoDelete: bool
    initializeParams: DiskInitializeParamsModel


class ComputeImageModel(BaseModel):
    """
    Google-defined model for public compute image objects
    """
    uuid: str
    name: str
    self_link: str
    disk_size: Union[int, str]
    os: str
    family: Optional[str]
    is_enabled: Optional[bool]
    creationTimestamp: Optional[str]
    project: Optional[str]
    global_id: Optional[str]
    description: Optional[str]
    architecture: Optional[str] = None

    @field_validator('global_id', mode='before')
    @classmethod
    def normalize_image_id(cls, value):
        # Compute IDs are uint64; Firestore integers are signed int64. Keep
        # identifiers as strings, including when reading older numeric records.
        if isinstance(value, int) and not isinstance(value, bool):
            return str(value)
        return value


class MachineTypeModel(BaseModel):
    id: str
    name: str
    description: str
    is_shared_core: bool
    memory_mb: int
    guest_cpus: int


class ClassroomUser(BaseModel):
    id: str = Field(..., description="Auto-generated ID of user.")
    email: str = Field(..., description="Email associated with user account.")


class ClassroomModel(BaseModel):
    id: str = Field(..., description='ID of Classroom')
    name: str = Field(..., description="Name of Classroom")
    owner: ClassroomUser = Field(..., description="User account responsible for Classroom management")
    teachers: List[str] = Field([], description="List of emails associated with teachers assigned to Classroom")
