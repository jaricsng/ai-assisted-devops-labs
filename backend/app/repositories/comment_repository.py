from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.comment import Comment


async def get_all_for_task(db: AsyncSession, task_id: int) -> list[Comment]:
    """Return all comments for a task, ordered by creation time."""
    result = await db.execute(
        select(Comment).where(Comment.task_id == task_id).order_by(Comment.created_at)
    )
    return list(result.scalars().all())


async def create(db: AsyncSession, task_id: int, author_id: int, body: str) -> Comment:
    """Insert a new comment and return the persisted instance."""
    comment = Comment(task_id=task_id, author_id=author_id, body=body)
    db.add(comment)
    await db.commit()
    await db.refresh(comment)
    return comment
