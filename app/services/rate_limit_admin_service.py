"""
Rate limit config service (Module 5): admin operations for reading and
updating per-client rate limit overrides.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.audit_log import AuditAction
from app.models.rate_limit import RateLimitConfig
from app.repositories.audit_repository import AuditLogRepository
from app.repositories.client_repository import ClientRepository
from app.repositories.rate_limit_repository import RateLimitConfigRepository


class RateLimitAdminService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.clients = ClientRepository(db)
        self.rate_limits = RateLimitConfigRepository(db)
        self.audit_logs = AuditLogRepository(db)

    async def get_config(self, client_id: int) -> RateLimitConfig:
        client = await self.clients.get_by_id(client_id)
        if client is None:
            raise NotFoundError(f"Client {client_id} not found")
        config = await self.rate_limits.get_by_client_id(client_id)
        if config is None:
            raise NotFoundError(f"No rate limit config found for client {client_id}")
        return config

    async def update_config(
        self, client_id: int, *, requests_allowed: int, window_seconds: int
    ) -> RateLimitConfig:
        client = await self.clients.get_by_id(client_id)
        if client is None:
            raise NotFoundError(f"Client {client_id} not found")

        config = await self.rate_limits.get_by_client_id(client_id)
        old_values = (
            {"requests_allowed": config.requests_allowed, "window_seconds": config.window_seconds}
            if config
            else None
        )

        if config is None:
            config = await self.rate_limits.create(
                client_id=client_id,
                requests_allowed=requests_allowed,
                window_seconds=window_seconds,
            )
        else:
            config = await self.rate_limits.update(
                config, requests_allowed=requests_allowed, window_seconds=window_seconds
            )

        await self.audit_logs.create(
            client_id=client_id,
            action=AuditAction.RATE_LIMIT_UPDATED,
            extra_data={
                "old": old_values,
                "new": {"requests_allowed": requests_allowed, "window_seconds": window_seconds},
            },
        )
        return config
