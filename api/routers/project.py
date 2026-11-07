from math import isfinite

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from google.cloud import compute_v1

from common.exceptions import NotFound, Unauthorized, BadRequest, AgogeValidationError
from common.models.agoge import CloudEnvModel
from common.models.response import AgogeResponse
from common.models.users import AgogeUser
from common.utilities.build_incidents import BuildIncidents
from common.utilities.gcp.cloud_logger import Logger, LoggerNames

from core.project import Project
from dependencies import (
    admin_required,
    get_cloud_env,
    teacher_required,
)

project_router = APIRouter(prefix="/project")
logger = Logger(LoggerNames.API)


def _build_availability(hold: dict | None, env: dict) -> dict:
    data = {'hold': BuildIncidents.hold_projection(hold)}
    contact = env.get('admin_email')
    if isinstance(contact, str) and contact.strip() and Project._validate_email(contact.strip()):
        data['support_contact'] = contact.strip()
    return data


@project_router.get("/build-availability/")
def get_build_availability(
    response: Response,
    _: AgogeUser = Depends(teacher_required),
    env: dict = Depends(get_cloud_env),
) -> AgogeResponse[dict]:
    try:
        project = Project(env)
        hold = BuildIncidents(project.db, project.env.project).active_hold()
    except Exception as error:
        logger.error('Could not read build availability.', error_type=type(error).__name__)
        raise HTTPException(status_code=503, detail="Build availability could not be checked.") from error
    response.headers["Cache-Control"] = "no-store"
    return AgogeResponse(data=_build_availability(hold, env))


@project_router.post("/build-availability/recheck/")
def recheck_build_availability(
    response: Response,
    current_user: AgogeUser = Depends(admin_required),
    env: dict = Depends(get_cloud_env),
) -> AgogeResponse[dict]:
    try:
        project = Project(env)
        incidents = BuildIncidents(project.db, project.env.project)
        previous = incidents.active_hold()
        result = compute_v1.ProjectsClient().get(project=project.env.project, retry=None, timeout=10)
        quota = next((entry for entry in result.quotas if entry.metric == 'NETWORKS'), None)
        # These are optional protobuf fields. A missing field reads as 0.0,
        # which would incorrectly free capacity when the usage field is absent.
        if quota is None or 'usage' not in quota or 'limit' not in quota:
            raise ValueError('Incomplete Compute Engine NETWORKS quota reading')
        usage, limit = quota.usage, quota.limit
        if not (isfinite(usage) and isfinite(limit) and usage >= 0 and limit >= 0):
            raise ValueError('Invalid Compute Engine NETWORKS quota reading')
        hold = incidents.update_verified_quota(previous, usage=usage, limit=limit, verified_by=current_user.uid)
    except Exception as error:
        logger.error('Could not verify the Google Cloud network quota.', error_type=type(error).__name__)
        raise HTTPException(status_code=503, detail="Google Cloud quota could not be verified.") from error
    response.headers["Cache-Control"] = "no-store"
    return AgogeResponse(data={**_build_availability(hold, env), 'quota': {'usage': usage, 'limit': limit}})


@project_router.get("/build-incidents/")
def list_build_incidents(
    response: Response,
    cursor: str | None = Query(default=None, pattern=r"^[a-f0-9]{32}$"),
    page_size: int = Query(default=50, ge=1, le=100),
    include_resolved: bool = False,
    _: AgogeUser = Depends(admin_required),
    env: dict = Depends(get_cloud_env),
) -> AgogeResponse[dict]:
    project = Project(env)
    incidents = BuildIncidents(project.db, project.env.project)
    try:
        data = incidents.list_recent(cursor=cursor, page_size=page_size, include_resolved=include_resolved)
    except ValueError as error:
        raise HTTPException(status_code=400, detail="Invalid incident cursor.") from error
    response.headers["Cache-Control"] = "no-store"
    return AgogeResponse(data=data)


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
