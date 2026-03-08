from typing import List

from common.constants.build_constants import BuildConstants
from ..lms_synchronizer import LMSSynchronizer
from ..canvas.lms_canvas import LMSCanvas


class LMSCanvasSynchronizer(LMSSynchronizer):
    def __init__(self, env_dict: dict = None) -> None:
        super().__init__(env_dict=env_dict)

    def _filter_active_lms_units(
        self,
        active_units: List
    ) -> List:
        active_lms_units = []
        for unit in active_units:
            if (lms_integration := unit.get('lms_integration')) is not None:
                if lms_integration['lms_connection']['lms_type'] == BuildConstants.LMS.CANVAS:
                    active_lms_units.append(unit)
        return active_lms_units

    def _get_active_students(
        self,
        unit: dict
    ) -> List:
        if lms_integration := unit.get('lms_integration'):
            url = lms_integration['lms_connection']['url']
            api_key = lms_integration['lms_connection']['api_key']
            course_code = lms_integration['lms_connection']['course_code']
            course_key = f"{url}-{course_code}"

            # This cache speeds up the function in cases where courses have several quizzes
            if course_key not in self.student_list_cache:
                lms = LMSCanvas(
                    url=url,
                    api_key=api_key,
                    course_code=course_code,
                    build=unit
                )
                class_list = lms.get_class_list(suppress_logs=True)
                self.student_list_cache[course_key] = class_list
            else:
                class_list = self.student_list_cache[course_key]
            return class_list
        return []
