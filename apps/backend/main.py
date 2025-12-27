import asyncio
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.database import close_db, get_db, init_db
from src.health import ServiceHealth, check_chromadb, check_ollama, check_postgres
from src.models import Experience


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize async database connection pool
    print("🚀 Starting Cherrypick Backend")
    await init_db()
    print("✅ Database tables created successfully")
    yield
    # Shutdown: Close connections
    print("👋 Shutting down Cherrypick Backend")
    await close_db()
    print("✅ Database connections closed")

app = FastAPI(
    title="Cherrypick API",
    description="Intelligent Resume Assembly Engine",
    version="0.1.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_cors_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"message": "Cherrypick API - Ready"}

@app.get("/health")
async def health_check():
    """Comprehensive health check for all service dependencies."""
    # Run all checks concurrently
    postgres_health, chroma_health, ollama_health = await asyncio.gather(
        check_postgres(settings.database_url),
        check_chromadb(settings.chroma_base_url),
        check_ollama(settings.ollama_base_url),
        return_exceptions=True,
    )

    # Determine overall status
    all_connected = all(
        h.status == "connected"
        for h in [postgres_health, chroma_health, ollama_health]
        if isinstance(h, ServiceHealth)
    )

    return {
        "status": "healthy" if all_connected else "degraded",
        "dependencies": {
            "postgres": (
                postgres_health.status
                if isinstance(postgres_health, ServiceHealth)
                else "error"
            ),
            "chromadb": (
                chroma_health.status
                if isinstance(chroma_health, ServiceHealth)
                else "error"
            ),
            "ollama": (
                ollama_health.status
                if isinstance(ollama_health, ServiceHealth)
                else "error"
            ),
        },
    }


@app.get("/db-test")
async def db_test(db: AsyncSession = Depends(get_db)):
    """Test database connection by querying Experience count."""
    result = await db.execute(select(Experience))
    experiences = result.scalars().all()
    return {
        "status": "connected",
        "experience_count": len(experiences),
        "message": "Database connection successful",
    }
