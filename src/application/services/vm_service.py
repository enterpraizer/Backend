from uuid import UUID

from fastapi import Depends, HTTPException, status

from src.application.services.audit_service import AuditService
from src.application.services.hypervisor_service import HypervisorService
from src.application.services.quota_service import QuotaService
from src.infrastructure.models.virtual_machine import VMStatus, VirtualMachine
from src.infrastructure.repositories.virtual_machine import VMRepository
from src.infrastructure.schemas.vm import VMCreate, VMResponse


class VMService:
    def __init__(
        self,
        vm_repo: VMRepository = Depends(),
        quota_service: QuotaService = Depends(),
        hypervisor: HypervisorService = Depends(),
        audit: AuditService = Depends(),
    ) -> None:
        self._vm_repo = vm_repo
        self._quota = quota_service
        self._hypervisor = hypervisor
        self._audit = audit

    async def create(self, tenant_id: UUID, owner_id: UUID, data: VMCreate) -> VMResponse:
        await self._quota.check_and_reserve(tenant_id, data.vcpu, data.ram_mb, data.disk_gb)

        vm = await self._vm_repo.create(
            tenant_id=tenant_id,
            owner_id=owner_id,
            name=data.name,
            vcpu=data.vcpu,
            ram_mb=data.ram_mb,
            disk_gb=data.disk_gb,
            status=VMStatus.PENDING,
        )

        result = await self._hypervisor.provision_vm(
            vm.id, tenant_id, data.name, data.vcpu, data.ram_mb, data.disk_gb
        )

        vm = await self._vm_repo.update_status(
            vm.id,
            tenant_id,
            VMStatus.RUNNING,
            container_id=result["container_id"],
            ip_address=result["ip_address"],
            container_name=result["container_name"],
        )

        await self._audit.log(
            tenant_id=tenant_id, user_id=owner_id,
            action="vm.create", resource_type="vm", resource_id=vm.id,
            details={"name": data.name, "vcpu": data.vcpu, "ram_mb": data.ram_mb, "disk_gb": data.disk_gb},
        )
        return VMResponse.model_validate(vm, from_attributes=True)

    async def start(self, vm_id: UUID, tenant_id: UUID, user_id: UUID | None = None) -> VMResponse:
        vm = await self._vm_repo.get(VirtualMachine.id == vm_id, tenant_id=tenant_id)
        if not vm:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="VM not found")
        if vm.status != VMStatus.STOPPED:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="VM is not stopped")

        await self._hypervisor.start_vm(vm.container_id)
        vm = await self._vm_repo.update_status(vm_id, tenant_id, VMStatus.RUNNING)

        # Re-reserve CPU/RAM (disk already counted)
        await self._quota.check_and_reserve(tenant_id, vm.vcpu, vm.ram_mb, 0)

        if user_id:
            await self._audit.log(
                tenant_id=tenant_id, user_id=user_id,
                action="vm.start", resource_type="vm", resource_id=vm_id,
            )
        return VMResponse.model_validate(vm, from_attributes=True)

    async def stop(self, vm_id: UUID, tenant_id: UUID, user_id: UUID | None = None) -> VMResponse:
        vm = await self._vm_repo.get(VirtualMachine.id == vm_id, tenant_id=tenant_id)
        if not vm:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="VM not found")
        if vm.status != VMStatus.RUNNING:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="VM is not running")

        await self._hypervisor.stop_vm(vm.container_id)
        vm = await self._vm_repo.update_status(vm_id, tenant_id, VMStatus.STOPPED)

        # Release CPU/RAM only — disk stays allocated
        await self._quota.release(tenant_id, vm.vcpu, vm.ram_mb, 0)

        if user_id:
            await self._audit.log(
                tenant_id=tenant_id, user_id=user_id,
                action="vm.stop", resource_type="vm", resource_id=vm_id,
            )
        return VMResponse.model_validate(vm, from_attributes=True)

    async def terminate(self, vm_id: UUID, tenant_id: UUID, user_id: UUID | None = None) -> None:
        vm = await self._vm_repo.get(VirtualMachine.id == vm_id, tenant_id=tenant_id)
        if not vm:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="VM not found")

        await self._hypervisor.terminate_vm(vm.container_id, vm_id)
        await self._vm_repo.update_status(vm_id, tenant_id, VMStatus.TERMINATED)

        # Full release: CPU + RAM + disk
        await self._quota.release(tenant_id, vm.vcpu, vm.ram_mb, vm.disk_gb)

        if user_id:
            await self._audit.log(
                tenant_id=tenant_id, user_id=user_id,
                action="vm.terminate", resource_type="vm", resource_id=vm_id,
            )

    async def get(self, vm_id: UUID, tenant_id: UUID) -> VMResponse:
        vm = await self._vm_repo.get(VirtualMachine.id == vm_id, tenant_id=tenant_id)
        if not vm:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="VM not found")
        return VMResponse.model_validate(vm, from_attributes=True)

    async def list(
        self,
        tenant_id: UUID,
        limit: int,
        offset: int,
        status_filter: VMStatus | None = None,
    ) -> tuple[list[VMResponse], int]:
        extra = (VirtualMachine.status == status_filter,) if status_filter else ()
        items = await self._vm_repo.get_all(
            tenant_id=tenant_id, limit=limit, offset=offset, *extra
        )
        total = await self._vm_repo.count(tenant_id=tenant_id, *extra)
        return [VMResponse.model_validate(v, from_attributes=True) for v in items], total

    async def update(self, vm_id: UUID, tenant_id: UUID, **kwargs) -> VMResponse:
        vm = await self._vm_repo.update(
            VirtualMachine.id == vm_id, tenant_id=tenant_id, **kwargs
        )
        if not vm:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="VM not found")
        return VMResponse.model_validate(vm, from_attributes=True)
