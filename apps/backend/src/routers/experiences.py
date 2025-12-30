"""Experience CRUD endpoints for Builder API."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.models import Experience
from src.schemas.experience import (
    ExperienceCreate,
    ExperienceResponse,
    ExperienceUpdate,
)

router = APIRouter(prefix="/api/v1/experiences", tags=["experiences"])


@router.post("/", response_model=ExperienceResponse, status_code=201)
async def create_experience(
    request: ExperienceCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new experience entry."""
    experience = Experience(**request.model_dump())
    db.add(experience)
    await db.commit()
    await db.refresh(experience)
    return experience


@router.get("/", response_model=list[ExperienceResponse])
async def list_experiences(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
):
    """List all experiences with pagination."""
    result = await db.execute(
        select(Experience).order_by(Experience.start_date.desc()).offset(skip).limit(limit)
    )
    experiences = result.scalars().all()
    return experiences


@router.get("/{experience_id}", response_model=ExperienceResponse)
async def get_experience(
    experience_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get a single experience by ID."""
    result = await db.execute(select(Experience).where(Experience.id == experience_id))
    experience = result.scalar_one_or_none()

    if not experience:
        raise HTTPException(status_code=404, detail="Experience not found")

    return experience


@router.patch("/{experience_id}", response_model=ExperienceResponse)
async def update_experience(
    experience_id: UUID,
    request: ExperienceUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update an existing experience."""
    result = await db.execute(select(Experience).where(Experience.id == experience_id))
    experience = result.scalar_one_or_none()

    if not experience:
        raise HTTPException(status_code=404, detail="Experience not found")

    # Update only provided fields
    update_data = request.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(experience, field, value)

    await db.commit()
    await db.refresh(experience)
    return experience


@router.delete("/{experience_id}", status_code=204)
async def delete_experience(
    experience_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Delete an experience (cascade deletes bullet points)."""
    result = await db.execute(select(Experience).where(Experience.id == experience_id))
    experience = result.scalar_one_or_none()

    if not experience:
        raise HTTPException(status_code=404, detail="Experience not found")

    await db.delete(experience)
    await db.commit()
