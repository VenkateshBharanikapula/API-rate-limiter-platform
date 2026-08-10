"""
Shared pytest fixtures.

Test DB strategy:
  - Uses SQLite via aiosqlite (no Postgres needed to run tests).
  - Each test gets a fresh set of tables via the `db_session` fixture.
  - aiosqlite supports the same SQLAlchemy async API as asyncpg, so the app
    code doesn't know the difference.

Redis strategy:
  - fakeredis is an in-process Redis emulator. It supports pipelines,
    INCR, EXPIRE, GET, SETEX -- everything the rate limit service needs.
  - No real Redis process required.
"""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import fakeredis.aioredis as fakeredis

from app.db.base import Base
from app.db.session import get_db
from app.db.redis import get_redis
from app.main import app

# SQLite in-memory DB for tests (one per session, tables recreated per test)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def db_engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine):
    """Yields a fresh AsyncSession per test, rolls back after."""
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def fake_redis():
    """In-process fake Redis that supports all commands the app uses."""
    server = fakeredis.FakeRedis()
    yield server
    await server.flushall()
    await server.aclose()


@pytest_asyncio.fixture
async def client(db_session, fake_redis):
    """
    Full async test client with DB and Redis dependencies overridden.
    Use this for integration and middleware tests.
    """
    async def override_get_db():
        yield db_session

    async def override_get_redis():
        yield fake_redis

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = override_get_redis

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
