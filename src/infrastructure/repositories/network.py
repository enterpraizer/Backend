from typing import Sequence
from uuid import UUID

import sqlalchemy as sa

from src.infrastructure.models.virtual_network import VirtualNetwork, vm_network_association
from src.infrastructure.models.virtual_machine import VirtualMachine
from src.infrastructure.repositories.tenant_scoped import TenantScopedRepository


class NetworkRepository(TenantScopedRepository):

    table = VirtualNetwork

    async def get_network_cidrs(self, tenant_id: UUID) -> list[str]:
        """Возвращает все CIDR тенанта — для проверки на пересечение."""
        query = sa.select(self.table.cidr).where(
            self.table.tenant_id == tenant_id
        )
        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def attach_vm(self, network_id: UUID, vm_id: UUID) -> None:
        query = sa.insert(vm_network_association).values(
            network_id=network_id,
            vm_id=vm_id,
        )
        await self._session.execute(query)
        await self._session.flush()

    async def detach_vm(self, network_id: UUID, vm_id: UUID) -> None:
        query = sa.delete(vm_network_association).where(
            vm_network_association.c.network_id == network_id,
            vm_network_association.c.vm_id == vm_id,
        )
        await self._session.execute(query)
        await self._session.flush()

    async def get_network_vms(self, network_id: UUID, tenant_id: UUID) -> Sequence[VirtualMachine]:
        """
        Возвращает все VM привязанные к сети.
        Проверяет что и сеть и VM принадлежат одному тенанту.
        """
        query = (
            sa.select(VirtualMachine)
            .join(
                vm_network_association,
                vm_network_association.c.vm_id == VirtualMachine.id,
            )
            .where(
                vm_network_association.c.network_id == network_id,
                VirtualMachine.tenant_id == tenant_id,
            )
        )
        result = await self._session.execute(query)
        return result.scalars().all()

    async def is_vm_attached(self, network_id: UUID, vm_id: UUID) -> bool:
        query = sa.select(sa.func.count()).where(
            vm_network_association.c.network_id == network_id,
            vm_network_association.c.vm_id == vm_id,
        )
        result = await self._session.execute(query)
        return result.scalar_one() > 0