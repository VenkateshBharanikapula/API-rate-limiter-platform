"""
Rate limit config endpoints (Module 5).

    GET  /api/v1/rate-limits/{client_id}  – view a client's current config
    PUT  /api/v1/rate-limits/{client_id}  – update (upsert) a client's limits

PUT is idempotent: if the client has no RateLimitConfig row yet (e.g. was
registered before this feature shipped), one is created; otherwise the
existing row is updated. Either way an AuditLog entry is written.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.rate_limit import RateLimitConfigRead, RateLimitConfigUpdate
from app.services.rate_limit_admin_service import RateLimitAdminService

router = APIRouter(prefix="/rate-limits", tags=["rate-limits"])


@router.get(
    "/{client_id}",
    response_model=RateLimitConfigRead,
    summary="Get current rate limit config for a client",
)
async def get_rate_limit_config(client_id: int, db: AsyncSession = Depends(get_db)):
    svc = RateLimitAdminService(db)
    return await svc.get_config(client_id)


@router.put(
    "/{client_id}",
    response_model=RateLimitConfigRead,
    summary="Update (upsert) rate limit config for a client",
)
async def update_rate_limit_config(
    client_id: int,
    payload: RateLimitConfigUpdate,
    db: AsyncSession = Depends(get_db),
):
    svc = RateLimitAdminService(db)
    config = await svc.update_config(
        client_id,
        requests_allowed=payload.requests_allowed,
        window_seconds=payload.window_seconds,
    )
    await db.commit()
    return config
