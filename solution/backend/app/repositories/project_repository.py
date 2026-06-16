from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project


async def get_all_for_user(db: AsyncSession, owner_id: int) -> list[Project]:
    """Return all active projects owned by the given user."""
    result = await db.execute(
        select(Project).where(Project.owner_id == owner_id, Project.deleted_at.is_(None))
    )
    return list(result.scalars().all())


async def get_by_id(db: AsyncSession, project_id: int) -> Project | None:
    """Return a single active project by id, or None if not found or deleted."""
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.deleted_at.is_(None))
    )
    return result.scalar_one_or_none()


async def create(db: AsyncSession, name: str, description: str | None, owner_id: int) -> Project:
    """Insert a new project and return the persisted instance."""
    project = Project(name=name, description=description, owner_id=owner_id)
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


async def delete(db: AsyncSession, project: Project) -> None:
    """Soft-delete a project by setting deleted_at to the current UTC time."""
    project.deleted_at = datetime.now(timezone.utc)
    await db.commit()
