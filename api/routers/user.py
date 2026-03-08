from fastapi import APIRouter, Depends, HTTPException, Request, Response

from common.exceptions import NotFound, Unauthorized, BadRequest, Conflict
from common.models.response import AgogeResponse, UsersListResponse
from common.models.users import AgogeUser, SafeAgogeUser
from common.models.lms_courses import Courses
from common.utilities.gcp.cloud_logger import Logger, LoggerNames

from core.users import Users
from dependencies import (
    teacher_required,
    admin_required,
    get_cloud_env,
)

user_router = APIRouter(prefix="/users")
logger = Logger(LoggerNames.API)


@user_router.get("/")
async def list_users(
    _: AgogeUser = Depends(admin_required),
) -> AgogeResponse[UsersListResponse]:
    users = Users().list_users()
    return AgogeResponse(data={'items': users})


@user_router.post("/")
async def create_user(
    request: Request,
    current_user: AgogeUser = Depends(admin_required),
    env_dict: dict = Depends(get_cloud_env)
) -> AgogeResponse[SafeAgogeUser]:
    json_data = await request.json()
    try:
        logger.info(f"POST request for create_user initiated by user {current_user.uid}")
        user = Users().create(json_data, env_dict)
        return AgogeResponse(data=user)
    except NotFound as e:
        logger.error(f'create user request failed with reason: {e.message}')
        raise HTTPException(status_code=404)
    except Unauthorized as e:
        logger.error(f'create user request failed with reason: {e.message}')
        raise HTTPException(status_code=403, detail=e.message)
    except (BadRequest, Conflict) as e:
        logger.error(f'create user request failed with reason: {e.message}')
        raise HTTPException(status_code=400, detail=e.message)


@user_router.get("/{user_id}/")
async def get_user(
    user_id: str,
    current_user: AgogeUser = Depends(teacher_required),
) -> AgogeResponse[AgogeUser]:
    try:
        user = Users().get_user_from_request(current_user, user_id)
        return AgogeResponse(data=user)
    except Unauthorized as e:
        logger.error(e.message)
        raise HTTPException(status_code=403, detail=e.message)
    except NotFound as e:
        logger.error(e.message)
        raise HTTPException(status_code=404, detail=e.message)


@user_router.post("/{user_id}/")
async def update_user(
    request: Request,
    user_id: str,
    current_user: AgogeUser = Depends(admin_required)
) -> AgogeResponse[SafeAgogeUser]:
    json_data = await request.json()
    try:
        logger.info(f"POST request by {current_user.uid} to update user {user_id}...")
        user = Users().update(current_user, user_id, json_data)
        return AgogeResponse(data=user)
    except NotFound as e:
        logger.error(f'User update request failed with reason: {e.message}')
        raise HTTPException(status_code=404, detail=e.message)
    except BadRequest as e:
        logger.error(f'User update request failed with reason: {e.message}')
        raise HTTPException(status_code=400, detail=e.message)


@user_router.post("/{user_id}/settings/")
async def update_user_settings(
    request: Request,
    user_id: str,
    current_user: AgogeUser = Depends(teacher_required)
) -> AgogeResponse[AgogeUser]:
    json_data = await request.json()
    try:
        logger.info(f"POST request by {current_user.uid} to update user settings...")
        user = Users().update_settings(current_user, user_id, data=json_data)
    except NotFound:
        raise HTTPException(status_code=404)
    except Unauthorized as e:
        logger.error(f'User update settings failed with reason: {e.message}')
        raise HTTPException(status_code=403, detail=e.message)
    except BadRequest as e:
        logger.error(f'User update settings failed with reason: {e.message}')
        raise HTTPException(status_code=400, detail=e.message)

    if user:
        return AgogeResponse(data=user)
    raise HTTPException(status_code=400)


@user_router.get("/{user_id}/courses/")
async def get_user_courses(
    current_user: AgogeUser = Depends(teacher_required),
) -> AgogeResponse[Courses]:
    """
    Retrieves LMS courses user has access to use
    """
    try:
        courses = Users().get_user_courses(current_user)
        return AgogeResponse(data=courses)
    except NotFound as e:
        logger.error(e.message)
        raise HTTPException(status_code=404, detail=e.message)


@user_router.delete("/{user_id}/")
async def delete_user(
    user_id: str,
    current_user: AgogeUser = Depends(admin_required),
) -> Response:
    try:
        logger.info(f"DELETE request by user {current_user.uid} for user {user_id}")
        Users().delete(user_id, requester=current_user)
        return Response(status_code=200)
    except NotFound:
        raise HTTPException(status_code=404)
    except Unauthorized as e:
        logger.error(f'DELETE user request failed with reason: {e.message}')
        raise HTTPException(status_code=403, detail=e.message)
    except BadRequest as e:
        logger.error(f'DELETE user request failed with reason: {e.message}')
        raise HTTPException(status_code=400, detail=e.message)
