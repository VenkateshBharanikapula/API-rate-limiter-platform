"""
Rate Limiting Middleware (Modules 3, 4, 9).

Intercepts every incoming request and orchestrates the full rate-limiting
lifecycle before the request reaches any endpoint handler:

    Request
      ↓
    Skip non-API routes (health, docs, root)
      ↓
    Extract X-API-KEY header
      ↓
    Validate key + load client (Postgres)
      ↓
    Fixed Window check-and-increment (Redis)
      ↓
    If allowed  → call next handler, then log usage row (Postgres, async)
    If rejected → return 429 immediately, log blocked usage row

Response headers set on every authenticated request:
    X-RateLimit-Limit     : requests_allowed in the window
    X-RateLimit-Remaining : how many requests left this window
    X-RateLimit-Window    : window size in seconds

Design note -- why middleware rather than a Depends():
  Rate limiting must intercept *every* protected request, including ones that
  FastAPI would otherwise reject before running dependencies (e.g. validation
  errors). A Starlette BaseHTTPMiddleware is the right layer for this.
  It also separates the cross-cutting rate-limit concern from individual
  endpoint business logic.

Design note -- usage logging:
  Usage rows are written AFTER the response is sent (via asyncio.create_task
  so they don't add latency to the hot path). This means usage data is
  eventually consistent (rows appear within milliseconds, not atomically with
  the response), which is the right trade-off for a rate limiter.
"""

import asyncio
import json

import redis.asyncio as redis
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from app.core.exceptions import AppError
from app.db.session import AsyncSessionLocal
from app.repositories.client_repository import ClientRepository
from app.repositories.usage_repository import UsageRepository
from app.services.rate_limit_service import RateLimitService

# Routes that bypass auth + rate limiting entirely.
EXEMPT_PATHS = {"/", "/health", "/docs", "/redoc", "/openapi.json"}


async def _log_usage(*, client_id: int, endpoint: str, was_allowed: bool) -> None:
    """
    Write a usage row in its own short-lived session so this never blocks the
    response path. Called via asyncio.create_task() after the response is sent.
    Errors here are caught and swallowed -- a failed usage log should never
    cause the client to see an error.
    """
    try:
        async with AsyncSessionLocal() as session:
            repo = UsageRepository(session)
            await repo.create(client_id=client_id, endpoint=endpoint, was_allowed=was_allowed)
            await session.commit()
    except Exception:
        # Observability: in production this would go to Sentry / structured log.
        pass


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, redis_client: redis.Redis):
        super().__init__(app)
        self.redis = redis_client

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # --- 1. Exempt paths bypass auth + rate limiting entirely ---
        if request.url.path in EXEMPT_PATHS or request.url.path.startswith("/openapi"):
            return await call_next(request)

        # --- 2. Extract API key ---
        api_key = request.headers.get("X-API-KEY")
        if not api_key:
            return JSONResponse(
                status_code=401, content={"detail": "Invalid API Key"}
            )

        # --- 3. Authenticate: load client + rate limit config in one query ---
        try:
            async with AsyncSessionLocal() as session:
                repo = ClientRepository(session)
                client = await repo.get_by_api_key_with_config(api_key)

                if client is None:
                    return JSONResponse(
                        status_code=401, content={"detail": "Invalid API Key"}
                    )

                if not client.is_active:
                    return JSONResponse(
                        status_code=403, content={"detail": "Client is disabled"}
                    )

                # Snapshot the values we need before the session closes
                client_id = client.id
                client_name = client.client_name

                # --- 4. Fixed Window rate limit check ---
                rate_svc = RateLimitService(self.redis)
                allowed, count, limit, window = await rate_svc.check_and_increment(client)

        except AppError as exc:
            return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

        # --- 5a. Rate limit exceeded: return 429, log blocked row ---
        if not allowed:
            asyncio.create_task(
                _log_usage(client_id=client_id, endpoint=request.url.path, was_allowed=False)
            )
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded"},
                headers={
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Window": str(window),
                },
            )

        # --- 5b. Allowed: attach client context to request state for endpoints,
        #          call the handler, then log usage asynchronously ---
        request.state.client_id = client_id
        request.state.client_name = client_name

        response = await call_next(request)

        # Add rate limit headers to every successful response
        remaining = max(0, limit - count)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Window"] = str(window)

        asyncio.create_task(
            _log_usage(client_id=client_id, endpoint=request.url.path, was_allowed=True)
        )

        return response
