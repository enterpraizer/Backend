from typing import Any, Sequence
from uuid import UUID

import sqlalchemy as sa

from src.infrastructure.repositories.base import BaseRepository


class TenantScopedRepository(BaseRepository):
    """
    Базовый репозиторий для всех моделей с tenant_id.
    Все методы автоматически фильтруют по tenant_id — утечка данных между тенантами невозможна.
    """
    table: sa.Table

    async def get(self, *args: Any, tenant_id: UUID) -> Any | None:
        query = sa.select(self.table).where(
            self.table.tenant_id == tenant_id, *args
        )
        result = await self._session.execute(query)
        return result.scalar_one_or_none()

    async def get_all(
        self,
        tenant_id: UUID,
        limit: int,
        offset: int,
        ordering: str | None = None,
        *args: Any,
    ) -> Sequence[Any]:
        query = (
            sa.select(self.table)
            .where(self.table.tenant_id == tenant_id, *args)
            .offset(offset)
            .limit(limit)
            .order_by(ordering)
        )
        result = await self._session.execute(query)
        return result.scalars().all()

    async def count(self, tenant_id: UUID, *args: Any) -> int:
        query = (
            sa.select(sa.func.count())
            .select_from(self.table)
            .where(self.table.tenant_id == tenant_id, *args)
        )
        result = await self._session.execute(query)
        return result.scalar_one()

    async def create(self, tenant_id: UUID, **kwargs: Any) -> Any | None:
        query = (
            sa.insert(self.table)
            .values(tenant_id=tenant_id, **kwargs)
            .returning(self.table)
        )
        result = await self._session.execute(query)
        await self._session.flush()
        return result.scalar_one_or_none()

    async def update(self, *args: Any, tenant_id: UUID, **kwargs: Any) -> Any | None:
        query = (
            sa.update(self.table)
            .where(self.table.tenant_id == tenant_id, *args)
            .values(**kwargs)
            .returning(self.table)
        )
        result = await self._session.execute(query)
        await self._session.flush()
        return result.scalar_one_or_none()

    async def delete(self, *args: Any, tenant_id: UUID) -> Any | None:
        query = (
            sa.delete(self.table)
            .where(self.table.tenant_id == tenant_id, *args)
            .returning(self.table)
        )
        result = await self._session.execute(query)
        await self._session.flush()
        return result.scalar_one_or_none()