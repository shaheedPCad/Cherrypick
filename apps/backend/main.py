import asyncio
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.database import close_db, get_db, init_db
from src.health import ServiceHealth, check_chromadb, check_ollama, check_postgres
from src.models import Experience
from src.routers import builder, bullet_points, experiences, projects, skills
from src.schemas.resume import ResumeIngestRequest, ResumeIngestResponse
from src.services.embeddings import ChromaDBClient
from src.services.normalizer import normalize_bullet_points
from src.services.parser import OllamaClient, extract_resume_structure, persist_resume
from src.services.resync import get_embedding_stats, resync_all_embeddings


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

# Include routers
app.include_router(skills.router)
app.include_router(experiences.router)
app.include_router(projects.router)
app.include_router(bullet_points.router)
app.include_router(builder.router)


@app.get("/")
async def root():
    return {"message": "Cherrypick API - Ready"}

@app.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    """Comprehensive health check for all service dependencies."""
    # Run all checks concurrently
    postgres_health, chroma_health, ollama_health = await asyncio.gather(
        check_postgres(settings.database_url),
        check_chromadb(settings.chroma_base_url),
        check_ollama(settings.ollama_base_url),
        return_exceptions=True,
    )

    # Check embedding service
    chroma_client = ChromaDBClient(
        settings.chroma_base_url,
        settings.chroma_collection_name
    )
    embedding_healthy = await chroma_client.health_check()

    # Get embedding statistics
    embedding_stats = await get_embedding_stats(db)

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
            "embeddings": "connected" if embedding_healthy else "disconnected",
        },
        "metrics": {
            "total_bullets": embedding_stats["total_bullets"],
            "bullets_with_embeddings": embedding_stats["with_embeddings"],
            "bullets_without_embeddings": embedding_stats["missing_embeddings"],
            "embedding_coverage_percent": embedding_stats["coverage_percent"],
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


@app.post("/api/v1/ingest/resume", response_model=ResumeIngestResponse, status_code=201)
async def ingest_resume(
    request: ResumeIngestRequest,
    db: AsyncSession = Depends(get_db)
):
    """Parse and ingest a resume from raw text.

    Extracts structured data using Llama 3 via Ollama, normalizes bullet points
    to action-verb format, and persists to PostgreSQL.

    Args:
        request: Resume ingestion request with raw_text
        db: Database session

    Returns:
        Resume ingestion summary with counts and ID

    Raises:
        HTTPException: On parsing, normalization, or database errors
    """
    try:
        # Step 1: Initialize Ollama client
        ollama = OllamaClient()

        # Step 2: Extract structure from resume
        parsed = await extract_resume_structure(request.raw_text, ollama)

        # Step 3: Collect all bullet points for normalization
        all_bullets = []
        for exp in parsed.experiences:
            all_bullets.extend(exp.bullet_points)
        for proj in parsed.projects:
            all_bullets.extend(proj.bullet_points)

        # Step 4: Normalize all bullet points in batch
        if all_bullets:
            normalized_bullets = await normalize_bullet_points(all_bullets, ollama)

            # Step 5: Replace bullet points with normalized versions
            bullet_index = 0
            for exp in parsed.experiences:
                count = len(exp.bullet_points)
                exp.bullet_points = normalized_bullets[bullet_index:bullet_index + count]
                bullet_index += count

            for proj in parsed.projects:
                count = len(proj.bullet_points)
                proj.bullet_points = normalized_bullets[bullet_index:bullet_index + count]
                bullet_index += count

        # Step 6: Persist to database
        exp_count, edu_count, proj_count, total_bullets = await persist_resume(
            parsed, db
        )

        # Step 7: Generate resume ID
        # TODO: Create a Resume table to store resume metadata
        # For now, use first experience ID as proxy, or generate UUID
        result = await db.execute(
            select(Experience).order_by(Experience.created_at.desc()).limit(1)
        )
        latest_exp = result.scalar_one_or_none()
        resume_id = latest_exp.id if latest_exp else uuid4()

        return ResumeIngestResponse(
            resume_id=resume_id,
            experience_count=exp_count,
            education_count=edu_count,
            project_count=proj_count,
            total_bullet_points=total_bullets,
            message="Resume ingested successfully"
        )

    except ValueError as e:
        # Parsing or validation errors
        raise HTTPException(
            status_code=422,
            detail=f"Failed to parse resume: {str(e)}"
        )
    except asyncio.TimeoutError:
        # Ollama timeout
        raise HTTPException(
            status_code=504,
            detail="Resume parsing timed out. Please try again or reduce resume length."
        )
    except Exception as e:
        # Log the full error for debugging
        print(f"ERROR: Resume ingestion failed: {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error during resume ingestion: {str(e)}"
        )


@app.post("/admin/resync-embeddings")
async def admin_resync_embeddings(db: AsyncSession = Depends(get_db)):
    """Resync all missing embeddings (admin endpoint).

    Regenerates embeddings for all bullet points that have NULL embedding_id.
    Useful for recovering from ChromaDB failures or backfilling old data.

    Returns:
        Resync statistics including total, success, and error counts
    """
    try:
        stats = await resync_all_embeddings(db)
        return {
            "message": "Resync completed",
            "stats": stats
        }
    except Exception as e:
        print(f"ERROR: Resync failed: {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Resync failed: {str(e)}"
        )
