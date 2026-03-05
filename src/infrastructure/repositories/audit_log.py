from datetime import datetime
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

    async def get_all_global(
        self,
        limit: int = 20,
        offset: int = 0,
        tenant_id: UUID | None = None,
        action: str | None = None,
        from_dt: datetime | None = None,
        to_dt: datetime | None = None,
    ) -> tuple[list[dict], int]:
        """Admin-only: fetch audit logs across all tenants with optional filters."""
        from src.infrastructure.models.users import User

        filters = []
        if tenant_id:
            filters.append(self.table.tenant_id == tenant_id)
        if action:
            filters.append(self.table.action == action)
        if from_dt:
            filters.append(self.table.created_at >= from_dt)
        if to_dt:
            filters.append(self.table.created_at <= to_dt)

        count_q = (
            sa.select(sa.func.count())
            .select_from(self.table)
            .where(*filters)
        )
        total = (await self._session.execute(count_q)).scalar_one()

        data_q = (
            sa.select(self.table, User.email.label("user_email"))
            .outerjoin(User, self.table.user_id == User.id)
            .where(*filters)
            .order_by(self.table.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        rows = (await self._session.execute(data_q)).all()

        items = [
            {
                "id": str(log.id),
                "tenant_id": str(log.tenant_id),
                "user_id": str(log.user_id),
                "user_email": user_email,
                "action": log.action,
                "resource_type": log.resource_type,
                "resource_id": str(log.resource_id) if log.resource_id else None,
                "details": log.details,
                "created_at": log.created_at.isoformat(),
            }
            for log, user_email in rows
        ]
        return items, total
