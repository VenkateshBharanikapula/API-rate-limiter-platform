"""Unit tests for app/core/security.py and app/core/constants.py."""

import pytest

from app.core.security import generate_api_key, API_KEY_BYTES
from app.core.constants import PLAN_RATE_LIMITS
from app.models.client import PlanType


class TestGenerateApiKey:
    def test_returns_string(self):
        key = generate_api_key()
        assert isinstance(key, str)

    def test_length_within_column_limit(self):
        # VARCHAR(64) -- every generated key must fit
        for _ in range(50):
            assert len(generate_api_key()) <= 64

    def test_uniqueness(self):
        keys = {generate_api_key() for _ in range(100)}
        assert len(keys) == 100

    def test_url_safe_characters_only(self):
        import re
        for _ in range(50):
            key = generate_api_key()
            assert re.match(r"^[A-Za-z0-9_\-]+$", key), f"Non-URL-safe key: {key}"


class TestPlanRateLimits:
    def test_all_plans_present(self):
        for plan in PlanType:
            assert plan in PLAN_RATE_LIMITS

    def test_free_plan_limits(self):
        requests, window = PLAN_RATE_LIMITS[PlanType.FREE]
        assert requests == 10
        assert window == 60

    def test_basic_plan_limits(self):
        requests, window = PLAN_RATE_LIMITS[PlanType.BASIC]
        assert requests == 50
        assert window == 60

    def test_premium_plan_limits(self):
        requests, window = PLAN_RATE_LIMITS[PlanType.PREMIUM]
        assert requests == 200
        assert window == 60

    def test_premium_has_highest_limit(self):
        limits = {plan: reqs for plan, (reqs, _) in PLAN_RATE_LIMITS.items()}
        assert limits[PlanType.PREMIUM] > limits[PlanType.BASIC] > limits[PlanType.FREE]
