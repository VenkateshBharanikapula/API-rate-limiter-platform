"""
Unit tests for ClientService business logic.

Uses an in-memory SQLite DB (via the db_session fixture from conftest).
Tests verify: registration flow, uniqueness enforcement, API key generation,
rate limit provisioning, audit log creation, enable/disable behaviour.
"""

import pytest

from app.core.exceptions import ConflictError, NotFoundError
from app.models.client import PlanType
from app.services.client_service import ClientService
from tests.factories.factories import create_client_in_db


@pytest.mark.asyncio
class TestClientServiceRegister:
    async def test_register_returns_client_and_key(self, db_session):
        svc = ClientService(db_session)
        client, api_key = await svc.register_client(
            client_name="Acme", email="acme@example.com", plan=PlanType.FREE
        )
        await db_session.commit()

        assert client.id is not None
        assert client.client_name == "Acme"
        assert client.email == "acme@example.com"
        assert client.plan == PlanType.FREE
        assert client.is_active is True
        assert isinstance(api_key, str)
        assert len(api_key) > 0

    async def test_api_key_stored_on_client(self, db_session):
        svc = ClientService(db_session)
        client, api_key = await svc.register_client(
            client_name="Test", email="t@example.com", plan=PlanType.FREE
        )
        assert client.api_key == api_key

    async def test_duplicate_email_raises_conflict(self, db_session):
        await create_client_in_db(db_session, email="dup@example.com")
        await db_session.commit()

        svc = ClientService(db_session)
        with pytest.raises(ConflictError):
            await svc.register_client(
                client_name="Other", email="dup@example.com", plan=PlanType.FREE
            )

    async def test_registration_provisions_rate_limit_config(self, db_session):
        svc = ClientService(db_session)
        client, _ = await svc.register_client(
            client_name="Tester", email="tester@example.com", plan=PlanType.BASIC
        )
        await db_session.commit()

        from app.repositories.rate_limit_repository import RateLimitConfigRepository
        repo = RateLimitConfigRepository(db_session)
        config = await repo.get_by_client_id(client.id)

        assert config is not None
        assert config.requests_allowed == 50   # BASIC plan default
        assert config.window_seconds == 60

    async def test_registration_writes_audit_logs(self, db_session):
        svc = ClientService(db_session)
        client, _ = await svc.register_client(
            client_name="Logged", email="logged@example.com", plan=PlanType.FREE
        )
        await db_session.commit()

        from sqlalchemy import select
        from app.models.audit_log import AuditLog, AuditAction
        result = await db_session.execute(
            select(AuditLog).where(AuditLog.client_id == client.id)
        )
        logs = result.scalars().all()
        actions = {log.action for log in logs}

        assert AuditAction.CLIENT_REGISTERED in actions
        assert AuditAction.API_KEY_GENERATED in actions


@pytest.mark.asyncio
class TestClientServiceGetAndList:
    async def test_get_client_returns_correct_client(self, db_session):
        existing = await create_client_in_db(db_session)
        await db_session.commit()

        svc = ClientService(db_session)
        fetched = await svc.get_client(existing.id)
        assert fetched.id == existing.id

    async def test_get_nonexistent_client_raises_not_found(self, db_session):
        svc = ClientService(db_session)
        with pytest.raises(NotFoundError):
            await svc.get_client(99999)

    async def test_list_returns_all_clients(self, db_session):
        for i in range(3):
            await create_client_in_db(db_session, email=f"list{i}@example.com")
        await db_session.commit()

        svc = ClientService(db_session)
        clients, total = await svc.list_clients()
        assert total == 3
        assert len(clients) == 3

    async def test_list_search_filters_by_name(self, db_session):
        await create_client_in_db(db_session, client_name="Weather API", email="w@example.com")
        await create_client_in_db(db_session, client_name="Finance API", email="f@example.com")
        await db_session.commit()

        svc = ClientService(db_session)
        clients, total = await svc.list_clients(search="Weather")
        assert total == 1
        assert clients[0].client_name == "Weather API"

    async def test_list_filter_by_status(self, db_session):
        await create_client_in_db(db_session, is_active=True, email="active@example.com")
        await create_client_in_db(db_session, is_active=False, email="inactive@example.com")
        await db_session.commit()

        svc = ClientService(db_session)
        active_clients, total = await svc.list_clients(status="active")
        assert total == 1
        assert active_clients[0].is_active is True

    async def test_list_filter_by_plan(self, db_session):
        await create_client_in_db(db_session, plan=PlanType.FREE, email="free@example.com")
        await create_client_in_db(db_session, plan=PlanType.PREMIUM, email="prem@example.com")
        await db_session.commit()

        svc = ClientService(db_session)
        clients, total = await svc.list_clients(plan="premium")
        assert total == 1
        assert clients[0].plan == PlanType.PREMIUM

    async def test_list_pagination(self, db_session):
        for i in range(5):
            await create_client_in_db(db_session, email=f"page{i}@example.com")
        await db_session.commit()

        svc = ClientService(db_session)
        page1, total = await svc.list_clients(page=1, page_size=2)
        assert total == 5
        assert len(page1) == 2

        page3, _ = await svc.list_clients(page=3, page_size=2)
        assert len(page3) == 1


@pytest.mark.asyncio
class TestClientServiceEnableDisable:
    async def test_disable_client(self, db_session):
        client = await create_client_in_db(db_session, is_active=True)
        await db_session.commit()

        svc = ClientService(db_session)
        updated = await svc.disable_client(client.id)
        await db_session.commit()

        assert updated.is_active is False

    async def test_enable_client(self, db_session):
        client = await create_client_in_db(db_session, is_active=False)
        await db_session.commit()

        svc = ClientService(db_session)
        updated = await svc.enable_client(client.id)
        await db_session.commit()

        assert updated.is_active is True

    async def test_disable_writes_audit_log(self, db_session):
        client = await create_client_in_db(db_session)
        await db_session.commit()

        svc = ClientService(db_session)
        await svc.disable_client(client.id)
        await db_session.commit()

        from sqlalchemy import select
        from app.models.audit_log import AuditLog, AuditAction
        result = await db_session.execute(
            select(AuditLog)
            .where(AuditLog.client_id == client.id)
            .where(AuditLog.action == AuditAction.CLIENT_DEACTIVATED)
        )
        assert result.scalar_one_or_none() is not None

    async def test_disable_nonexistent_client_raises_not_found(self, db_session):
        svc = ClientService(db_session)
        with pytest.raises(NotFoundError):
            await svc.disable_client(99999)
