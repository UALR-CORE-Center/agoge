
class BaseAgogeException(Exception):
    def __init__(self, message: str = None):
        if isinstance(message, dict):
            self.error_report_id = message.get("error_report_id", None)

            errors = message.get("errors", False)
            if errors:
                self.message = errors
            else:
                self.message = ("Something went wrong. ", message)
        elif message:
            self.message = message
        else:
            self.message = "An error occurred."

    def __str__(self):
        return str(self.message)


class BadRequest(BaseAgogeException):
    pass


class ContentTooLarge(BaseAgogeException):
    pass


class Forbidden(BaseAgogeException):
    pass


class NotFound(BaseAgogeException):
    pass


class OperationTimeout(BaseAgogeException):
    pass


class RateLimitExceeded(BaseAgogeException):
    pass


class Conflict(BaseAgogeException):
    pass


class Unauthorized(BaseAgogeException):
    pass


class ServiceUnavailable(BaseAgogeException):
    pass


class NotReady(BaseAgogeException):
    pass


class AgogeValidationError(BaseAgogeException):
    pass


class GuacamoleServerNotFound(BaseAgogeException):
    pass


class GuacamoleSessionNotFound(BaseAgogeException):
    pass


class GuacamoleInvalidSession(BaseAgogeException):
    pass


class GuacamoleUserNotFound(BaseAgogeException):
    pass


class NotAllowed(BaseAgogeException):
    pass


class ResourceExhausted(BaseAgogeException):
    pass
