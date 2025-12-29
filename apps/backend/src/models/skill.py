"""Skills model for master technical skills repository.

This module defines the Skill model for storing and managing technical skills
that can be matched against resume bullet points for semantic search.
"""

from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin


class Skill(Base, TimestampMixin):
    """Technical skill with optional embedding for semantic matching.

    Represents a technical skill (e.g., "Python", "FastAPI") that can be
    uploaded in batch and later used for semantic matching against resume
    bullet points.
    """

    __tablename__ = "skills"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True
    )
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ChromaDB reference for future semantic matching
    embedding_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        index=True
    )

    def __repr__(self) -> str:
        """String representation of Skill."""
        return f"<Skill(id={self.id}, name='{self.name}', category='{self.category}')>"
