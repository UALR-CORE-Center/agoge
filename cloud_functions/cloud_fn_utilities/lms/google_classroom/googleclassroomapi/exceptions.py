class GoogleClassroomException(Exception):
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


class FailedPrecondition(GoogleClassroomException):
    pass


class Unauthorized(GoogleClassroomException):
    pass


class Forbidden(GoogleClassroomException):
    pass


class RateLimitExceeded(GoogleClassroomException):
    pass


class APIQuotaReached(GoogleClassroomException):
    pass


class ResourceNotFound(GoogleClassroomException):
    pass


class CourseUserNotFound(GoogleClassroomException):
    pass


class InvalidRequest(GoogleClassroomException):
    pass


class BadRequest(GoogleClassroomException):
    pass


class ResourceDoesNotExist(GoogleClassroomException):
    pass


class Conflict(GoogleClassroomException):
    pass


class UnprocessableEntity(GoogleClassroomException):
    pass


class InvalidCourseWorkObject(GoogleClassroomException):
    pass
