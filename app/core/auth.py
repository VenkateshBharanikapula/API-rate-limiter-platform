"""
API Key Authentication dependency (Module 2).

Every protected endpoint declares `client: APIClient = Depends(get_current_client)`.
The middleware (app/middleware/rate_limiter.py) also reuses `authenticate_api_key`
directly so validation logic lives in exactly one place.

Flow:
    Request header  X-API-KEY: <key>
          ↓
    Look up key in Postgres (indexed column, sub-ms)
          ↓
    Key missing → 401 InvalidAPIKeyError
          ↓
    Client inactive → 403 InactiveClientError
          ↓
    Return APIClient object (attached to the current DB session)
"""

from fastapi import Depends, Security
from fastapi.security import APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InactiveClientError, InvalidAPIKeyError
from app.db.session import get_db
from app.models.client import APIClient
from app.repositories.client_repository import ClientRepository

# FastAPI will auto-document this header in Swagger UI under "Authorize"
api_key_header = APIKeyHeader(name="X-API-KEY", auto_error=False)


async def authenticate_api_key(
    api_key: str | None,
    db: AsyncSession,
) -> APIClient:
    """
    Core validation logic, extracted from the FastAPI dependency so the
    middleware can call it directly without going through Depends().
    Raises AppError subclasses — these are caught by the central handler
    in main.py and turned into the correct HTTP responses.
    """
    if not api_key:
        raise InvalidAPIKeyError()

    repo = ClientRepository(db)
    client = await repo.get_by_api_key_with_config(api_key)

    if client is None:
        raise InvalidAPIKeyError()

    if not client.is_active:
        raise InactiveClientError()

    return client


async def get_current_client(
    api_key: str | None = Security(api_key_header),
    db: AsyncSession = Depends(get_db),
) -> APIClient:
    """
    FastAPI dependency for endpoint-level auth.

    Usage:
        @router.get("/protected")
        async def protected(client: APIClient = Depends(get_current_client)):
            ...
    """
    return await authenticate_api_key(api_key, db)
