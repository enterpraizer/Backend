from uuid import UUID

import sqlalchemy as sa

from src.infrastructure.models.vm_suggestion import VmSuggestion, SuggestionStatus
from src.infrastructure.repositories.base import BaseRepository


class VmSuggestionRepository(BaseRepository):
    table = VmSuggestion

    async def get_pending(self, vm_id: UUID) -> list[VmSuggestion]:
        query = (
            sa.select(self.table)
            .where(
                self.table.vm_id == vm_id,
                self.table.status == SuggestionStatus.PENDING,
            )
            .order_by(self.table.created_at.desc())
        )
        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def get_by_id(self, suggestion_id: UUID, vm_id: UUID) -> VmSuggestion | None:
        query = sa.select(self.table).where(
            self.table.id == suggestion_id,
            self.table.vm_id == vm_id,
        )
        result = await self._session.execute(query)
        return result.scalar_one_or_none()

    async def set_status(self, suggestion_id: UUID, status: SuggestionStatus) -> VmSuggestion | None:
        query = (
            sa.update(self.table)
            .where(self.table.id == suggestion_id)
            .values(status=status)
            .returning(self.table)
        )
        result = await self._session.execute(query)
        await self._session.flush()
        return result.scalar_one_or_none()

    async def has_recent(self, vm_id: UUID, hours: int = 24) -> bool:
        """Return True if a suggestion was created for this VM in the last N hours."""
        from datetime import datetime, timedelta, timezone
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        query = sa.select(sa.exists().where(
            self.table.vm_id == vm_id,
            self.table.created_at >= cutoff,
        ))
        result = await self._session.execute(query)
        return bool(result.scalar())
