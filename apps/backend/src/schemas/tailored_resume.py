"""Tailored Resume schemas for CP-15.

This module defines Pydantic schemas for the tailored resume generation feature.
After the matchmaker (CP-14) returns top 15 bullets and top 20 skills, the cherrypicker
uses LLM to select exactly 3-5 bullets per experience/project, and the assembler
fetches full database entities to construct the final TailoredResumeResponse.
"""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field


class TailoredBulletPoint(BaseModel):
    """Selected bullet point for tailored resume.

    Represents a single bullet point chosen by the LLM from the match set.
    Includes similarity score for debugging and optimization.
    """

    id: UUID
    content: str
    similarity_score: float = Field(..., ge=0.0, le=1.0, description="Semantic similarity to job (0-1)")


class TailoredExperience(BaseModel):
    """Experience with cherry-picked bullets (3-5).

    Represents a work experience with LLM-selected bullets. The cherrypicker
    ensures exactly 3-5 non-redundant bullets per experience to keep the
    resume concise and targeted.
    """

    id: UUID
    company_name: str
    role_title: str
    location: str
    start_date: date
    end_date: date | None
    is_current: bool
    bullet_points: list[TailoredBulletPoint] = Field(
        ..., min_length=3, max_length=5, description="LLM-selected bullets (3-5)"
    )


class TailoredProject(BaseModel):
    """Project with cherry-picked bullets (3-5).

    Similar to TailoredExperience, but for project entries. The same 3-5
    bullet constraint applies to maintain consistency and resume brevity.
    """

    id: UUID
    name: str
    description: str
    technologies: list[str]
    link: str | None
    bullet_points: list[TailoredBulletPoint] = Field(
        ..., min_length=3, max_length=5, description="LLM-selected bullets (3-5)"
    )


class TailoredSkill(BaseModel):
    """Selected skill (flat list, no nesting).

    Represents a skill from the top 20 match set. Skills are presented as a
    flat list (not grouped by category) for simplicity in Typst rendering.
    """

    id: UUID
    name: str
    category: str | None
    similarity_score: float = Field(..., ge=0.0, le=1.0, description="Semantic similarity to job (0-1)")


class TailoredEducation(BaseModel):
    """Education entry (unchanged from master library).

    Education entries are included as-is from the database without filtering
    or selection, as they are typically static (1-2 entries) and not bullet-based.
    """

    id: UUID
    institution: str
    degree: str
    field_of_study: str
    location: str
    start_date: date
    end_date: date | None
    gpa: float | None


class TailoredResumeResponse(BaseModel):
    """Complete tailored resume ready for Typst rendering.

    This is the main response schema for the /jobs/{id}/tailor endpoint.
    It contains all selected content organized in a structure that matches
    the Typst template requirements:
    - Nested experiences/projects (with selected bullets)
    - Flat skills list (top 20 from match set)
    - All education entries (no filtering)

    Experiences/projects with 0 selected bullets are excluded entirely.
    """

    job_id: UUID
    job_title: str
    company_name: str

    # Core sections (ordered by relevance/chronology)
    experiences: list[TailoredExperience] = Field(
        ..., description="Experiences with 3-5 selected bullets each (chronological)"
    )
    projects: list[TailoredProject] = Field(
        ..., description="Projects with 3-5 selected bullets each"
    )
    skills: list[TailoredSkill] = Field(
        ..., max_length=20, description="Top 20 skills from match set (flat list)"
    )
    education: list[TailoredEducation] = Field(
        ..., description="All education entries (no filtering)"
    )

    # Metadata
    generated_at: datetime
    total_bullets_selected: int = Field(..., description="Total bullets across all experiences/projects")
    total_skills_selected: int = Field(..., description="Number of skills in the list")

    class Config:
        """Pydantic config for SQLAlchemy model compatibility."""

        from_attributes = True
