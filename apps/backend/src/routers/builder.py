"""Builder state endpoint for fetching full resume data."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.models import Education, Experience, Project, Skill
from src.schemas.builder import BuilderStateResponse

router = APIRouter(prefix="/api/v1/builder", tags=["builder"])


@router.get("/state", response_model=BuilderStateResponse)
async def get_builder_state(db: AsyncSession = Depends(get_db)):
    """Get full builder state (all experiences, projects, skills, education)."""
    # Fetch all experiences
    result = await db.execute(select(Experience).order_by(Experience.start_date.desc()))
    experiences = result.scalars().all()

    # Fetch all projects
    result = await db.execute(select(Project).order_by(Project.created_at.desc()))
    projects = result.scalars().all()

    # Fetch all skills
    result = await db.execute(select(Skill).order_by(Skill.name))
    skills = result.scalars().all()

    # Fetch all education
    result = await db.execute(select(Education).order_by(Education.start_date.desc()))
    education = result.scalars().all()

    return BuilderStateResponse(
        experiences=experiences,
        projects=projects,
        skills=skills,
        education=education,
    )
