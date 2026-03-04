import ipaddress
from typing import List
from uuid import UUID

from fastapi import Depends, HTTPException, status

from src.application.services.audit_service import AuditService
from src.infrastructure.models.virtual_network import VirtualNetwork
from src.infrastructure.repositories.network import NetworkRepository
from src.infrastructure.repositories.virtual_machine import VMRepository
from src.infrastructure.schemas.network import NetworkCreate, NetworkListResponse, NetworkResponse
from src.infrastructure.schemas.vm import VMResponse


class NetworkService:
    def __init__(
        self,
        repo: NetworkRepository = Depends(),
        vm_repo: VMRepository = Depends(),
        audit: AuditService = Depends(),
    ) -> None:
        self._repo = repo
        self._vm_repo = vm_repo
        self._audit = audit

    async def create(self, tenant_id: UUID, data: NetworkCreate, user_id: UUID | None = None) -> NetworkResponse:
        # Check CIDR overlap with existing tenant networks
        existing_cidrs = await self._repo.get_network_cidrs(tenant_id)
        new_net = ipaddress.ip_network(data.cidr, strict=False)
        for cidr in existing_cidrs:
            existing_net = ipaddress.ip_network(cidr, strict=False)
            if new_net.overlaps(existing_net):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"CIDR {data.cidr} overlaps with existing network {cidr}",
                )

        network = await self._repo.create(
            tenant_id=tenant_id,
            name=data.name,
            cidr=data.cidr,
            is_public=data.is_public,
        )
        if user_id:
            await self._audit.log(
                tenant_id=tenant_id, user_id=user_id,
                action="network.create", resource_type="network", resource_id=network.id,
                details={"name": data.name, "cidr": data.cidr},
            )
        return NetworkResponse.model_validate(network, from_attributes=True)

    async def get(self, network_id: UUID, tenant_id: UUID) -> NetworkResponse:
        network = await self._repo.get(VirtualNetwork.id == network_id, tenant_id=tenant_id)
        if not network:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Network not found")
        return NetworkResponse.model_validate(network, from_attributes=True)

    async def list(self, tenant_id: UUID, limit: int, offset: int) -> NetworkListResponse:
        items = await self._repo.get_all(tenant_id=tenant_id, limit=limit, offset=offset)
        total = await self._repo.count(tenant_id=tenant_id)
        return NetworkListResponse(
            items=[NetworkResponse.model_validate(n, from_attributes=True) for n in items],
            total=total,
        )

    async def delete(self, network_id: UUID, tenant_id: UUID, user_id: UUID | None = None) -> None:
        network = await self._repo.get(VirtualNetwork.id == network_id, tenant_id=tenant_id)
        if not network:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Network not found")
        await self._repo.delete(VirtualNetwork.id == network_id, tenant_id=tenant_id)
        if user_id:
            await self._audit.log(
                tenant_id=tenant_id, user_id=user_id,
                action="network.delete", resource_type="network", resource_id=network_id,
            )

    async def attach_vm(self, network_id: UUID, vm_id: UUID, tenant_id: UUID) -> None:
        # Both must belong to the same tenant
        network = await self._repo.get(VirtualNetwork.id == network_id, tenant_id=tenant_id)
        if not network:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Network not found")

        from src.infrastructure.models.virtual_machine import VirtualMachine
        vm = await self._vm_repo.get(VirtualMachine.id == vm_id, tenant_id=tenant_id)
        if not vm:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="VM not found")

        if await self._repo.is_vm_attached(network_id, vm_id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="VM is already attached to this network",
            )

        await self._repo.attach_vm(network_id, vm_id)

    async def detach_vm(self, network_id: UUID, vm_id: UUID, tenant_id: UUID) -> None:
        network = await self._repo.get(VirtualNetwork.id == network_id, tenant_id=tenant_id)
        if not network:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Network not found")
        await self._repo.detach_vm(network_id, vm_id)

    async def get_network_vms(self, network_id: UUID, tenant_id: UUID) -> List[VMResponse]:
        # Verify network belongs to tenant
        network = await self._repo.get(VirtualNetwork.id == network_id, tenant_id=tenant_id)
        if not network:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Network not found")
        vms = await self._repo.get_network_vms(network_id, tenant_id)
        return [VMResponse.model_validate(v, from_attributes=True) for v in vms]
