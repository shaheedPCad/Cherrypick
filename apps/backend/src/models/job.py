"""Job model for target job descriptions."""

from uuid import UUID, uuid4

from sqlalchemy import String, Text
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

    # created_at from TimestampMixin is sufficient

    def __repr__(self) -> str:
        return f"<Job(title='{self.job_title}', company='{self.company_name}')>"
