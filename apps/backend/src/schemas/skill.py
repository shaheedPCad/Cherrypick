"""Pydantic schemas for Skills API.

This module defines the request and response schemas for the skills
batch upload and management endpoints.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, computed_field


class SkillCreate(BaseModel):
    """Schema for creating a single skill."""

    name: str = Field(..., min_length=1, max_length=255, description="Skill name (e.g., 'Python', 'FastAPI')")
    category: str | None = Field(None, max_length=100, description="Skill category (e.g., 'language', 'framework')")
    description: str | None = Field(None, description="Optional description or notes about the skill")


class SkillBatchCreate(BaseModel):
    """Schema for batch creating multiple skills."""

    skills: list[SkillCreate] = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="List of skills to create (1-1000)"
    )


class SkillResponse(BaseModel):
    """Schema for skill response."""

    id: UUID
    name: str
    category: str | None
    created_at: datetime
    embedding_id: str | None

    class Config:
        """Pydantic config."""
        from_attributes = True

    @computed_field
    @property
    def has_embedding(self) -> bool:
        """Check if skill has an associated embedding.

        Returns:
            True if the skill has an associated embedding in ChromaDB
        """
        return self.embedding_id is not None

    @classmethod
    def from_orm_model(cls, skill):
        """Create response from ORM model.

        Args:
            skill: Skill ORM instance

        Returns:
            SkillResponse instance
        """
        return cls(
            id=skill.id,
            name=skill.name,
            category=skill.category,
            created_at=skill.created_at,
            embedding_id=skill.embedding_id
        )


class SkillBatchResponse(BaseModel):
    """Schema for batch create response."""

    created: int = Field(description="Number of new skills created")
    skipped: int = Field(description="Number of duplicate skills skipped")
    total: int = Field(description="Total skills in request")
    skill_ids: list[UUID] = Field(description="IDs of all skills (created + existing)")
