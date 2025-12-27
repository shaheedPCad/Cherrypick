"""Experience and BulletPoint models for professional work history."""

from datetime import date
from typing import List, Optional
from uuid import UUID, uuid4

from sqlalchemy import Boolean, Date, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin


class Experience(Base, TimestampMixin):
    """Professional work experience model."""

    __tablename__ = "experiences"

    # Primary Key - UUID
    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
        nullable=False,
    )

    # Company Information
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role_title: Mapped[str] = mapped_column(String(255), nullable=False)
    location: Mapped[str] = mapped_column(String(255), nullable=False)

    # Date Range
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    bullet_points: Mapped[List["BulletPoint"]] = relationship(
        back_populates="experience",
        cascade="all, delete-orphan",
        lazy="selectin",  # Async-friendly eager loading
    )

    def __repr__(self) -> str:
        return f"<Experience(company='{self.company_name}', role='{self.role_title}')>"


class BulletPoint(Base, TimestampMixin):
    """Bullet point for experience achievements."""

    __tablename__ = "bullet_points"

    # Primary Key - UUID
    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
        nullable=False,
    )

    # Foreign Key to Experience
    experience_id: Mapped[UUID] = mapped_column(
        ForeignKey("experiences.id", ondelete="CASCADE"),
        nullable=False,
        index=True,  # Index for faster joins
    )

    # Content
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # ChromaDB reference
    embedding_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        index=True,  # Index for embedding lookups
    )

    # Relationships
    experience: Mapped["Experience"] = relationship(back_populates="bullet_points")

    def __repr__(self) -> str:
        preview = self.content[:50] + "..." if len(self.content) > 50 else self.content
        return f"<BulletPoint(id={self.id}, content='{preview}')>"
