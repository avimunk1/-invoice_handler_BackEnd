"""Database connection and session management."""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine
from .config import settings

# Create async engine
engine: AsyncEngine | None = None


def get_engine() -> AsyncEngine:
    """Get or create the async database engine."""
    global engine
    if engine is None:
        # Convert postgresql:// to postgresql+asyncpg://
        db_url = settings.database_url.replace("postgresql://", "postgresql+asyncpg://")
        engine = create_async_engine(
            db_url,
            echo=False,  # Set to True for SQL logging during development
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,  # Verify connections before using
        )
    return engine


async def close_engine():
    """Close the database engine and dispose of the connection pool."""
    global engine
    if engine:
        await engine.dispose()
        engine = None

