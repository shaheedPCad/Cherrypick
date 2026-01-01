"""Assembler service for constructing tailored resumes.

This module implements the final assembly logic for CP-15. It takes the
cherrypicker selections (bullet IDs per source) and fetches full database
entities to construct a complete TailoredResumeResponse ready for Typst rendering.

Key Features:
- Batch database queries for efficiency
- Filtering of experiences/projects with 0 bullets
- Chronological ordering (most recent first)
- Inclusion of all education entries
- Preserves similarity scores for debugging
"""

import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import BulletPoint, Education, Experience, Job, Project, ProjectBulletPoint, Skill
from src.schemas.matchmaker import MatchSet
from src.schemas.tailored_resume import (
    TailoredBulletPoint,
    TailoredEducation,
    TailoredExperience,
    TailoredProject,
    TailoredResumeResponse,
    TailoredSkill,
)
from src.services.cherrypicker import CherrypickerResult

logger = logging.getLogger(__name__)


async def assemble_tailored_resume(
    job_id: UUID, match_set: MatchSet, cherrypicker_result: CherrypickerResult, db: AsyncSession
) -> TailoredResumeResponse:
    """Assemble complete tailored resume from cherrypicker selections.

    This is the main entry point for resume assembly. It orchestrates the
    fetching of all database entities and constructs the final TailoredResumeResponse.

    Database Query Strategy:
    - Use selectin loading for async-friendly relationships
    - Single batch query per entity type (efficient)
    - Filter results in Python to preserve order

    Args:
        job_id: Job UUID (for metadata)
        match_set: Original match set from CP-14 (for skill scores)
        cherrypicker_result: LLM selections from cherrypicker
        db: Database session

    Returns:
        Complete TailoredResumeResponse ready for Typst

    Raises:
        ValueError: If job not found
    """
    # Fetch job details for metadata
    job_result = await db.execute(select(Job).where(Job.id == job_id))
    job = job_result.scalar_one_or_none()

    if not job:
        raise ValueError(f"Job {job_id} not found")

    # Build score lookup maps (for preserving similarity scores)
    skill_scores = {match.skill_id: match.similarity_score for match in match_set.matched_skills}

    bullet_scores = {match.bullet_id: match.similarity_score for match in match_set.matched_bullets}

    logger.info(f"Assembling tailored resume for job {job_id}: {job.job_title} at {job.company_name}")

    # Assemble each entity type
    experiences = await _assemble_experiences(cherrypicker_result.experience_selections, bullet_scores, db)

    projects = await _assemble_projects(cherrypicker_result.project_selections, bullet_scores, db)

    skills = await _assemble_skills(match_set, db)

    education = await _fetch_all_education(db)

    # Count totals
    total_bullets = sum(len(exp.bullet_points) for exp in experiences)
    total_bullets += sum(len(proj.bullet_points) for proj in projects)

    logger.info(
        f"Assembled resume: {len(experiences)} experiences, {len(projects)} projects, "
        f"{len(skills)} skills, {len(education)} education, {total_bullets} total bullets"
    )

    return TailoredResumeResponse(
        job_id=job_id,
        job_title=job.job_title,
        company_name=job.company_name,
        experiences=experiences,
        projects=projects,
        skills=skills,
        education=education,
        generated_at=datetime.now(timezone.utc),
        total_bullets_selected=total_bullets,
        total_skills_selected=len(skills),
    )


async def _assemble_experiences(
    selections: dict[UUID, list[UUID]], bullet_scores: dict[UUID, float], db: AsyncSession
) -> list[TailoredExperience]:
    """Fetch and assemble experience entities with selected bullets.

    Critical Filtering:
    - Experiences with 0 selected bullets are EXCLUDED entirely
    - This keeps the resume focused and avoids empty sections

    Ordering:
    - Experiences are ordered chronologically (most recent first)
    - Bullets within each experience preserve LLM selection order

    Args:
        selections: Map of experience_id -> list of bullet_ids
        bullet_scores: Map of bullet_id -> similarity_score (for preservation)
        db: Database session

    Returns:
        List of TailoredExperience objects (may be empty)
    """
    if not selections:
        logger.info("No experiences selected (empty match set)")
        return []

    # Fetch all selected experiences (batch query)
    exp_ids = list(selections.keys())
    result = await db.execute(
        select(Experience).where(Experience.id.in_(exp_ids)).order_by(Experience.start_date.desc())
    )
    experiences = result.scalars().all()

    logger.info(f"Fetched {len(experiences)} experiences from database")

    # For each experience, fetch selected bullets
    tailored_experiences = []

    for exp in experiences:
        selected_bullet_ids = selections.get(exp.id, [])

        if not selected_bullet_ids:
            logger.debug(f"Skipping experience {exp.id} (no bullets selected)")
            continue  # CRITICAL: Skip experiences with no bullets

        # Fetch bullets (batch query)
        bullet_result = await db.execute(select(BulletPoint).where(BulletPoint.id.in_(selected_bullet_ids)))
        bullets_dict = {b.id: b for b in bullet_result.scalars().all()}

        # Build TailoredBulletPoints in LLM selection order
        tailored_bullets = []
        for bullet_id in selected_bullet_ids:
            if bullet_id in bullets_dict:
                tailored_bullets.append(
                    TailoredBulletPoint(
                        id=bullet_id,
                        content=bullets_dict[bullet_id].content,
                        similarity_score=bullet_scores.get(bullet_id, 0.0),
                    )
                )
            else:
                logger.warning(f"Bullet {bullet_id} not found in database (selected for exp {exp.id})")

        # If no valid bullets after fetch, skip experience
        if not tailored_bullets:
            logger.warning(f"Skipping experience {exp.id} (no valid bullets found in DB)")
            continue

        tailored_experiences.append(
            TailoredExperience(
                id=exp.id,
                company_name=exp.company_name,
                role_title=exp.role_title,
                location=exp.location,
                start_date=exp.start_date,
                end_date=exp.end_date,
                is_current=exp.is_current,
                bullet_points=tailored_bullets,
            )
        )

    logger.info(f"Assembled {len(tailored_experiences)} tailored experiences")
    return tailored_experiences


