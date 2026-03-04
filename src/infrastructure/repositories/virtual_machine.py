from typing import Sequence
from uuid import UUID

import sqlalchemy as sa

from src.infrastructure.models.virtual_machine import VirtualMachine, VMStatus
from src.infrastructure.repositories.tenant_scoped import TenantScopedRepository


class VMRepository(TenantScopedRepository):
    table = VirtualMachine

    async def get_by_status(
        self, tenant_id: UUID, status: VMStatus
    ) -> Sequence[VirtualMachine]:
        query = sa.select(self.table).where(
            self.table.tenant_id == tenant_id,
            self.table.status == status,
        )
        result = await self._session.execute(query)
        return result.scalars().all()

    async def update_status(
        self,
        vm_id: UUID,
        tenant_id: UUID,
        status: VMStatus,
        **kwargs,                 # container_id, container_name, ip_address — опционально
    ) -> VirtualMachine | None:
        query = (
            sa.update(self.table)
            .where(
                self.table.id == vm_id,
                self.table.tenant_id == tenant_id,
            )
            .values(status=status, **kwargs)
            .returning(self.table)
        )
        result = await self._session.execute(query)
        await self._session.flush()
        return result.scalar_one_or_none()

    async def count_active(self, tenant_id: UUID) -> int:
        """Считает VM со статусом RUNNING или PENDING."""
        query = (
            sa.select(sa.func.count())
            .select_from(self.table)
            .where(
                self.table.tenant_id == tenant_id,
                self.table.status.in_([VMStatus.RUNNING, VMStatus.PENDING]),
            )
        )
        result = await self._session.execute(query)
        return result.scalar_one()

    async def count_by_status(self, tenant_id: UUID) -> dict[str, int]:
        """Возвращает счётчики по всем статусам для дашборда."""
        query = (
            sa.select(self.table.status, sa.func.count())
            .where(self.table.tenant_id == tenant_id)
            .group_by(self.table.status)
        )
        result = await self._session.execute(query)
        rows = result.all()
        # гарантируем что все статусы присутствуют
        counts = {s.value: 0 for s in VMStatus}
        for status, count in rows:
            counts[status.value] = count
        return counts

    async def get_all_across_tenants(
        self, limit: int, offset: int
    ) -> Sequence[VirtualMachine]:
        """Только для admin — без фильтра по tenant_id."""
        query = (
            sa.select(self.table)
            .offset(offset)
            .limit(limit)
            .order_by(self.table.created_at.desc())
        )
        result = await self._session.execute(query)
        return result.scalars().all()

    async def get_all_running(self) -> Sequence[VirtualMachine]:
        """Для Celery-задачи синхронизации статусов."""
        query = sa.select(self.table).where(
            self.table.status.in_([VMStatus.RUNNING, VMStatus.PENDING])
        )
        result = await self._session.execute(query)
        return result.scalars().all()

    async def delete_old_terminated(self, older_than_hours: int = 24) -> int:
        """Для Celery-задачи очистки. Возвращает кол-во удалённых записей."""
        from datetime import datetime, timedelta
        threshold = datetime.now() - timedelta(hours=older_than_hours)
        query = (
            sa.delete(self.table)
            .where(
                self.table.status == VMStatus.TERMINATED,
                self.table.updated_at < threshold,
            )
            .returning(self.table.id)
        )
        result = await self._session.execute(query)
        await self._session.flush()
        return len(result.fetchall())