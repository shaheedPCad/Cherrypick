"""Skills API router for master technical skills repository.

This module provides endpoints for batch uploading and managing technical skills
that can be used for semantic matching against resume bullet points.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.models.skill import Skill
from src.schemas.skill import (
    SkillBatchCreate,
    SkillBatchResponse,
    SkillResponse,
)

router = APIRouter(prefix="/api/v1/skills", tags=["skills"])


@router.post("/batch", response_model=SkillBatchResponse, status_code=201)
async def batch_create_skills(
    request: SkillBatchCreate,
    db: AsyncSession = Depends(get_db)
):
    """Upload multiple skills at once.

    Handles duplicates gracefully using PostgreSQL's ON CONFLICT DO NOTHING.
    Returns counts of created vs skipped skills.

    Args:
        request: Batch of skills to create
        db: Database session

    Returns:
        SkillBatchResponse with creation statistics and skill IDs
    """
    total = len(request.skills)
    created_ids = []
    skipped_count = 0

    # Attempt to insert each skill, handling duplicates
    for skill_data in request.skills:
        # Use PostgreSQL INSERT ... ON CONFLICT DO NOTHING
        stmt = insert(Skill).values(
            name=skill_data.name,
            category=skill_data.category,
            description=skill_data.description
        ).on_conflict_do_nothing(index_elements=["name"])

        # Execute and check if row was inserted
        result = await db.execute(stmt)

        if result.rowcount > 0:
            # New skill created - fetch its ID
            query = select(Skill).where(Skill.name == skill_data.name)
            created_skill = await db.execute(query)
            skill = created_skill.scalar_one()
            created_ids.append(skill.id)
        else:
            # Duplicate - fetch existing skill ID
            query = select(Skill).where(Skill.name == skill_data.name)
            existing_skill = await db.execute(query)
            skill = existing_skill.scalar_one()
            created_ids.append(skill.id)
            skipped_count += 1

    await db.commit()

    return SkillBatchResponse(
        created=total - skipped_count,
        skipped=skipped_count,
        total=total,
        skill_ids=created_ids
    )


@router.get("/", response_model=list[SkillResponse])
async def list_skills(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
    category: str | None = Query(None, description="Filter by category"),
    db: AsyncSession = Depends(get_db)
):
    """List all skills with optional filtering and pagination.

    Args:
        skip: Number of records to skip (for pagination)
        limit: Maximum number of records to return (1-1000)
        category: Optional category filter
        db: Database session

    Returns:
        List of SkillResponse objects
    """
    # Build query with optional category filter
    query = select(Skill).order_by(Skill.name)

    if category:
        query = query.where(Skill.category == category)

    query = query.offset(skip).limit(limit)

    # Execute query
    result = await db.execute(query)
    skills = result.scalars().all()

    # Convert to response schema
    return [SkillResponse.from_orm_model(skill) for skill in skills]


@router.get("/{skill_id}", response_model=SkillResponse)
async def get_skill(
    skill_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Get a single skill by ID.

    Args:
        skill_id: UUID of the skill
        db: Database session

    Returns:
        SkillResponse object

    Raises:
        HTTPException: 404 if skill not found
    """
    query = select(Skill).where(Skill.id == skill_id)
    result = await db.execute(query)
    skill = result.scalar_one_or_none()

    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill with ID {skill_id} not found")

    return SkillResponse.from_orm_model(skill)


@router.delete("/{skill_id}", status_code=204)
async def delete_skill(
    skill_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Delete a skill.

    Args:
        skill_id: UUID of the skill to delete
        db: Database session

    Returns:
        No content (204)

    Raises:
        HTTPException: 404 if skill not found
    """
    query = select(Skill).where(Skill.id == skill_id)
    result = await db.execute(query)
    skill = result.scalar_one_or_none()

    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill with ID {skill_id} not found")

    await db.delete(skill)
    await db.commit()