async def _assemble_projects(
    selections: dict[UUID, list[UUID]], bullet_scores: dict[UUID, float], db: AsyncSession
) -> list[TailoredProject]:
    """Fetch and assemble project entities with selected bullets.

    Identical logic to _assemble_experiences, but uses Project and
    ProjectBulletPoint models. Same filtering and ordering applies.

    Args:
        selections: Map of project_id -> list of bullet_ids
        bullet_scores: Map of bullet_id -> similarity_score
        db: Database session

    Returns:
        List of TailoredProject objects (may be empty)
    """
    if not selections:
        logger.info("No projects selected (empty match set)")
        return []

    # Fetch all selected projects (batch query)
    proj_ids = list(selections.keys())
    result = await db.execute(
        select(Project).where(Project.id.in_(proj_ids)).order_by(Project.created_at.desc())
    )
    projects = result.scalars().all()

    logger.info(f"Fetched {len(projects)} projects from database")

    # For each project, fetch selected bullets
    tailored_projects = []

    for proj in projects:
        selected_bullet_ids = selections.get(proj.id, [])

        if not selected_bullet_ids:
            logger.debug(f"Skipping project {proj.id} (no bullets selected)")
            continue  # CRITICAL: Skip projects with no bullets

        # Fetch project bullets (batch query)
        bullet_result = await db.execute(
            select(ProjectBulletPoint).where(ProjectBulletPoint.id.in_(selected_bullet_ids))
        )
        bullets_dict = {b.id: b for b in bullet_result.scalars().all()}

        # Build TailoredBulletPoints in LLM selection order
        tailored_bullets = []
        for bullet_id in selected_bullet_ids:
            if bullet_id in bullets_dict:
                tailored_bullets.append(
                    TailoredBulletPoint(
                        id=bullet_id,
                        content=bullets_dict[bullet_id].content,
                        similarity_score=bullet_scores.get(bullet_id, 0.0),
                    )
                )
            else:
                logger.warning(f"Project bullet {bullet_id} not found in database (selected for proj {proj.id})")

        # If no valid bullets after fetch, skip project
        if not tailored_bullets:
            logger.warning(f"Skipping project {proj.id} (no valid bullets found in DB)")
            continue

        # Handle technologies field (may be None or empty list)
        technologies = proj.technologies if proj.technologies else []

        tailored_projects.append(
            TailoredProject(
                id=proj.id,
                name=proj.name,
                description=proj.description,
                technologies=technologies,
                link=proj.link,
                bullet_points=tailored_bullets,
            )
        )

    logger.info(f"Assembled {len(tailored_projects)} tailored projects")
    return tailored_projects


async def _assemble_skills(match_set: MatchSet, db: AsyncSession) -> list[TailoredSkill]:
    """Fetch top 20 skills from match set with full details.

    Skills are presented as a flat list (not grouped by category) for
    simplicity in Typst rendering. Order is preserved from match set
    (ranked by similarity).

    Args:
        match_set: Original match set from CP-14
        db: Database session

    Returns:
        List of up to 20 TailoredSkill objects
    """
    if not match_set.matched_skills:
        logger.info("No skills in match set")
        return []

    # Extract skill IDs and scores
    skill_ids = [match.skill_id for match in match_set.matched_skills]

    # Fetch skills (batch query)
    result = await db.execute(select(Skill).where(Skill.id.in_(skill_ids)))
    skills_dict = {skill.id: skill for skill in result.scalars().all()}

    logger.info(f"Fetched {len(skills_dict)} skills from database")

    # Build TailoredSkills in match_set order (by similarity)
    tailored_skills = []
    for match in match_set.matched_skills:
        if match.skill_id in skills_dict:
            skill = skills_dict[match.skill_id]
            tailored_skills.append(
                TailoredSkill(
                    id=skill.id,
                    name=skill.name,
                    category=skill.category,
                    similarity_score=match.similarity_score,
                )
            )
        else:
            logger.warning(f"Skill {match.skill_id} from match set not found in database")

    logger.info(f"Assembled {len(tailored_skills)} tailored skills")
    return tailored_skills


async def _fetch_all_education(db: AsyncSession) -> list[TailoredEducation]:
    """Fetch all education entries (no filtering).

    Education is included as-is from the database without any filtering
    or selection. This is because:
    - Education is typically static (1-2 entries)
    - Not bullet-based, so no cherrypicking applies
    - Safer to include everything than risk missing credentials

    Ordering:
    - Most recent first (by start_date desc)

    Args:
        db: Database session

    Returns:
        List of all TailoredEducation objects
    """
    result = await db.execute(select(Education).order_by(Education.start_date.desc()))
    education_entries = result.scalars().all()

    logger.info(f"Fetched {len(education_entries)} education entries")

    return [
        TailoredEducation(
            id=edu.id,
            institution=edu.institution,
            degree=edu.degree,
            field_of_study=edu.field_of_study,
            location=edu.location,
            start_date=edu.start_date,
            end_date=edu.end_date,
            gpa=edu.gpa,
        )
        for edu in education_entries
    ]
