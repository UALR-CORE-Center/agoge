from typing import Union
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)
from google.cloud.datastore import Entity

from common.exceptions import (
    NotFound,
    GuacamoleInvalidSession,
    GuacamoleServerNotFound,
    GuacamoleSessionNotFound,
    GuacamoleUserNotFound, BadRequest
)
from common.models.response import AgogeResponse
from common.utilities.gcp.cloud_logger import Logger, LoggerNames

from core.guacamole_api import Guacamole
from dependencies import get_cloud_env

guacamole_router = APIRouter(
    prefix="/guacamole"
)
logger = Logger(LoggerNames.API)


@guacamole_router.get('/{build_id}/servers/{server_idx}/')
async def get_connection(
    build_id: str,
    server_idx: str,
    env_dict: dict = Depends(get_cloud_env),
) -> AgogeResponse:
    try:
        session = (
            Guacamole(build_id=build_id, env_dict=env_dict)
            .get_connection_from_server(server_idx)
        )
        return AgogeResponse(data=session)
    except BadRequest as e:
        logger.warning(e.message, build_id=build_id, server_idx=server_idx)
        raise HTTPException(status_code=400, detail=e.message)
    except NotFound as e:
        logger.warning(e.message, build_id=build_id, server_idx=server_idx)
        raise HTTPException(status_code=404, detail=e.message)
    except GuacamoleSessionNotFound as e:
        logger.warning(e.message, build_id=build_id, server_idx=server_idx)
        raise HTTPException(status_code=404, detail=e.message)
    except GuacamoleUserNotFound as e:
        logger.warning(e.message, build_id=build_id, server_idx=server_idx)
        raise HTTPException(status_code=404, detail="Requested user not found")
    except GuacamoleServerNotFound as e:
        logger.warning(e.message, build_id=build_id, server_idx=server_idx)
        raise HTTPException(status_code=404, detail=e.message)
    except GuacamoleInvalidSession as e:
        logger.warning(e.message, build_id=build_id, server_idx=server_idx)
        raise HTTPException(status_code=503, detail=e.message)
    except Exception as e:
        logger.warning(str(e), build_id=build_id, server_idx=server_idx)
        raise HTTPException(status_code=500, detail=str(e))
