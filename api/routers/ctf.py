import re
from typing import Any, Optional, Type, TypeVar

from fastapi import APIRouter, Body, Depends, Path
from pydantic import BaseModel, ValidationError

from common.exceptions.agoge import BadRequest
from common.models.agoge import (
    CtfActionRequest,
    CtfCreateRequest,
    CtfEventModel,
    CtfHostResetRequest,
    CtfReplantRequest,
    CtfScoreAdjustRequest,
    CtfUpdateRequest,
)
from common.models.response import (
    AgogeIDResponse,
    AgogeResponse,
    CtfConfigResponse,
    CtfFlagRevealResponse,
    CtfStateResponse,
)
from common.models.users import AgogeUser
from common.utilities.gcp.cloud_logger import Logger, LoggerNames
from common.utilities.id_generator import IdGenerator

from core.ctf.audit import CtfAudit
from core.ctf.config import is_ctf_enabled
from core.ctf.event import CtfEvent
from core.ctf.hosts import CtfHosts
from core.ctf.scoring import CtfScoring
from dependencies import admin_required, ctf_enabled_required, get_cloud_env, teacher_required
from utilities.http_errors import to_http_exception

# Every route but GET /ctf/config/ 404s while the feature is off (SC-19); config is how the UI finds out.
ctf_router = APIRouter(prefix="/ctf")
enabled = [Depends(ctf_enabled_required)]
logger = Logger(LoggerNames.API, class_name='CtfRouter')

ModelT = TypeVar('ModelT', bound=BaseModel)
BUILD_ID_PATTERN = "^[a-z]{10}$"


def ctf_id_path(ctf_id: str = Path(..., pattern=BUILD_ID_PATTERN)) -> str:
    return ctf_id


def workout_id_path(workout_id: str = Path(..., pattern=BUILD_ID_PATTERN)) -> str:
    return workout_id


def _parse(model: Type[ModelT], payload: Any) -> ModelT:
    """Validate a body here rather than in the signature, because FastAPI answers a bad body with
    422 and the Error Handling table promises 400 for a malformed body, unknown action or mode.
    The message names fields and problems only, never the submitted values."""
    try:
        return model.model_validate(payload)
    except ValidationError as e:
        problems = "; ".join(
            f"{'.'.join(str(part) for part in error['loc']) or 'body'}: {error['msg']}" for error in e.errors()
        )
        raise BadRequest(message=f"Invalid request body: {problems}")


def _fail(e: Exception, route: str, ctf_id: Optional[str] = None, **log_args):
    logger.warning(f"CtfRouter:{ctf_id or '-'} - {route} failed: {type(e).__name__}", **log_args)
    return to_http_exception(e)


@ctf_router.get("/config/")
def get_config(current_user: AgogeUser = Depends(teacher_required)) -> AgogeResponse[CtfConfigResponse]:
    return AgogeResponse(data=CtfConfigResponse(ctf_enabled=is_ctf_enabled()))


@ctf_router.get("/", dependencies=enabled)
def list_events(
    env_dict: dict = Depends(get_cloud_env),
    current_user: AgogeUser = Depends(teacher_required),
) -> AgogeResponse:
    try:
        return AgogeResponse(data={'items': CtfEvent(env_dict=env_dict).list(current_user)})
    except Exception as e:
        raise _fail(e, "list_events", user=current_user.uid) from e


@ctf_router.post("/", dependencies=enabled)
def create_event(
    payload: Any = Body(default=None),
    env_dict: dict = Depends(get_cloud_env),
    current_user: AgogeUser = Depends(teacher_required),
) -> AgogeResponse[AgogeIDResponse]:
    try:
        request = _parse(CtfCreateRequest, payload)
        # Chosen here so the CTF_CREATE row names the event even when creation fails.
        ctf_id = IdGenerator.build_id()
        with CtfAudit(env_dict=env_dict).action(ctf_id, 'CTF_CREATE', current_user.email, target=request.unit_id):
            CtfEvent(env_dict=env_dict).create(request.unit_id, current_user, ctf_id=ctf_id)
        return AgogeResponse(data=AgogeIDResponse(build_id=ctf_id))
    except Exception as e:
        raise _fail(e, "create_event", user=current_user.uid) from e


