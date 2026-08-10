"""
Top-level v1 API router.
Each module's endpoints register themselves here; main.py includes this
single router under the configured api_v1_prefix (/api/v1).
"""

from fastapi import APIRouter

from app.api.v1.endpoints import analytics, clients, rate_limits, usage

api_router = APIRouter()
api_router.include_router(clients.router)
api_router.include_router(usage.router)
api_router.include_router(analytics.router)
api_router.include_router(rate_limits.router)
