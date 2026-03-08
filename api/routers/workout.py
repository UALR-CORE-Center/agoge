from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import Response
from typing import Optional

from common.exceptions import (
    BadRequest,
    Forbidden,
    NotFound,
    Unauthorized,
    Conflict,
    ServiceUnavailable,
    NotReady,
    NotAllowed
)
from common.models.agoge import AssessmentModel, WorkoutModel
from common.models.response import (
    AgogeResponse,
    AgogeIDResponse,
    WorkoutListResponse,
    WorkoutStateResponse,
    WorkoutFullResponse
)
from common.models.users import AgogeUser, AnonymousAppUser
from common.utilities.gcp.cloud_logger import Logger, LoggerNames

from core.workout import Workout
from core.workout_internet_firewall import WorkoutInternetFirewall
from dependencies import (
    admin_required,
    get_cloud_env,
    get_current_user,
    build_id_path
)

workout_router = APIRouter(
    prefix="/workouts",
    dependencies=[Depends(get_cloud_env)]
)
logger = Logger(LoggerNames.API)


@workout_router.get("/")
async def list_workouts(
    active: Optional[bool] = True,
    days: Optional[int] = None,
    student: Optional[bool] = False,
    env_dict: dict = Depends(get_cloud_env),
    current_user: [AgogeUser, AnonymousAppUser] = Depends(get_current_user)
) -> AgogeResponse[WorkoutListResponse]:
    log_args = {
        'user': current_user.uid
    }

    try:
        workout_list = (
            Workout(env_dict=env_dict)
            .list(
                requester=current_user,
                active=active,
                days=days,
                student=student
            )
        )
        return AgogeResponse(data={'items': workout_list})
    except (BadRequest, ValueError) as e:
        if isinstance(e, BadRequest):
            logger.info(e.message, **log_args)
        raise HTTPException(status_code=400)
    except NotFound as e:
        logger.info(e.message, **log_args)
        raise HTTPException(status_code=404)


@workout_router.post("/")
async def create_workout(
    request: Request,
    env_dict: dict = Depends(get_cloud_env),
) -> AgogeResponse[AgogeIDResponse]:
    log_args = {
        'origin': request.client.host
    }

    json_data = await request.json()
    try:
        logger.info(f'POST request to create workout', **log_args)
        build_id, exists = Workout(env_dict=env_dict).build(json_data)
        return AgogeResponse(data={'build_id': build_id, 'exists': exists})
    except BadRequest as e:
        msg = "Invalid request data. Please ensure all required fields are correctly filled and formatted"
        logger.error(e.message, details=msg, **log_args)
        raise HTTPException(status_code=400, detail=msg)
    except Forbidden as e:
        msg = ("Request denied. Maximum allowed workout builds for the "
               "unit have been reached. Contact your instructor for further assistance.")
        logger.error(e.message, details=msg, **log_args)
        raise HTTPException(status_code=403, detail=msg)
    except NotFound as e:
        msg = "Join code not found. Please verify the join code and try again."
        logger.error(e.message, details=msg, **log_args)
        raise HTTPException(status_code=404, detail=msg)


@workout_router.get("/{build_id}/")
async def get_workout(
    build_id: str = Depends(build_id_path),
    env_dict: dict = Depends(get_cloud_env),
) -> AgogeResponse[WorkoutModel]:
    try:
        workout = Workout(env_dict=env_dict).get(build_id)
        return AgogeResponse(data=workout)
    except BadRequest:
        raise HTTPException(status_code=400)
    except NotFound:
        raise HTTPException(status_code=404)


@workout_router.get(
    "/{build_id}/full/",
    description="Return an item with all Workout data, `{workouts, servers}`"
)
async def get_all_data(
    build_id: str = Depends(build_id_path),
    env_dict: dict = Depends(get_cloud_env),
) -> AgogeResponse[WorkoutFullResponse]:
    logger.workout_id = build_id
    try:
        workout_full = Workout(env_dict=env_dict).get_all_data(build_id)
        return AgogeResponse(data=WorkoutFullResponse(**workout_full))
    except NotFound as e:
        logger.warning(e.message)
        raise HTTPException(status_code=404, detail=e.message)
    except BadRequest as e:
        logger.error(e.message)
        raise HTTPException(status_code=400, detail=e.message)


@workout_router.get('/{build_id}/state/')
async def get_state(
    build_id: str = Depends(build_id_path),
    env_dict: dict = Depends(get_cloud_env),
) -> AgogeResponse[WorkoutStateResponse]:
    try:
        state = Workout(env_dict=env_dict).get_state(build_id)
        return AgogeResponse(data=state)
    except BadRequest:
        raise HTTPException(status_code=400)
    except NotFound:
        raise HTTPException(status_code=404)


