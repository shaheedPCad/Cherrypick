"""Job model for target job descriptions."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import ARRAY, Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class Job(Base, TimestampMixin):
    """Target job description model."""

    __tablename__ = "jobs"

    # Primary Key - UUID
    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
        nullable=False,
    )

    # Job Information
    job_title: Mapped[str] = mapped_column(String(255), nullable=False)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Raw job description (will be processed for RAG)
    raw_description: Mapped[str] = mapped_column(Text, nullable=False)

    # Parsed job analysis fields (populated by job_analyzer service)
    top_responsibilities: Mapped[list[str] | None] = mapped_column(
        ARRAY(Text),
        nullable=True,
    )
    hard_skills: Mapped[list[str] | None] = mapped_column(
        ARRAY(Text),
        nullable=True,
    )

    # Analysis status tracking
    is_analyzed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        server_default="false",
    )
    analyzed_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    # created_at, updated_at from TimestampMixin

    def __repr__(self) -> str:
        return f"<Job(title='{self.job_title}', company='{self.company_name}', analyzed={self.is_analyzed})>"
