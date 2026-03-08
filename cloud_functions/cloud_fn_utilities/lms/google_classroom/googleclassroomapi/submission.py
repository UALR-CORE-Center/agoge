from .google_classroom_object import GoogleClassroomObject


class Submission(GoogleClassroomObject):

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
