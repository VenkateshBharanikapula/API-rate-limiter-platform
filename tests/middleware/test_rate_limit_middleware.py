"""
Middleware tests (Modules 2, 3, 4).

These tests exercise the RateLimitMiddleware end-to-end via the httpx
AsyncClient fixture. They verify:
  - missing/invalid API key → 401
  - disabled client → 403
  - within-limit requests → 200 with X-RateLimit-* headers
  - over-limit requests → 429
  - exempt paths (health, docs) bypass auth entirely
  - rate limit counters are independent per client
"""

import pytest


async def register(client, name: str, email: str, plan: str = "free") -> dict:
    """Helper: register a client and return {client_id, api_key}."""
    resp = await client.post("/api/v1/clients", json={
        "client_name": name, "email": email, "plan": plan
    })
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.mark.asyncio
class TestAuthMiddleware:
    async def test_missing_api_key_returns_401(self, client):
        resp = await client.get("/api/v1/usage/current")
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid API Key"

    async def test_invalid_api_key_returns_401(self, client):
        resp = await client.get(
            "/api/v1/usage/current",
            headers={"X-API-KEY": "totally-bogus-key"},
        )
        assert resp.status_code == 401

    async def test_valid_api_key_is_accepted(self, client):
        creds = await register(client, "ValidUser", "valid@example.com")
        resp = await client.get(
            "/api/v1/usage/current",
            headers={"X-API-KEY": creds["api_key"]},
        )
        assert resp.status_code == 200

    async def test_disabled_client_returns_403(self, client):
        creds = await register(client, "ToDisable", "disable@example.com")
        await client.patch(f"/api/v1/clients/{creds['client_id']}/disable")

        resp = await client.get(
            "/api/v1/usage/current",
            headers={"X-API-KEY": creds["api_key"]},
        )
        assert resp.status_code == 403
        assert "disabled" in resp.json()["detail"].lower()


@pytest.mark.asyncio
class TestExemptPaths:
    async def test_health_exempt_from_auth(self, client):
        resp = await client.get("/health")
        # Health might return 503 if DB/Redis aren't available in test env,
        # but it must NEVER return 401.
        assert resp.status_code != 401

    async def test_root_exempt_from_auth(self, client):
        resp = await client.get("/")
        assert resp.status_code != 401

    async def test_docs_exempt_from_auth(self, client):
        resp = await client.get("/docs")
        assert resp.status_code != 401

    async def test_client_registration_exempt_from_auth(self, client):
        """POST /api/v1/clients must work without an API key."""
        resp = await client.post("/api/v1/clients", json={
            "client_name": "Bootstrap", "email": "boot@example.com", "plan": "free"
        })
        assert resp.status_code == 201


@pytest.mark.asyncio
class TestRateLimitHeaders:
    async def test_rate_limit_headers_present_on_success(self, client):
        creds = await register(client, "HeaderTest", "hdr@example.com", plan="free")
        resp = await client.get(
            "/api/v1/usage/current",
            headers={"X-API-KEY": creds["api_key"]},
        )
        assert resp.status_code == 200
        assert "x-ratelimit-limit" in resp.headers
        assert "x-ratelimit-remaining" in resp.headers
        assert "x-ratelimit-window" in resp.headers

    async def test_remaining_decrements_on_each_request(self, client):
        creds = await register(client, "Decrement", "dec@example.com", plan="free")
        headers = {"X-API-KEY": creds["api_key"]}

        resp1 = await client.get("/api/v1/usage/current", headers=headers)
        resp2 = await client.get("/api/v1/usage/current", headers=headers)

        remaining1 = int(resp1.headers["x-ratelimit-remaining"])
        remaining2 = int(resp2.headers["x-ratelimit-remaining"])
        assert remaining2 < remaining1

    async def test_limit_header_matches_plan(self, client):
        creds = await register(client, "PremiumH", "premh@example.com", plan="premium")
        resp = await client.get(
            "/api/v1/usage/current",
            headers={"X-API-KEY": creds["api_key"]},
        )
        assert int(resp.headers["x-ratelimit-limit"]) == 200


@pytest.mark.asyncio
class TestRateLimitEnforcement:
    async def test_requests_blocked_after_limit(self, client):
        """Free plan = 10 req/min. The 11th should get 429."""
        creds = await register(client, "RateLimitee", "rl@example.com", plan="free")
        headers = {"X-API-KEY": creds["api_key"]}

        for i in range(10):
            resp = await client.get("/api/v1/usage/current", headers=headers)
            assert resp.status_code == 200, f"Request {i+1} should be allowed"

        resp = await client.get("/api/v1/usage/current", headers=headers)
        assert resp.status_code == 429
        assert resp.json()["detail"] == "Rate limit exceeded"

    async def test_429_response_includes_rate_limit_headers(self, client):
        creds = await register(client, "Exhausted", "exh@example.com", plan="free")
        headers = {"X-API-KEY": creds["api_key"]}

        for _ in range(10):
            await client.get("/api/v1/usage/current", headers=headers)

        resp = await client.get("/api/v1/usage/current", headers=headers)
        assert resp.status_code == 429
        assert "x-ratelimit-limit" in resp.headers
        assert resp.headers["x-ratelimit-remaining"] == "0"

    async def test_two_clients_have_independent_limits(self, client):
        creds_a = await register(client, "ClientA", "ca@example.com", plan="free")
        creds_b = await register(client, "ClientB", "cb@example.com", plan="free")

        # Exhaust client A
        for _ in range(10):
            await client.get(
                "/api/v1/usage/current", headers={"X-API-KEY": creds_a["api_key"]}
            )

        # client A is now rate limited
        resp_a = await client.get(
            "/api/v1/usage/current", headers={"X-API-KEY": creds_a["api_key"]}
        )
        assert resp_a.status_code == 429

        # client B should still be allowed
        resp_b = await client.get(
            "/api/v1/usage/current", headers={"X-API-KEY": creds_b["api_key"]}
        )
        assert resp_b.status_code == 200

    async def test_premium_plan_allows_more_requests(self, client):
        creds = await register(client, "PremiumUser", "pu@example.com", plan="premium")
        headers = {"X-API-KEY": creds["api_key"]}

        # 50 requests should all be allowed (well within 200/min premium limit)
        for i in range(50):
            resp = await client.get("/api/v1/usage/current", headers=headers)
            assert resp.status_code == 200, f"Premium request {i+1} was blocked"
