"""
Audit log repository: append-only writes for AuditLog rows.

Reads (listing/filtering audit history) live in app/selectors/, not here --
see app/selectors/audit_selectors.py once added, following the project's
convention of repositories-for-writes vs selectors-for-read-heavy/reporting
queries.
"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditAction, AuditLog


class AuditLogRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self, *, client_id: int, action: AuditAction, extra_data: dict[str, Any] | None = None
    ) -> AuditLog:
        entry = AuditLog(client_id=client_id, action=action, extra_data=extra_data)
        self.db.add(entry)
        await self.db.flush()
        await self.db.refresh(entry)
        return entry
