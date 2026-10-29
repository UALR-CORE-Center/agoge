from fastapi import Depends, Security, Request, HTTPException, Path, Query, WebSocketException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from firebase_admin import auth
from typing import Optional

from common.exceptions.agoge import BadRequest, NotFound, Unauthorized
from common.models.users import AgogeUser, AnonymousAppUser
from common.utilities.gcp.cloud_logger import Logger, LoggerNames

from core.ctf.config import is_ctf_enabled
from core.users import Users

security = HTTPBearer()
optional_security = HTTPBearer(auto_error=False)
logger = Logger(log_name=LoggerNames.API)


def get_cloud_env(request: Request):
    return request.app.state.cloud_env.get_env()


def build_id_path(build_id: str = Path(..., regex="^[a-z]{10}$")):
    return build_id


def get_current_user(
    request: Request,
    token: Optional[HTTPAuthorizationCredentials] = Security(security)
) -> AgogeUser:
    if token:
        # Dependencies resolve outside each route's try/except, so custom
        # exceptions must become HTTPExceptions here or FastAPI returns a 500.
        try:
            return verify_token(request=request, token=token)
        except Unauthorized as e:
            raise HTTPException(status_code=401, detail=e.message)
        except BadRequest as e:
            raise HTTPException(status_code=400, detail=e.message)
    return AnonymousAppUser()


def get_optional_user(
    request: Request,
    token: Optional[HTTPAuthorizationCredentials] = Security(optional_security)
) -> AgogeUser:
    """Like get_current_user, but a missing Authorization header yields AnonymousAppUser
    instead of a 403, for routes that serve both anonymous students and instructors."""
    return get_current_user(request=request, token=token)


def teacher_required(
    current_user: AgogeUser = Depends(get_current_user)
) -> AgogeUser:
    if not current_user.is_authorized:
        logger.error("Insufficient permissions")
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    return current_user


def admin_required(
    current_user: AgogeUser = Depends(get_current_user)
) -> AgogeUser:

    if not current_user.is_admin:
        logger.error("Insufficient permissions")
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    return current_user


def websocket_admin_required(
    token: Optional[str] = Query(None, description="Firebase ID token")
) -> AgogeUser:
    """admin_required for WebSocket routes. Browsers cannot set an Authorization header on a
    WebSocket, so the ID token arrives as ?token=. Raising before accept() rejects the handshake."""
    user = None
    if token:
        try:
            user = verify_token(
                request=None,
                token=HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
            )
        except (Unauthorized, BadRequest):
            user = None
    if not user or not user.is_admin:
        logger.error("Insufficient permissions")
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason="Insufficient permissions")
    return user


def ctf_enabled_required() -> None:
    # 404 rather than 403 so a disabled deployment doesn't reveal the CTF routes exist (SC-19).
    if not is_ctf_enabled():
        raise HTTPException(status_code=404, detail="Not Found")


def verify_token(
    request: Request,
    token: HTTPAuthorizationCredentials = Security(security)
) -> AgogeUser:
    try:
        decoded_token = auth.verify_id_token(token.credentials)
    except auth.InvalidIdTokenError:
        logger.error("Authentication failed! Invalid token")
        raise Unauthorized("Authentication failed! Invalid token")
    except Exception as e:
        logger.error("Unexpected error occurred", error=str(e))
        raise BadRequest("Unexpected error occurred")

    # TODO: Relying on email is not the optimal choice; Consider verifying project
    #   as well. email exists + project
    email = decoded_token.get('email')
    try:
        agoge_user = Users().get_user(user_email=email)
    except NotFound as e:
        logger.error(f"Authentication failed! {e.message}")
        raise Unauthorized(f"Authentication failed! {e.message}")

    user_name = decoded_token.get('name')
    agoge_user.set_default_name_or_email(user_name)
    return agoge_user
