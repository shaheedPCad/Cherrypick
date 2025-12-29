"""ChromaDB vector embeddings service with Ollama integration.

This module provides the core functionality for generating and storing vector embeddings
of resume bullet points in ChromaDB using Ollama's nomic-embed-text model.
"""

import asyncio
from datetime import datetime
from typing import Any
from uuid import UUID

import chromadb
import httpx
from chromadb.api.models.Collection import Collection
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.models import BulletPoint, ProjectBulletPoint


class ChromaDBClient:
    """Singleton ChromaDB client manager.

    Provides connection management and collection operations for ChromaDB.
    """

    _instance = None
    _collection: Collection | None = None

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
            print(f"WARNING: Empty embedding generated for bullet {bullet_id}")
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
        print(f"ERROR: Failed to store embedding for bullet {bullet_id}: {e}")
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
            print(f"WARNING: Empty embedding generated for bullet {bullet_id}")
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
        print(f"ERROR: Failed to update embedding for bullet {bullet_id}: {e}")
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
        print(f"ERROR: Failed to delete embedding for bullet {bullet_id}: {e}")
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
            # Update database record
            bullet.embedding_id = embedding_id
            db.add(bullet)
            return True
        else:
            return False

    except Exception as e:
        print(f"ERROR: Failed to sync bullet {bullet.id}: {e}")
        return False
