"""
Rate limit config repository: raw data access for RateLimitConfig rows.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rate_limit import RateLimitConfig


class RateLimitConfigRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, *, client_id: int, requests_allowed: int, window_seconds: int) -> RateLimitConfig:
        config = RateLimitConfig(
            client_id=client_id, requests_allowed=requests_allowed, window_seconds=window_seconds
        )
        self.db.add(config)
        await self.db.flush()
        await self.db.refresh(config)
        return config

    async def get_by_client_id(self, client_id: int) -> RateLimitConfig | None:
        result = await self.db.execute(
            select(RateLimitConfig).where(RateLimitConfig.client_id == client_id)
        )
        return result.scalar_one_or_none()

    async def update(
        self, config: RateLimitConfig, *, requests_allowed: int, window_seconds: int
    ) -> RateLimitConfig:
        config.requests_allowed = requests_allowed
        config.window_seconds = window_seconds
        await self.db.flush()
        await self.db.refresh(config)
        return config
