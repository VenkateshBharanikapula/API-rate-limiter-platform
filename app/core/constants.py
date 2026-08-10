"""
Shared constants.

PLAN_RATE_LIMITS defines the default (requests_allowed, window_seconds) pair
per plan tier, per Module 5 of the spec:

    Free:    10 requests/minute
    Basic:   50 requests/minute
    Premium: 200 requests/minute

These are used by the rate limit service when a client has no explicit
RateLimitConfig row -- see app/services/rate_limit_service.py.
"""

from app.models.client import PlanType

PLAN_RATE_LIMITS: dict[PlanType, tuple[int, int]] = {
    PlanType.FREE: (10, 60),
    PlanType.BASIC: (50, 60),
    PlanType.PREMIUM: (200, 60),
}
