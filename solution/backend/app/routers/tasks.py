import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.business_metrics import tasks_created_total
from app.database import get_db
from app.models.task import TaskPriority, TaskStatus
from app.models.user import User
from app.repositories import comment_repository, project_repository, task_repository
from app.routers.deps import current_user
from app.schemas.comment import CommentCreate, CommentRead
from app.schemas.task import TaskCreate, TaskRead, TaskUpdate
from app.services.task_service import apply_task_update

router = APIRouter(tags=["tasks"])
logger = structlog.get_logger(__name__)


async def _get_project_or_404(db, project_id: int, user_id: int):
    project = await project_repository.get_by_id(db, project_id)
    if not project or project.owner_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    return project


async def _get_task_or_404(db, task_id: int, project_id: int):
    task = await task_repository.get_by_id(db, task_id)
    if not task or task.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.")
    return task


@router.get("/projects/{project_id}/tasks", response_model=list[TaskRead])
async def list_tasks(
    project_id: int,
    status: TaskStatus | None = None,
    priority: TaskPriority | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_user),
):
    await _get_project_or_404(db, project_id, user.id)
    if status is not None or priority is not None:
        return await task_repository.get_filtered(db, project_id, status=status, priority=priority)
    return await task_repository.get_all_for_project(db, project_id)


@router.post("/projects/{project_id}/tasks", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
async def create_task(
    project_id: int,
    payload: TaskCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_user),
):
    await _get_project_or_404(db, project_id, user.id)
    task = await task_repository.create(
        db,
        project_id=project_id,
        title=payload.title,
        description=payload.description,
        priority=payload.priority,
        assignee_id=payload.assignee_id,
        due_date=payload.due_date,
    )
    logger.info("audit", action="TASK_CREATED", resource="task", resource_id=task.id, project_id=project_id)
    tasks_created_total.inc()
    return task


@router.get("/projects/{project_id}/tasks/{task_id}", response_model=TaskRead)
async def get_task(
    project_id: int,
    task_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_user),
):
    await _get_project_or_404(db, project_id, user.id)
    return await _get_task_or_404(db, task_id, project_id)


@router.patch("/projects/{project_id}/tasks/{task_id}", response_model=TaskRead)
async def update_task(
    project_id: int,
    task_id: int,
    payload: TaskUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_user),
):
    await _get_project_or_404(db, project_id, user.id)
    task = await _get_task_or_404(db, task_id, project_id)
    updated = apply_task_update(task, payload)
    result = await task_repository.save(db, updated)
    logger.info("audit", action="TASK_UPDATED", resource="task", resource_id=task_id, project_id=project_id)
    return result


@router.delete("/projects/{project_id}/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    project_id: int,
    task_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_user),
):
    await _get_project_or_404(db, project_id, user.id)
    task = await _get_task_or_404(db, task_id, project_id)
    await task_repository.delete(db, task)
    logger.info("audit", action="TASK_DELETED", resource="task", resource_id=task_id, project_id=project_id)


@router.get("/projects/{project_id}/tasks/{task_id}/comments", response_model=list[CommentRead])
async def list_comments(
    project_id: int,
    task_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_user),
):
    await _get_project_or_404(db, project_id, user.id)
    await _get_task_or_404(db, task_id, project_id)
    return await comment_repository.get_all_for_task(db, task_id)


@router.post(
    "/projects/{project_id}/tasks/{task_id}/comments",
    response_model=CommentRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_comment(
    project_id: int,
    task_id: int,
    payload: CommentCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_user),
):
    await _get_project_or_404(db, project_id, user.id)
    await _get_task_or_404(db, task_id, project_id)
    comment = await comment_repository.create(db, task_id, user.id, payload.body)
    logger.info("audit", action="COMMENT_CREATED", resource="comment", resource_id=comment.id, task_id=task_id)
    return comment
