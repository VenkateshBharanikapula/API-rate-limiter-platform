"""
Usage tracking endpoints (Module 6).

    GET /api/v1/usage/current   – last 60 minutes for the authenticated client
    GET /api/v1/usage/daily     – today UTC
    GET /api/v1/usage/monthly   – current calendar month UTC

All three require a valid X-API-KEY header (the client can only see their
own usage -- there is no admin override here by design, which is a natural
interview talking point: a separate admin auth layer would be the extension).
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_client
from app.db.session import get_db
from app.models.client import APIClient
from app.schemas.analytics import CurrentUsageResponse, DailyUsageResponse, MonthlyUsageResponse
from app.services.usage_service import UsageService

router = APIRouter(prefix="/usage", tags=["usage"])


@router.get("/current", response_model=CurrentUsageResponse, summary="Current usage (last 60 min)")
async def get_current_usage(
    client: APIClient = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
):
    svc = UsageService(db)
    return await svc.get_current_usage(client.id)


@router.get("/daily", response_model=DailyUsageResponse, summary="Usage today (UTC)")
async def get_daily_usage(
    client: APIClient = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
):
    svc = UsageService(db)
    return await svc.get_daily_usage(client.id)


@router.get("/monthly", response_model=MonthlyUsageResponse, summary="Usage this month (UTC)")
async def get_monthly_usage(
    client: APIClient = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
):
    svc = UsageService(db)
    return await svc.get_monthly_usage(client.id)
