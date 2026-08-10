"""
APIUsage: a durable, queryable record of API consumption.

This is distinct from the Redis rate-limit counters (app/db/redis.py), which
are ephemeral and only exist to enforce the current window's limit. This
table is what powers historical analytics (Module 6/7) -- daily/monthly
usage, top consumers, success/blocked breakdowns -- queries Redis is a poor
fit for since its counters expire.

Rows are written by the rate limiting middleware after each request is
processed (see app/middleware/rate_limiter.py), one row per request so we
retain endpoint-level granularity. For high-traffic production systems this
would typically be batched/aggregated, but per-request rows keep the
analytics queries simple and the audit trail exact, which suits this
project's scope.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.client import APIClient


class APIUsage(Base):
    __tablename__ = "api_usage"
    __table_args__ = (
        # Powers "usage for client X in time range" queries (current/daily/monthly
        # usage endpoints, analytics summaries) without a full table scan.
        Index("ix_api_usage_client_timestamp", "client_id", "timestamp"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    client_id: Mapped[int] = mapped_column(
        ForeignKey("api_clients.id", ondelete="CASCADE"), nullable=False, index=True
    )

    endpoint: Mapped[str] = mapped_column(String(255), nullable=False)

    # request_count exists per the spec's schema; for the per-request logging
    # strategy used here it's effectively always 1, but keeping the column lets
    # this table absorb pre-aggregated/batched writes later without a schema
    # change (see module docstring above).
    request_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")

    was_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")

    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    # --- relationships ---
    client: Mapped[APIClient] = relationship(back_populates="usage_records")

    def __repr__(self) -> str:
        return f"<APIUsage client_id={self.client_id} endpoint={self.endpoint!r} allowed={self.was_allowed}>"
