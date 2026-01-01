"""Matchmaker service for semantic job-resume matching.

This module implements the core RAG (Retrieval-Augmented Generation) logic
for matching job descriptions to resume content. It combines semantic search
and exact matching to find the most relevant bullets and skills.
"""

import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Job
from src.schemas.matchmaker import BulletMatch, MatchSet, SkillMatch
from src.services.embeddings import query_similar_bullets, query_similar_skills
from src.services.skill_matcher import find_exact_skill_matches

logger = logging.getLogger(__name__)


async def generate_match_set(
    job_id: UUID,
    db: AsyncSession
) -> MatchSet:
    """Generate match set for a job.

    Finds the most relevant bullet points and skills from the user's resume
    library based on the job description's responsibilities and skills.

    Workflow:
    1. Fetch Job record and validate it's analyzed
    2. Match bullets against top_responsibilities (semantic search, top 15)
    3. Match skills against hard_skills (exact + semantic, top 20)
    4. Return MatchSet with ranked results

    Args:
        job_id: UUID of Job record
        db: Database session

    Returns:
        MatchSet with ranked bullets and skills

    Raises:
        ValueError: If job not found or not analyzed
        Exception: On matching errors (ChromaDB, Ollama failures)
    """
    # Step 1: Fetch and validate Job
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()

    if not job:
        raise ValueError(f"Job {job_id} not found")

    if not job.is_analyzed:
        raise ValueError(
            f"Job {job_id} not analyzed. "
            f"Call POST /api/v1/jobs/{job_id}/analyze first."
        )

    logger.info(
        f"Generating match set for job {job_id}: "
        f"{job.job_title} at {job.company_name}"
    )

    # Step 2: Bullet Matching (semantic search)
    matched_bullets = []

    if job.top_responsibilities and len(job.top_responsibilities) > 0:
        # Combine all responsibilities into single query text for better context
        responsibilities_text = " ".join(job.top_responsibilities)

        logger.info(
            f"Searching for bullets matching {len(job.top_responsibilities)} "
            f"responsibilities"
        )

        # Get top 15 similar bullets via semantic search
        bullet_matches = await query_similar_bullets(
            query_text=responsibilities_text,
            top_n=15
        )

        # Convert to BulletMatch schema
        matched_bullets = [
            BulletMatch(
                bullet_id=match["bullet_id"],
                similarity_score=match["similarity_score"],
                content=match["content"],
                source_type=match["source_type"],
                source_id=match["source_id"]
            )
            for match in bullet_matches
        ]

        logger.info(f"Found {len(matched_bullets)} matching bullets")
    else:
        logger.warning(f"Job {job_id} has no responsibilities to match against")

    # Step 3: Skill Matching (hybrid: exact + semantic)
    matched_skills = []

    if job.hard_skills and len(job.hard_skills) > 0:
        logger.info(f"Matching {len(job.hard_skills)} hard skills")

        # Step 3a: Exact matches (case-insensitive)
        exact_skill_ids = await find_exact_skill_matches(job.hard_skills, db)
        logger.info(f"Found {len(exact_skill_ids)} exact skill matches")

        # Build skill scores dict: skill_id -> score
        skill_scores: dict[UUID, float] = {}

        # Add exact matches with perfect score (1.0)
        for skill_id in exact_skill_ids:
            skill_scores[skill_id] = 1.0

        # Step 3b: Semantic matches for each skill
        for skill_name in job.hard_skills:
            try:
                semantic_matches = await query_similar_skills(
                    query_text=skill_name,
                    top_n=5  # Get top 5 per skill for diversity
                )

                for match in semantic_matches:
                    skill_id = match["skill_id"]
                    score = match["similarity_score"]

                    # Keep highest score if duplicate
                    # Exact matches (1.0) will always win over semantic
                    if skill_id not in skill_scores or score > skill_scores[skill_id]:
                        skill_scores[skill_id] = score

            except Exception as e:
                logger.warning(f"Semantic search failed for skill '{skill_name}': {e}")
                # Continue with other skills even if one fails
                continue

        # Step 3c: Sort by score and take top 20
        sorted_skills = sorted(
            skill_scores.items(),
            key=lambda x: x[1],  # Sort by score
            reverse=True  # Highest first
        )[:20]  # Top 20

        # Convert to SkillMatch schema
        matched_skills = [
            SkillMatch(
                skill_id=skill_id,
                similarity_score=score
            )
            for skill_id, score in sorted_skills
        ]

        logger.info(
            f"Found {len(matched_skills)} total skill matches "
            f"({len(exact_skill_ids)} exact, "
            f"{len(matched_skills) - len(exact_skill_ids)} semantic)"
        )
    else:
        logger.warning(f"Job {job_id} has no skills to match against")

    # Step 4: Build and return MatchSet
    match_set = MatchSet(
        job_id=job_id,
        matched_bullets=matched_bullets,
        matched_skills=matched_skills,
        generated_at=datetime.now(timezone.utc)
    )

    logger.info(
        f"Match set generated for job {job_id}: "
        f"{len(matched_bullets)} bullets, {len(matched_skills)} skills"
    )

    return match_set
