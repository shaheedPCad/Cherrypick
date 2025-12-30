"""Experience request/response schemas for Builder API."""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field


class BulletPointBase(BaseModel):
    """Base schema for bullet points."""

    content: str = Field(..., min_length=1, max_length=2000)


class BulletPointCreate(BulletPointBase):
    """Schema for creating a bullet point."""

    pass


class BulletPointUpdate(BulletPointBase):
    """Schema for updating a bullet point."""

    pass


class BulletPointResponse(BulletPointBase):
    """Schema for bullet point response."""

    id: UUID
    experience_id: UUID
    embedding_id: str | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ExperienceBase(BaseModel):
    """Base schema for experience."""

    company_name: str = Field(..., min_length=1, max_length=255)
    role_title: str = Field(..., min_length=1, max_length=255)
    location: str = Field(..., max_length=255)
    start_date: date
    end_date: date | None = None
    is_current: bool = False


class ExperienceCreate(ExperienceBase):
    """Schema for creating an experience."""

    pass


class ExperienceUpdate(BaseModel):
    """Schema for updating an experience (all fields optional)."""

    company_name: str | None = Field(None, min_length=1, max_length=255)
    role_title: str | None = Field(None, min_length=1, max_length=255)
    location: str | None = Field(None, max_length=255)
    start_date: date | None = None
    end_date: date | None = None
    is_current: bool | None = None


class ExperienceResponse(ExperienceBase):
    """Schema for experience response with nested bullet points."""

    id: UUID
    bullet_points: list[BulletPointResponse]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
