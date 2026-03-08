from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    Response
)

from common.exceptions import NotFound, BadRequest, AgogeValidationError
from common.models.response import SnapshotListResponse, AgogeResponse, SnapshotResponse
from common.models.users import AgogeUser
from common.utilities.gcp.cloud_logger import Logger, LoggerNames

from core.compute.snapshot import ComputeSnapshot
from dependencies import teacher_required, get_cloud_env, admin_required

compute_snapshot_router = APIRouter(prefix="/compute/snapshot")
logger = Logger(LoggerNames.API)


@compute_snapshot_router.get("/")
async def list_snapshots(
    request: Request,
    build_id: str,
    course_object: int,
    env_dict: dict = Depends(get_cloud_env),
    current_user: AgogeUser = Depends(teacher_required)
) -> AgogeResponse[SnapshotListResponse]:
    log_args = {
        'user': current_user.uid,
        'origin': request.client.host
    }
    try:
        logger.debug(f'GET request initiated by {current_user.uid}', **log_args)
        snapshots = await ComputeSnapshot(env_dict=env_dict).list(build_id, course_object)
        return AgogeResponse(data={'items': snapshots})
    except (BadRequest, AgogeValidationError) as e:
        logger.error(f'snapshot list request failed with reason: {e.message}', **log_args)
        raise HTTPException(status_code=400, detail=e.message)
    except NotFound as e:
        logger.error(f'snapshot list request failed with reason: {e.message}', **log_args)
        raise HTTPException(status_code=404, detail=e.message)


@compute_snapshot_router.get("/{server_name}/")
async def get_server_snapshots(
    request: Request,
    server_name: str,
    env_dict: dict = Depends(get_cloud_env),
    current_user: AgogeUser = Depends(teacher_required)
) -> AgogeResponse[SnapshotResponse]:
    log_args = {
        'user': current_user.uid,
        'origin': request.client.host
    }
    try:
        snapshots = await ComputeSnapshot(env_dict=env_dict).get(server_name)
        return AgogeResponse(data=snapshots)
    except (BadRequest, AgogeValidationError) as e:
        logger.error(f'snapshot get request failed with reason: {e.message}', **log_args)
        raise HTTPException(status_code=400, detail=e.message)
    except NotFound as e:
        logger.error(f'snapshot get request failed with reason: {e.message}', **log_args)
        raise HTTPException(status_code=404, detail=e.message)


@compute_snapshot_router.post("/")
async def process_snapshot_list_action(
    request: Request,
    env_dict: dict = Depends(get_cloud_env),
    current_user: AgogeUser = Depends(teacher_required)
) -> Response:
    log_args = {
        'user': current_user.uid,
        'origin': request.client.host
    }

    json_data = await request.json()
    try:
        logger.info(f'POST request initiated by {current_user.uid}', **log_args)
        ComputeSnapshot(env_dict=env_dict).process_action_on_list(json_data)
        return Response(status_code=200)
    except BadRequest as e:
        logger.error(f'action on list failed with reason: {e.message}', **log_args)
        raise HTTPException(status_code=400, detail=e.message)


@compute_snapshot_router.put("/{server_name}/")
async def process_snapshot_action(
    request: Request,
    server_name: str,
    env_dict: dict = Depends(get_cloud_env),
    current_user: AgogeUser = Depends(teacher_required)
) -> Response:
    log_args = {
        'user': current_user.uid,
        'server': server_name,
        'origin': request.client.host
    }

    json_data = await request.json()
    if json_data:
        try:
            logger.info(f"PUT request for server action from user {current_user.uid}", **log_args)
            ComputeSnapshot(env_dict=env_dict).process_server_action(
                data=json_data,
                server_name=server_name,
            )
            return Response(status_code=200)
        except NotFound as e:
            logger.error(e.message, **log_args)
            raise HTTPException(status_code=404, detail=e.message)
        except (BadRequest, AgogeValidationError) as e:
            logger.error(e.message, **log_args)
            raise HTTPException(status_code=400, detail=e.message)
    else:
        error_msg = 'Invalid or missing data in request'
        logger.error(error_msg, **log_args)
        raise HTTPException(status_code=400, detail=error_msg)
