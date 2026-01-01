"""Skill embedding service for ChromaDB integration.

This module provides functionality for generating and storing vector embeddings
of skills in ChromaDB using Ollama. Skills are stored in a separate collection
from bullet points to enable skill-specific semantic search.
"""

import asyncio
import logging
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.models import Skill
from src.services.embeddings import ChromaDBClient, OllamaEmbeddingClient

logger = logging.getLogger(__name__)


async def store_skill_embedding(
    skill_id: UUID,
    skill_name: str,
    description: str | None = None,
    category: str | None = None,
    chroma_client: ChromaDBClient | None = None,
    ollama_client: OllamaEmbeddingClient | None = None
) -> str | None:
    """Generate and store embedding for a skill.

    Combines skill name and description to create richer semantic representation.
    Stores in separate "resume_skills" collection in ChromaDB.

    Args:
        skill_id: UUID of the Skill record
        skill_name: Name of the skill (e.g., "Python")
        description: Optional description of the skill
        category: Optional category (e.g., "language", "framework")
        chroma_client: Optional ChromaDB client (creates new if None)
        ollama_client: Optional Ollama client (creates new if None)

    Returns:
        Embedding ID (same as skill_id) or None on failure
    """
    try:
        # Initialize clients if not provided
        if chroma_client is None:
            chroma_client = ChromaDBClient()
        if ollama_client is None:
            ollama_client = OllamaEmbeddingClient()

        # Build embedding text: combine name + description for richer context
        if description:
            embedding_text = f"{skill_name} - {description}"
        else:
            embedding_text = skill_name

        # Generate embedding
        embedding = await ollama_client.generate_embedding(embedding_text)

        if not embedding:
            logger.warning(f"Empty embedding generated for skill {skill_id}")
            return None

        # Get or create skills collection
        collection = await chroma_client.get_or_create_skills_collection()

        # Run synchronous ChromaDB operation in thread pool
        loop = asyncio.get_event_loop()

        def _add_embedding():
            collection.add(
                embeddings=[embedding],
                documents=[embedding_text],
                metadatas=[{
                    "skill_id": str(skill_id),
                    "name": skill_name,
                    "category": category or "",
                    "created_at": datetime.utcnow().isoformat()
                }],
                ids=[str(skill_id)]
            )

        await loop.run_in_executor(None, _add_embedding)

        logger.info(f"Stored embedding for skill {skill_id}: {skill_name}")
        return str(skill_id)

    except Exception as e:
        logger.error(f"Failed to store embedding for skill {skill_id}: {e}")
        return None


async def update_skill_embedding(
    skill_id: UUID,
    skill_name: str,
    description: str | None = None,
    chroma_client: ChromaDBClient | None = None,
    ollama_client: OllamaEmbeddingClient | None = None
) -> bool:
    """Update embedding for an existing skill.

    Args:
        skill_id: UUID of the skill to update
        skill_name: Updated skill name
        description: Updated description
        chroma_client: Optional ChromaDB client
        ollama_client: Optional Ollama client

    Returns:
        True on success, False on failure
    """
    try:
        # Initialize clients if not provided
        if chroma_client is None:
            chroma_client = ChromaDBClient()
        if ollama_client is None:
            ollama_client = OllamaEmbeddingClient()

        # Build embedding text
        if description:
            embedding_text = f"{skill_name} - {description}"
        else:
            embedding_text = skill_name

        # Generate new embedding
        embedding = await ollama_client.generate_embedding(embedding_text)

        if not embedding:
            logger.warning(f"Empty embedding generated for skill {skill_id}")
            return False

        # Get skills collection
        collection = await chroma_client.get_or_create_skills_collection()

        # Run synchronous ChromaDB operation in thread pool
        loop = asyncio.get_event_loop()

        def _update_embedding():
            collection.update(
                embeddings=[embedding],
                documents=[embedding_text],
                ids=[str(skill_id)]
            )

        await loop.run_in_executor(None, _update_embedding)

        logger.info(f"Updated embedding for skill {skill_id}: {skill_name}")
        return True

    except Exception as e:
        logger.error(f"Failed to update embedding for skill {skill_id}: {e}")
        return False


async def delete_skill_embedding(
    skill_id: UUID,
    chroma_client: ChromaDBClient | None = None
) -> bool:
    """Delete embedding for a skill.

    Args:
        skill_id: UUID of the skill to delete
        chroma_client: Optional ChromaDB client

    Returns:
        True on success, False on failure
    """
    try:
        # Initialize client if not provided
        if chroma_client is None:
            chroma_client = ChromaDBClient()

        # Get skills collection
        collection = await chroma_client.get_or_create_skills_collection()

        # Run synchronous ChromaDB operation in thread pool
        loop = asyncio.get_event_loop()

        def _delete_embedding():
            collection.delete(ids=[str(skill_id)])

        await loop.run_in_executor(None, _delete_embedding)

        logger.info(f"Deleted embedding for skill {skill_id}")
        return True

    except Exception as e:
        logger.error(f"Failed to delete embedding for skill {skill_id}: {e}")
        return False


async def sync_skill_embedding(
    skill: Skill,
    db: AsyncSession
) -> bool:
    """Sync a skill to ChromaDB and update its embedding_id.

    Similar to sync_bullet_point() pattern for consistency.

    Args:
        skill: Skill ORM instance
        db: Database session

    Returns:
        True on success, False on failure
    """
    # Check if embedding sync is enabled
    if not settings.embedding_sync_enabled:
        logger.warning("Embedding sync is disabled")
        return False

    try:
        # Store embedding
        embedding_id = await store_skill_embedding(
            skill_id=skill.id,
            skill_name=skill.name,
            description=skill.description,
            category=skill.category
        )

        if embedding_id:
            # Update database record
            skill.embedding_id = embedding_id
            return True
        else:
            logger.warning(f"Failed to generate embedding for skill {skill.id}")
            return False

    except Exception as e:
        logger.error(f"Failed to sync skill {skill.id}: {e}")
        return False


async def sync_all_skills(db: AsyncSession) -> dict[str, int]:
    """Batch sync all skills without embeddings.

    Generates embeddings for all skills where embedding_id is None.
    Useful for initial setup or recovering from ChromaDB failures.

    Args:
        db: Database session

    Returns:
        Dictionary with sync statistics:
        - total: Total skills processed
        - success: Number successfully synced
        - errors: Number of failures
    """
    # Query all skills without embeddings
    result = await db.execute(
        select(Skill).where(Skill.embedding_id.is_(None))
    )
    skills = result.scalars().all()

    logger.info(f"Found {len(skills)} skills without embeddings")

    success_count = 0
    error_count = 0

    for skill in skills:
        try:
            success = await sync_skill_embedding(skill, db)
            if success:
                success_count += 1
            else:
                error_count += 1
        except Exception as e:
            logger.error(f"Failed to sync skill {skill.id}: {e}")
            error_count += 1

    # Commit all updates
    await db.commit()

    logger.info(
        f"Skill embedding sync complete: "
        f"{success_count} success, {error_count} errors out of {len(skills)} total"
    )

    return {
        "total": len(skills),
        "success": success_count,
        "errors": error_count
    }
