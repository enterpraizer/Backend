from uuid import UUID

import sqlalchemy as sa

from src.infrastructure.models.vm_metrics import VmMetrics
from src.infrastructure.repositories.base import BaseRepository


class VmMetricsRepository(BaseRepository):
    table = VmMetrics

    async def get_recent(self, vm_id: UUID, hours: int = 168) -> list[VmMetrics]:
        """Return metrics for a VM from the last N hours (default 7 days)."""
        from datetime import datetime, timedelta
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        query = (
            sa.select(self.table)
            .where(self.table.vm_id == vm_id, self.table.recorded_at >= cutoff)
            .order_by(self.table.recorded_at.asc())
        )
        result = await self._session.execute(query)
        return list(result.scalars().all())
