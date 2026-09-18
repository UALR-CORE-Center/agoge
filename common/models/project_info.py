from pydantic import (
    BaseModel,
    Field
)
from typing import List, Optional, Union, Any, Dict
from datetime import datetime

class ProjectContact(BaseModel):
    """
    Contact information for a given project.
    """
    contact_name: str = Field(..., description="Name of the contact")
    contact_email: Optional[str] = Field(default=None, description="The contact email")
    contact_phone: Optional[str] = Field(default=None, description="The contact phone")
    primary_contact: Optional[bool] = Field(default=False, description="Whether the contact is primary")

class ProjectInfo(BaseModel):
    """
    Information about a distinct Agoge project.
    """
    project_name: str = Field(..., description="Name of the project")
    impersonation_account: str = Field(..., description="The account used for managing the project services")
    tenant_name: str = Field(..., description="The name of the tenant (e.g. company, school, unit, etc.)")
    setup_menu_name: Optional[str] = Field(default=None, description="Optional label shown by the setup project menu")
    setup_menu_hidden: bool = Field(default=False, description="Hide this project from the setup menu")
    created_date: datetime = Field(..., description="The date the project was created")
    last_modified: datetime = Field(..., description="The date the project was last modified")
    deployed_version: Optional[str] = Field(default=None, description="The overall version of the project deployed")
    git_commit: Optional[str] = Field(default=None, description="The git commit hash of the project")
    contacts: Optional[List[ProjectContact]] = Field(default=None, description="The contacts associated with the "
                                                                               "project")
