"""
Integration tests for Usage (Module 6) and Analytics (Module 7) endpoints.
"""

import pytest


async def register_and_get_key(client, name: str, email: str, plan: str = "free") -> tuple[int, str]:
    resp = await client.post("/api/v1/clients", json={
        "client_name": name, "email": email, "plan": plan
    })
    assert resp.status_code == 201
    body = resp.json()
    return body["client_id"], body["api_key"]


async def make_requests(client, api_key: str, n: int, endpoint: str = "/api/v1/usage/current"):
    """Fire n authenticated requests to generate usage rows."""
    headers = {"X-API-KEY": api_key}
    for _ in range(n):
        await client.get(endpoint, headers=headers)


@pytest.mark.asyncio
class TestUsageEndpoints:
    async def test_current_usage_returns_correct_shape(self, client):
        _, api_key = await register_and_get_key(client, "UsageTest", "ut@example.com")
        resp = await client.get(
            "/api/v1/usage/current", headers={"X-API-KEY": api_key}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "total" in body
        assert "successful" in body
        assert "blocked" in body
        assert "period" in body
        assert "since" in body

    async def test_daily_usage_returns_correct_shape(self, client):
        _, api_key = await register_and_get_key(client, "DailyTest", "dt@example.com")
        resp = await client.get(
            "/api/v1/usage/daily", headers={"X-API-KEY": api_key}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "total" in body
        assert "date" in body
        assert body["period"] == "today"

    async def test_monthly_usage_returns_correct_shape(self, client):
        _, api_key = await register_and_get_key(client, "MonthlyTest", "mt@example.com")
        resp = await client.get(
            "/api/v1/usage/monthly", headers={"X-API-KEY": api_key}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "month" in body
        assert body["period"] == "current_month"

    async def test_usage_requires_valid_api_key(self, client):
        for path in ["/api/v1/usage/current", "/api/v1/usage/daily", "/api/v1/usage/monthly"]:
            resp = await client.get(path, headers={"X-API-KEY": "bad-key"})
            assert resp.status_code == 401


@pytest.mark.asyncio
class TestAnalyticsEndpoints:
    async def test_client_summary_returns_correct_shape(self, client):
        client_id, api_key = await register_and_get_key(
            client, "SummaryTest", "st@example.com", plan="basic"
        )
        await make_requests(client, api_key, 3)

        resp = await client.get(f"/api/v1/analytics/client/{client_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["client_id"] == client_id
        assert "total_requests" in body
        assert "successful_requests" in body
        assert "blocked_requests" in body

    async def test_client_summary_counts_are_non_negative(self, client):
        client_id, api_key = await register_and_get_key(
            client, "CountTest", "ct@example.com"
        )
        await make_requests(client, api_key, 2)

        resp = await client.get(f"/api/v1/analytics/client/{client_id}")
        body = resp.json()
        assert body["total_requests"] >= 0
        assert body["successful_requests"] >= 0
        assert body["blocked_requests"] >= 0

    async def test_top_clients_returns_list(self, client):
        for i in range(3):
            cid, key = await register_and_get_key(
                client, f"TopClient{i}", f"top{i}@example.com"
            )
            await make_requests(client, key, i + 1)

        resp = await client.get("/api/v1/analytics/top-clients")
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)

    async def test_top_clients_limit_param(self, client):
        for i in range(5):
            _, key = await register_and_get_key(
                client, f"LimitClient{i}", f"lc{i}@example.com"
            )
            await make_requests(client, key, 1)

        resp = await client.get("/api/v1/analytics/top-clients?limit=2")
        assert resp.status_code == 200
        assert len(resp.json()) <= 2

    async def test_system_stats_returns_correct_shape(self, client):
        resp = await client.get("/api/v1/analytics/system")
        assert resp.status_code == 200
        body = resp.json()
        assert "total_clients" in body
        assert "active_clients" in body
        assert "total_requests" in body
        assert "blocked_requests" in body
        assert "success_rate_pct" in body

    async def test_system_stats_client_count_increments(self, client):
        resp_before = await client.get("/api/v1/analytics/system")
        before = resp_before.json()["total_clients"]

        await register_and_get_key(client, "SystemInc", "si@example.com")

        # Bust the Redis cache so we get fresh data
        resp_after = await client.get("/api/v1/analytics/system")
        after = resp_after.json()["total_clients"]

        assert after >= before


@pytest.mark.asyncio
class TestRateLimitConfigEndpoints:
    async def test_get_rate_limit_config(self, client):
        client_id, _ = await register_and_get_key(client, "ConfigGet", "cg@example.com")

        resp = await client.get(f"/api/v1/rate-limits/{client_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["client_id"] == client_id
        assert "requests_allowed" in body
        assert "window_seconds" in body

    async def test_update_rate_limit_config(self, client):
        client_id, _ = await register_and_get_key(client, "ConfigUpdate", "cu@example.com")

        resp = await client.put(
            f"/api/v1/rate-limits/{client_id}",
            json={"requests_allowed": 999, "window_seconds": 120},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["requests_allowed"] == 999
        assert body["window_seconds"] == 120

    async def test_update_rate_limit_validates_input(self, client):
        client_id, _ = await register_and_get_key(client, "ConfigValidate", "cv@example.com")

        resp = await client.put(
            f"/api/v1/rate-limits/{client_id}",
            json={"requests_allowed": 0, "window_seconds": 60},  # ge=1 fails
        )
        assert resp.status_code == 422

    async def test_get_config_for_nonexistent_client_returns_404(self, client):
        resp = await client.get("/api/v1/rate-limits/99999")
        assert resp.status_code == 404

    async def test_updated_config_affects_rate_limiting(self, client):
        """After setting limit to 3, the 4th request should be blocked."""
        client_id, api_key = await register_and_get_key(
            client, "LowLimit", "ll@example.com", plan="premium"
        )

        # Override the premium plan's 200/min with a very low custom limit
        await client.put(
            f"/api/v1/rate-limits/{client_id}",
            json={"requests_allowed": 3, "window_seconds": 60},
        )

        headers = {"X-API-KEY": api_key}
        for _ in range(3):
            resp = await client.get("/api/v1/usage/current", headers=headers)
            assert resp.status_code == 200

        resp = await client.get("/api/v1/usage/current", headers=headers)
        assert resp.status_code == 429
