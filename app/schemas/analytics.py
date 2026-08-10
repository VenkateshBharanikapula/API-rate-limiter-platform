"""Schemas for usage tracking (Module 6) and analytics (Module 7)."""

from pydantic import BaseModel

class UsageStats(BaseModel):
    total: int
    successful: int
    blocked: int
    period: str


class CurrentUsageResponse(UsageStats):
    since: str


class DailyUsageResponse(UsageStats):
    date: str


class MonthlyUsageResponse(UsageStats):
    month: str


# --- Analytics ---

class ClientSummaryResponse(BaseModel):
    client_id: int
    total_requests: int
    successful_requests: int
    blocked_requests: int


class TopClientEntry(BaseModel):
    client_id: int
    client_name: str
    total_requests: int


class SystemStatsResponse(BaseModel):
    total_clients: int
    active_clients: int
    total_requests: int
    successful_requests: int
    blocked_requests: int
    success_rate_pct: float
