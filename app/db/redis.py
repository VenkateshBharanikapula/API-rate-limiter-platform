"""
Async Redis client.

Redis is the hot-path data store for rate limiting (Module 9): request
counters live here, not in Postgres, because we need sub-millisecond
increment+expire operations on every single request.

A single connection pool is created at import time and reused for the life
of the process, mirroring how the async SQLAlchemy engine is set up in
app/db/session.py.
"""

from collections.abc import AsyncGenerator

import redis.asyncio as redis

from app.core.config import get_settings

settings = get_settings()

redis_pool = redis.ConnectionPool.from_url(
    settings.redis_url,
    decode_responses=True,  # work with str, not bytes, throughout the app
    max_connections=50,
)


def get_redis_client() -> redis.Redis:
    """Return a Redis client bound to the shared connection pool."""
    return redis.Redis(connection_pool=redis_pool)


async def get_redis() -> AsyncGenerator[redis.Redis, None]:
    """
    FastAPI dependency for Redis access.

    Usage: `r: redis.Redis = Depends(get_redis)`
    """
    client = get_redis_client()
    try:
        yield client
    finally:
        await client.aclose()
