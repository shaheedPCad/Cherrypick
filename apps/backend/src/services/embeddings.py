"""ChromaDB vector embeddings service with Ollama integration.

This module provides the core functionality for generating and storing vector embeddings
of resume bullet points in ChromaDB using Ollama's nomic-embed-text model.
"""

import asyncio
import logging
from datetime import datetime
from typing import Any
from uuid import UUID

import chromadb
import httpx
from chromadb.api.models.Collection import Collection
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.models import BulletPoint, ProjectBulletPoint

logger = logging.getLogger(__name__)


class ChromaDBClient:
    """Singleton ChromaDB client manager.

    Provides connection management and collection operations for ChromaDB.
    Supports both bullet points and skills collections.
    """

    _instance = None
    _collection: Collection | None = None
    _skills_collection: Collection | None = None

    def __new__(cls, base_url: str | None = None, collection_name: str | None = None):
        """Singleton pattern to reuse ChromaDB connection."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        base_url: str | None = None,
        collection_name: str | None = None
    ):
        """Initialize ChromaDB client.

        Args:
            base_url: ChromaDB server URL. Defaults to settings.chroma_base_url
            collection_name: Collection name. Defaults to settings.chroma_collection_name
        """
        self.base_url = base_url or settings.chroma_base_url
        self.collection_name = collection_name or settings.chroma_collection_name
        self._client = None

    def _get_client(self) -> chromadb.HttpClient:
        """Get or create ChromaDB HTTP client.

        Returns:
            ChromaDB HTTP client instance
        """
        if self._client is None:
            self._client = chromadb.HttpClient(
                host=self.base_url.replace("http://", "").replace("https://", "").split(":")[0],
                port=int(self.base_url.split(":")[-1]) if ":" in self.base_url else 8000
            )
        return self._client

    async def get_or_create_collection(self) -> Collection:
        """Get or create the resume bullets collection.

        Returns:
            ChromaDB collection instance

        Raises:
            Exception: If ChromaDB is unavailable
        """
        if self._collection is not None:
            return self._collection

        try:
            # Run synchronous ChromaDB operation in thread pool
            loop = asyncio.get_event_loop()

            def _create_collection():
                client = self._get_client()
                return client.get_or_create_collection(
                    name=self.collection_name,
                    metadata={"description": "Resume bullet point embeddings"}
                )

            self._collection = await loop.run_in_executor(None, _create_collection)
            return self._collection

        except Exception as e:
            raise Exception(f"Failed to connect to ChromaDB: {str(e)}")

    async def get_or_create_skills_collection(self) -> Collection:
        """Get or create the resume skills collection.

        Returns:
            ChromaDB collection instance for skills

        Raises:
            Exception: If ChromaDB is unavailable
        """
        if self._skills_collection is not None:
            return self._skills_collection

        try:
            # Run synchronous ChromaDB operation in thread pool
            loop = asyncio.get_event_loop()

            def _create_skills_collection():
                client = self._get_client()
                return client.get_or_create_collection(
                    name="resume_skills",
                    metadata={"description": "Resume skill embeddings"}
                )

            self._skills_collection = await loop.run_in_executor(None, _create_skills_collection)
            return self._skills_collection

        except Exception as e:
            raise Exception(f"Failed to connect to ChromaDB skills collection: {str(e)}")

    async def health_check(self) -> bool:
        """Check if ChromaDB is accessible.

        Returns:
            True if ChromaDB is healthy, False otherwise
        """
        try:
            collection = await self.get_or_create_collection()
            # Simple operation to verify connectivity
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, lambda: collection.count())
            return True
        except Exception:
            return False


class OllamaEmbeddingClient:
    """Generate embeddings via Ollama API.

    Uses nomic-embed-text model for 768-dimension embeddings optimized
    for semantic search.
    """

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None
    ):
        """Initialize Ollama embedding client.

        Args:
            base_url: Ollama API base URL. Defaults to settings.ollama_base_url
            model: Embedding model name. Defaults to settings.ollama_embedding_model
        """
        self.base_url = base_url or settings.ollama_base_url
        self.model = model or settings.ollama_embedding_model
        self.timeout = 30.0

    async def generate_embedding(self, text: str) -> list[float]:
        """Generate embedding vector for text.

        Args:
            text: Text to embed (typically a bullet point)

        Returns:
            768-dimension embedding vector (or model-specific dimension)

        Raises:
            httpx.HTTPError: On API failure
            asyncio.TimeoutError: On timeout
        """
        try:
            async with asyncio.timeout(self.timeout):
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        f"{self.base_url}/api/embeddings",
                        json={
                            "model": self.model,
                            "prompt": text
                        },
                        timeout=self.timeout
                    )
                    response.raise_for_status()
                    data = response.json()
                    # Ollama returns {"embedding": [...]}
                    return data.get("embedding", [])
        except asyncio.TimeoutError:
            raise asyncio.TimeoutError(
                f"Ollama embedding request timed out after {self.timeout}s"
            )
        except httpx.HTTPError as e:
            raise httpx.HTTPError(f"Ollama embedding API error: {str(e)}")


async def store_bullet_embedding(
    bullet_id: UUID,
    content: str,
    source_type: str,
    source_id: UUID,
    chroma_client: ChromaDBClient | None = None,
    ollama_client: OllamaEmbeddingClient | None = None
) -> str | None:
    """Generate and store embedding for a bullet point.

    Args:
        bullet_id: UUID of the BulletPoint or ProjectBulletPoint
        content: Text content to embed
        source_type: "experience" or "project"
        source_id: UUID of parent Experience or Project
        chroma_client: Optional ChromaDB client (creates new if None)
        ollama_client: Optional Ollama client (creates new if None)

    Returns:
        Embedding ID (same as bullet_id) or None on failure
    """
    try:
        # Initialize clients if not provided
        if chroma_client is None:
            chroma_client = ChromaDBClient()
        if ollama_client is None:
            ollama_client = OllamaEmbeddingClient()

        # Generate embedding
        embedding = await ollama_client.generate_embedding(content)

        if not embedding:
            logger.warning(f"Empty embedding generated for bullet {bullet_id}")
            return None

        # Store in ChromaDB
        collection = await chroma_client.get_or_create_collection()

        # Run synchronous ChromaDB operation in thread pool
        loop = asyncio.get_event_loop()

        def _add_embedding():
            collection.add(
                embeddings=[embedding],
                documents=[content],
                metadatas=[{
                    "bullet_id": str(bullet_id),
                    "source_type": source_type,
                    "source_id": str(source_id),
                    "created_at": datetime.utcnow().isoformat()
                }],
                ids=[str(bullet_id)]
            )

        await loop.run_in_executor(None, _add_embedding)

        return str(bullet_id)

    except Exception as e:
        logger.error(f"Failed to store embedding for bullet {bullet_id}: {e}")
        return None


async def update_bullet_embedding(
    bullet_id: UUID,
    new_content: str,
    chroma_client: ChromaDBClient | None = None,
    ollama_client: OllamaEmbeddingClient | None = None
) -> bool:
    """Update embedding for an existing bullet point.

    Args:
        bullet_id: UUID of the bullet to update
        new_content: New text content
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

        # Generate new embedding
        embedding = await ollama_client.generate_embedding(new_content)

        if not embedding:
            logger.warning(f"Empty embedding generated for bullet {bullet_id}")
            return False

        # Update in ChromaDB
        collection = await chroma_client.get_or_create_collection()

        # Run synchronous ChromaDB operation in thread pool
        loop = asyncio.get_event_loop()

        def _update_embedding():
            collection.update(
                embeddings=[embedding],
                documents=[new_content],
                ids=[str(bullet_id)]
            )

        await loop.run_in_executor(None, _update_embedding)

        return True

    except Exception as e:
        logger.error(f"Failed to update embedding for bullet {bullet_id}: {e}")
        return False


