from sqlalchemy.ext.asyncio import AsyncSession
from src.infrastructure.models.base import async_session_maker


async def get_db() -> AsyncSession:
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
