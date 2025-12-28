"""Pydantic schemas for resume ingestion API.

This module defines the request and response models for the resume parsing endpoint,
including intermediate data structures for parsing and validation.
"""

from uuid import UUID

from pydantic import BaseModel, Field


class ResumeIngestRequest(BaseModel):
    """Request model for resume ingestion endpoint.

    Accepts raw resume text for parsing and normalization.
    """

    raw_text: str = Field(
        ...,
        min_length=100,
        description="Raw resume text to parse (minimum 100 characters)"
    )


class ExperienceData(BaseModel):
    """Intermediate model for parsed experience data.

    Used for validation during the parsing process before database persistence.
    """

    company_name: str = Field(..., description="Company or organization name")
    role_title: str = Field(..., description="Job title or position")
    location: str = Field(..., description="City, State or location")
    start_date: str = Field(..., description="Start date (will be parsed later)")
    end_date: str | None = Field(None, description="End date or null if current")
    is_current: bool = Field(False, description="Whether this is the current position")
    bullet_points: list[str] = Field(
        default_factory=list,
        description="List of achievement bullet points"
    )


class EducationData(BaseModel):
    """Intermediate model for parsed education data."""

    institution: str = Field(..., description="University or school name")
    degree: str = Field(..., description="Degree type (e.g., Bachelor of Science)")
    field_of_study: str = Field(..., description="Major or field of study")
    location: str = Field(..., description="City, State or location")
    start_date: str = Field(..., description="Start date (will be parsed later)")
    end_date: str | None = Field(None, description="End date or null if ongoing")
    gpa: float | None = Field(None, description="Grade point average (optional)")


class ProjectData(BaseModel):
    """Intermediate model for parsed project data."""

    name: str = Field(..., description="Project name or title")
    description: str = Field(..., description="Project description")
    technologies: list[str] | None = Field(
        None,
        description="List of technologies used (e.g., ['Python', 'React'])"
    )
    link: str | None = Field(None, description="Project URL (GitHub, demo, etc.)")
    bullet_points: list[str] = Field(
        default_factory=list,
        description="List of achievement bullet points"
    )


class ParsedResume(BaseModel):
    """Container for all parsed resume data.

    This model validates the complete structure extracted from the resume
    before normalization and database persistence.
    """

    experiences: list[ExperienceData] = Field(
        default_factory=list,
        description="List of work experiences"
    )
    education: list[EducationData] = Field(
        default_factory=list,
        description="List of education entries"
    )
    projects: list[ProjectData] = Field(
        default_factory=list,
        description="List of projects"
    )


class ResumeIngestResponse(BaseModel):
    """Response model for successful resume ingestion.

    Provides summary statistics about the parsed and stored resume data.
    """

    resume_id: UUID = Field(..., description="Unique identifier for the resume")
    experience_count: int = Field(..., description="Number of experiences parsed")
    education_count: int = Field(..., description="Number of education entries parsed")
    project_count: int = Field(..., description="Number of projects parsed")
    total_bullet_points: int = Field(
        ...,
        description="Total number of bullet points across all sections"
    )
    message: str = Field(..., description="Success message")
