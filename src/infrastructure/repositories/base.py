from typing import Any, Sequence
import sqlalchemy as sa
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from src.interfaces.api.dependencies.session import get_db


class BaseRepository:
    table: sa.Table

    def __init__(self, session: AsyncSession = Depends(get_db)) -> None:
        self._session = session

    @property
    def session(self) -> AsyncSession:
        return self._session

    async def create(self, **kwargs: Any) -> Any | None:
        query = sa.insert(self.table).values(**kwargs).returning(self.table)
        query_result = await self._session.execute(query)
        await self._session.flush()
        return query_result.scalar_one_or_none()

    async def get(self, *args: Any) -> Any | None:
        query = sa.select(self.table).where(*args)
        query_result = await self._session.execute(query)
        return query_result.scalar_one_or_none()

    async def get_all(self, limit: int, offset: int, ordering: str | None = None, *args) -> Sequence[Any]:
        query = sa.select(self.table).where(*args).offset(offset).limit(limit).order_by(ordering)
        query_result = await self._session.execute(query)
        return query_result.scalars().all()

    async def update(self, *args: Any, **kwargs: Any) -> Any | None:
        query = sa.update(self.table).where(*args).values(**kwargs).returning(self.table)
        query_result = await self._session.execute(query)
        await self.session.flush()
        return query_result.scalar_one_or_none()

    async def delete(self, *args: Any) -> Any | None:
        query = sa.delete(self.table).where(*args).returning(self.table)
        query_result = await self._session.execute(query)
        await self.session.flush()
        return query_result.scalar_one_or_none()
