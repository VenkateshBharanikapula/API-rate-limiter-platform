"""
Usage repository: writes per-request APIUsage rows (called by the rate
limiting middleware) and provides aggregate reads for the usage/analytics
endpoints (Modules 6, 7).
"""

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.usage import APIUsage


class UsageRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, *, client_id: int, endpoint: str, was_allowed: bool) -> APIUsage:
        record = APIUsage(client_id=client_id, endpoint=endpoint, was_allowed=was_allowed)
        self.db.add(record)
        await self.db.flush()
        return record

    async def get_current_window_usage(self, client_id: int, since: datetime) -> dict:
        """Total + allowed + blocked since `since` (used by /usage/current)."""
        result = await self.db.execute(
            select(
                func.count().label("total"),
                func.count().filter(APIUsage.was_allowed.is_(True)).label("allowed"),
                func.count().filter(APIUsage.was_allowed.is_(False)).label("blocked"),
            )
            .where(APIUsage.client_id == client_id)
            .where(APIUsage.timestamp >= since)
        )
        row = result.mappings().one()
        return {
            "total": row["total"] or 0,
            "successful": row["allowed"] or 0,
            "blocked": row["blocked"] or 0,
        }

    async def get_usage_by_period(self, client_id: int, start: datetime, end: datetime) -> dict:
        """Aggregate counts for an arbitrary time window (daily / monthly)."""
        result = await self.db.execute(
            select(
                func.count().label("total"),
                func.count().filter(APIUsage.was_allowed.is_(True)).label("allowed"),
                func.count().filter(APIUsage.was_allowed.is_(False)).label("blocked"),
            )
            .where(APIUsage.client_id == client_id)
            .where(APIUsage.timestamp >= start)
            .where(APIUsage.timestamp < end)
        )
        row = result.mappings().one()
        return {
            "total": row["total"] or 0,
            "successful": row["allowed"] or 0,
            "blocked": row["blocked"] or 0,
        }

    async def get_top_clients(self, limit: int = 10) -> list[dict]:
        """Ranked list of clients by total request volume (all time)."""
        result = await self.db.execute(
            select(APIUsage.client_id, func.count().label("total_requests"))
            .group_by(APIUsage.client_id)
            .order_by(func.count().desc())
            .limit(limit)
        )
        return [{"client_id": r.client_id, "total_requests": r.total_requests} for r in result]

    async def get_system_totals(self) -> dict:
        """Aggregate totals across all clients for the system stats endpoint."""
        result = await self.db.execute(
            select(
                func.count().label("total"),
                func.count().filter(APIUsage.was_allowed.is_(True)).label("allowed"),
                func.count().filter(APIUsage.was_allowed.is_(False)).label("blocked"),
            )
        )
        row = result.mappings().one()
        return {
            "total": row["total"] or 0,
            "successful": row["allowed"] or 0,
            "blocked": row["blocked"] or 0,
        }
