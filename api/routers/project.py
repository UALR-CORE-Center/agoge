from fastapi import APIRouter, Depends, HTTPException, Request, Response

from common.exceptions import NotFound, Unauthorized, BadRequest, AgogeValidationError
from common.models.agoge import CloudEnvModel
from common.models.response import AgogeResponse
from common.models.users import AgogeUser
from common.utilities.gcp.cloud_logger import Logger, LoggerNames

from core.project import Project
from dependencies import (
    admin_required,
    get_cloud_env,
)

project_router = APIRouter(prefix="/project")
logger = Logger(LoggerNames.API)


@project_router.get("/")
async def get_project_settings(
    _: AgogeUser = Depends(admin_required),
    env: dict = Depends(get_cloud_env)
) -> AgogeResponse[CloudEnvModel]:
    cleaned_env = Project(env).get()
    return AgogeResponse(data=cleaned_env)


@project_router.patch("/")
async def update_project_settings(
    request: Request,
    current_user: AgogeUser = Depends(admin_required),
    env: dict = Depends(get_cloud_env)
) -> Response:
    json_data = await request.json()
    log_args = {
        'origin': request.client.host,
        'user': current_user.uid,
    }
    try:
        logger.info(f"PATCH request by {current_user.uid} to update project settings...")
        Project(env_dict=env).update(current_user, data=json_data)
        return Response(status_code=200)
    except BadRequest as e:
        logger.error(f'project update settings failed with reason: {e.message}', **log_args)
        raise HTTPException(status_code=400, detail=e.message)
    except AgogeValidationError as e:
        raise HTTPException(status_code=400, detail=e.message)
    except NotFound:
        raise HTTPException(status_code=404)
    except Unauthorized as e:
        logger.error(f'project update settings failed with reason: {e.message}', **log_args)
        raise HTTPException(status_code=403, detail=e.message)