@workout_router.put("/{build_id}/")
async def process_action(
    request: Request,
    build_id: str = Depends(build_id_path),
    env_dict: dict = Depends(get_cloud_env),
) -> AgogeResponse[WorkoutStateResponse]:
    logger.workout_id = build_id
    log_args = {'origin': request.client.host}
    try:
        logger.info(f"PUT request for workout with id {build_id}", **log_args)
        workout_state = (
            await Workout(env_dict=env_dict)
            .process_action(
                build_id=build_id,
                request=request,
            )
        )
        return AgogeResponse(data=workout_state)
    except BadRequest as e:
        logger.error(e.message, **log_args)
        raise HTTPException(status_code=400)
    except NotFound as e:
        logger.error(e.message, **log_args)
        raise HTTPException(status_code=404)


@workout_router.patch("/{build_id}/")
async def update_workout(
    request: Request,
    build_id: str = Depends(build_id_path),
    env_dict: dict = Depends(get_cloud_env),
    current_user: AgogeUser = Depends(admin_required)
) -> Response:
    logger.workout_id = build_id
    log_args = {
        'origin': request.client.host,
        'user': current_user.uid
    }

    try:
        logger.info(
            f"PATCH request to update workout with id {build_id}",
            **log_args
        )
        await Workout(env_dict=env_dict).update(
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


@workout_router.put("/{build_id}/access/")
async def update_firewall(
    request: Request,
    build_id: str = Depends(build_id_path),
    env_dict: dict = Depends(get_cloud_env),
) -> Response:
    logger.workout_id = build_id
    log_args = {'origin': request.client.host}

    json_data = await request.json()
    try:
        logger.info(f"PUT request to update firewall for workout with id {build_id}", **log_args)

        WorkoutInternetFirewall(workout_id=build_id, env_dict=env_dict).add_ip_address(json_data=json_data)
        return Response(status_code=200)
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=e.message)
    except Unauthorized as e:
        raise HTTPException(status_code=401, detail=e.message)
    except NotAllowed as e:
        logger.warning(e.message, **log_args)
        raise HTTPException(status_code=405)
    except Conflict as e:
        raise HTTPException(status_code=409, detail=e.message)
    except ServiceUnavailable as e:
        raise HTTPException(status_code=500, detail=e.message)
    except NotReady as e:
        raise HTTPException(status_code=503, detail=e.message)


@workout_router.delete("/{build_id}/access/")
async def disable_internet_access(
    build_id: str = Depends(build_id_path),
    env_dict: dict = Depends(get_cloud_env),
) -> Response:
    logger.workout_id = build_id

    try:
        logger.info(f"DELETE request to disable internet access for workout with id {build_id}")

        WorkoutInternetFirewall(workout_id=build_id, env_dict=env_dict).disable_internet_access()
        return Response(status_code=200)
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=e.message)
    except Unauthorized as e:
        raise HTTPException(status_code=401, detail=e.message)
    except Conflict as e:
        raise HTTPException(status_code=409, detail=e.message)


@workout_router.put("/{build_id}/question/{question_key}/")
async def process_question(
    request: Request,
    question_key: str,
    build_id: str = Depends(build_id_path),
    env_dict: dict = Depends(get_cloud_env),
) -> AgogeResponse[AssessmentModel] or Response:
    logger.workout_id = build_id
    log_args = {
        'origin': request.client.host,
        'question_key': question_key
    }

    try:
        logger.info(
            f"PUT request to answer question for workout {build_id} "
            f"with question key {question_key}",
            **log_args
        )
        assessment = await (
            Workout(env_dict=env_dict)
            .process_question_response(
                build_id=build_id,
                question_key=question_key,
                request=request
            )
        )
        if assessment:
            return AgogeResponse(data=assessment)
        return Response(status_code=200)
    except NotFound as e:
        logger.error(e.message, **log_args)
        raise HTTPException(status_code=404, detail=e.message)
    except BadRequest as e:
        logger.error(e.message, **log_args)
        raise HTTPException(status_code=400, detail=e.message)
    except ValueError as e:
        logger.error(str(e), detail="Unsupported LMS type", **log_args)
        raise HTTPException(status_code=400, detail='Unsupported LMS type')


@workout_router.delete("/{build_id}/")
async def delete_workout(
    request: Request,
    build_id: str = Depends(build_id_path),
    env_dict: dict = Depends(get_cloud_env),
    current_user: AgogeUser = Depends(admin_required),
) -> Response:
    log_args = {
        'build_id': build_id,
        'user': current_user.uid,
        'origin': request.client.host
    }

    try:
        logger.info(f'DELETE request for workout with id {build_id} from user {current_user.uid}', **log_args)
        Workout(env_dict=env_dict).delete(requester=current_user, build_id=build_id)
        return Response(status_code=200)
    except NotFound as e:
        logger.error(e.message, **log_args)
        raise HTTPException(status_code=404, detail=e.message)
    except Unauthorized as e:
        logger.error(e.message, **log_args)
        raise HTTPException(status_code=403, detail=e.message)