@ctf_router.get("/{ctf_id}/", dependencies=enabled)
def get_event(
    ctf_id: str = Depends(ctf_id_path),
    env_dict: dict = Depends(get_cloud_env),
    current_user: AgogeUser = Depends(teacher_required),
) -> AgogeResponse[CtfEventModel]:
    try:
        return AgogeResponse(data=CtfEvent(env_dict=env_dict).get(ctf_id, current_user))
    except Exception as e:
        raise _fail(e, "get_event", ctf_id=ctf_id, user=current_user.uid) from e


@ctf_router.put("/{ctf_id}/", dependencies=enabled)
def update_event(
    payload: Any = Body(default=None),
    ctf_id: str = Depends(ctf_id_path),
    env_dict: dict = Depends(get_cloud_env),
    current_user: AgogeUser = Depends(teacher_required),
) -> AgogeResponse[CtfEventModel]:
    try:
        request = _parse(CtfUpdateRequest, payload)
        fields = ",".join(sorted(request.model_fields_set))
        with CtfAudit(env_dict=env_dict).action(ctf_id, 'CTF_UPDATE', current_user.email, detail={'fields': fields}):
            event = CtfEvent(env_dict=env_dict).update(ctf_id, request, current_user)
        return AgogeResponse(data=event)
    except Exception as e:
        raise _fail(e, "update_event", ctf_id=ctf_id, user=current_user.uid) from e


@ctf_router.delete("/{ctf_id}/", dependencies=enabled)
def delete_event(
    ctf_id: str = Depends(ctf_id_path),
    env_dict: dict = Depends(get_cloud_env),
    current_user: AgogeUser = Depends(admin_required),
) -> AgogeResponse[AgogeIDResponse]:
    try:
        with CtfAudit(env_dict=env_dict).action(ctf_id, 'CTF_DELETE', current_user.email):
            CtfEvent(env_dict=env_dict).delete(ctf_id, current_user)
        return AgogeResponse(data=AgogeIDResponse(build_id=ctf_id, exists=False))
    except Exception as e:
        raise _fail(e, "delete_event", ctf_id=ctf_id, user=current_user.uid) from e


@ctf_router.get("/{ctf_id}/state/", dependencies=enabled)
def get_state(
    ctf_id: str = Depends(ctf_id_path),
    env_dict: dict = Depends(get_cloud_env),
    current_user: AgogeUser = Depends(teacher_required),
) -> AgogeResponse[CtfStateResponse]:
    try:
        return AgogeResponse(data=CtfEvent(env_dict=env_dict).state(ctf_id, current_user))
    except Exception as e:
        raise _fail(e, "get_state", ctf_id=ctf_id, user=current_user.uid) from e


@ctf_router.put("/{ctf_id}/action/", dependencies=enabled)
def process_action(
    payload: Any = Body(default=None),
    ctf_id: str = Depends(ctf_id_path),
    env_dict: dict = Depends(get_cloud_env),
    current_user: AgogeUser = Depends(teacher_required),
) -> AgogeResponse[CtfEventModel]:
    try:
        request = _parse(CtfActionRequest, payload)
        # CtfAction values map one-to-one onto the CTF_<ACTION> log actions.
        log_action = f"CTF_{request.action.upper()}"
        with CtfAudit(env_dict=env_dict).action(ctf_id, log_action, current_user.email):
            event = CtfEvent(env_dict=env_dict).process_action(ctf_id, request, current_user)
        return AgogeResponse(data=event)
    except Exception as e:
        raise _fail(e, "process_action", ctf_id=ctf_id, user=current_user.uid) from e


