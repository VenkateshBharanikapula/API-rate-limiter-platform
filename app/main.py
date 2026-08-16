"""
Application entrypoint.

Run locally with:
    uvicorn app.main:app --reload

Run via Docker:
    docker-compose up --build
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.db.redis import get_redis_client
from app.db.session import engine
from app.middleware.rate_limiter import RateLimitMiddleware

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: nothing eager to warm up yet (engine/pool are lazy).
    yield
    # Shutdown: dispose the engine's connection pool cleanly.
    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    description=(
        "API Key Authentication, Fixed-Window Rate Limiting, Usage Analytics, "
        "and Audit Logging for protecting downstream APIs."
    ),
    version="0.1.0",
    lifespan=lifespan,
)


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """
    Translates the AppError hierarchy (app/core/exceptions.py) into the HTTP
    responses the spec calls for, e.g. NotFoundError -> 404, ConflictError ->
    409, RateLimitExceededError -> 429. Keeps services free of any FastAPI
    import while still producing correct status codes.
    """
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


# Register rate limiting middleware.
# NOTE: Starlette processes middleware in LIFO order (last added = first to run),
# so RateLimitMiddleware is added last to ensure it runs first on every request.
app.add_middleware(RateLimitMiddleware, redis_client=get_redis_client())

app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/health", tags=["health"], summary="Liveness/readiness check")
async def health_check():
    """
    Reports app liveness plus connectivity to its two hard dependencies
    (Postgres, Redis). Returns 503 if either is unreachable so this can be
    wired into Docker healthchecks / orchestrator readiness probes.
    """
    checks = {"database": "unknown", "redis": "unknown"}
    healthy = True

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:
        checks["database"] = f"error: {exc}"
        healthy = False

    try:
        client = get_redis_client()
        await client.ping()
        await client.aclose()
        checks["redis"] = "ok"
    except Exception as exc:
        checks["redis"] = f"error: {exc}"
        healthy = False

    body = {"status": "ok" if healthy else "degraded", "checks": checks}
    if not healthy:
        return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content=body)
    return body


@app.get("/", tags=["health"], summary="Root")
async def root():
    return {"service": settings.app_name, "docs": "/docs"} 
