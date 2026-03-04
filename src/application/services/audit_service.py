from typing import Optional
from uuid import UUID

from fastapi import Depends

from src.infrastructure.repositories.audit_log import AuditLogRepository


class AuditService:
    def __init__(self, repo: AuditLogRepository = Depends()) -> None:
        self._repo = repo

    async def log(
        self,
        tenant_id: UUID,
        user_id: UUID,
        action: str,
        resource_type: str,
        resource_id: Optional[UUID] = None,
        details: Optional[dict] = None,
    ) -> None:
        """Write an audit log entry. Silently ignores errors to never break the main flow."""
        try:
            await self._repo.create_log(
                tenant_id=tenant_id,
                user_id=user_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                details=details,
            )
        except Exception:
            pass
