"""
Rate Limit Service: Fixed Window algorithm (Module 4 / Module 9).

Fixed Window algorithm:
  - A Redis key is constructed from the API key + the current time window
    bucket (truncated to `window_seconds`).
  - On each request: INCR the key, set its TTL to `window_seconds` on first
    increment (using SET NX / EXPIRE atomically via a pipeline).
  - If the resulting count exceeds `requests_allowed` → rate limited.

Redis key structure (Module 9 spec):
    rate_limit:{api_key}:{window_bucket}
    e.g. rate_limit:abc123:2026-06-14-10:30

Why Fixed Window and not Sliding Window / Token Bucket:
  - The spec explicitly calls for Fixed Window for this project.
  - It is the easiest to reason about and implement correctly, which makes
    it a better interview talking point when you explain trade-offs (e.g.
    burst at window boundary is the known weakness; Sliding Window fixes
    this at higher Redis cost).

Why Redis and not Postgres for counters:
  - INCR is O(1) and atomic without transactions.
  - Keys auto-expire so no cleanup job is needed.
  - Sub-millisecond latency keeps the middleware overhead negligible.
"""

import time

import redis.asyncio as redis

from app.core.constants import PLAN_RATE_LIMITS
from app.models.client import APIClient


def _window_key(api_key: str, window_seconds: int) -> str:
    """
    Build the Redis key for the current time window bucket.

    Bucket = floor(unix_time / window_seconds) * window_seconds
    This gives a stable integer that only changes every `window_seconds`
    seconds, producing keys like:
        rate_limit:abc123:1718352600   (for a 60-second window)
    """
    bucket = int(time.time() // window_seconds) * window_seconds
    return f"rate_limit:{api_key}:{bucket}"


class RateLimitService:
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client

    def _get_limits(self, client: APIClient) -> tuple[int, int]:
        """
        Resolve (requests_allowed, window_seconds) for a client.

        Priority:
          1. Client's explicit RateLimitConfig row (loaded via relationship)
          2. Plan-based default from PLAN_RATE_LIMITS
        """
        if client.rate_limit_config is not None:
            return (
                client.rate_limit_config.requests_allowed,
                client.rate_limit_config.window_seconds,
            )
        return PLAN_RATE_LIMITS[client.plan]

    async def check_and_increment(self, client: APIClient) -> tuple[bool, int, int, int]:
        """
        Perform one Fixed Window rate limit check-and-increment for `client`.

        Returns:
            allowed        (bool)  – True if the request is within the limit
            current_count  (int)   – counter value after this increment
            limit          (int)   – requests_allowed for this client
            window_seconds (int)   – window size in seconds

        The caller (middleware) uses `allowed` to decide whether to forward
        the request, and the remaining three values to populate
        X-RateLimit-* response headers (good practice, expected in interviews).
        """
        requests_allowed, window_seconds = self._get_limits(client)
        key = _window_key(client.api_key, window_seconds)

        # Atomic pipeline: INCR + conditional EXPIRE.
        # Using a pipeline (single round-trip) rather than two separate calls
        # prevents a race condition where INCR succeeds but the process dies
        # before EXPIRE, leaving a key that never expires.
        async with self.redis.pipeline(transaction=True) as pipe:
            await pipe.incr(key)
            await pipe.expire(key, window_seconds)
            results = await pipe.execute()

        current_count: int = results[0]
        allowed = current_count <= requests_allowed

        return allowed, current_count, requests_allowed, window_seconds

    async def get_current_count(self, client: APIClient) -> int:
        """Read the current counter without incrementing (for analytics/debug)."""
        _, window_seconds = self._get_limits(client)
        key = _window_key(client.api_key, window_seconds)
        value = await self.redis.get(key)
        return int(value) if value else 0
