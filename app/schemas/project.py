from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ProjectDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str = Field(description="Unique Project identifier(UUID)")
    user_id: str = Field(description="Owner User Identifier(UUID String)")
    name:str = Field(description="Display or folder name of the Project")
    root_path : str = Field(description = "Absolute local file system directory path")

    description:str | None = Field(default=None, description="Optional Projecyt Overview")
    created_at : datetime | None = Field(default=None)
    updated_at: datetime | None = Field(default=None)




