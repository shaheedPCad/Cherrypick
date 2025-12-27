"""Education model for academic background."""

from datetime import date
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import Date, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class Education(Base, TimestampMixin):
    """Academic education model."""

    __tablename__ = "education"

    # Primary Key - UUID
    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
        nullable=False,
    )

    # Institution Information
    institution: Mapped[str] = mapped_column(String(255), nullable=False)
    degree: Mapped[str] = mapped_column(String(255), nullable=False)
    field_of_study: Mapped[str] = mapped_column(String(255), nullable=False)
    location: Mapped[str] = mapped_column(String(255), nullable=False)

    # Date Range
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    # Optional GPA
    gpa: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    def __repr__(self) -> str:
        return f"<Education(institution='{self.institution}', degree='{self.degree}')>"
