import firebase_admin
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Response, Request, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
from dotenv import load_dotenv

from common.models.users import SafeAgogeUser
from common.models.response import AgogeResponse
from common.utilities.gcp.cloud_env import CloudEnv
from common.utilities.gcp.cloud_logger import Logger, LoggerNames
from common.exceptions import BadRequest, Unauthorized, Forbidden

from app_config import AppConfig
from dependencies import verify_token
from routers.puzzle_control import puzzle_control_router
from routers.rubric import rubric_router
from routers.webgl import webgl_router

# Routers
from routers.compute_image import compute_image_router
from routers.compute_snapshot import compute_snapshot_router
from routers.docs import docs_router
from routers.guacamole import guacamole_router
from routers.lab_specs import lab_spec_router
from routers.llm_agent import llm_agent_router
from routers.project import project_router
from routers.unit import unit_router
from routers.user import user_router
from routers.workout import workout_router
from routers.wireguard import wireguard_router

logger = Logger(log_name=LoggerNames.API)

load_dotenv()

app_config = AppConfig()


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.cloud_env = CloudEnv(log_name=LoggerNames.API)
    yield

app = FastAPI(
    lifespan=lifespan,
    docs_url=None if not app_config.is_development else "/docs",
    redoc_url=None if not app_config.is_development else "/redoc",
    openapi_url=None if not app_config.is_development else "/openapi.json",
)

# Add Middleware
origins = app_config.origins()
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")

hosts = app_config.hosts()
app.add_middleware(TrustedHostMiddleware, allowed_hosts=hosts)

# Initialize Firebase
firebase_admin.initialize_app()
cloud_env = None

# Add APIRouters
app.include_router(compute_image_router)
app.include_router(compute_snapshot_router)
app.include_router(docs_router)
app.include_router(guacamole_router)
app.include_router(lab_spec_router)
app.include_router(unit_router)
app.include_router(workout_router)
app.include_router(user_router)
app.include_router(llm_agent_router)
app.include_router(rubric_router)
app.include_router(project_router)
app.include_router(puzzle_control_router)
app.include_router(webgl_router)
app.include_router(wireguard_router)


@app.get("/")
async def root():
    return Response("Server is running!")


@app.options("/auth/")
async def options_auth(response: Response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
    response.status_code = 200
    return response


@app.post("/auth/")
async def authenticate(
    request: Request,
    token: HTTPAuthorizationCredentials = Security(HTTPBearer()),
) -> AgogeResponse[SafeAgogeUser]:
    """
    Processes Firebase authentication token and authorizes with Agoge API
    Args:
        request (object): Request event object
        token (str): Firebase authentication token

    Returns: Redirect URL and SafeAgogeUser
    """
    try:
        user = verify_token(request=request, token=token)
        if user.is_authorized:
            safe_user = SafeAgogeUser.from_agoge_user(user)
            return AgogeResponse(redirect="/teacher/home", data=safe_user)
        else:
            return AgogeResponse(redirect="/student/join")
    except Unauthorized as e:
        raise HTTPException(status_code=401, detail=e.message)
    except BadRequest as e:
        raise HTTPException(status_code=400, detail=e.message)
    except Forbidden as e:
        raise HTTPException(status_code=403, detail=e.message)
    except Exception as e:
        logger.error(message=str(e), method="main.authenticate")
        raise HTTPException(status_code=500, detail="Something went wrong")


@app.get('/whoami')
async def who_am_i(request: Request) -> AgogeResponse:
    ip = request.client.host
    logger.info(f'Who am I? Who are you?? {ip}')
    return AgogeResponse(data={'requester': ip})


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

# [ eof ]
