"""
Client service: business logic for the Client Management module (Module 1).

Orchestrates the repository layer and owns rules that don't belong in a
repository, e.g.:
  - rejecting duplicate emails
  - generating the API key
  - provisioning a default RateLimitConfig row at registration time, sized
    by the client's plan (see app/core/constants.PLAN_RATE_LIMITS)
  - writing an AuditLog entry for every state-changing action

The caller (endpoint layer) is responsible for committing the transaction;
this service only flushes, so a failure partway through a multi-step
operation (e.g. client created but rate limit provisioning fails) rolls back
cleanly as one unit via the request-scoped session in app/db/session.py.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import PLAN_RATE_LIMITS
from app.core.exceptions import ConflictError, NotFoundError
from app.core.security import generate_api_key
from app.models.audit_log import AuditAction
from app.models.client import APIClient, PlanType
from app.repositories.audit_repository import AuditLogRepository
from app.repositories.client_repository import ClientRepository
from app.repositories.rate_limit_repository import RateLimitConfigRepository


class ClientService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.clients = ClientRepository(db)
        self.rate_limits = RateLimitConfigRepository(db)
        self.audit_logs = AuditLogRepository(db)

    async def register_client(self, *, client_name: str, email: str, plan: PlanType) -> tuple[APIClient, str]:
        """
        Registers a new client and provisions their default rate limit.

        Returns (client, plaintext_api_key) -- the plaintext key only ever
        exists in memory here and in the registration response; it is never
        persisted in readable form elsewhere (the api_key column itself
        *is* the lookup credential, so unlike a password it isn't hashed --
        the security model relies on key length/entropy and HTTPS in
        transit, not a verify-on-read hash comparison).
        """
        existing = await self.clients.get_by_email(email)
        if existing is not None:
            raise ConflictError(f"A client with email '{email}' is already registered")

        api_key = generate_api_key()
        client = await self.clients.create(client_name=client_name, email=email, api_key=api_key, plan=plan)

        requests_allowed, window_seconds = PLAN_RATE_LIMITS[plan]
        await self.rate_limits.create(
            client_id=client.id, requests_allowed=requests_allowed, window_seconds=window_seconds
        )

        await self.audit_logs.create(
            client_id=client.id,
            action=AuditAction.CLIENT_REGISTERED,
            extra_data={"plan": plan.value},
        )
        await self.audit_logs.create(
            client_id=client.id,
            action=AuditAction.API_KEY_GENERATED,
            extra_data=None,
        )

        return client, api_key

    async def get_client(self, client_id: int) -> APIClient:
        client = await self.clients.get_by_id(client_id)
        if client is None:
            raise NotFoundError(f"Client {client_id} not found")
        return client

    async def list_clients(
        self,
        *,
        search: str | None = None,
        status: str | None = None,
        plan: str | None = None,
        ordering: str = "-created_at",
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[APIClient], int]:
        offset = (page - 1) * page_size
        return await self.clients.list(
            search=search,
            status=status,
            plan=plan,
            ordering=ordering,
            offset=offset,
            limit=page_size,
        )

    async def disable_client(self, client_id: int) -> APIClient:
        client = await self.get_client(client_id)
        client = await self.clients.set_active(client, is_active=False)
        await self.audit_logs.create(client_id=client.id, action=AuditAction.CLIENT_DEACTIVATED)
        return client

    async def enable_client(self, client_id: int) -> APIClient:
        client = await self.get_client(client_id)
        client = await self.clients.set_active(client, is_active=True)
        await self.audit_logs.create(client_id=client.id, action=AuditAction.CLIENT_ACTIVATED)
        return client
