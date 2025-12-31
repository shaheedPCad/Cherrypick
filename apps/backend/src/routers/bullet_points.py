"""Bullet point CRUD endpoints for Builder API (unified for experience and project)."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.models import BulletPoint, Experience, Project, ProjectBulletPoint
from src.schemas.bullet_point import (
    BulletPointCreateRequest,
    BulletPointResponse,
    BulletPointUpdateRequest,
)
from src.services.embeddings import delete_bullet_embedding, sync_bullet_point

router = APIRouter(prefix="/api/v1/bullet-points", tags=["bullet-points"])
logger = logging.getLogger(__name__)


@router.post("/", response_model=BulletPointResponse, status_code=201)
async def create_bullet_point(
    request: BulletPointCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create a new bullet point for an experience or project."""
    # Validate parent exists
    if request.source_type == "experience":
        result = await db.execute(select(Experience).where(Experience.id == request.source_id))
        parent = result.scalar_one_or_none()
        if not parent:
            raise HTTPException(status_code=404, detail="Experience not found")

        bullet = BulletPoint(experience_id=request.source_id, content=request.content)
    else:  # project
        result = await db.execute(select(Project).where(Project.id == request.source_id))
        parent = result.scalar_one_or_none()
        if not parent:
            raise HTTPException(status_code=404, detail="Project not found")

        bullet = ProjectBulletPoint(project_id=request.source_id, content=request.content)

    db.add(bullet)
    await db.commit()
    await db.refresh(bullet)

    # Auto-sync embedding with rollback on failure
    try:
        await sync_bullet_point(bullet, db)
        await db.commit()
        await db.refresh(bullet)  # Refresh to load embedding_id
        logger.info(f"Successfully created bullet {bullet.id} with embedding")
    except Exception as e:
        logger.error(f"Failed to sync embedding for bullet {bullet.id}: {e}")
        # Rollback the bullet creation if embedding sync fails
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create bullet point with embedding: {str(e)}"
        )

    # Convert to response format
    return BulletPointResponse(
        id=bullet.id,
        content=bullet.content,
        source_type=request.source_type,
        source_id=request.source_id,
        embedding_id=bullet.embedding_id,
        created_at=bullet.created_at,
        updated_at=bullet.updated_at,
    )


@router.patch("/{bullet_id}", response_model=BulletPointResponse)
async def update_bullet_point(
    bullet_id: UUID,
    request: BulletPointUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Update a bullet point's content (auto-syncs embedding)."""
    # Try to find as experience bullet
    result = await db.execute(select(BulletPoint).where(BulletPoint.id == bullet_id))
    bullet = result.scalar_one_or_none()

    if bullet:
        source_type = "experience"
        source_id = bullet.experience_id
    else:
        # Try as project bullet
        result = await db.execute(select(ProjectBulletPoint).where(ProjectBulletPoint.id == bullet_id))
        bullet = result.scalar_one_or_none()

        if not bullet:
            raise HTTPException(status_code=404, detail="Bullet point not found")

        source_type = "project"
        source_id = bullet.project_id

    # Update content
    bullet.content = request.content
    await db.commit()
    await db.refresh(bullet)

    # Auto-sync embedding if content changed
    try:
        await sync_bullet_point(bullet, db)
        await db.commit()
        await db.refresh(bullet)  # Refresh to load updated embedding_id
        logger.info(f"Successfully updated bullet {bullet.id} and embedding")
    except Exception as e:
        logger.error(f"Failed to sync embedding for bullet {bullet.id}: {e}")
        # Rollback the content update if embedding sync fails
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update bullet point with embedding: {str(e)}"
        )

    return BulletPointResponse(
        id=bullet.id,
        content=bullet.content,
        source_type=source_type,
        source_id=source_id,
        embedding_id=bullet.embedding_id,
        created_at=bullet.created_at,
        updated_at=bullet.updated_at,
    )


@router.delete("/{bullet_id}", status_code=204)
async def delete_bullet_point(
    bullet_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Delete a bullet point and its embedding."""
    # Try experience bullet first
    result = await db.execute(select(BulletPoint).where(BulletPoint.id == bullet_id))
    bullet = result.scalar_one_or_none()

    if not bullet:
        # Try project bullet
        result = await db.execute(select(ProjectBulletPoint).where(ProjectBulletPoint.id == bullet_id))
        bullet = result.scalar_one_or_none()

    if not bullet:
        raise HTTPException(status_code=404, detail="Bullet point not found")

    try:
        # Delete embedding from ChromaDB FIRST
        logger.info(f"Deleting embedding for bullet {bullet_id}")
        success = await delete_bullet_embedding(bullet_id)

        if not success:
            logger.warning(f"Failed to delete embedding for bullet {bullet_id}, continuing with DB deletion")

        # Delete from database
        await db.delete(bullet)
        await db.commit()

        logger.info(f"Successfully deleted bullet {bullet_id}")

    except Exception as e:
        logger.error(f"Failed to delete bullet {bullet_id}: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete bullet point: {str(e)}"
        )
