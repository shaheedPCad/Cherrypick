"""Project CRUD endpoints for Builder API."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.models import Project, ProjectBulletPoint
from src.schemas.project import (
    ProjectCreate,
    ProjectResponse,
    ProjectUpdate,
)
from src.services.embeddings import delete_bullet_embedding

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])
logger = logging.getLogger(__name__)


@router.post("/", response_model=ProjectResponse, status_code=201)
async def create_project(
    request: ProjectCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new project entry."""
    project = Project(**request.model_dump())
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


@router.get("/", response_model=list[ProjectResponse])
async def list_projects(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
):
    """List all projects with pagination."""
    result = await db.execute(
        select(Project).order_by(Project.created_at.desc()).offset(skip).limit(limit)
    )
    projects = result.scalars().all()
    return projects


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get a single project by ID."""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    return project


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: UUID,
    request: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update an existing project."""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Update only provided fields
    update_data = request.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(project, field, value)

    await db.commit()
    await db.refresh(project)
    return project


@router.delete("/{project_id}", status_code=204)
async def delete_project(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Delete a project (cascade deletes bullet points and embeddings)."""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        # Fetch all related bullet points BEFORE deletion
        bullet_result = await db.execute(
            select(ProjectBulletPoint).where(ProjectBulletPoint.project_id == project_id)
        )
        bullets = bullet_result.scalars().all()

        logger.info(f"Deleting project {project_id} with {len(bullets)} bullet points")

        # Delete embeddings for all bullets
        for bullet in bullets:
            logger.debug(f"Deleting embedding for bullet {bullet.id}")
            success = await delete_bullet_embedding(bullet.id)
            if not success:
                logger.warning(f"Failed to delete embedding for bullet {bullet.id}")

        # Delete the project (cascade will delete bullets from DB)
        await db.delete(project)
        await db.commit()

        logger.info(f"Successfully deleted project {project_id}")

    except Exception as e:
        logger.error(f"Failed to delete project {project_id}: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete project: {str(e)}"
        )
