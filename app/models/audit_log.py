"""
AuditLog: an append-only record of administrative/security-relevant actions
(Module 8) -- client registration, API key generation, rate limit changes,
activation/deactivation.

`metadata` is intentionally a flexible JSON blob rather than a fixed set of
columns, since each action type carries different contextual data (e.g. a
rate limit update logs old/new values; a registration logs the assigned
plan). A fixed schema would force either a lot of nullable columns or a
separate table per action type, neither of which earns its complexity here.
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, Enum, ForeignKey, Index, JSON, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.client import APIClient


class AuditAction(str, enum.Enum):
    CLIENT_REGISTERED = "client_registered"
    API_KEY_GENERATED = "api_key_generated"
    RATE_LIMIT_UPDATED = "rate_limit_updated"
    CLIENT_ACTIVATED = "client_activated"
    CLIENT_DEACTIVATED = "client_deactivated"


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_client_created", "client_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    client_id: Mapped[int] = mapped_column(
        ForeignKey("api_clients.id", ondelete="CASCADE"), nullable=False, index=True
    )

    action: Mapped[AuditAction] = mapped_column(
        Enum(AuditAction, name="audit_action", native_enum=False), nullable=False, index=True
    )

    # Note: named `extra_data` rather than `metadata` -- `metadata` is a
    # reserved attribute name on SQLAlchemy's declarative Base. The DB
    # column itself is still named `metadata` to match the spec exactly.
    extra_data: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    # --- relationships ---
    client: Mapped[APIClient] = relationship(back_populates="audit_logs")

    def __repr__(self) -> str:
        return f"<AuditLog client_id={self.client_id} action={self.action}>"