async def delete_bullet_embedding(
    bullet_id: UUID,
    chroma_client: ChromaDBClient | None = None
) -> bool:
    """Delete embedding for a bullet point.

    Args:
        bullet_id: UUID of the bullet to delete
        chroma_client: Optional ChromaDB client

    Returns:
        True on success, False on failure
    """
    try:
        # Initialize client if not provided
        if chroma_client is None:
            chroma_client = ChromaDBClient()

        # Delete from ChromaDB
        collection = await chroma_client.get_or_create_collection()

        # Run synchronous ChromaDB operation in thread pool
        loop = asyncio.get_event_loop()

        def _delete_embedding():
            collection.delete(ids=[str(bullet_id)])

        await loop.run_in_executor(None, _delete_embedding)

        return True

    except Exception as e:
        logger.error(f"Failed to delete embedding for bullet {bullet_id}: {e}")
        return False


async def sync_bullet_point(
    bullet: BulletPoint | ProjectBulletPoint,
    db: AsyncSession
) -> bool:
    """Sync a bullet point to ChromaDB and update its embedding_id.

    This is the main entry point for syncing a single bullet point.

    Args:
        bullet: BulletPoint or ProjectBulletPoint instance
        db: Database session

    Returns:
        True on success, False on failure
    """
    # Check if embedding sync is enabled
    if not settings.embedding_sync_enabled:
        return False

    try:
        # Determine source type and ID
        if isinstance(bullet, BulletPoint):
            source_type = "experience"
            source_id = bullet.experience_id
        else:  # ProjectBulletPoint
            source_type = "project"
            source_id = bullet.project_id

        # Store embedding
        embedding_id = await store_bullet_embedding(
            bullet_id=bullet.id,
            content=bullet.content,
            source_type=source_type,
            source_id=source_id
        )

        if embedding_id:
            # Update database record (no need to add - already tracked by session)
            bullet.embedding_id = embedding_id
            return True
        else:
            return False

    except Exception as e:
        logger.error(f"Failed to sync bullet {bullet.id}: {e}")
        return False


