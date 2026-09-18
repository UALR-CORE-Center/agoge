from typing import Optional
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    Response,
)

from common.exceptions import NotFound, BadRequest, Unauthorized
from common.models.agoge import UnitModel
from common.models.response import (
    ActiveExpiredUnitListResponse,
    AgogeIDResponse,
    AgogeResponse,
    UnitStateResponse,
    WorkoutListResponse, UnitRosterResponse, UnitFullResponse, UnitListResponse
)
from common.models.users import AgogeUser
from common.utilities.gcp.cloud_logger import Logger, LoggerNames

from core.unit import Unit
from dependencies import (
    teacher_required,
    get_cloud_env,
    build_id_path
)


unit_router = APIRouter(
    prefix="/units",
)
logger = Logger(LoggerNames.API)


@unit_router.get("/")
async def list_units(
    request: Request,
    env_dict: dict = Depends(get_cloud_env),
    current_user: AgogeUser = Depends(teacher_required),
    active: Optional[bool] = True,
    expired: Optional[bool] = True,
    days: Optional[int] = None,
    instructor: Optional[bool] = True,
) -> AgogeResponse[ActiveExpiredUnitListResponse] | AgogeResponse[UnitListResponse]:
    log_args = {
        'user': current_user.uid,
        'origin': request.client.host,
    }

    try:
        units = (
            Unit(env_dict=env_dict)
            .list(
                requester=current_user,
                active=active,
                expired=expired,
                days=days,
                instructor=instructor
            )
        )
        if isinstance(units, tuple):
            return AgogeResponse(data={'active': units[0], 'expired': units[1]})
        else:
            return AgogeResponse(data={'items': units, 'total': len(units)})
    except NotFound:
        raise HTTPException(status_code=404)
    except BadRequest as e:
        logger.error(e.message, **log_args)
        raise HTTPException(status_code=400, detail=e.message)
    except Unauthorized as e:
        logger.error(e.message, **log_args)
        raise HTTPException(status_code=401, detail=e.message)


@unit_router.post("/")
async def create_unit(
    request: Request,
    env_dict: dict = Depends(get_cloud_env),
    current_user: AgogeUser = Depends(teacher_required)
) -> AgogeResponse[AgogeIDResponse]:
    log_args = {
        'user': current_user.uid,
        'origin': request.client.host,
    }
    json_data = await request.json()

    try:
        logger.info(f"POST request to create unit from user {current_user.uid}", **log_args)
        build_id = (
            Unit(env_dict=env_dict)
            .build(requester=current_user, data=json_data)
        )
        return AgogeResponse(data={'build_id': build_id})
    except NotFound as e:
        logger.error(e.message, **log_args)
        raise HTTPException(404, detail=e.message)
    except BadRequest as e:
        logger.error(e.message, **log_args)
        raise HTTPException(400, detail=e.message)


@unit_router.get("/{build_id}/")
async def get_unit(
    build_id: str = Depends(build_id_path),
    env_dict: dict = Depends(get_cloud_env),
    current_user: AgogeUser = Depends(teacher_required)
) -> AgogeResponse[UnitModel]:
    try:
        unit_manager = Unit(env_dict=env_dict)
        unit = unit_manager.get(build_id)
        unit_manager._require_instructor_access(unit, current_user)
        return AgogeResponse(data=unit)
    except NotFound as e:
        logger.error(e.message)
        raise HTTPException(status_code=404)
    except BadRequest as e:
        logger.error(e.message)
        raise HTTPException(status_code=400)
    except Unauthorized as e:
        logger.error(e.message)
        raise HTTPException(status_code=403, detail=e.message)


@unit_router.get("/{build_id}/state/")
async def get_unit_state(
    build_id: str = Depends(build_id_path),
    env_dict: dict = Depends(get_cloud_env),
) -> AgogeResponse[UnitStateResponse]:
    exists, states = Unit(env_dict=env_dict).get_states(build_id)
    total = len(states)
    return AgogeResponse(data={'exists': exists, 'items': states, 'total': total})


@unit_router.get("/{build_id}/roster/")
async def get_unit_roster(
    build_id: str = Depends(build_id_path),
    env_dict: dict = Depends(get_cloud_env)
) -> AgogeResponse[UnitRosterResponse]:
    roster = Unit(env_dict=env_dict).get_unit_roster_size(build_id=build_id)
    return AgogeResponse(data={'roster': roster})


