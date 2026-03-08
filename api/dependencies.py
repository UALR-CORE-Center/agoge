import os

from fastapi import Depends, Security, Request, HTTPException, Path
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from firebase_admin import auth
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from typing import Optional

from common.exceptions.agoge import BadRequest, Forbidden, NotFound, Unauthorized
from common.models.users import AgogeUser, AnonymousAppUser
from common.utilities.gcp.cloud_logger import Logger, LoggerNames

from core.users import Users

security = HTTPBearer()
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
        return verify_token(request=request, token=token)
    return AnonymousAppUser()


def teacher_required(
    current_user: AgogeUser = Depends(get_current_user)
) -> AgogeUser:
    if not current_user.is_authorized:
        logger.error("Insufficient permissions")
        raise Forbidden("Insufficient permissions")
    return current_user


def admin_required(
    current_user: AgogeUser = Depends(get_current_user)
) -> AgogeUser:

    if not current_user.is_admin:
        logger.error("Insufficient permissions")
        raise Forbidden("Insufficient permissions")
    return current_user


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


def verify_request_origin(request: Request):
    """
    Verifies that the request is coming from an authorized source,
    such as the React application running on Cloud Run.

    Args:
        request (Request): The incoming FastAPI request object.

    Raises:
        HTTPException: If the origin is invalid.
    """
    auth_header = request.headers.get("Authorization")

    if not auth_header or not auth_header.startswith("Bearer "):
        msg = "Missing or invalid authorization header"
        logger.error(msg)
        raise HTTPException(status_code=403, detail=msg)
    try:
        # Extract the bearer token
        identity_token = auth_header.split(" ")[1]

        # Verify the identity token with Google
        audience = os.getenv("SERVICE_URL")
        id_info = id_token.verify_oauth2_token(identity_token, google_requests.Request(), audience)

        # Check that the token was issued to the correct service account
        expected_email = 'agoge-react-service@agoge-test-427119.iam.gserviceaccount.com'
        if id_info['email'] != expected_email:
            msg = "Unauthorized request: Invalid token issuer"
            logger.error(msg)
            raise HTTPException(status_code=403, detail=msg)

        # Token is valid; request is authorized
        return True

    except ValueError as e:
        # This exception is raised for token verification issues
        logger.error(f"Token verification failed: {str(e)}")
        raise HTTPException(status_code=401, detail="Token verification failed")

    except KeyError:
        logger.error("Token missing required email claim")
        raise HTTPException(status_code=401, detail="Missing auth token")

    except Exception as e:
        # Catch other exceptions and raise an HTTPException
        logger.error(f"Internal Server Error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
