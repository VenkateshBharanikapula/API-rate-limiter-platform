"""
Integration tests for Client Management endpoints (Module 1).

Uses the `client` fixture (httpx AsyncClient with real DB + fakeredis)
so these tests exercise the full request/response cycle including
middleware, dependency injection, and serialisation.
"""

import pytest


@pytest.mark.asyncio
class TestRegisterClient:
    async def test_register_returns_201_with_key(self, client):
        resp = await client.post("/api/v1/clients", json={
            "client_name": "Weather Service",
            "email": "admin@weather.com",
            "plan": "free",
        })
        assert resp.status_code == 201
        body = resp.json()
        assert "client_id" in body
        assert "api_key" in body
        assert isinstance(body["api_key"], str)
        assert len(body["api_key"]) > 20

    async def test_register_default_plan_is_free(self, client):
        resp = await client.post("/api/v1/clients", json={
            "client_name": "No Plan Service",
            "email": "noplan@example.com",
        })
        assert resp.status_code == 201

    async def test_register_duplicate_email_returns_409(self, client):
        payload = {"client_name": "Dup", "email": "dup@example.com", "plan": "free"}
        await client.post("/api/v1/clients", json=payload)
        resp = await client.post("/api/v1/clients", json=payload)
        assert resp.status_code == 409
        assert "already registered" in resp.json()["detail"]

    async def test_register_invalid_email_returns_422(self, client):
        resp = await client.post("/api/v1/clients", json={
            "client_name": "Bad Email",
            "email": "not-an-email",
            "plan": "free",
        })
        assert resp.status_code == 422

    async def test_register_missing_name_returns_422(self, client):
        resp = await client.post("/api/v1/clients", json={
            "email": "ok@example.com",
            "plan": "free",
        })
        assert resp.status_code == 422


@pytest.mark.asyncio
class TestGetClient:
    async def test_get_existing_client(self, client):
        reg = await client.post("/api/v1/clients", json={
            "client_name": "Getter", "email": "getter@example.com", "plan": "basic",
        })
        client_id = reg.json()["client_id"]

        resp = await client.get(f"/api/v1/clients/{client_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == client_id
        assert body["client_name"] == "Getter"
        assert "api_key" not in body   # key must never appear in read responses

    async def test_get_nonexistent_returns_404(self, client):
        resp = await client.get("/api/v1/clients/99999")
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestListClients:
    async def test_list_returns_paginated_envelope(self, client):
        for i in range(3):
            await client.post("/api/v1/clients", json={
                "client_name": f"Client {i}", "email": f"cl{i}@example.com", "plan": "free",
            })

        resp = await client.get("/api/v1/clients")
        assert resp.status_code == 200
        body = resp.json()
        assert "total" in body
        assert "results" in body
        assert body["total"] == 3

    async def test_list_search_filter(self, client):
        await client.post("/api/v1/clients", json={
            "client_name": "WeatherAPI", "email": "wx@example.com", "plan": "free"
        })
        await client.post("/api/v1/clients", json={
            "client_name": "FinanceAPI", "email": "fin@example.com", "plan": "premium"
        })

        resp = await client.get("/api/v1/clients?search=Weather")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1
        assert resp.json()["results"][0]["client_name"] == "WeatherAPI"

    async def test_list_plan_filter(self, client):
        await client.post("/api/v1/clients", json={
            "client_name": "FreeClient", "email": "fr@example.com", "plan": "free"
        })
        await client.post("/api/v1/clients", json={
            "client_name": "PremClient", "email": "pr@example.com", "plan": "premium"
        })

        resp = await client.get("/api/v1/clients?plan=premium")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    async def test_list_pagination(self, client):
        for i in range(5):
            await client.post("/api/v1/clients", json={
                "client_name": f"P{i}", "email": f"p{i}@example.com", "plan": "free"
            })

        resp = await client.get("/api/v1/clients?page=1&page_size=2")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 5
        assert len(body["results"]) == 2
        assert body["page"] == 1


@pytest.mark.asyncio
class TestEnableDisableClient:
    async def test_disable_client(self, client):
        reg = await client.post("/api/v1/clients", json={
            "client_name": "Disabler", "email": "dis@example.com", "plan": "free"
        })
        client_id = reg.json()["client_id"]

        resp = await client.patch(f"/api/v1/clients/{client_id}/disable")
        assert resp.status_code == 200
        assert resp.json()["is_active"] is False

    async def test_enable_client(self, client):
        reg = await client.post("/api/v1/clients", json={
            "client_name": "Enabler", "email": "en@example.com", "plan": "free"
        })
        client_id = reg.json()["client_id"]
        await client.patch(f"/api/v1/clients/{client_id}/disable")

        resp = await client.patch(f"/api/v1/clients/{client_id}/enable")
        assert resp.status_code == 200
        assert resp.json()["is_active"] is True

    async def test_disable_nonexistent_returns_404(self, client):
        resp = await client.patch("/api/v1/clients/99999/disable")
        assert resp.status_code == 404
