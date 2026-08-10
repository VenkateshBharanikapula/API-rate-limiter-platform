"""
APIClient: an API consumer (e.g. a company/service) that has been issued an
API key and consumes the platform's protected endpoints.

This is the root entity everything else (rate limit config, usage records,
audit logs) hangs off of.
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Enum, String, Boolean, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.rate_limit import RateLimitConfig
    from app.models.usage import APIUsage
    from app.models.audit_log import AuditLog


class PlanType(str, enum.Enum):
    """
    Subscription tier. Determines the default rate limit applied to a client
    when no custom RateLimitConfig row exists for them yet (see
    app/services/rate_limit_service.py for the resolution logic).
    """

    FREE = "free"
    BASIC = "basic"
    PREMIUM = "premium"


class APIClient(Base):
    __tablename__ = "api_clients"

    id: Mapped[int] = mapped_column(primary_key=True)

    client_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)

    # Stored as a unique, indexed string -- this is the value clients send via
    # the X-API-KEY header on every request, so lookups must be O(1)/indexed.
    api_key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)

    plan: Mapped[PlanType] = mapped_column(
        Enum(PlanType, name="plan_type", native_enum=False),
        nullable=False,
        default=PlanType.FREE,
        server_default=PlanType.FREE.value,
    )

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # --- relationships ---
    rate_limit_config: Mapped[RateLimitConfig | None] = relationship(
        back_populates="client", uselist=False, cascade="all, delete-orphan"
    )
    usage_records: Mapped[list[APIUsage]] = relationship(
        back_populates="client", cascade="all, delete-orphan"
    )
    audit_logs: Mapped[list[AuditLog]] = relationship(
        back_populates="client", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<APIClient id={self.id} name={self.client_name!r} plan={self.plan} active={self.is_active}>"
