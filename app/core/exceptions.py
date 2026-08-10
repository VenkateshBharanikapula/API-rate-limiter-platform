"""
Application-level exceptions.

Services raise these instead of HTTPException directly, which keeps the
service layer framework-agnostic (no FastAPI import needed) and lets us
register a single set of exception handlers in main.py that translate them
to the right HTTP status + response body.
"""


class AppError(Exception):
    """Base class for all application-raised errors."""

    status_code: int = 500
    detail: str = "Internal server error"

    def __init__(self, detail: str | None = None):
        if detail:
            self.detail = detail
        super().__init__(self.detail)


class NotFoundError(AppError):
    status_code = 404
    detail = "Resource not found"


class ConflictError(AppError):
    status_code = 409
    detail = "Resource already exists"


class InvalidAPIKeyError(AppError):
    status_code = 401
    detail = "Invalid API Key"


class InactiveClientError(AppError):
    status_code = 403
    detail = "Client is disabled"


class RateLimitExceededError(AppError):
    status_code = 429
    detail = "Rate limit exceeded"
