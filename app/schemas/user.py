from datetime import datetime

from pydantic import BaseModel
from pydantic import ConfigDict


class UserDTO(BaseModel):
    id: str
    created_at: datetime | None = None
    model_config = ConfigDict(from_attributes=True)
