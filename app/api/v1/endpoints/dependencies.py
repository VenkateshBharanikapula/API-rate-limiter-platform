"""
Shared pagination query parameters (Module 10).

A single dependency reused by every list endpoint in the project so page/
page_size bounds-checking lives in one place instead of being copy-pasted
per router.
"""

from fastapi import Query

from app.core.config import get_settings

settings = get_settings()


class PaginationParams:
    def __init__(
        self,
        page: int = Query(default=1, ge=1, description="1-indexed page number"),
        page_size: int = Query(
            default=settings.default_page_size,
            ge=1,
            le=settings.max_page_size,
            description=f"Items per page (max {settings.max_page_size})",
        ),
    ):
        self.page = page
        self.page_size = page_size
