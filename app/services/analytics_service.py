"""
Analytics service (Module 7): client summaries, top consumers, system stats.

Cache strategy (Module 9 spec: "Cache analytics"):
  - top_clients and system_stats are cached in Redis for 60 seconds.
    These are the most expensive aggregate queries and tolerate a short
    staleness window.
  - Per-client summaries are not cached (they're cheap single-client queries
    and users expect near-real-time data when viewing their own stats).

Cache keys:
    analytics:top_clients
    analytics:system_stats
"""

import json

import redis.asyncio as redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.client import APIClient
from app.repositories.client_repository import ClientRepository
from app.repositories.usage_repository import UsageRepository

CACHE_TTL = 60  # seconds


class AnalyticsService:
    def __init__(self, db: AsyncSession, redis_client: redis.Redis):
        self.db = db
        self.redis = redis_client
        self.usage_repo = UsageRepository(db)
        self.client_repo = ClientRepository(db)

    async def get_client_summary(self, client_id: int) -> dict:
        """
        Total / successful / blocked counts for a specific client (all time).
        """
        totals = await self.usage_repo.get_system_totals()
        # Re-query scoped to this client
        from app.models.usage import APIUsage
        from sqlalchemy import func, select

        result = await self.db.execute(
            select(
                func.count().label("total"),
                func.count().filter(APIUsage.was_allowed.is_(True)).label("allowed"),
                func.count().filter(APIUsage.was_allowed.is_(False)).label("blocked"),
            ).where(APIUsage.client_id == client_id)
        )
        row = result.mappings().one()
        total = row["total"] or 0
        allowed = row["allowed"] or 0
        blocked = row["blocked"] or 0
        return {
            "client_id": client_id,
            "total_requests": total,
            "successful_requests": allowed,
            "blocked_requests": blocked,
        }

    async def get_top_clients(self, limit: int = 10) -> list[dict]:
        """
        Top API consumers by volume. Result is cached in Redis for CACHE_TTL
        seconds since it queries the full usage table.
        """
        cache_key = "analytics:top_clients"
        cached = await self.redis.get(cache_key)
        if cached:
            return json.loads(cached)

        rows = await self.usage_repo.get_top_clients(limit=limit)

        # Enrich with client names for a more useful response
        if rows:
            client_ids = [r["client_id"] for r in rows]
            clients_result = await self.db.execute(
                select(APIClient.id, APIClient.client_name).where(APIClient.id.in_(client_ids))
            )
            name_map = {row.id: row.client_name for row in clients_result}
            for row in rows:
                row["client_name"] = name_map.get(row["client_id"], "unknown")

        await self.redis.setex(cache_key, CACHE_TTL, json.dumps(rows))
        return rows

    async def get_system_stats(self) -> dict:
        """
        Platform-wide metrics. Cached in Redis for CACHE_TTL seconds.
        """
        cache_key = "analytics:system_stats"
        cached = await self.redis.get(cache_key)
        if cached:
            return json.loads(cached)

        totals = await self.usage_repo.get_system_totals()

        # Client counts
        total_clients_result = await self.db.execute(
            select(func.count()).select_from(APIClient)
        )
        active_clients_result = await self.db.execute(
            select(func.count()).select_from(APIClient).where(APIClient.is_active.is_(True))
        )
        total_clients = total_clients_result.scalar_one() or 0
        active_clients = active_clients_result.scalar_one() or 0

        total = totals["total"]
        successful = totals["successful"]
        blocked = totals["blocked"]
        success_rate = round((successful / total * 100), 2) if total > 0 else 0.0

        stats = {
            "total_clients": total_clients,
            "active_clients": active_clients,
            "total_requests": total,
            "successful_requests": successful,
            "blocked_requests": blocked,
            "success_rate_pct": success_rate,
        }

        await self.redis.setex(cache_key, CACHE_TTL, json.dumps(stats))
        return stats
