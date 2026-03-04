from typing import Optional
from uuid import UUID

from select import select

from sqlalchemy import update
from src.infrastructure.models import Tenant

from src.infrastructure.models.users import User
from src.infrastructure.repositories.base import BaseRepository


class UserRepository(BaseRepository):
    table = User

    async def confirm_user(self, email: str) -> None:
        query = (
            update(self.table)
            .where(self.table.email == email)
            .values(is_verified=True, is_active=True)
        )
        await self._session.execute(query)
        await self.session.flush()

    async def get_tenant_id_for_user(self, user_id: UUID) -> Optional[UUID]:
        query = select(Tenant.id).where(
            Tenant.owner_id == user_id,
            Tenant.is_active == True
        ).limit(1)
        result = await self._session.execute(query)
        tenant_id = result.scalar_one_or_none()
        return tenant_id
