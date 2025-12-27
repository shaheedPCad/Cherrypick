"""Project and ProjectBulletPoint models for personal/side projects."""

from typing import List, Optional
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin


class Project(Base, TimestampMixin):
    """Personal/side project model."""

    __tablename__ = "projects"

    # Primary Key - UUID
    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
        nullable=False,
    )

    # Project Information
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    # Technologies - Store as JSON array
    technologies: Mapped[Optional[List[str]]] = mapped_column(
        JSON,
        nullable=True,
        default=list,  # Callable default
    )

    # External link (GitHub, demo, etc.)
    link: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    # Relationships
    bullet_points: Mapped[List["ProjectBulletPoint"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Project(name='{self.name}')>"


class ProjectBulletPoint(Base, TimestampMixin):
    """Bullet point for project achievements."""

    __tablename__ = "project_bullet_points"

    # Primary Key - UUID
    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
        nullable=False,
    )

    # Foreign Key to Project
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Content
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # ChromaDB reference
    embedding_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )

    # Relationships
    project: Mapped["Project"] = relationship(back_populates="bullet_points")

    def __repr__(self) -> str:
        preview = self.content[:50] + "..." if len(self.content) > 50 else self.content
        return f"<ProjectBulletPoint(id={self.id}, content='{preview}')>"
