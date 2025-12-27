"""Health check module for service dependencies."""

import asyncio
import time
from dataclasses import dataclass
from typing import Literal

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


@dataclass
class ServiceHealth:
    """Health status for a service dependency."""

    status: Literal["connected", "unreachable", "error"]
    latency_ms: float | None = None
    error: str | None = None


async def check_postgres(db_url: str) -> ServiceHealth:
    """Check PostgreSQL connectivity with SELECT 1 query.

    Args:
        db_url: PostgreSQL connection URL

    Returns:
        ServiceHealth with connection status and latency
    """
    start = time.perf_counter()
    try:
        async with asyncio.timeout(2.0):
            # Create temporary engine to avoid polluting connection pool
            engine = create_async_engine(db_url, pool_pre_ping=True)
            async with engine.begin() as conn:
                await conn.execute(text("SELECT 1"))
            await engine.dispose()
            latency = (time.perf_counter() - start) * 1000
            return ServiceHealth(status="connected", latency_ms=round(latency, 2))
    except asyncio.TimeoutError:
        return ServiceHealth(status="unreachable", error="timeout")
    except Exception as e:
        return ServiceHealth(status="error", error=str(e))


async def check_chromadb(base_url: str) -> ServiceHealth:
    """Check ChromaDB heartbeat endpoint.

    Args:
        base_url: ChromaDB base URL (e.g., http://localhost:8000)

    Returns:
        ServiceHealth with connection status and latency
    """
    start = time.perf_counter()
    try:
        async with asyncio.timeout(2.0):
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{base_url}/api/v2/heartbeat")
                if response.status_code == 200:
                    latency = (time.perf_counter() - start) * 1000
                    return ServiceHealth(
                        status="connected", latency_ms=round(latency, 2)
                    )
                return ServiceHealth(
                    status="error", error=f"HTTP {response.status_code}"
                )
    except asyncio.TimeoutError:
        return ServiceHealth(status="unreachable", error="timeout")
    except Exception as e:
        return ServiceHealth(status="error", error=str(e))


async def check_ollama(base_url: str) -> ServiceHealth:
    """Check Ollama API reachability.

    Args:
        base_url: Ollama base URL (e.g., http://localhost:11434)

    Returns:
        ServiceHealth with connection status and latency
    """
    start = time.perf_counter()
    try:
        async with asyncio.timeout(2.0):
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{base_url}/api/tags")
                if response.status_code == 200:
                    latency = (time.perf_counter() - start) * 1000
                    return ServiceHealth(
                        status="connected", latency_ms=round(latency, 2)
                    )
                return ServiceHealth(
                    status="error", error=f"HTTP {response.status_code}"
                )
    except asyncio.TimeoutError:
        return ServiceHealth(status="unreachable", error="timeout")
    except Exception as e:
        return ServiceHealth(status="error", error=str(e))