@ctf_router.get("/{ctf_id}/flags/", dependencies=enabled)
def get_flags(
    ctf_id: str = Depends(ctf_id_path),
    env_dict: dict = Depends(get_cloud_env),
    current_user: AgogeUser = Depends(teacher_required),
) -> AgogeResponse:
    try:
        return AgogeResponse(data={'items': CtfEvent(env_dict=env_dict).flags(ctf_id, current_user)})
    except Exception as e:
        raise _fail(e, "get_flags", ctf_id=ctf_id, user=current_user.uid) from e


@ctf_router.put("/{ctf_id}/flags/", dependencies=enabled)
def replant_flags(
    payload: Any = Body(default=None),
    ctf_id: str = Depends(ctf_id_path),
    env_dict: dict = Depends(get_cloud_env),
    current_user: AgogeUser = Depends(teacher_required),
) -> AgogeResponse:
    try:
        request = _parse(CtfReplantRequest, payload)
        # Scope as counts only: board and server names are already in the published messages.
        detail = {
            'boards': 'all' if request.workout_ids is None else len(request.workout_ids),
            'servers': 'all' if request.servers is None else len(request.servers),
        }
        with CtfAudit(env_dict=env_dict).action(ctf_id, 'FLAG_REPLANT', current_user.email, detail=detail) as entry:
            messages = CtfHosts(env_dict=env_dict).replant(ctf_id, request.workout_ids, request.servers, current_user)
            entry.add_detail(messages=messages)
        return AgogeResponse(data={'messages': messages})
    except Exception as e:
        raise _fail(e, "replant_flags", ctf_id=ctf_id, user=current_user.uid) from e


@ctf_router.get("/{ctf_id}/flags/{flag_id}/reveal/", dependencies=enabled)
def reveal_flag(
    flag_id: str,
    workout_id: Optional[str] = None,
    ctf_id: str = Depends(ctf_id_path),
    env_dict: dict = Depends(get_cloud_env),
    current_user: AgogeUser = Depends(admin_required),
) -> AgogeResponse[CtfFlagRevealResponse]:
    try:
        # Checked before the audit so a request that cannot reach core leaves no row.
        # Also keeps flag-shaped text out of the audit detail, which would reject it as a 500.
        if not workout_id or not re.fullmatch(BUILD_ID_PATTERN, workout_id):
            raise BadRequest(message="workout_id must be a ten-letter build id")
        # The revealed value never goes into the row: only who looked at which flag on which board.
        with CtfAudit(env_dict=env_dict).action(
            ctf_id, 'FLAG_REVEAL', current_user.email, target=flag_id, detail={'workout_id': workout_id}
        ):
            revealed = CtfEvent(env_dict=env_dict).reveal(ctf_id, flag_id, workout_id, current_user)
        return AgogeResponse(data=revealed)
    except Exception as e:
        raise _fail(e, "reveal_flag", ctf_id=ctf_id, user=current_user.uid) from e


@ctf_router.get("/{ctf_id}/boards/", dependencies=enabled)
def get_boards(
    ctf_id: str = Depends(ctf_id_path),
    env_dict: dict = Depends(get_cloud_env),
    current_user: AgogeUser = Depends(teacher_required),
) -> AgogeResponse:
    try:
        return AgogeResponse(data={'items': CtfEvent(env_dict=env_dict).boards(ctf_id, current_user)})
    except Exception as e:
        raise _fail(e, "get_boards", ctf_id=ctf_id, user=current_user.uid) from e


@ctf_router.get("/{ctf_id}/hosts/", dependencies=enabled)
def get_hosts(
    ctf_id: str = Depends(ctf_id_path),
    env_dict: dict = Depends(get_cloud_env),
    current_user: AgogeUser = Depends(teacher_required),
) -> AgogeResponse:
    try:
        return AgogeResponse(data={'items': CtfHosts(env_dict=env_dict).hosts(ctf_id, current_user)})
    except Exception as e:
        raise _fail(e, "get_hosts", ctf_id=ctf_id, user=current_user.uid) from e


