class BlackboardException(Exception):
    def __init__(self, message):
        if isinstance(message, dict):
            self.error_report_id = message.get("error_report_id", None)

            errors = message.get("errors", False)
            if errors:
                self.message = errors
            else:
                self.message = ("Something went wrong. ", message)
        else:
            self.message = message

    def __str__(self):
        return str(self.message)


class BadRequest(BlackboardException):
    """Blackboard was unable to understand the request. More information may be needed."""

    pass


class InvalidAccessToken(BlackboardException):
    """BlackboardAPI was unable to make an API connection."""

    pass


class Unauthorized(BlackboardException):
    """BlackboardAPI's key is valid, but is unauthorized to access the requested resource."""

    pass


class ResourceDoesNotExist(BlackboardException):
    """Blackboard could not locate the requested resource."""

    pass


class RequiredFieldMissing(BlackboardException):
    """A required field is missing."""

    pass


class Forbidden(BlackboardException):
    """Blackboard has denied access to the resource for this user."""

    pass


class RateLimitExceeded(Forbidden):
    """
    Blackboard has received to many requests from this access token and is
    throttling this request. Try again later.
    """

    pass


class Conflict(BlackboardException):
    """Blackboard had a conflict with an existing resource."""

    pass


class UnprocessableEntity(BlackboardException):
    """Blackboard was unable to process the entity."""

    pass