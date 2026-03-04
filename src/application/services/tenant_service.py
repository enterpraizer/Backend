import re
from typing import Sequence
from uuid import UUID

from fastapi import Depends, HTTPException, status

from src.infrastructure.models.tenant import Tenant
from src.infrastructure.repositories.quotas import QuotaRepository, UsageRepository
from src.infrastructure.repositories.tenant import TenantRepository


def _slugify(name: str) -> str:
    slug = name.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug.strip("-")


class TenantService:
    def __init__(
        self,
        repo: TenantRepository = Depends(),
        quota_repo: QuotaRepository = Depends(),
        usage_repo: UsageRepository = Depends(),
    ) -> None:
        self._repo = repo
        self._quota_repo = quota_repo
        self._usage_repo = usage_repo

    async def create_tenant(self, name: str, owner_id: UUID) -> Tenant:
        slug = _slugify(name)

        # Ensure unique slug
        existing = await self._repo.get_by_slug(slug)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Tenant with slug '{slug}' already exists",
            )

        tenant = await self._repo.create(name=name, slug=slug, owner_id=owner_id)

        # Create default quota
        await self._quota_repo.create(
            tenant_id=tenant.id,
            max_vcpu=8,
            max_ram_mb=16384,
            max_disk_gb=200,
            max_vms=5,
        )

        # Create zeroed usage record
        await self._usage_repo.create(
            tenant_id=tenant.id,
            used_vcpu=0,
            used_ram_mb=0,
            used_disk_gb=0,
            used_vms=0,
        )

        return tenant

    async def get_tenant(self, tenant_id: UUID) -> Tenant:
        tenant = await self._repo.get(Tenant.id == tenant_id)
        if not tenant:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
        return tenant

    async def list_tenants(self, limit: int = 20, offset: int = 0) -> tuple[Sequence[Tenant], int]:
        items = await self._repo.get_all(limit=limit, offset=offset)
        total = await self._repo.count()
        return items, total

    async def update_tenant(self, tenant_id: UUID, **kwargs) -> Tenant:
        tenant = await self._repo.update(Tenant.id == tenant_id, **kwargs)
        if not tenant:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
        return tenant

    async def deactivate_tenant(self, tenant_id: UUID) -> None:
        result = await self._repo.deactivate(tenant_id)
        if not result:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
