from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, StringConstraints


class CommentCreate(BaseModel):
    body: Annotated[str, StringConstraints(min_length=1, max_length=5000)]


class CommentRead(BaseModel):
    id: int
    task_id: int
    author_id: int
    body: str
    created_at: datetime

    model_config = {"from_attributes": True}
