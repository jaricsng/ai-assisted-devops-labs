from datetime import datetime
from typing import Annotated
from pydantic import BaseModel, StringConstraints


class ProjectCreate(BaseModel):
    name: Annotated[str, StringConstraints(min_length=1, max_length=255)]
    description: Annotated[str | None, StringConstraints(max_length=2000)] = None


class ProjectRead(BaseModel):
    id: int
    name: str
    description: str | None
    owner_id: int
    created_at: datetime

    model_config = {"from_attributes": True}
