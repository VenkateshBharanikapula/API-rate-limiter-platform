"""
Async database session management.

Exposes:
  - `engine`: the process-wide async engine (one per app instance)
  - `AsyncSessionLocal`: session factory
  - `get_db`: FastAPI dependency that yields a session per-request and
    guarantees it's closed afterward, regardless of exceptions.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_pre_ping=True,  # avoids "stale connection" errors after idle periods
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,  # let callers use objects after commit without a refetch
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Per-request session dependency.

    Usage: `db: AsyncSession = Depends(get_db)`

    Rolls back on exception so a failed request never leaves a half-committed
    transaction open on the connection before it's returned to the pool.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
