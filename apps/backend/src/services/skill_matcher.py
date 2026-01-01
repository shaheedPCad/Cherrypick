"""Exact skill matching service.

This module provides functionality for matching skills using exact string comparison
(case-insensitive). Used in combination with semantic matching for comprehensive
skill matching in the matchmaker service.
"""

import logging
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Skill

logger = logging.getLogger(__name__)


async def find_exact_skill_matches(
    skill_names: list[str],
    db: AsyncSession
) -> list[UUID]:
    """Find skills by exact name match (case-insensitive).

    Uses ILIKE for case-insensitive matching against the Skills table.
    This ensures direct matches are always included (e.g., "Python" in JD
    matches "Python" in skills library).

    Args:
        skill_names: List of skill names from job description
        db: Database session

    Returns:
        List of matching Skill UUIDs (may be empty if no matches)

    Example:
        >>> skill_names = ["Python", "React", "AWS"]
        >>> skill_ids = await find_exact_skill_matches(skill_names, db)
        >>> # Returns UUIDs of skills with names matching "python", "react", "aws"
    """
    if not skill_names:
        return []

    try:
        # Build case-insensitive query for each skill name
        # Using func.lower for PostgreSQL case-insensitive comparison
        conditions = [func.lower(Skill.name) == skill_name.lower() for skill_name in skill_names]

        # Execute query with OR conditions
        if len(conditions) == 1:
            stmt = select(Skill.id).where(conditions[0])
        else:
            stmt = select(Skill.id).where(func.or_(*conditions))

        result = await db.execute(stmt)
        skill_ids = result.scalars().all()

        logger.info(
            f"Found {len(skill_ids)} exact matches for "
            f"{len(skill_names)} skill names"
        )

        return list(skill_ids)

    except Exception as e:
        logger.error(f"Failed to find exact skill matches: {e}")
        raise
