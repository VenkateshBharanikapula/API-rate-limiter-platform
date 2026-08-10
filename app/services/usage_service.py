"""
Usage service (Module 6): resolves the time windows for current/daily/monthly
usage and delegates the actual aggregation queries to UsageRepository.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.usage_repository import UsageRepository
from app.services.rate_limit_service import RateLimitService


class UsageService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.usage_repo = UsageRepository(db)

    async def get_current_usage(self, client_id: int) -> dict:
        """Usage in the last 60 minutes (rolling hour as 'current')."""
        since = datetime.now(timezone.utc) - timedelta(hours=1)
        data = await self.usage_repo.get_current_window_usage(client_id, since)
        return {**data, "period": "last_60_minutes", "since": since.isoformat()}

    async def get_daily_usage(self, client_id: int) -> dict:
        """Usage for today UTC (midnight to now)."""
        now = datetime.now(timezone.utc)
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        data = await self.usage_repo.get_usage_by_period(client_id, start, now)
        return {**data, "period": "today", "date": start.date().isoformat()}

    async def get_monthly_usage(self, client_id: int) -> dict:
        """Usage for the current calendar month UTC."""
        now = datetime.now(timezone.utc)
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        data = await self.usage_repo.get_usage_by_period(client_id, start, now)
        return {
            **data,
            "period": "current_month",
            "month": start.strftime("%Y-%m"),
        }
