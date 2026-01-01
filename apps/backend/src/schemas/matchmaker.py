"""Matchmaker-related Pydantic schemas.

This module defines request and response schemas for the semantic matchmaker
service, including match sets with ranked bullets and skills.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class BulletMatch(BaseModel):
    """Schema for a matched bullet point with similarity score.

    Internal schema used by matchmaker service.
    """

    bullet_id: UUID
    similarity_score: float = Field(..., ge=0.0, le=1.0)
    content: str
    source_type: str  # "experience" or "project"
    source_id: UUID


class SkillMatch(BaseModel):
    """Schema for a matched skill with similarity score.

    Internal schema used by matchmaker service.
    """

    skill_id: UUID
    similarity_score: float = Field(..., ge=0.0, le=1.0)


class MatchSet(BaseModel):
    """Schema for complete match set (internal).

    Used by matchmaker service to return full match data.
    """

    job_id: UUID
    matched_bullets: list[BulletMatch]
    matched_skills: list[SkillMatch]
    generated_at: datetime


class BulletMatchResponse(BaseModel):
    """Schema for bullet match in API response.

    Content is optional based on include_details query parameter.
    """

    bullet_id: UUID
    similarity_score: float = Field(..., ge=0.0, le=1.0)
    content: str | None = None
    source_type: str | None = None
    source_id: UUID | None = None


class SkillMatchResponse(BaseModel):
    """Schema for skill match in API response.

    Name and category are optional based on include_details query parameter.
    """

    skill_id: UUID
    similarity_score: float = Field(..., ge=0.0, le=1.0)
    name: str | None = None
    category: str | None = None


class MatchSetResponse(BaseModel):
    """Schema for match set API response."""

    job_id: UUID
    matched_bullets: list[BulletMatchResponse]
    matched_skills: list[SkillMatchResponse]
    generated_at: datetime
    total_bullets: int = Field(..., description="Number of bullets matched")
    total_skills: int = Field(..., description="Number of skills matched")

    class Config:
        from_attributes = True
