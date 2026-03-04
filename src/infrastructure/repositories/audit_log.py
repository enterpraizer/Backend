from typing import Sequence
from uuid import UUID

import sqlalchemy as sa

from src.infrastructure.models.audit_log import AuditLog
from src.infrastructure.repositories.base import BaseRepository


class AuditLogRepository(BaseRepository):
    table = AuditLog

    async def create_log(
        self,
        tenant_id: UUID,
        user_id: UUID,
        action: str,
        resource_type: str,
        resource_id: UUID | None = None,
        details: dict | None = None,
    ) -> AuditLog | None:
        query = (
            sa.insert(self.table)
            .values(
                tenant_id=tenant_id,
                user_id=user_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                details=details,
            )
            .returning(self.table)
        )
        result = await self._session.execute(query)
        await self._session.flush()
        return result.scalar_one_or_none()

    async def get_recent(
        self, tenant_id: UUID, limit: int = 20
    ) -> Sequence[AuditLog]:
        query = (
            sa.select(self.table)
            .where(self.table.tenant_id == tenant_id)
            .order_by(self.table.created_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(query)
        return result.scalars().all()

    async def get_by_resource(
        self,
        tenant_id: UUID,
        resource_type: str,
        resource_id: UUID,
    ) -> Sequence[AuditLog]:
        query = (
            sa.select(self.table)
            .where(
                self.table.tenant_id == tenant_id,
                self.table.resource_type == resource_type,
                self.table.resource_id == resource_id,
            )
            .order_by(self.table.created_at.desc())
        )
        result = await self._session.execute(query)
        return result.scalars().all()
