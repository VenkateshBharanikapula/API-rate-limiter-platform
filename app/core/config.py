"""
Centralized application configuration.

All runtime config is loaded from environment variables (see .env.example).
Using pydantic-settings gives us:
  - type validation at startup (fail fast if a required var is missing/malformed)
  - a single source of truth instead of os.environ scattered through the codebase
  - easy overrides in tests via Settings(**overrides)
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- App ---
    app_name: str = "API Rate Limiting & API Key Management Platform"
    environment: str = "local"
    debug: bool = True
    secret_key: str = "insecure-dev-key-override-me"
    api_v1_prefix: str = "/api/v1"

    # --- Database ---
    database_url: str = "postgresql+asyncpg://ratelimiter:ratelimiter@localhost:5432/ratelimiter"
    database_url_sync: str = "postgresql+psycopg2://ratelimiter:ratelimiter@localhost:5432/ratelimiter"

    # --- Redis ---
    redis_url: str = "redis://localhost:6379/0"

    # --- Rate limiting defaults (used when a client has no RateLimitConfig row) ---
    default_rate_limit_requests: int = 10
    default_rate_limit_window_seconds: int = 60

    # --- Pagination ---
    default_page_size: int = 20
    max_page_size: int = 100


@lru_cache
def get_settings() -> Settings:
    """
    Cached settings accessor.

    FastAPI dependencies call this rather than instantiating Settings() directly,
    so the environment is only parsed once per process and can be overridden
    cleanly in tests via dependency_overrides.
    """
    return Settings()
