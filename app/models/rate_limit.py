"""
RateLimitConfig: per-client override of the fixed-window rate limit.

A client without a row here falls back to the plan-based default defined in
app.core.constants (FREE/BASIC/PREMIUM). A row here lets an admin grant a
custom limit regardless of plan (Module 5: "Admin APIs should allow updating
limits").
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.client import APIClient


class RateLimitConfig(Base):
    __tablename__ = "rate_limit_configs"

    id: Mapped[int] = mapped_column(primary_key=True)

    client_id: Mapped[int] = mapped_column(
        ForeignKey("api_clients.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )

    requests_allowed: Mapped[int] = mapped_column(Integer, nullable=False)
    window_seconds: Mapped[int] = mapped_column(Integer, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # --- relationships ---
    client: Mapped[APIClient] = relationship(back_populates="rate_limit_config")

    def __repr__(self) -> str:
        return (
            f"<RateLimitConfig client_id={self.client_id} "
            f"{self.requests_allowed}/{self.window_seconds}s>"
        )
