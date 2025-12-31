"""Bulk resync utility for regenerating missing embeddings.

This module provides admin utilities for resyncing embeddings for bullet points
that are missing their ChromaDB vectors.
"""

import logging

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import BulletPoint, ProjectBulletPoint
from src.services.embeddings import sync_bullet_point

logger = logging.getLogger(__name__)


async def resync_all_embeddings(db: AsyncSession) -> dict:
    """Regenerate embeddings for all bullets with None embedding_id.

    This is an admin utility for recovering from ChromaDB failures or
    backfilling embeddings for old data.

    Args:
        db: Database session

    Returns:
        Dictionary with resync statistics:
        - total: Total bullets processed
        - success: Number successfully synced
        - errors: Number of failures
    """
    # Query all experience bullets without embeddings
    result = await db.execute(
        select(BulletPoint).where(BulletPoint.embedding_id.is_(None))
    )
    bullets = result.scalars().all()

    # Query all project bullets without embeddings
    result = await db.execute(
        select(ProjectBulletPoint).where(ProjectBulletPoint.embedding_id.is_(None))
    )
    project_bullets = result.scalars().all()

    all_bullets = list(bullets) + list(project_bullets)
    success_count = 0
    error_count = 0

    for bullet in all_bullets:
        try:
            success = await sync_bullet_point(bullet, db)
            if success:
                success_count += 1
            else:
                error_count += 1
        except Exception as e:
            logger.error(f"Failed to sync bullet {bullet.id}: {e}")
            error_count += 1

    # Commit all updates
    await db.commit()

    return {
        "total": len(all_bullets),
        "success": success_count,
        "errors": error_count
    }


async def get_embedding_stats(db: AsyncSession) -> dict:
    """Get statistics about embedding coverage.

    Args:
        db: Database session

    Returns:
        Dictionary with embedding statistics:
        - total_bullets: Total number of bullet points
        - with_embeddings: Number with embeddings
        - missing_embeddings: Number without embeddings
        - coverage_percent: Percentage with embeddings
    """
    # Count total bullets
    result = await db.execute(
        select(func.count()).select_from(BulletPoint)
    )
    bullet_count = result.scalar() or 0

    result = await db.execute(
        select(func.count()).select_from(ProjectBulletPoint)
    )
    project_bullet_count = result.scalar() or 0

    total_bullets = bullet_count + project_bullet_count

    # Count bullets with embeddings
    result = await db.execute(
        select(func.count())
        .select_from(BulletPoint)
        .where(BulletPoint.embedding_id.is_not(None))
    )
    bullets_with_embeddings = result.scalar() or 0

    result = await db.execute(
        select(func.count())
        .select_from(ProjectBulletPoint)
        .where(ProjectBulletPoint.embedding_id.is_not(None))
    )
    project_bullets_with_embeddings = result.scalar() or 0

    with_embeddings = bullets_with_embeddings + project_bullets_with_embeddings
    missing_embeddings = total_bullets - with_embeddings

    coverage_percent = (
        round((with_embeddings / total_bullets) * 100, 2)
        if total_bullets > 0
        else 0.0
    )

    return {
        "total_bullets": total_bullets,
        "with_embeddings": with_embeddings,
        "missing_embeddings": missing_embeddings,
        "coverage_percent": coverage_percent
    }
