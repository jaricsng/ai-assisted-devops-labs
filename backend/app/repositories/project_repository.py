from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project


async def get_all_for_user(db: AsyncSession, owner_id: int) -> list[Project]:
    """Return all projects owned by the given user."""
    result = await db.execute(select(Project).where(Project.owner_id == owner_id))
    return list(result.scalars().all())


async def get_by_id(db: AsyncSession, project_id: int) -> Project | None:
    """Return a single project by id, or None if not found."""
    return await db.get(Project, project_id)


async def create(db: AsyncSession, name: str, description: str | None, owner_id: int) -> Project:
    """Insert a new project and return the persisted instance."""
    project = Project(name=name, description=description, owner_id=owner_id)
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


async def delete(db: AsyncSession, project: Project) -> None:
    """Delete a project (cascades to tasks and comments)."""
    await db.delete(project)
    await db.commit()
