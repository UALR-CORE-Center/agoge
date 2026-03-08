from pydantic import BaseModel, Extra
from typing import Generic, List, Optional, TypeVar

from .users import SafeAgogeUser
from .agoge import (
    UnitModel,
    AgogeImageModel,
    WorkoutModel,
    CatalogModel,
    NicModel,
    HumanInteractionModel,
    AgogeInstructionsModel,
    AgogeInstructionMinimal,
    CatalogEditModel, SnapshotModel,
)
from .google import ComputeImageModel, MachineTypeModel
T = TypeVar('T')


class AgogeResponse(BaseModel, Generic[T]):
    redirect: Optional[str] = None
    data: Optional[T] = None


class AgogeIDResponse(BaseModel):
    build_id: str
    exists: Optional[bool] = True


class AgogeInstructionsResponse(BaseModel):
    items: List[AgogeInstructionsModel]

class AgogeInstructionsMinimalResponse(BaseModel):
    items: List[AgogeInstructionMinimal]


class AgogeInstructionsImageResponse(BaseModel):
    image_url: str


class ServerResponse(BaseModel):
    build_id: Optional[str] = None
    parent_id: Optional[str] = None
    build_type: Optional[str] = None
    parent_build_type: Optional[str] = None
    name: str
    nics: List[NicModel]
    hostname: Optional[str] = None
    dns_hostname: Optional[str] = None
    human_interaction: Optional[List[HumanInteractionModel]] = None

    class Config:
        extra = Extra.ignore


class SnapshotResponse(BaseModel):
    server_id: str
    name: Optional[str] = None
    parent_build_id: Optional[str] = None
    expiration_date: Optional[int] = None
    snapshots: Optional[List[SnapshotModel]] = []


class SnapshotListResponse(BaseModel):
    items: List[SnapshotResponse]


class ComputeImageListResponse(BaseModel):
    custom: List[AgogeImageModel]
    project: List[ComputeImageModel]


class GoogleImageListResponse(BaseModel):
    items: List[ComputeImageModel]


class ImageListResponse(BaseModel):
    items: List[AgogeImageModel]


class MachineTypeListResponse(BaseModel):
    items: List[MachineTypeModel]


class CatalogEditListResponse(BaseModel):
    items: List[CatalogEditModel]


class LabSpecListResponse(BaseModel):
    items: List[CatalogModel]


class StartupScriptListResponse(BaseModel):
    items: List[str]


class WorkoutFullResponse(BaseModel):
    workout: WorkoutModel
    servers: Optional[List[ServerResponse]]


class WorkoutListResponse(BaseModel):
    items: List[WorkoutModel]


class WorkoutStateResponse(BaseModel):
    build_id: str
    state: str | int


class ActiveExpiredUnitListResponse(BaseModel):
    active: List[UnitModel]
    expired: List[UnitModel]


class UnitListResponse(BaseModel):
    items: List[UnitModel]
    total: int


class UnitFullResponse(BaseModel):
    unit: UnitModel
    workouts: List[WorkoutModel]
    roster: int
    rubric_support: bool


class UnitStateResponse(BaseModel):
    exists: bool
    items: List[WorkoutStateResponse]
    total: int


class UnitRosterResponse(BaseModel):
    roster: int


class UsersListResponse(BaseModel):
    items: List[SafeAgogeUser]


class EscapeRoomStateResponse(BaseModel):
    id: str
    state: str | int


class EscapeRoomUnitStateResponse(BaseModel):
    items: List[EscapeRoomStateResponse]


class EscapeRoomUnitResponse(BaseModel):
    items: List[EscapeRoomStateResponse]


class EscapeRoomUnitTeamsResponse(BaseModel):
    id: str
    name: str


class EscapeRoomUnitTeamsListResponse(BaseModel):
    items: List[EscapeRoomUnitTeamsResponse]


class EscapeRoomQuestionResponse(BaseModel):
    question_id: Optional[str] = None
    correct: bool
    escape_room: UnitModel


class EscapeRoomQuestionListResponse(BaseModel):
    items: List[EscapeRoomQuestionResponse]
