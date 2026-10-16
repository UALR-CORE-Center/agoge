from typing import Any

from fastapi import APIRouter, Body, Depends, Path, Request

from common.models.agoge import CtfSubmitRequest
from common.models.response import (
    AgogeResponse,
    CtfHintResponse,
    CtfStudentBoardResponse,
    CtfSubmitResponse,
)
from common.utilities.gcp.cloud_logger import Logger, LoggerNames

from core.ctf.config import is_ctf_enabled
from core.ctf.scoring import CtfScoring
from dependencies import ctf_enabled_required, get_cloud_env
from routers.ctf import _parse, workout_id_path
from utilities.http_errors import to_http_exception

# Student routes. Deliberately unauthenticated, like GET /workouts/{build_id}/: knowing the ten-letter
# workout id is the capability (PRD "On the unauthenticated student routes"). Do not add auth here.
ctf_board_router = APIRouter(prefix="/ctf-board")
enabled = [Depends(ctf_enabled_required)]
logger = Logger(LoggerNames.API, class_name='CtfBoardRouter')

FLAG_ID_PATTERN = r'^[a-z0-9][a-z0-9-]{1,31}$'  # CtfFlagSpecModel.id


def flag_id_path(flag_id: str = Path(..., pattern=FLAG_ID_PATTERN)) -> str:
    return flag_id


def _fail(e: Exception, route: str, workout_id: str, **log_args):
    # Type name only: a submit failure's message must never carry the submitted value into the log.
    logger.warning(f"CtfBoardRouter:{workout_id} - {route} failed: {type(e).__name__}", **log_args)
    return to_http_exception(e)


@ctf_board_router.get("/{workout_id}/")
def get_board(
    workout_id: str = Depends(workout_id_path),
    env_dict: dict = Depends(get_cloud_env),
) -> AgogeResponse[CtfStudentBoardResponse]:
    # Not gated by ctf_enabled_required: the student page polls this on every workout, so a disabled
    # deployment answers `enrolled: false` rather than 404 (SC-19), and touches no CTF collection.
    if not is_ctf_enabled():
        return AgogeResponse(data=CtfStudentBoardResponse(enrolled=False))
    try:
        return AgogeResponse(data=CtfScoring(env_dict=env_dict).board(workout_id))
    except Exception as e:
        raise _fail(e, "get_board", workout_id) from e


@ctf_board_router.post("/{workout_id}/submit/", dependencies=enabled)
def submit_flag(
    request: Request,
    payload: Any = Body(default=None),
    workout_id: str = Depends(workout_id_path),
    env_dict: dict = Depends(get_cloud_env),
) -> AgogeResponse[CtfSubmitResponse]:
    try:
        submission = _parse(CtfSubmitRequest, payload)
        # ProxyHeadersMiddleware in main.py makes this the caller's address, not the load balancer's.
        origin_ip = request.client.host if request.client else None
        result = CtfScoring(env_dict=env_dict).submit(workout_id, submission.flag, origin_ip=origin_ip)
        return AgogeResponse(data=result)
    except Exception as e:
        raise _fail(e, "submit_flag", workout_id) from e


@ctf_board_router.post("/{workout_id}/hint/{flag_id}/", dependencies=enabled)
def take_hint(
    workout_id: str = Depends(workout_id_path),
    flag_id: str = Depends(flag_id_path),
    env_dict: dict = Depends(get_cloud_env),
) -> AgogeResponse[CtfHintResponse]:
    try:
        return AgogeResponse(data=CtfScoring(env_dict=env_dict).hint(workout_id, flag_id))
    except Exception as e:
        raise _fail(e, "take_hint", workout_id, flag_id=flag_id) from e


@ctf_board_router.get("/{workout_id}/scoreboard/", dependencies=enabled)
def get_public_scoreboard(
    workout_id: str = Depends(workout_id_path),
    env_dict: dict = Depends(get_cloud_env),
) -> AgogeResponse:
    try:
        return AgogeResponse(data={'items': CtfScoring(env_dict=env_dict).public_scoreboard(workout_id)})
    except Exception as e:
        raise _fail(e, "get_public_scoreboard", workout_id) from e
