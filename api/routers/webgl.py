from os.path import exists

from fastapi import APIRouter, Depends, HTTPException, Request

from common.exceptions import NotFound, BadRequest, Forbidden
from common.models.response import AgogeIDResponse, AgogeResponse
from common.utilities.gcp.cloud_logger import Logger, LoggerNames
from core.webgl import WebGL
from core.workout import Workout
from dependencies import get_cloud_env

webgl_router = APIRouter(prefix="/webxr")
logger = Logger(LoggerNames.API)

@webgl_router.post("/token")
async def issue_jwt_token(
        request: Request,
        env_dict: dict = Depends(get_cloud_env),
):
    log_args = {
        'origin': request.client.host
    }
    json_data = await request.json()

    # If json doesn't have buildId then it is using email and join_code
    if json_data.get("buildId") is None:
        try:
            logger.info(f"POST request to create workout", **log_args)
            buildId, exists = Workout(env_dict=env_dict).build(json_data)
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
    elif json_data.get("buildId"):
        buildId = json_data["buildId"]
    else:
        msg = "Invalid request format. Either a buildId or a valid join_code and email must be provided."
        logger.error("Missing buildId, join_code, or email in request payload", details=msg, **log_args)
        raise HTTPException(status_code=400, detail=msg)

    try:
        token = WebGL(env_dict=env_dict).generate_jwt_token(buildId=buildId)
    except NotFound:
        msg = "Build ID not found. Please ensure the ID is correct."
        logger.error("buildId not found", details=msg, **log_args)
        raise HTTPException(status_code=404, detail=msg)
    except Exception as e:
        msg = "Failed to generate JWT token."
        logger.error(str(e), details=msg, **log_args)
        raise HTTPException(status_code=500, detail=msg)
    return {"buildId": buildId, "access_token": token, "token_type": "bearer"}

@webgl_router.post("/assessment")
async def save_score(
    request: Request,
    env_dict: dict = Depends(get_cloud_env)
) -> AgogeResponse[AgogeIDResponse]:
    json_data = await request.json()
    buildId: str = json_data.get("buildId")
    score = json_data.get("score")

    if buildId is None or score is None:
        raise HTTPException(status_code=422, detail="Build ID and score are required")

    log_args = {
        "origin": request.client.host,
        "buildId": buildId,
        "score": score,
    }
    try:
        logger.info(f"POST request to save score for id", **log_args)
        WebGL(env_dict=env_dict).save_score(data=json_data)
        return AgogeResponse(data={'buildId': buildId})
    except Exception as e:
        logger.error(f"POST request to save score for id {buildId}", exc_info=e)
        raise HTTPException(status_code=500, detail="Unable to save score")

@webgl_router.get("/.well-known/jwks.json")
async def get_jwks(env_dict: dict = Depends(get_cloud_env)):
    # This function is called from hivemq to fetch the public jwt key
    return WebGL(env_dict=env_dict).serve_jwk()
