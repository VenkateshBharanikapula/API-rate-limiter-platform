"""
Analytics endpoints (Module 7).

    GET /api/v1/analytics/client/{id}  – per-client usage summary
    GET /api/v1/analytics/top-clients  – ranked by request volume
    GET /api/v1/analytics/system       – platform-wide stats

These are admin-style endpoints (no client auth required -- they expose
cross-client data). In a real system these would be behind an admin API key
or internal network; for this project they're open to keep the scope
manageable and focus on the rate limiting story.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

import redis.asyncio as redis

from app.db.redis import get_redis
from app.db.session import get_db
from app.schemas.analytics import ClientSummaryResponse, SystemStatsResponse, TopClientEntry
from app.services.analytics_service import AnalyticsService

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get(
    "/client/{client_id}",
    response_model=ClientSummaryResponse,
    summary="Usage summary for a specific client",
)
async def get_client_summary(
    client_id: int,
    db: AsyncSession = Depends(get_db),
    r: redis.Redis = Depends(get_redis),
):
    svc = AnalyticsService(db, r)
    return await svc.get_client_summary(client_id)


@router.get(
    "/top-clients",
    response_model=list[TopClientEntry],
    summary="Top API consumers by request volume",
)
async def get_top_clients(
    limit: int = Query(default=10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    r: redis.Redis = Depends(get_redis),
):
    svc = AnalyticsService(db, r)
    results = await svc.get_top_clients(limit=limit)
    return [
        TopClientEntry(
            client_id=row["client_id"],
            client_name=row.get("client_name", "unknown"),
            total_requests=row["total_requests"],
        )
        for row in results
    ]


@router.get(
    "/system",
    response_model=SystemStatsResponse,
    summary="Platform-wide system statistics",
)
async def get_system_stats(
    db: AsyncSession = Depends(get_db),
    r: redis.Redis = Depends(get_redis),
):
    svc = AnalyticsService(db, r)
    return await svc.get_system_stats()
