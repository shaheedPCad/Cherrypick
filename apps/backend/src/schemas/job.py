"""Job-related Pydantic schemas.

This module defines request and response schemas for Job endpoints,
including job creation, analysis results, and parsed job descriptions.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class JobCreate(BaseModel):
    """Schema for creating a new job."""

    job_title: str = Field(..., min_length=1, max_length=255)
    company_name: str = Field(..., min_length=1, max_length=255)
    raw_description: str = Field(..., min_length=1)


class JobResponse(BaseModel):
    """Schema for job response with all fields."""

    id: UUID
    job_title: str
    company_name: str
    raw_description: str
    top_responsibilities: list[str] | None = None
    hard_skills: list[str] | None = None
    is_analyzed: bool
    analyzed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ParsedJobDescription(BaseModel):
    """Schema for parsed job description data extracted by Llama 3.

    Used by job_analyzer.py service for validation.
    """

    top_responsibilities: list[str] = Field(
        ...,
        min_length=3,
        max_length=10,
        description="5-10 key technical responsibilities extracted from job description"
    )
    hard_skills: list[str] = Field(
        ...,
        min_length=3,
        description="Technical/hard skills only (no soft skills)"
    )


class JobAnalysisResponse(BaseModel):
    """Schema for job analysis result."""

    job_id: UUID
    top_responsibilities: list[str]
    hard_skills: list[str]
    analyzed_at: datetime

    class Config:
        from_attributes = True


class JobListResponse(BaseModel):
    """Schema for paginated job list response."""

    total: int
    jobs: list[JobResponse]
    page: int
    page_size: int
