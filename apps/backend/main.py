from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import close_db, get_db, init_db
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

@app.get("/")
async def root():
    return {"message": "Cherrypick API - Ready"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "backend"}


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
