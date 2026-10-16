from fastapi import HTTPException
from pydantic import ValidationError

from common.exceptions.agoge import (
    AgogeValidationError,
    BadRequest,
    Conflict,
    Forbidden,
    NotFound,
    RateLimitExceeded,
    ServiceUnavailable,
    Unauthorized,
)
from common.utilities.gcp.cloud_logger import Logger, LoggerNames

logger = Logger(LoggerNames.API, class_name='HttpErrors')

UNAUTHORIZED_DETAIL = "Requesting user is not authorized to make this request"
FORBIDDEN_DETAIL = "Insufficient permissions"
SERVICE_UNAVAILABLE_DETAIL = (
    "CTF is not provisioned on this deployment. Ask an administrator to enable it in setup."
)
UNHANDLED_DETAIL = "Something went wrong"

# Exception type → (status, fixed detail). A None detail means the exception's own message is the
# body. Unauthorized/Forbidden/ServiceUnavailable use fixed text so a core message can never leak
# internals (e.g. which instructor list was checked, or the secret name) to the caller.
_MAPPING = (
    (BadRequest, 400, None),
    (AgogeValidationError, 400, None),
    (Unauthorized, 403, UNAUTHORIZED_DETAIL),
    (Forbidden, 403, FORBIDDEN_DETAIL),
    (NotFound, 404, None),
    (Conflict, 409, None),
    (RateLimitExceeded, 429, None),
    (ServiceUnavailable, 503, SERVICE_UNAVAILABLE_DETAIL),
)


def to_http_exception(e: Exception) -> HTTPException:
    """
    Translates an exception raised by api/core into the HTTPException a CTF router raises, per the
    PRD's Error Handling table. Usage: `except Exception as e: raise to_http_exception(e) from e`.
    Only the CTF routers use this; existing routers keep their own mappings.
    """
    if isinstance(e, HTTPException):
        # Already translated (e.g. raised by a dependency); pass it through unchanged.
        return e

    for exception_type, status_code, detail in _MAPPING:
        if isinstance(e, exception_type):
            return HTTPException(status_code=status_code, detail=detail or str(e))

    if isinstance(e, ValidationError):
        # A malformed ctf block surfaces from the spec validators as a pydantic error. Report where
        # and what, but never the offending input values.
        problems = "; ".join(
            f"{'.'.join(str(part) for part in error['loc']) or 'body'}: {error['msg']}"
            for error in e.errors()
        )
        return HTTPException(status_code=400, detail=f"Invalid specification: {problems}")

    logger.error(f"HttpErrors - Unhandled {type(e).__name__}: {e}", error_type=type(e).__name__)
    return HTTPException(status_code=500, detail=UNHANDLED_DETAIL)
