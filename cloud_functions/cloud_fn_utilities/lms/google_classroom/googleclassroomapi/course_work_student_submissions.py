from .google_classroom_object import GoogleClassroomObject
from .constants import CourseWorkEnums


class CourseWorkStudentSubmissions(GoogleClassroomObject):
    def __init__(self, client):
        super().__init__(client)
        self.class_name = self.__class__.__name__
        self.course_work_enums = CourseWorkEnums

    def create(self, *args, **kwargs):
        raise NotImplementedError(f"{self.class_name}:create - Method not implemented")

    def delete(self, *args, **kwargs):
        raise NotImplementedError(f"{self.class_name}:delete - Method not implemented")

    def update(self, *args, **kwargs):
        raise NotImplementedError(f"{self.class_name}:update - Method not implemented")

    def get(self, *args, **kwargs):
        raise NotImplementedError(f"{self.class_name}:get - Method not implemented")

    def list(self, *args, **kwargs):
        raise NotImplementedError(f"{self.class_name}:list - Method not implemented")

# [ eof ]