async def query_similar_bullets(
    query_text: str,
    top_n: int = 15,
    chroma_client: ChromaDBClient | None = None,
    ollama_client: OllamaEmbeddingClient | None = None
) -> list[dict[str, Any]]:
    """Query ChromaDB for most similar bullet points.

    Uses semantic search to find bullet points most similar to the query text.
    Generates embedding for query text and searches the resume_bullets collection.

    Args:
        query_text: Text to find similar bullets for (e.g., job responsibility)
        top_n: Number of results to return (default 15)
        chroma_client: Optional ChromaDB client (creates new if None)
        ollama_client: Optional Ollama client (creates new if None)

    Returns:
        List of matches with structure:
        [
            {
                "bullet_id": UUID,
                "content": str,
                "similarity_score": float,  # 0-1, higher is better
                "source_type": "experience" | "project",
                "source_id": UUID
            },
            ...
        ]

    Raises:
        Exception: If ChromaDB or Ollama are unavailable
    """
    try:
        # Initialize clients if not provided
        if chroma_client is None:
            chroma_client = ChromaDBClient()
        if ollama_client is None:
            ollama_client = OllamaEmbeddingClient()

        # Generate embedding for query text
        query_embedding = await ollama_client.generate_embedding(query_text)

        if not query_embedding:
            logger.warning("Empty embedding generated for query text")
            return []

        # Get bullets collection
        collection = await chroma_client.get_or_create_collection()

        # Run synchronous ChromaDB query in thread pool
        loop = asyncio.get_event_loop()

        def _query_bullets():
            return collection.query(
                query_embeddings=[query_embedding],
                n_results=top_n,
                include=["documents", "metadatas", "distances"]
            )

        results = await loop.run_in_executor(None, _query_bullets)

        # Parse results into structured format
        matches = []
        if results and results["ids"] and len(results["ids"]) > 0:
            ids = results["ids"][0]
            documents = results["documents"][0]
            metadatas = results["metadatas"][0]
            distances = results["distances"][0]

            for i, bullet_id_str in enumerate(ids):
                # Convert distance to similarity score (1 - distance for cosine)
                # ChromaDB uses L2 distance by default, normalize to 0-1
                similarity_score = 1.0 - min(distances[i], 1.0)

                matches.append({
                    "bullet_id": UUID(bullet_id_str),
                    "content": documents[i],
                    "similarity_score": similarity_score,
                    "source_type": metadatas[i].get("source_type", ""),
                    "source_id": UUID(metadatas[i].get("source_id", "00000000-0000-0000-0000-000000000000"))
                })

        logger.info(f"Found {len(matches)} similar bullets for query")
        return matches

    except Exception as e:
        logger.error(f"Failed to query similar bullets: {e}")
        raise


async def query_similar_skills(
    query_text: str,
    top_n: int = 20,
    chroma_client: ChromaDBClient | None = None,
    ollama_client: OllamaEmbeddingClient | None = None
) -> list[dict[str, Any]]:
    """Query ChromaDB for most similar skills.

    Uses semantic search to find skills most similar to the query text.
    Generates embedding for query text and searches the resume_skills collection.

    Args:
        query_text: Text to find similar skills for (e.g., skill name from JD)
        top_n: Number of results to return (default 20)
        chroma_client: Optional ChromaDB client (creates new if None)
        ollama_client: Optional Ollama client (creates new if None)

    Returns:
        List of matches with structure:
        [
            {
                "skill_id": UUID,
                "name": str,
                "category": str | None,
                "similarity_score": float  # 0-1, higher is better
            },
            ...
        ]

    Raises:
        Exception: If ChromaDB or Ollama are unavailable
    """
    try:
        # Initialize clients if not provided
        if chroma_client is None:
            chroma_client = ChromaDBClient()
        if ollama_client is None:
            ollama_client = OllamaEmbeddingClient()

        # Generate embedding for query text
        query_embedding = await ollama_client.generate_embedding(query_text)

        if not query_embedding:
            logger.warning("Empty embedding generated for query text")
            return []

        # Get skills collection
        collection = await chroma_client.get_or_create_skills_collection()

        # Run synchronous ChromaDB query in thread pool
        loop = asyncio.get_event_loop()

        def _query_skills():
            return collection.query(
                query_embeddings=[query_embedding],
                n_results=top_n,
                include=["metadatas", "distances"]
            )

        results = await loop.run_in_executor(None, _query_skills)

        # Parse results into structured format
        matches = []
        if results and results["ids"] and len(results["ids"]) > 0:
            ids = results["ids"][0]
            metadatas = results["metadatas"][0]
            distances = results["distances"][0]

            for i, skill_id_str in enumerate(ids):
                # Convert distance to similarity score (1 - distance for cosine)
                similarity_score = 1.0 - min(distances[i], 1.0)

                matches.append({
                    "skill_id": UUID(skill_id_str),
                    "name": metadatas[i].get("name", ""),
                    "category": metadatas[i].get("category", "") or None,
                    "similarity_score": similarity_score
                })

        logger.info(f"Found {len(matches)} similar skills for query")
        return matches

    except Exception as e:
        logger.error(f"Failed to query similar skills: {e}")
        raise
