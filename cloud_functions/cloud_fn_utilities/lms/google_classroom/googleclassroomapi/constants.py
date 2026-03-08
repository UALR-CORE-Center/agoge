class Scopes:
    FULL = [
            'https://www.googleapis.com/auth/classroom.courses',
            'https://www.googleapis.com/auth/classroom.coursework.students',
            'https://www.googleapis.com/auth/classroom.rosters',
            'https://www.googleapis.com/auth/classroom.profile.emails'
    ]


class CourseRole:
    COURSE_ROLE_UNSPECIFIED = 'COURSE_ROLE_UNSPECIFIED'
    STUDENT = 'STUDENT'
    TEACHER = 'TEACHER'
    OWNER = 'OWNER'


class CourseState:
    ACTIVE = 'ACTIVE'
    PROVISIONED = 'PROVISIONED'
    ARCHIVED = 'ARCHIVED'


class CourseScopes:
    TEACHER = 'teacher'
    STUDENT = 'student'
    WORKSPACE = 'workspace'


class CourseWorkEnums:
    class CourseWorkState:
        PUBLISHED = 'PUBLISHED'
        DRAFT = 'DRAFT'
        DELETED = 'DELETED'

    class Material:
        LINK = {"url": "", "title": ""}
        FORM = {"formUrl": "", "responseUrl": "", "title": ""}

    class CourseWorkType:
        ASSIGNMENT = 'ASSIGNMENT'
        SHORT_ANSWER_QUESTION = 'SHORT_ANSWER_QUESTION'
        MULTIPLE_CHOICE_QUESTION = 'MULTIPLE_CHOICE_QUESTION'
        QUIZ = 'QUIZ'

    class SubmissionState:
        NEW = 'NEW'
        CREATED = 'CREATED'
        TURNED_IN = 'TURNED_IN'
        RETURNED = 'RETURNED'
        RECLAIMED_BY_STUDENT = 'RECLAIMED_BY_STUDENT'

    class SubmissionModificationMode:
        MODIFIABLE_UNTIL_TURNED_IN = 'MODIFIABLE_UNTIL_TURNED_IN'
        MODIFIABLE = 'MODIFIABLE'

    class GradeChangeType:
        DRAFT_GRADE_POINTS_EARNED_CHANGE = 'DRAFT_GRADE_POINTS_EARNED_CHANGE'
        ASSIGNED_GRADE_POINTS_EARNED_CHANGE = 'ASSIGNED_GRADE_POINTS_EARNED_CHANGE'
        MAX_POINTS_CHANGE = 'MAX_POINTS_CHANGE'

# [ eof ]
