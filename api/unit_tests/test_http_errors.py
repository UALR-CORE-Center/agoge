import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field, ValidationError

from common.exceptions.agoge import (
    AgogeValidationError,
    BadRequest,
    Conflict,
    Forbidden,
    NotAllowed,
    NotFound,
    PreconditionFailed,
    RateLimitExceeded,
    ServiceUnavailable,
    Unauthorized,
)
from utilities import http_errors
from utilities.http_errors import to_http_exception


@pytest.fixture
def logged(monkeypatch):
    calls = []
    monkeypatch.setattr(http_errors.logger, "error", lambda message, **kwargs: calls.append((message, kwargs)))
    return calls


@pytest.mark.parametrize(
    "exc, status, detail",
    [
        (BadRequest("Unknown action 'explode'"), 400, "Unknown action 'explode'"),
        (AgogeValidationError("Flag f1 references unknown server"), 400, "Flag f1 references unknown server"),
        (NotFound("CTF event not found"), 404, "CTF event not found"),
        (Conflict("Cannot start an event in state DRAFT"), 409, "Cannot start an event in state DRAFT"),
        (Conflict("Submissions are closed."), 409, "Submissions are closed."),
        (
            RateLimitExceeded("Too many submissions for this challenge. Try again in 42 seconds."),
            429,
            "Too many submissions for this challenge. Try again in 42 seconds.",
        ),
    ],
)
def test_message_passthrough_rows(exc, status, detail, logged):
    result = to_http_exception(exc)

    assert isinstance(result, HTTPException)
    assert result.status_code == status
    assert result.detail == detail
    assert logged == []


# These rows use fixed text so a core message (instructor lists, secret names) never reaches the caller.
@pytest.mark.parametrize(
    "exc, status, detail",
    [
        (Unauthorized("user x not in instructors of unit abc"), 403, http_errors.UNAUTHORIZED_DETAIL),
        (Forbidden("role student < teacher"), 403, "Insufficient permissions"),
        (
            ServiceUnavailable("secret ctf_flag_seed missing"),
            503,
            "CTF is not provisioned on this deployment. Ask an administrator to enable it in setup.",
        ),
    ],
)
def test_fixed_text_rows(exc, status, detail):
    result = to_http_exception(exc)

    assert result.status_code == status
    assert result.detail == detail


def test_unauthorized_is_403_not_401():
    # 401 stays reserved for a missing/invalid Firebase token (verify_token).
    assert to_http_exception(Unauthorized()).status_code == 403
    assert http_errors.UNAUTHORIZED_DETAIL == "Requesting user is not authorized to make this request"


def test_http_exception_passes_through_unchanged():
    original = HTTPException(status_code=401, detail="Invalid token")

    assert to_http_exception(original) is original


@pytest.mark.parametrize("exc", [RuntimeError("db exploded at /secret/path"), KeyError("ctf_id"),
                                 PreconditionFailed("stale fingerprint"), NotAllowed("nope")])
def test_unhandled_is_generic_500_and_logs_cause(exc, logged):
    result = to_http_exception(exc)

    assert result.status_code == 500
    assert result.detail == "Something went wrong"
    assert len(logged) == 1
    message, kwargs = logged[0]
    assert type(exc).__name__ in message
    assert str(exc) in message
    assert kwargs["error_type"] == type(exc).__name__


class _Spec(BaseModel):
    points: int = Field(ge=1)


def test_pydantic_validation_error_is_400_without_input_values(logged):
    with pytest.raises(ValidationError) as caught:
        _Spec(points=-987654)

    result = to_http_exception(caught.value)

    assert result.status_code == 400
    assert result.detail.startswith("Invalid specification: points:")
    assert "-987654" not in result.detail
    assert logged == []


def test_wire_shape_through_fastapi():
    # The frontend's handleError reads e.response.data.detail, so the body must be {"detail": "..."}.
    app = FastAPI()

    @app.get("/conflict")
    def conflict():
        try:
            raise Conflict("Cannot pause an event in state ARMED")
        except Exception as e:
            raise to_http_exception(e) from e

    @app.get("/boom")
    def boom():
        try:
            raise RuntimeError("internal detail")
        except Exception as e:
            raise to_http_exception(e) from e

    client = TestClient(app)

    response = client.get("/conflict")
    assert response.status_code == 409
    assert response.json() == {"detail": "Cannot pause an event in state ARMED"}

    response = client.get("/boom")
    assert response.status_code == 500
    assert response.json() == {"detail": "Something went wrong"}
