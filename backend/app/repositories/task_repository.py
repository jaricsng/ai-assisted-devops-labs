from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import Task, TaskStatus, TaskPriority


async def get_all_for_project(db: AsyncSession, project_id: int) -> list[Task]:
    """Return all tasks belonging to a project."""
    result = await db.execute(select(Task).where(Task.project_id == project_id))
    return list(result.scalars().all())


async def get_by_id(db: AsyncSession, task_id: int) -> Task | None:
    """Return a single task by id, or None if not found."""
    return await db.get(Task, task_id)


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
    """Delete a task (cascades to comments)."""
    await db.delete(task)
    await db.commit()
