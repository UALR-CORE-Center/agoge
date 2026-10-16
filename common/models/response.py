from pydantic import BaseModel, Extra
from typing import Generic, List, Literal, Optional, TypeVar

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
    ArmStatus, LocationType, PlantStatus,
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


class CtfConfigResponse(BaseModel):
    ctf_enabled: bool


class CtfEventSummary(BaseModel):          # GET /ctf/ items
    id: str
    name: str
    unit_id: str
    state: int
    state_name: str
    board_count: int
    creation_timestamp: float
    starts_at: Optional[float]
    ends_at: Optional[float]


class CtfBoardStatus(BaseModel):
    workout_id: str
    team_name: str
    arm_status: ArmStatus
    arm_error: Optional[str]
    plant_failed_count: int
    plant_stale_count: int


class CtfStateResponse(BaseModel):         # GET /ctf/{id}/state/
    id: str
    state: int
    state_name: str
    state_timestamp: str
    starts_at: Optional[float]
    ends_at: Optional[float]
    paused_at: Optional[float]
    accumulated_pause_seconds: float
    scoreboard_frozen_at: Optional[float]
    public_scoreboard_enabled: bool
    budget_exceeded: bool
    boards: List[CtfBoardStatus]


class CtfFlagBoardStatus(BaseModel):
    workout_id: str
    team_name: str
    plant_status: PlantStatus
    planted_at: Optional[float]
    plant_error: Optional[str]
    solved: bool


class CtfFlagRow(BaseModel):               # GET /ctf/{id}/flags/ items
    flag_id: str
    server: str
    slot: int
    category: Optional[str]
    location_type: LocationType
    points: int
    decoy: bool
    boards: List[CtfFlagBoardStatus]


class CtfFlagRevealResponse(BaseModel):
    flag_id: str
    workout_id: str
    value: str


class CtfHostRow(BaseModel):               # GET /ctf/{id}/hosts/ items
    workout_id: str
    team_name: str
    server: str
    server_state: Optional[int]
    server_state_name: Optional[str]
    flag_count: int
    rebuild_allowed: bool                  # False when the server has a wireguard_endpoint_id


class CtfScoreboardRow(BaseModel):         # instructor
    rank: int
    workout_id: str
    team_name: str
    score: int
    solve_count: int
    decoy_count: int
    last_solve_at: Optional[float]


class CtfPublicScoreboardRow(BaseModel):   # student
    rank: int
    team_label: str                        # "Team <n>", n by board order
    score: int
    solve_count: int
    is_you: bool


class CtfChallenge(BaseModel):
    flag_id: str
    category: Optional[str]
    points: int
    solved: bool
    solved_at: Optional[float]
    hint_available: bool
    hint_cost: int
    hint: Optional[str]                    # only once taken


class CtfStudentBoardResponse(BaseModel):  # GET /ctf-board/{wid}/
    enrolled: bool
    ctf_id: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    rules_url: Optional[str] = None
    state_name: Optional[str] = None
    remaining_seconds: Optional[int] = None
    flag_format: Optional[str] = None      # e.g. "agoge{<challenge>_<20 hex characters>}"
    score: Optional[int] = None
    challenges: List[CtfChallenge] = []
    public_scoreboard_enabled: bool = False


class CtfSubmitResponse(BaseModel):
    # cross_submission is answered as 'incorrect'; rate_limited/closed become 429/409, never a verdict here.
    verdict: Literal['correct', 'incorrect', 'duplicate', 'decoy']
    correct: bool
    points_awarded: int                    # 0 for a decoy unless reveal_decoy_penalty
    message: str


class CtfHintResponse(BaseModel):
    flag_id: str
    hint: str
    hint_cost: int
    score: int
