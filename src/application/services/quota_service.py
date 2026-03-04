from uuid import UUID

from fastapi import Depends, HTTPException, status

from src.infrastructure.models.resource_quota import ResourceQuota
from src.infrastructure.repositories.quotas import QuotaRepository, UsageRepository
from src.infrastructure.schemas.users import UserRequest


class QuotaExceededError(Exception):
    def __init__(self, resource: str, requested: int, available: int) -> None:
        self.resource = resource
        self.requested = requested
        self.available = available
        super().__init__(
            f"Quota exceeded for {resource}: requested {requested}, available {available}"
        )


class QuotaService:
    def __init__(
        self,
        quota_repo: QuotaRepository = Depends(),
        usage_repo: UsageRepository = Depends(),
    ) -> None:
        self._quota = quota_repo
        self._usage = usage_repo

    async def check_and_reserve(
        self, tenant_id: UUID, vcpu: int, ram_mb: int, disk_gb: int
    ) -> None:
        """Validate current_usage + requested <= quota, then atomically increment usage."""
        quota = await self._quota.get_by_tenant(tenant_id)
        usage = await self._usage.get_by_tenant(tenant_id)

        if quota is None or usage is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Quota or usage record not found for tenant",
            )

        if usage.used_vcpu + vcpu > quota.max_vcpu:
            raise QuotaExceededError("vCPU", vcpu, quota.max_vcpu - usage.used_vcpu)
        if usage.used_ram_mb + ram_mb > quota.max_ram_mb:
            raise QuotaExceededError("RAM", ram_mb, quota.max_ram_mb - usage.used_ram_mb)
        if usage.used_disk_gb + disk_gb > quota.max_disk_gb:
            raise QuotaExceededError("Disk", disk_gb, quota.max_disk_gb - usage.used_disk_gb)
        if usage.used_vms + 1 > quota.max_vms:
            raise QuotaExceededError("VM count", 1, quota.max_vms - usage.used_vms)

        await self._usage.increment(tenant_id, vcpu, ram_mb, disk_gb)

    async def release(self, tenant_id: UUID, vcpu: int, ram_mb: int, disk_gb: int) -> None:
        """Decrement usage after VM stop or terminate."""
        await self._usage.decrement(tenant_id, vcpu, ram_mb, disk_gb)

    async def get_usage_summary(self, tenant_id: UUID) -> dict:
        quota = await self._quota.get_by_tenant(tenant_id)
        usage = await self._usage.get_by_tenant(tenant_id)

        if quota is None or usage is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Quota or usage record not found for tenant",
            )

        return {
            "vcpu": {
                "used": usage.used_vcpu,
                "max": quota.max_vcpu,
                "pct": round(usage.used_vcpu / quota.max_vcpu * 100, 1),
            },
            "ram_mb": {
                "used": usage.used_ram_mb,
                "max": quota.max_ram_mb,
                "pct": round(usage.used_ram_mb / quota.max_ram_mb * 100, 1),
            },
            "disk_gb": {
                "used": usage.used_disk_gb,
                "max": quota.max_disk_gb,
                "pct": round(usage.used_disk_gb / quota.max_disk_gb * 100, 1),
            },
            "vms": {
                "used": usage.used_vms,
                "max": quota.max_vms,
                "pct": round(usage.used_vms / quota.max_vms * 100, 1),
            },
        }

    async def update_quota(
        self, tenant_id: UUID, admin_user: UserRequest, **quota_fields
    ) -> ResourceQuota:
        """Admin-only: update quota limits."""
        if admin_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admins can update quotas",
            )
        result = await self._quota.update_by_tenant(tenant_id, **quota_fields)
        if result is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Quota not found for tenant",
            )
        return result
