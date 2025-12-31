"""Education request/response schemas for Builder API."""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field


class EducationBase(BaseModel):
    """Base schema for education."""

    institution: str = Field(..., min_length=1, max_length=255)
    degree: str = Field(..., min_length=1, max_length=255)
    field_of_study: str | None = Field(None, max_length=255)
    location: str | None = Field(None, max_length=255)
    start_date: date | None = None
    end_date: date | None = None
    gpa: float | None = Field(None, ge=0.0, le=4.0)


class EducationResponse(EducationBase):
    """Schema for education response."""

    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
