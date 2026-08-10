"""Pydantic schemas for rate limit config endpoints (Module 5)."""

from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class RateLimitConfigRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    client_id: int
    requests_allowed: int
    window_seconds: int
    created_at: datetime
    updated_at: datetime


class RateLimitConfigUpdate(BaseModel):
    requests_allowed: int = Field(..., ge=1, le=100_000, examples=[100])
    window_seconds: int = Field(..., ge=1, le=86_400, examples=[60])
