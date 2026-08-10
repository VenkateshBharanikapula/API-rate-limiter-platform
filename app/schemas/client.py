"""
Pydantic schemas for the Client Management module (Module 1).

Naming convention used throughout the project:
  - `*Create` / `*Update`: inbound request bodies
  - bare `*` (e.g. `ClientRead`): outbound response bodies
  - `*WithKey`: a response variant that includes the plaintext API key,
    used ONLY on the registration response (the one time the key is
    safe/expected to be shown -- see note on ClientRegisterResponse below)
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.client import PlanType


class ClientCreate(BaseModel):
    client_name: str = Field(..., min_length=1, max_length=255, examples=["Weather Service"])
    email: EmailStr = Field(..., examples=["admin@weather.com"])
    plan: PlanType = Field(default=PlanType.FREE, examples=["free"])


class ClientRead(BaseModel):
    """
    Standard client representation. Deliberately excludes `api_key` --
    once issued, the key is never returned again by any read endpoint.
    If a client loses their key, the correct flow is a key rotation
    endpoint (not implemented here), not re-displaying the old one.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    client_name: str
    email: str
    plan: PlanType
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ClientRegisterResponse(BaseModel):
    """
    Response returned exactly once, at registration time. This is the only
    endpoint in the system that ever exposes the plaintext API key.
    """

    client_id: int
    api_key: str


class ClientListResponse(BaseModel):
    """Paginated list envelope -- see Module 10 (search/filter/pagination)."""

    total: int
    page: int
    page_size: int
    results: list[ClientRead]
