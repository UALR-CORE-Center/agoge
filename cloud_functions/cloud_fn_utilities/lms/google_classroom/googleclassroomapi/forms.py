from .google_classroom_object import GoogleClassroomObject
from .constants import CourseWorkEnums


class Forms(GoogleClassroomObject):
    def __init__(self, client, unit):
        super().__init__(client)
        self.class_name = self.__class__.__name__
        self.unit = unit
        if 'assessment' in self.unit:
            self.assessment = unit.get('assessment')
        elif 'lms_integration' in self.unit:
            self.assessment = self.unit['lms_integration']
        else:
            raise ValueError('No assessment object found')
        self.form = None

    def create(self):
        # Build form body from assessment object
        form_body = {
            # TODO: Create this object
        }
        request = self._client.forms().create(body=form_body)
        form_response = self._make_request(request, 'create')
        if form_response:
            self.form = form_response

    def create_quiz_from_form(self):
        """Converts a Google Form into a quiz format"""
        pass

    def delete(self, *args, **kwargs):
        raise NotImplementedError(f"{self.class_name}:delete - Method not implemented")

    def update(self, *args, **kwargs):
        raise NotImplementedError(f"{self.class_name}:update - Method not implemented")

    def get(self, *args, **kwargs):
        raise NotImplementedError(f"{self.class_name}:get - Method not implemented")

    def list(self, *args, **kwargs):
        raise NotImplementedError(f"{self.class_name}:list - Method not implemented")

# [ eof ]
