"""Database configuration and session management."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from .config import settings
from .models.base import Base

# Create async engine
engine: AsyncEngine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency to get database session.

    Yields:
        AsyncSession: Database session

    Example:
        @app.get("/items")
        async def get_items(db: AsyncSession = Depends(get_db)):
            result = await db.execute(select(Item))
            return result.scalars().all()
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize database tables.

    Creates all tables defined in the models if they don't exist.
    Should be called during application startup.
    """
    async with engine.begin() as conn:
        # Import all models to ensure they are registered
        from .models import (
            Base,
            BulletPoint,
            Education,
            Experience,
            Job,
            Project,
            ProjectBulletPoint,
            Skill,
            TailoredResume,
        )

        # Create all tables
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Close database connections.

    Disposes the engine and closes all connections.
    Should be called during application shutdown.
    """
    await engine.dispose()
