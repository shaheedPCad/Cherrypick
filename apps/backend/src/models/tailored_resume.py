"""TailoredResume model for async persistence of cherrypicker results.

This module provides the database model for storing pre-computed tailored resume
results, enabling instant PDF generation without blocking HTTP requests.
"""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID

from .base import Base, TimestampMixin


class TailoredResume(Base, TimestampMixin):
    """Stores pre-computed tailored resume results for instant PDF generation.

    This model enables async persistence pattern where expensive LLM operations
    (cherrypicker) run in background tasks, storing results for later retrieval
    by PDF generation endpoints.

    Status Flow:
        pending → processing → completed (success)
                             → failed (error)

    Attributes:
        id: Primary key UUID
        job_id: Foreign key to jobs table (unique constraint)
        status: Current task status (pending/processing/completed/failed)
        total_steps: Number of steps in the background task (typically 4)
        completed_steps: Progress counter (0 to total_steps)
        current_step: Human-readable description of current operation
        result_json: Serialized TailoredResumeResponse (null until completed)
        error_message: Error summary if status=failed
        error_traceback: Full traceback for debugging if status=failed
        started_at: Timestamp when background task began processing
        completed_at: Timestamp when task finished (success or failure)
        created_at: Record creation timestamp (from TimestampMixin)
        updated_at: Last update timestamp (from TimestampMixin)
    """

    __tablename__ = "tailored_resumes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    job_id = Column(
        UUID(as_uuid=True), ForeignKey("jobs.id"), nullable=False, unique=True
    )

    # Status tracking
    status = Column(String, nullable=False, default="pending")
    # Valid values: "pending", "processing", "completed", "failed"

    # Progress tracking
    total_steps = Column(Integer, nullable=True)
    completed_steps = Column(Integer, default=0)
    current_step = Column(String, nullable=True)

    # Result storage
    result_json = Column(JSON, nullable=True)
    # Stores serialized TailoredResumeResponse from assembler

    # Error handling
    error_message = Column(Text, nullable=True)
    error_traceback = Column(Text, nullable=True)

    # Performance tracking
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Indexes for efficient queries
    __table_args__ = (
        Index("idx_tailored_resumes_job_id", "job_id"),
        Index("idx_tailored_resumes_status", "status"),
    )

    def __repr__(self) -> str:
        return (
            f"<TailoredResume(id={self.id}, job_id={self.job_id}, "
            f"status={self.status}, progress={self.completed_steps}/{self.total_steps})>"
        )
