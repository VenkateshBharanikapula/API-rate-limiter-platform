"""
Test factories using factory-boy.

These create ORM model instances (not persisted unless you call
`session.add()` manually or use the async helper below). Keeping object
construction in factories means tests stay concise and the "default valid
object" definition lives in one place.
"""

import factory

from app.core.security import generate_api_key
from app.models.audit_log import AuditAction, AuditLog
from app.models.client import APIClient, PlanType
from app.models.rate_limit import RateLimitConfig
from app.models.usage import APIUsage


class APIClientFactory(factory.Factory):
    class Meta:
        model = APIClient

    client_name = factory.Sequence(lambda n: f"Test Client {n}")
    email = factory.Sequence(lambda n: f"client{n}@example.com")
    api_key = factory.LazyFunction(generate_api_key)
    plan = PlanType.FREE
    is_active = True


class RateLimitConfigFactory(factory.Factory):
    class Meta:
        model = RateLimitConfig

    client_id = factory.Sequence(lambda n: n + 1)
    requests_allowed = 10
    window_seconds = 60


class APIUsageFactory(factory.Factory):
    class Meta:
        model = APIUsage

    client_id = factory.Sequence(lambda n: n + 1)
    endpoint = "/api/v1/usage/current"
    request_count = 1
    was_allowed = True


class AuditLogFactory(factory.Factory):
    class Meta:
        model = AuditLog

    client_id = factory.Sequence(lambda n: n + 1)
    action = AuditAction.CLIENT_REGISTERED
    extra_data = None


async def create_client_in_db(session, **kwargs) -> APIClient:
    """
    Convenience helper: build an APIClient via factory, persist it,
    and attach a default RateLimitConfig row. Returns the saved client.
    """
    from app.core.constants import PLAN_RATE_LIMITS

    client = APIClientFactory(**kwargs)
    session.add(client)
    await session.flush()
    await session.refresh(client)

    requests_allowed, window_seconds = PLAN_RATE_LIMITS[client.plan]
    config = RateLimitConfig(
        client_id=client.id,
        requests_allowed=requests_allowed,
        window_seconds=window_seconds,
    )
    session.add(config)
    await session.flush()
    await session.refresh(client)
    return client
