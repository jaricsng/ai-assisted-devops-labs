import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.business_metrics import projects_created_total
from app.database import get_db
from app.models.user import User
from app.repositories import project_repository
from app.routers.deps import current_user
from app.schemas.project import ProjectCreate, ProjectRead

router = APIRouter(prefix="/projects", tags=["projects"])
logger = structlog.get_logger(__name__)


@router.get("", response_model=list[ProjectRead])
async def list_projects(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_user),
):
    return await project_repository.get_all_for_user(db, user.id)


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_user),
):
    project = await project_repository.create(db, payload.name, payload.description, user.id)
    logger.info("audit", action="PROJECT_CREATED", resource="project", resource_id=project.id)
    projects_created_total.inc()
    return project


@router.get("/{project_id}", response_model=ProjectRead)
async def get_project(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_user),
):
    project = await project_repository.get_by_id(db, project_id)
    if not project or project.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_user),
):
    project = await project_repository.get_by_id(db, project_id)
    if not project or project.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    await project_repository.delete(db, project)
    logger.info("audit", action="PROJECT_DELETED", resource="project", resource_id=project_id)
