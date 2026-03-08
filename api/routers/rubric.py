from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    Response,
    Body,
)

from common.exceptions import NotFound, BadRequest, Unauthorized, ServiceUnavailable
from common.models.agoge import RubricModel
from common.models.response import AgogeResponse
from common.models.users import AgogeUser
from common.utilities.gcp.cloud_logger import Logger, LoggerNames

from core.rubric import Rubric
from dependencies import build_id_path, get_cloud_env, teacher_required
from utilities.llm.rubric.rubric_generator import RubricGenerator

rubric_router = APIRouter(prefix="/rubrics")
logger = Logger(LoggerNames.API)
route_name = "rubrics"


@rubric_router.get("/{build_id}/")
def get_rubric(
    build_id: str = Depends(build_id_path),
    env_dict: dict = Depends(get_cloud_env),
    current_user: AgogeUser = Depends(teacher_required),
) -> AgogeResponse[RubricModel]:
    log_args = {
        'rubric_id': build_id,
        'user': current_user.uid
    }

    try:
        rubric = Rubric(env_dict=env_dict).get(build_id)
        return AgogeResponse(data=rubric)
    except NotFound as e:
        logger.error(f"{route_name}:get_rubric - {e.message}", **log_args)
        raise HTTPException(status_code=404)
    except BadRequest as e:
        logger.error(f"{route_name}:get_rubric - {e.message}", **log_args)
        raise HTTPException(status_code=400)


@rubric_router.post("/generate/{build_id}/")
def generate_rubric(
    rubric_params: dict = Body(...),
    env_dict: dict = Depends(get_cloud_env),
    current_user: AgogeUser = Depends(teacher_required),
) -> AgogeResponse:
    log_args = {
        'user': current_user.uid
    }

    try:
        logger.info(f'POST request to generate rubric')
        generator = RubricGenerator(env_dict=env_dict)
        generated_content = generator.generate_rubric(rubric_params)
        return AgogeResponse(data={"content": generated_content, "id": rubric_params["id"]})
    except BadRequest as e:
        msg = "Invalid request data. Please ensure all required fields are correctly filled and formated"
        logger.error(e.message, **log_args)
        raise HTTPException(status_code=400, detail=msg)
    except ServiceUnavailable as e:
        logger.error(e.message, **log_args)
        raise HTTPException(status_code=503, detail=e.message)
    except Exception as e:
        logger.error(f"{route_name}:generate_rubric - An unexpected error occurred: {e}",
                     **log_args, detail=str(e))
        raise HTTPException(status_code=500, detail="Failed to generate rubric.")


@rubric_router.patch("/{build_id}/")
async def update_rubric(
    request: Request,
    build_id: str = Depends(build_id_path),
    env_dict: dict = Depends(get_cloud_env),
    current_user: AgogeUser = Depends(teacher_required)
) -> Response:
    log_args = {
        'rubric_id': build_id,
        'user': current_user.uid,
        'origin': request.client.host
    }

    try:
        logger.info(
            f"PATCH request to update rubric with id {build_id} and current user {current_user}",
            **log_args
        )
        await Rubric(env_dict=env_dict).update(
            build_id=build_id,
            request=request,
            requester=current_user
        )
        return Response(status_code=200)
    except BadRequest as e:
        logger.error(e.message, **log_args)
        raise HTTPException(status_code=400, detail=e.message)
    except NotFound as e:
        logger.error(e.message, **log_args)
        raise HTTPException(404, detail=e.message)
    except Unauthorized as e:
        logger.error(e.message, **log_args)
        raise HTTPException(status_code=401, detail=e.message)
