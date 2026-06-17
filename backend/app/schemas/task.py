from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, StringConstraints

from app.models.task import TaskPriority, TaskStatus


class TaskCreate(BaseModel):
    title: Annotated[str, StringConstraints(min_length=1, max_length=255)]
    description: Annotated[str | None, StringConstraints(max_length=2000)] = None
    priority: TaskPriority = TaskPriority.MEDIUM
    assignee_id: int | None = None
    due_date: date | None = None


class TaskUpdate(BaseModel):
    title: Annotated[str | None, StringConstraints(min_length=1, max_length=255)] = None
    description: Annotated[str | None, StringConstraints(max_length=2000)] = None
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    assignee_id: int | None = None
    due_date: date | None = None


class TaskRead(BaseModel):
    id: int
    project_id: int
    title: str
    description: str | None
    status: TaskStatus
    priority: TaskPriority
    assignee_id: int | None
    due_date: date | None
    created_at: datetime

    model_config = {"from_attributes": True}
