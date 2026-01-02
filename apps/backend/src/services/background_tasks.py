"""Background task execution for long-running operations.

This module provides background task execution for expensive operations that should
not block HTTP requests, such as the cherrypicker LLM inference (2-3+ minutes).
"""

import asyncio
import json
import logging
import traceback
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.database import get_db
from src.models import Job, TailoredResume
from src.services.assembler import assemble_tailored_resume
from src.services.cherrypicker import cherrypick_bullets
from src.services.matchmaker import generate_match_set
from src.services.parser import OllamaClient

logger = logging.getLogger(__name__)


async def execute_tailor_resume_task(job_id: UUID) -> None:
    """Execute tailored resume generation in background.

    This function runs independently of HTTP request lifecycle, allowing
    the LLM cherrypicker to take as long as needed (up to 5 minutes) without
    timing out the client.

    The function updates the TailoredResume status throughout execution:
        - pending → processing (when task starts)
        - processing → completed (on success)
        - processing → failed (on error or timeout)

    Args:
        job_id: UUID of the job to tailor resume for

    Process:
        1. Update status to "processing"
        2. Fetch job from database
        3. Generate match set (CP-14) - semantic search for top 15 bullets + 20 skills
        4. Cherry-pick bullets (CP-15) - LLM selects 3-5 per source (SLOW: 2-3 min)
        5. Assemble tailored resume - fetch full entities and construct response
        6. Serialize result to JSON
        7. Update status to "completed" and store result

    Error Handling:
        - TimeoutError: If cherrypicker exceeds 5 minutes
        - Exception: Any other error during execution
        - All errors update status to "failed" with error message and traceback

    Performance:
        - Expected duration: 2-3 minutes (cherrypicker-dominated)
        - Timeout: 5 minutes (configurable via settings.cherrypicker_timeout)
        - Non-blocking: Runs independently of HTTP request
    """
    # Get new database session (independent of request)
    async for db in get_db():
        try:
            logger.info(f"Starting background tailor task for job {job_id}")

            # Step 1: Update status to processing
            await db.execute(
                update(TailoredResume)
                .where(TailoredResume.job_id == job_id)
                .values(
                    status="processing",
                    started_at=datetime.now(timezone.utc),
                    total_steps=4,
                    completed_steps=0,
                    current_step="Generating match set",
                )
            )
            await db.commit()

            # Step 2: Fetch job
            result = await db.execute(select(Job).where(Job.id == job_id))
            job = result.scalar_one()

            # Step 3: Generate match set (CP-14)
            logger.info(f"Generating match set for job {job_id}")
            match_set = await generate_match_set(job_id, db)

            await _update_progress(db, job_id, 1, "Cherry-picking bullets")

            # Step 4: Cherry-pick bullets (CP-15) - LONG OPERATION
            logger.info(
                f"Starting cherrypicker for job {job_id} "
                f"({len(match_set.matched_bullets)} bullets, "
                f"{len(match_set.matched_skills)} skills)"
            )
            ollama = OllamaClient()
            cherrypicker_result = await asyncio.wait_for(
                cherrypick_bullets(match_set, job.raw_description, ollama),
                timeout=settings.cherrypicker_timeout,  # 5 minutes
            )

            await _update_progress(db, job_id, 2, "Assembling resume")

            # Step 5: Assemble tailored resume
            logger.info(f"Assembling tailored resume for job {job_id}")
            tailored_resume = await assemble_tailored_resume(
                job_id, match_set, cherrypicker_result, db
            )

            await _update_progress(db, job_id, 3, "Finalizing")

            # Step 6: Serialize result to JSON
            result_json = json.loads(tailored_resume.model_dump_json())

            # Step 7: Mark as completed
            await db.execute(
                update(TailoredResume)
                .where(TailoredResume.job_id == job_id)
                .values(
                    status="completed",
                    completed_steps=4,
                    current_step="Completed",
                    result_json=result_json,
                    completed_at=datetime.now(timezone.utc),
                )
            )
            await db.commit()

            logger.info(f"Successfully completed tailor task for job {job_id}")

        except asyncio.TimeoutError:
            error_msg = (
                f"Cherrypicker timed out after {settings.cherrypicker_timeout}s"
            )
            logger.error(f"Task failed for job {job_id}: {error_msg}")
            await _mark_failed(db, job_id, error_msg, traceback.format_exc())

        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)}"
            logger.error(f"Task failed for job {job_id}: {error_msg}")
            await _mark_failed(db, job_id, error_msg, traceback.format_exc())


async def _update_progress(
    db: AsyncSession, job_id: UUID, completed: int, step: str
) -> None:
    """Update task progress.

    Args:
        db: Database session
        job_id: Job UUID
        completed: Number of completed steps
        step: Human-readable description of current step
    """
    await db.execute(
        update(TailoredResume)
        .where(TailoredResume.job_id == job_id)
        .values(completed_steps=completed, current_step=step)
    )
    await db.commit()


async def _mark_failed(
    db: AsyncSession, job_id: UUID, error: str, tb: str
) -> None:
    """Mark task as failed.

    Args:
        db: Database session
        job_id: Job UUID
        error: Error message
        tb: Full traceback string
    """
    await db.execute(
        update(TailoredResume)
        .where(TailoredResume.job_id == job_id)
        .values(
            status="failed",
            error_message=error,
            error_traceback=tb,
            completed_at=datetime.now(timezone.utc),
        )
    )
    await db.commit()
