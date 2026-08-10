"""
Unit tests for RateLimitService (Fixed Window algorithm).

Uses fakeredis so no real Redis process is needed.
Tests cover: counter increment, limit enforcement, window key structure,
pipeline atomicity behaviour, and the config resolution priority.
"""

import pytest
import pytest_asyncio
import fakeredis.aioredis as fakeredis

from app.models.client import APIClient, PlanType
from app.models.rate_limit import RateLimitConfig
from app.services.rate_limit_service import RateLimitService, _window_key


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_client(plan: PlanType = PlanType.FREE, api_key: str = "testkey123") -> APIClient:
    """Build an unsaved APIClient instance for tests."""
    c = APIClient()
    c.id = 1
    c.client_name = "Test"
    c.email = "test@example.com"
    c.api_key = api_key
    c.plan = plan
    c.is_active = True
    c.rate_limit_config = None
    return c


def attach_config(client: APIClient, requests_allowed: int, window_seconds: int) -> APIClient:
    cfg = RateLimitConfig()
    cfg.client_id = client.id
    cfg.requests_allowed = requests_allowed
    cfg.window_seconds = window_seconds
    client.rate_limit_config = cfg
    return client


# ---------------------------------------------------------------------------
# Window key tests
# ---------------------------------------------------------------------------

class TestWindowKey:
    def test_key_prefix(self):
        key = _window_key("mykey", 60)
        assert key.startswith("rate_limit:mykey:")

    def test_key_changes_with_api_key(self):
        k1 = _window_key("key_a", 60)
        k2 = _window_key("key_b", 60)
        assert k1 != k2

    def test_key_stable_within_window(self):
        """Two calls in the same second return the same key."""
        k1 = _window_key("abc", 60)
        k2 = _window_key("abc", 60)
        assert k1 == k2

    def test_key_differs_across_window_sizes(self):
        k1 = _window_key("abc", 60)
        k2 = _window_key("abc", 120)
        assert k1 != k2


# ---------------------------------------------------------------------------
# Rate limit check-and-increment tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestRateLimitService:
    @pytest_asyncio.fixture(autouse=True)
    async def setup(self):
        self.redis = fakeredis.FakeRedis()
        self.svc = RateLimitService(self.redis)
        yield
        await self.redis.flushall()
        await self.redis.aclose()

    async def test_first_request_always_allowed(self):
        client = make_client(PlanType.FREE)
        allowed, count, limit, window = await self.svc.check_and_increment(client)
        assert allowed is True
        assert count == 1
        assert limit == 10
        assert window == 60

    async def test_counter_increments_on_each_call(self):
        client = make_client(PlanType.FREE)
        for expected in range(1, 6):
            _, count, _, _ = await self.svc.check_and_increment(client)
            assert count == expected

    async def test_request_blocked_when_limit_reached(self):
        client = make_client(PlanType.FREE)  # limit = 10
        for _ in range(10):
            allowed, _, _, _ = await self.svc.check_and_increment(client)
            assert allowed is True

        # 11th request must be blocked
        allowed, count, limit, _ = await self.svc.check_and_increment(client)
        assert allowed is False
        assert count == 11
        assert limit == 10

    async def test_premium_plan_has_higher_limit(self):
        client = make_client(PlanType.PREMIUM)  # limit = 200
        for _ in range(200):
            allowed, _, _, _ = await self.svc.check_and_increment(client)
            assert allowed is True

        allowed, _, _, _ = await self.svc.check_and_increment(client)
        assert allowed is False

    async def test_custom_config_overrides_plan_default(self):
        client = make_client(PlanType.FREE)
        attach_config(client, requests_allowed=3, window_seconds=60)

        for _ in range(3):
            allowed, _, _, _ = await self.svc.check_and_increment(client)
            assert allowed is True

        allowed, _, limit, _ = await self.svc.check_and_increment(client)
        assert allowed is False
        assert limit == 3

    async def test_different_clients_have_independent_counters(self):
        client_a = make_client(PlanType.FREE, api_key="key_a")
        client_b = make_client(PlanType.FREE, api_key="key_b")

        for _ in range(10):
            await self.svc.check_and_increment(client_a)

        # client_b's counter is still at 0 — first request must be allowed
        allowed, count, _, _ = await self.svc.check_and_increment(client_b)
        assert allowed is True
        assert count == 1

    async def test_get_current_count_reads_without_incrementing(self):
        client = make_client(PlanType.FREE)
        await self.svc.check_and_increment(client)
        await self.svc.check_and_increment(client)

        count = await self.svc.get_current_count(client)
        assert count == 2

        # A third check_and_increment should give 3, not 4
        _, after, _, _ = await self.svc.check_and_increment(client)
        assert after == 3

    async def test_basic_plan_limit(self):
        client = make_client(PlanType.BASIC)  # limit = 50
        _, _, limit, _ = await self.svc.check_and_increment(client)
        assert limit == 50
