from pydantic import BaseModel, Field
from typing import List, Optional


class LMSCourseOwner(BaseModel):
    id: str = Field(..., description="ID of LMS course owner")
    email: Optional[str] = Field(default=None, description="Optional email of course owner")


class LMSCourse(BaseModel):
    id: str
    name: str
    owner: Optional[LMSCourseOwner] = None
    teachers: Optional[List] = Field(default=None, description="List of teachers assigned to course")


class Courses(BaseModel):
    canvas: Optional[List[LMSCourse]] = None
    blackboard: Optional[List[LMSCourse]] = None
    classroom: Optional[List[LMSCourse]] = None
