"""Bullet point request/response schemas for Builder API."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class BulletPointCreateRequest(BaseModel):
    """Schema for creating a bullet point (unified for experience and project)."""

    content: str = Field(..., min_length=1, max_length=2000)
    source_type: str = Field(..., pattern="^(experience|project)$")
    source_id: UUID


class BulletPointUpdateRequest(BaseModel):
    """Schema for updating a bullet point's content."""

    content: str = Field(..., min_length=1, max_length=2000)


class BulletPointResponse(BaseModel):
    """Schema for unified bullet point response."""

    id: UUID
    content: str
    source_type: str  # "experience" or "project"
    source_id: UUID
    embedding_id: str | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
