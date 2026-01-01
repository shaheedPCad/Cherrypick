"""Jobs API router.

This module provides REST endpoints for job management, analysis, and matching.
Implements the core RAG retrieval logic for CP-14 (Semantic Matchmaker).
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.models import BulletPoint, Job, ProjectBulletPoint, Skill
from src.schemas.job import (
    JobAnalysisResponse,
    JobCreate,
    JobListResponse,
    JobResponse,
)
from src.schemas.matchmaker import (
    BulletMatchResponse,
    MatchSetResponse,
    SkillMatchResponse,
)
from src.services.job_analyzer import analyze_job
from src.services.matchmaker import generate_match_set

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])


@router.post(
    "",
    response_model=JobResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new job"
)
async def create_job(
    job_data: JobCreate,
    db: AsyncSession = Depends(get_db)
) -> JobResponse:
    """Create a new job with raw description.

    Job will be created in unanalyzed state. Call POST /jobs/{job_id}/analyze
    to extract responsibilities and skills.

    Args:
        job_data: Job creation data (title, company, raw description)
        db: Database session

    Returns:
        Created job record

    Raises:
        HTTPException 422: Validation error
        HTTPException 500: Database error
    """
    try:
        job = Job(
            job_title=job_data.job_title,
            company_name=job_data.company_name,
            raw_description=job_data.raw_description,
            is_analyzed=False
        )

        db.add(job)
        await db.commit()
        await db.refresh(job)

        logger.info(f"Created job {job.id}: {job.job_title} at {job.company_name}")
        return JobResponse.model_validate(job)

    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to create job: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create job: {str(e)}"
        )


@router.get(
    "",
    response_model=JobListResponse,
    summary="List all jobs"
)
async def list_jobs(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    analyzed_only: bool = Query(False, description="Only return analyzed jobs"),
    db: AsyncSession = Depends(get_db)
) -> JobListResponse:
    """List jobs with pagination and filtering.

    Args:
        page: Page number (1-indexed)
        page_size: Number of items per page (max 100)
        analyzed_only: Filter to only analyzed jobs
        db: Database session

    Returns:
        Paginated list of jobs

    Raises:
        HTTPException 500: Database error
    """
    try:
        # Build query
        query = select(Job).order_by(Job.created_at.desc())

        if analyzed_only:
            query = query.where(Job.is_analyzed == True)

        # Get total count
        count_result = await db.execute(select(Job.id))
        total = len(count_result.scalars().all())

        # Apply pagination
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)

        # Execute query
        result = await db.execute(query)
        jobs = result.scalars().all()

        return JobListResponse(
            total=total,
            jobs=[JobResponse.model_validate(job) for job in jobs],
            page=page,
            page_size=page_size
        )

    except Exception as e:
        logger.error(f"Failed to list jobs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list jobs: {str(e)}"
        )


@router.get(
    "/{job_id}",
    response_model=JobResponse,
    summary="Get a specific job"
)
async def get_job(
    job_id: UUID,
    db: AsyncSession = Depends(get_db)
) -> JobResponse:
    """Get a single job by ID.

    Args:
        job_id: Job UUID
        db: Database session

    Returns:
        Job record

    Raises:
        HTTPException 404: Job not found
        HTTPException 500: Database error
    """
    try:
        result = await db.execute(select(Job).where(Job.id == job_id))
        job = result.scalar_one_or_none()

        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job {job_id} not found"
            )

        return JobResponse.model_validate(job)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get job {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get job: {str(e)}"
        )


@router.delete(
    "/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a job"
)
async def delete_job(
    job_id: UUID,
    db: AsyncSession = Depends(get_db)
) -> None:
    """Delete a job by ID.

    Args:
        job_id: Job UUID
        db: Database session

    Raises:
        HTTPException 404: Job not found
        HTTPException 500: Database error
    """
    try:
        result = await db.execute(select(Job).where(Job.id == job_id))
        job = result.scalar_one_or_none()

        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job {job_id} not found"
            )

        await db.delete(job)
        await db.commit()

        logger.info(f"Deleted job {job_id}")

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to delete job {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete job: {str(e)}"
        )


@router.post(
    "/{job_id}/analyze",
    response_model=JobAnalysisResponse,
    summary="Analyze job description"
)
async def analyze_job_description(
    job_id: UUID,
    db: AsyncSession = Depends(get_db)
) -> JobAnalysisResponse:
    """Analyze job description to extract responsibilities and skills.

    Uses Llama 3 via Ollama to parse raw job description and extract:
    - Top 5-10 technical responsibilities
    - Hard skills (no soft skills)

    This endpoint must be called before generating match sets.

    Args:
        job_id: Job UUID
        db: Database session

    Returns:
        Analysis results with extracted responsibilities and skills

    Raises:
        HTTPException 404: Job not found
        HTTPException 400: Job already analyzed
        HTTPException 504: Ollama timeout
        HTTPException 500: Analysis failure
    """
    try:
        # Fetch job
        result = await db.execute(select(Job).where(Job.id == job_id))
        job = result.scalar_one_or_none()

        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job {job_id} not found"
            )

        # Check if already analyzed
        if job.is_analyzed:
            logger.info(f"Job {job_id} already analyzed, returning existing results")
            return JobAnalysisResponse(
                job_id=job.id,
                top_responsibilities=job.top_responsibilities or [],
                hard_skills=job.hard_skills or [],
                analyzed_at=job.analyzed_at
            )

        # Analyze job
        logger.info(f"Starting analysis for job {job_id}")
        success = await analyze_job(job, db)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Job analysis failed"
            )

        # Refresh to get updated data
        await db.refresh(job)

        return JobAnalysisResponse(
            job_id=job.id,
            top_responsibilities=job.top_responsibilities or [],
            hard_skills=job.hard_skills or [],
            analyzed_at=job.analyzed_at
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to analyze job {job_id}: {e}")

        # Check for timeout errors
        if "timeout" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="Ollama request timed out. Ensure Ollama is running and responsive."
            )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Job analysis failed: {str(e)}"
        )


@router.post(
    "/{job_id}/match",
    response_model=MatchSetResponse,
    summary="Generate match set (MAIN FEATURE)"
)
async def generate_job_match_set(
    job_id: UUID,
    include_details: bool = Query(
        False,
        description="Include full bullet/skill details in response"
    ),
    db: AsyncSession = Depends(get_db)
) -> MatchSetResponse:
    """Generate semantic match set for a job (CP-14 main feature).

    Finds the most relevant bullets and skills from the resume library
    based on the job description's analyzed responsibilities and skills.

    **Prerequisites:**
    - Job must be analyzed first (call POST /jobs/{job_id}/analyze)
    - Skills must have embeddings (call POST /admin/sync-skill-embeddings)

    **Matching Logic:**
    - **Bullets**: Semantic search against top_responsibilities (top 15)
    - **Skills**: Hybrid matching (exact + semantic) against hard_skills (top 20)

    Args:
        job_id: Job UUID
        include_details: Include full content/names in response (default: False)
        db: Database session

    Returns:
        Match set with ranked bullets and skills

    Raises:
        HTTPException 404: Job not found
        HTTPException 400: Job not analyzed
        HTTPException 503: ChromaDB or Ollama unavailable
        HTTPException 500: Matching failure
    """
    try:
        # Generate match set
        logger.info(f"Generating match set for job {job_id}")
        match_set = await generate_match_set(job_id, db)

        # Build response
        matched_bullets = []
        matched_skills = []

        # Process bullets
        for bullet in match_set.matched_bullets:
            if include_details:
                matched_bullets.append(
                    BulletMatchResponse(
                        bullet_id=bullet.bullet_id,
                        similarity_score=bullet.similarity_score,
                        content=bullet.content,
                        source_type=bullet.source_type,
                        source_id=bullet.source_id
                    )
                )
            else:
                matched_bullets.append(
                    BulletMatchResponse(
                        bullet_id=bullet.bullet_id,
                        similarity_score=bullet.similarity_score
                    )
                )

        # Process skills (fetch details if requested)
        if include_details:
            skill_ids = [skill.skill_id for skill in match_set.matched_skills]
            result = await db.execute(
                select(Skill).where(Skill.id.in_(skill_ids))
            )
            skills_dict = {skill.id: skill for skill in result.scalars().all()}

            for skill_match in match_set.matched_skills:
                skill = skills_dict.get(skill_match.skill_id)
                matched_skills.append(
                    SkillMatchResponse(
                        skill_id=skill_match.skill_id,
                        similarity_score=skill_match.similarity_score,
                        name=skill.name if skill else None,
                        category=skill.category if skill else None
                    )
                )
        else:
            matched_skills = [
                SkillMatchResponse(
                    skill_id=skill.skill_id,
                    similarity_score=skill.similarity_score
                )
                for skill in match_set.matched_skills
            ]

        return MatchSetResponse(
            job_id=match_set.job_id,
            matched_bullets=matched_bullets,
            matched_skills=matched_skills,
            generated_at=match_set.generated_at,
            total_bullets=len(matched_bullets),
            total_skills=len(matched_skills)
        )

    except ValueError as e:
        # Job not found or not analyzed
        error_msg = str(e)
        if "not found" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=error_msg
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg
            )
    except Exception as e:
        logger.error(f"Failed to generate match set for job {job_id}: {e}")

        # Check for ChromaDB/Ollama errors
        error_msg = str(e).lower()
        if "chroma" in error_msg or "connection" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="ChromaDB unavailable. Ensure vector database is running."
            )
        elif "ollama" in error_msg or "embedding" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Ollama unavailable. Ensure Ollama service is running."
            )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Match set generation failed: {str(e)}"
        )