@ctf_router.put("/{ctf_id}/boards/{workout_id}/hosts/{server}/reset/", dependencies=enabled)
def reset_host(
    server: str,
    payload: Any = Body(default=None),
    ctf_id: str = Depends(ctf_id_path),
    workout_id: str = Depends(workout_id_path),
    env_dict: dict = Depends(get_cloud_env),
    current_user: AgogeUser = Depends(teacher_required),
) -> AgogeResponse[AgogeIDResponse]:
    try:
        request = _parse(CtfHostResetRequest, payload)
        # The server goes in `target`, not `detail`: detail rejects flag-shaped text, and an odd
        # path segment must reach core (and 404) rather than fail the audit.
        with CtfAudit(env_dict=env_dict).action(
            ctf_id, 'HOST_RESET', current_user.email, target=server,
            detail={'workout_id': workout_id, 'mode': request.mode},
        ):
            CtfHosts(env_dict=env_dict).reset(ctf_id, workout_id, server, request.mode, current_user)
        return AgogeResponse(data=AgogeIDResponse(build_id=workout_id))
    except Exception as e:
        raise _fail(e, "reset_host", ctf_id=ctf_id, user=current_user.uid) from e


@ctf_router.put("/{ctf_id}/boards/{workout_id}/score/", dependencies=enabled)
def adjust_score(
    payload: Any = Body(default=None),
    ctf_id: str = Depends(ctf_id_path),
    workout_id: str = Depends(workout_id_path),
    env_dict: dict = Depends(get_cloud_env),
    current_user: AgogeUser = Depends(teacher_required),
) -> AgogeResponse:
    try:
        request = _parse(CtfScoreAdjustRequest, payload)
        # Not wrapped in CtfAudit: adjust writes its own SCORE_ADJUST row (the only place the
        # reason is kept), and a second wrap would break SC-18's one row per action.
        score = CtfScoring(env_dict=env_dict).adjust(ctf_id, workout_id, request.delta, request.reason, current_user)
        return AgogeResponse(data={'workout_id': workout_id, 'score': score})
    except Exception as e:
        raise _fail(e, "adjust_score", ctf_id=ctf_id, user=current_user.uid) from e


@ctf_router.get("/{ctf_id}/scoreboard/", dependencies=enabled)
def get_scoreboard(
    ctf_id: str = Depends(ctf_id_path),
    env_dict: dict = Depends(get_cloud_env),
    current_user: AgogeUser = Depends(teacher_required),
) -> AgogeResponse:
    try:
        return AgogeResponse(data={'items': CtfScoring(env_dict=env_dict).scoreboard(ctf_id, current_user)})
    except Exception as e:
        raise _fail(e, "get_scoreboard", ctf_id=ctf_id, user=current_user.uid) from e


@ctf_router.get("/{ctf_id}/submissions/", dependencies=enabled)
def get_submissions(
    verdict: Optional[str] = None,
    ctf_id: str = Depends(ctf_id_path),
    env_dict: dict = Depends(get_cloud_env),
    current_user: AgogeUser = Depends(teacher_required),
) -> AgogeResponse:
    try:
        items = CtfEvent(env_dict=env_dict).submissions(ctf_id, current_user, verdict=verdict)
        return AgogeResponse(data={'items': items})
    except Exception as e:
        raise _fail(e, "get_submissions", ctf_id=ctf_id, user=current_user.uid) from e


@ctf_router.get("/{ctf_id}/log/", dependencies=enabled)
def get_log(
    action: Optional[str] = None,
    ctf_id: str = Depends(ctf_id_path),
    env_dict: dict = Depends(get_cloud_env),
    current_user: AgogeUser = Depends(teacher_required),
) -> AgogeResponse:
    try:
        return AgogeResponse(data={'items': CtfEvent(env_dict=env_dict).log(ctf_id, current_user, action=action)})
    except Exception as e:
        raise _fail(e, "get_log", ctf_id=ctf_id, user=current_user.uid) from e
