"""
Client repository: raw data access for APIClient rows.

Rule of thumb for this layer (applies across all repositories in the
project): a repository method maps roughly 1:1 to a SQL operation. It knows
nothing about business rules (e.g. "can this client be disabled twice?") --
that belongs in the service layer. This keeps repositories trivially mockable
in service-level unit tests and keeps query logic in one place per entity.
"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.client import APIClient, PlanType


class ClientRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, *, client_name: str, email: str, api_key: str, plan: PlanType) -> APIClient:
        client = APIClient(client_name=client_name, email=email, api_key=api_key, plan=plan)
        self.db.add(client)
        await self.db.flush()  # populate client.id without committing the transaction
        await self.db.refresh(client)
        return client

    async def get_by_id(self, client_id: int) -> APIClient | None:
        return await self.db.get(APIClient, client_id)

    async def get_by_email(self, email: str) -> APIClient | None:
        result = await self.db.execute(select(APIClient).where(APIClient.email == email))
        return result.scalar_one_or_none()

    async def get_by_api_key(self, api_key: str) -> APIClient | None:
        result = await self.db.execute(select(APIClient).where(APIClient.api_key == api_key))
        return result.scalar_one_or_none()

    async def get_by_api_key_with_config(self, api_key: str) -> APIClient | None:
        """
        Like get_by_api_key but eagerly loads the rate_limit_config relationship
        in the same query (one JOIN, no lazy-load N+1). Used by the middleware
        which needs both the client identity AND the rate limit config in the
        hot path without triggering SQLAlchemy's async greenlet error.
        """
        result = await self.db.execute(
            select(APIClient)
            .options(selectinload(APIClient.rate_limit_config))
            .where(APIClient.api_key == api_key)
        )
        return result.scalar_one_or_none()

    async def list(
        self,
        *,
        search: str | None = None,
        status: str | None = None,
        plan: str | None = None,
        ordering: str = "-created_at",
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[APIClient], int]:
        """
        Returns (rows, total_count) for the given filters, applied before
        pagination so `total` reflects the full filtered set, not just the
        current page (Module 10).
        """
        query = select(APIClient)
        count_query = select(func.count()).select_from(APIClient)

        if search:
            pattern = f"%{search}%"
            search_filter = APIClient.client_name.ilike(pattern) | APIClient.email.ilike(pattern)
            query = query.where(search_filter)
            count_query = count_query.where(search_filter)

        if status == "active":
            query = query.where(APIClient.is_active.is_(True))
            count_query = count_query.where(APIClient.is_active.is_(True))
        elif status == "inactive":
            query = query.where(APIClient.is_active.is_(False))
            count_query = count_query.where(APIClient.is_active.is_(False))

        if plan:
            query = query.where(APIClient.plan == plan)
            count_query = count_query.where(APIClient.plan == plan)

        sortable_columns = {
            "created_at": APIClient.created_at,
            "client_name": APIClient.client_name,
            "email": APIClient.email,
        }
        field_name = ordering.lstrip("-")
        column = sortable_columns.get(field_name, APIClient.created_at)
        query = query.order_by(column.desc() if ordering.startswith("-") else column.asc())

        query = query.offset(offset).limit(limit)

        rows = (await self.db.execute(query)).scalars().all()
        total = (await self.db.execute(count_query)).scalar_one()
        return list(rows), total

    async def set_active(self, client: APIClient, *, is_active: bool) -> APIClient:
        client.is_active = is_active
        await self.db.flush()
        await self.db.refresh(client)
        return client
