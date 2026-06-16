from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import Task, TaskPriority, TaskStatus


async def get_all_for_project(db: AsyncSession, project_id: int) -> list[Task]:
    """Return all active tasks belonging to a project."""
    result = await db.execute(
        select(Task).where(Task.project_id == project_id, Task.deleted_at.is_(None))
    )
    return list(result.scalars().all())


async def get_filtered(
    db: AsyncSession,
    project_id: int,
    status: TaskStatus | None = None,
    priority: TaskPriority | None = None,
) -> list[Task]:
    """Return active tasks for a project, optionally filtered by status and/or priority."""
    conditions = [Task.project_id == project_id, Task.deleted_at.is_(None)]
    if status is not None:
        conditions.append(Task.status == status)
    if priority is not None:
        conditions.append(Task.priority == priority)
    result = await db.execute(select(Task).where(*conditions))
    return list(result.scalars().all())


async def get_by_id(db: AsyncSession, task_id: int) -> Task | None:
    """Return a single active task by id, or None if not found or deleted."""
    result = await db.execute(
        select(Task).where(Task.id == task_id, Task.deleted_at.is_(None))
    )
    return result.scalar_one_or_none()


async def create(
    db: AsyncSession,
    project_id: int,
    title: str,
    description: str | None,
    priority: TaskPriority,
    assignee_id: int | None,
    due_date,
) -> Task:
    """Insert a new task with default TODO status and return the persisted instance."""
    task = Task(
        project_id=project_id,
        title=title,
        description=description,
        status=TaskStatus.TODO,
        priority=priority,
        assignee_id=assignee_id,
        due_date=due_date,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


async def save(db: AsyncSession, task: Task) -> Task:
    """Persist changes to an existing task and return the refreshed instance."""
    await db.commit()
    await db.refresh(task)
    return task


async def delete(db: AsyncSession, task: Task) -> None:
    """Soft-delete a task by setting deleted_at to the current UTC time."""
    task.deleted_at = datetime.now(timezone.utc)
    await db.commit()
