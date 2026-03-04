from uuid import UUID

import sqlalchemy as sa

from src.infrastructure.models.resource_quota import ResourceQuota
from src.infrastructure.models.resource_usage import ResourceUsage
from src.infrastructure.repositories.base import BaseRepository


class QuotaRepository(BaseRepository):

    table = ResourceQuota

    async def get_by_tenant(self, tenant_id: UUID) -> ResourceQuota | None:
        query = sa.select(self.table).where(self.table.tenant_id == tenant_id)
        result = await self._session.execute(query)
        return result.scalar_one_or_none()

    async def update_by_tenant(self, tenant_id: UUID, **kwargs) -> ResourceQuota | None:
        query = (
            sa.update(self.table)
            .where(self.table.tenant_id == tenant_id)
            .values(**kwargs)
            .returning(self.table)
        )
        result = await self._session.execute(query)
        await self._session.flush()
        return result.scalar_one_or_none()


class UsageRepository(BaseRepository):
    
    table = ResourceUsage

    async def get_by_tenant(self, tenant_id: UUID) -> ResourceUsage | None:
        query = sa.select(self.table).where(self.table.tenant_id == tenant_id)
        result = await self._session.execute(query)
        return result.scalar_one_or_none()

    async def increment(
        self, tenant_id: UUID, vcpu: int, ram_mb: int, disk_gb: int
    ) -> None:
        """
        Атомарный инкремент через UPDATE ... SET x = x + N.
        Исключает race condition при параллельных запросах.
        """
        query = (
            sa.update(self.table)
            .where(self.table.tenant_id == tenant_id)
            .values(
                used_vcpu=self.table.used_vcpu + vcpu,
                used_ram_mb=self.table.used_ram_mb + ram_mb,
                used_disk_gb=self.table.used_disk_gb + disk_gb,
                used_vms=self.table.used_vms + 1,
            )
        )
        await self._session.execute(query)
        await self._session.flush()

    async def decrement(
        self, tenant_id: UUID, vcpu: int, ram_mb: int, disk_gb: int
    ) -> None:
        """
        Атомарный декремент с защитой от отрицательных значений.
        Uses CASE WHEN for cross-database compatibility (PostgreSQL + SQLite).
        """

        def _safe_sub(col, n: int):
            return sa.case((col > n, col - n), else_=0)

        query = (
            sa.update(self.table)
            .where(self.table.tenant_id == tenant_id)
            .values(
                used_vcpu=_safe_sub(self.table.used_vcpu, vcpu),
                used_ram_mb=_safe_sub(self.table.used_ram_mb, ram_mb),
                used_disk_gb=_safe_sub(self.table.used_disk_gb, disk_gb),
                used_vms=_safe_sub(self.table.used_vms, 1),
            )
        )
        await self._session.execute(query)
        await self._session.flush()

    async def reset(self, tenant_id: UUID) -> None:
        """Обнуляет счётчики — для admin или тестов."""
        query = (
            sa.update(self.table)
            .where(self.table.tenant_id == tenant_id)
            .values(used_vcpu=0, used_ram_mb=0, used_disk_gb=0, used_vms=0)
        )
        await self._session.execute(query)
        await self._session.flush()

    async def get_total_allocated(self) -> dict:
        """Для admin/stats — суммирует потребление по всем тенантам."""
        query = sa.select(
            sa.func.sum(self.table.used_vcpu).label("total_vcpu"),
            sa.func.sum(self.table.used_ram_mb).label("total_ram_mb"),
            sa.func.sum(self.table.used_disk_gb).label("total_disk_gb"),
            sa.func.sum(self.table.used_vms).label("total_vms"),
        )
        result = await self._session.execute(query)
        row = result.one()
        return {
            "total_vcpu": row.total_vcpu or 0,
            "total_ram_mb": row.total_ram_mb or 0,
            "total_disk_gb": row.total_disk_gb or 0,
            "total_vms": row.total_vms or 0,
        }