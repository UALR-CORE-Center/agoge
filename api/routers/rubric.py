from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    Response,
    Body,
)

from common.exceptions import NotFound, BadRequest, Forbidden, Unauthorized, RateLimitExceeded, ServiceUnavailable
from common.models.agoge import RubricModel
from common.models.response import AgogeResponse
from common.models.users import AgogeUser
from common.utilities.gcp.cloud_logger import Logger, LoggerNames

from core.rubric import Rubric
from core.unit import Unit
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
    build_id: str = Depends(build_id_path),
    env_dict: dict = Depends(get_cloud_env),
    current_user: AgogeUser = Depends(teacher_required),
) -> AgogeResponse:
    log_args = {
        'rubric_id': build_id,
        'user': current_user.uid
    }

    try:
        if rubric_params.get("id", build_id) != build_id:
            raise BadRequest(message="The rubric ID must match the unit ID in the request URL.")
        # Reject old clients' automatic requests before loading any AI credentials.
        if rubric_params.get("confirm_ai_generation") is not True:
            raise BadRequest(message="AI rubric generation requires explicit confirmation that it uses OpenAI API credits.")
        unit = Unit(env_dict=env_dict).get(build_id, as_dict=True)
        if unit.get("rubric_support") is not True:
            raise Forbidden(message="Rubric generation is disabled for this lab. Its specification must explicitly enable rubric support.")
        rubric_params = {**rubric_params, "id": build_id}
        logger.info(f'POST request to generate rubric')
        generator = RubricGenerator(env_dict=env_dict)
        generated_content = generator.generate_rubric(rubric_params)
        return AgogeResponse(data={"content": generated_content, "id": rubric_params["id"]})
    except BadRequest as e:
        logger.error(e.message, **log_args)
        raise HTTPException(status_code=400, detail=e.message)
    except Forbidden as e:
        logger.warning(e.message, **log_args)
        raise HTTPException(status_code=403, detail=e.message)
    except NotFound as e:
        logger.warning(e.message, **log_args)
        raise HTTPException(status_code=404, detail=e.message)
    except RateLimitExceeded as e:
        logger.warning(e.message, **log_args)
        raise HTTPException(status_code=429, detail=e.message)
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
