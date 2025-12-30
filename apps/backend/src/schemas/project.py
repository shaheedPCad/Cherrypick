"""Project request/response schemas for Builder API."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ProjectBulletPointBase(BaseModel):
    """Base schema for project bullet points."""

    content: str = Field(..., min_length=1, max_length=2000)


class ProjectBulletPointCreate(ProjectBulletPointBase):
    """Schema for creating a project bullet point."""

    pass


class ProjectBulletPointUpdate(ProjectBulletPointBase):
    """Schema for updating a project bullet point."""

    pass


class ProjectBulletPointResponse(ProjectBulletPointBase):
    """Schema for project bullet point response."""

    id: UUID
    project_id: UUID
    embedding_id: str | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProjectBase(BaseModel):
    """Base schema for project."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str = Field(..., min_length=1)
    technologies: list[str] | None = None
    link: str | None = Field(None, max_length=512)


class ProjectCreate(ProjectBase):
    """Schema for creating a project."""

    pass


class ProjectUpdate(BaseModel):
    """Schema for updating a project (all fields optional)."""

    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = Field(None, min_length=1)
    technologies: list[str] | None = None
    link: str | None = Field(None, max_length=512)


class ProjectResponse(ProjectBase):
    """Schema for project response with nested bullet points."""

    id: UUID
    bullet_points: list[ProjectBulletPointResponse]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
