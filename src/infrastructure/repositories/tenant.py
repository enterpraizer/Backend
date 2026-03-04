from typing import Sequence
from uuid import UUID

import sqlalchemy as sa

from src.infrastructure.models.tenant import Tenant
from src.infrastructure.repositories.base import BaseRepository


class TenantRepository(BaseRepository):

    table = Tenant

    async def get_by_owner(self, owner_id: UUID) -> Tenant | None:
        query = sa.select(self.table).where(
            self.table.owner_id == owner_id,
            self.table.is_active == True,
        ).limit(1)
        result = await self._session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> Tenant | None:
        query = sa.select(self.table).where(self.table.slug == slug)
        result = await self._session.execute(query)
        return result.scalar_one_or_none()

    async def get_all(
        self,
        limit: int,
        offset: int,
        ordering: sa.Column | None = None,
        *args,
    ) -> Sequence[Tenant]:
        query = (
            sa.select(self.table)
            .where(*args)
            .offset(offset)
            .limit(limit)
            .order_by(ordering)
        )
        result = await self._session.execute(query)
        return result.scalars().all()

    async def count(self, *args) -> int:
        query = (
            sa.select(sa.func.count())
            .select_from(self.table)
            .where(*args)
        )
        result = await self._session.execute(query)
        return result.scalar_one()

    async def deactivate(self, tenant_id: UUID) -> Tenant | None:
        query = (
            sa.update(self.table)
            .where(self.table.id == tenant_id)
            .values(is_active=False)
            .returning(self.table)
        )
        result = await self._session.execute(query)
        await self._session.flush()
        return result.scalar_one_or_none()
