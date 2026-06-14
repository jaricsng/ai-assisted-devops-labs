from datetime import datetime
from pydantic import BaseModel


class CommentCreate(BaseModel):
    body: str


class CommentRead(BaseModel):
    id: int
    task_id: int
    author_id: int
    body: str
    created_at: datetime

    model_config = {"from_attributes": True}
