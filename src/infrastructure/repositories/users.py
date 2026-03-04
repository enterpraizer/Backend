from sqlalchemy import update

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