@unit_router.get(
    "/{build_id}/full/",
    description="Return an item with all Unit data, `{unit, unit workouts, roster size}`"
)
async def get_all_data(
    build_id: str = Depends(build_id_path),
    env_dict: dict = Depends(get_cloud_env),
    current_user: AgogeUser = Depends(teacher_required),
) -> AgogeResponse[UnitFullResponse]:
    log_args = {
        'unit_id': build_id,
        'user': current_user.uid
    }
    try:
        unit_full = Unit(env_dict=env_dict).get_all_data(build_id, requester=current_user)
        rubric_support = env_dict.get("rubric_support", False)
        return AgogeResponse(
            data=UnitFullResponse(
                **unit_full,
                rubric_support=rubric_support
            )
        )
    except NotFound as e:
        logger.error(e.message, **log_args)
        raise HTTPException(status_code=404, detail=e.message)
    except BadRequest as e:
        logger.error(e.message, **log_args)
        raise HTTPException(status_code=400, detail=e.message)
    except Unauthorized as e:
        logger.error(e.message, **log_args)
        raise HTTPException(status_code=403, detail=e.message)


@unit_router.get("/{build_id}/workouts/")
async def get_unit_workouts(
    build_id: str = Depends(build_id_path),
    env_dict: dict = Depends(get_cloud_env),
    current_user: AgogeUser = Depends(teacher_required)
) -> AgogeResponse[WorkoutListResponse]:
    log_args = {
        'unit_id': build_id,
        'user': current_user.uid
    }

    try:
        unit_workouts = Unit(env_dict=env_dict).list_workouts(build_id)
        return AgogeResponse(data={'items': unit_workouts})
    except BadRequest as e:
        logger.error(e.message, **log_args)
        raise HTTPException(status_code=400)
    except NotFound as e:
        logger.error(e.message, **log_args)
        raise HTTPException(status_code=404)


@unit_router.post("/{build_id}/")
async def build_all_workouts(
    request: Request,
    build_id: str = Depends(build_id_path),
    env_dict: dict = Depends(get_cloud_env),
    current_user: AgogeUser = Depends(teacher_required)
) -> Response:
    log_args = {
        'unit_id': build_id,
        'user': current_user.uid,
        'origin': request.client.host
    }

    try:
        logger.info(
            f'POST request to build all workouts for unit {build_id} from user {current_user.uid}',
            **log_args
        )
        Unit(env_dict=env_dict).build_all(build_id)
        return Response(status_code=200)
    except NotFound as e:
        logger.error(e.message, **log_args)
        raise HTTPException(status_code=404)
    except BadRequest as e:
        logger.error(e.message, **log_args)
        raise HTTPException(status_code=400)


@unit_router.put("/{build_id}/")
async def process_action(
    request: Request,
    build_id: str = Depends(build_id_path),
    env_dict: dict = Depends(get_cloud_env),
    current_user: AgogeUser = Depends(teacher_required)
) -> Response:
    log_args = {
        'unit_id': build_id,
        'user': current_user.uid,
        'origin': request.client.host
    }

    try:
        logger.info(
            f'PUT request for unit with id {build_id} from user {current_user.uid}',
            **log_args
        )
        await Unit(env_dict=env_dict).process_action(
            build_id=build_id,
            request=request
        )
        return Response(status_code=200)
    except BadRequest as e:
        logger.error(e.message, **log_args)
        raise HTTPException(400, detail=e.message)
    except NotFound as e:
        logger.error(e.message, **log_args)
        raise HTTPException(404, detail=e.message)


@unit_router.patch("/{build_id}/")
async def update_unit(
    request: Request,
    build_id: str = Depends(build_id_path),
    env_dict: dict = Depends(get_cloud_env),
    current_user: AgogeUser = Depends(teacher_required)
) -> Response:
    log_args = {
        'unit_id': build_id,
        'user': current_user.uid,
        'origin': request.client.host
    }

    try:
        logger.info(f'PATCH request for unit with id {build_id} from user {current_user.uid}', **log_args)
        await Unit(env_dict=env_dict).update(
            build_id=build_id,
            request=request,
            requester=current_user
        )
        return Response(status_code=200)
    except BadRequest as e:
        logger.error(e.message, **log_args)
        raise HTTPException(400, detail=e.message)
    except NotFound as e:
        logger.error(e.message, **log_args)
        raise HTTPException(404, detail=e.message)
    except Unauthorized as e:
        logger.error(e.message, **log_args)
        raise HTTPException(status_code=401, detail=e.message)


@unit_router.delete("/{build_id}/")
async def delete_unit(
    request: Request,
    build_id: str = Depends(build_id_path),
    env_dict: dict = Depends(get_cloud_env),
    current_user: AgogeUser = Depends(teacher_required),
) -> Response:
    log_args = {
        'build_id': build_id,
        'user': current_user.uid,
        'origin': request.client.host
    }

    try:
        logger.info(f'DELETE request for unit with id {build_id} from user {current_user.uid}', **log_args)
        Unit(env_dict=env_dict).delete(requester=current_user, build_id=build_id)
        return Response(status_code=200)
    except NotFound as e:
        logger.error(e.message, **log_args)
        raise HTTPException(status_code=404, detail=e.message)
    except Unauthorized as e:
        logger.error(e.message, **log_args)
        raise HTTPException(status_code=403, detail=e.message)


