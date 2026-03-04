from typing import Optional
from uuid import UUID

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, status

from src.application.services.quota_service import QuotaService
from src.application.services.tenant_service import TenantService
from src.infrastructure.models.tenant import Tenant
from src.infrastructure.models.virtual_machine import VMStatus, VirtualMachine
from src.infrastructure.repositories.tenant import TenantRepository
from src.infrastructure.repositories.virtual_machine import VMRepository
from src.infrastructure.schemas.quota import QuotaResponse, QuotaUpdate, UsageSummaryResponse, ResourceMetric
from src.infrastructure.schemas.tenant import TenantCreate, TenantListResponse, TenantResponse
from src.infrastructure.schemas.vm import VMResponse
from src.interfaces.api.dependencies.permissions import require_admin

admin_router = APIRouter(
    prefix="/admin",
    tags=["Admin"],
    dependencies=[Depends(require_admin)],
)


# ─── Tenant management ────────────────────────────────────────────────────────

@admin_router.get("/tenants", response_model=TenantListResponse, status_code=status.HTTP_200_OK)
async def list_tenants(
    limit: int = 20,
    offset: int = 0,
    service: TenantService = Depends(),
) -> TenantListResponse:
    """List all tenants (admin only)."""
    items, total = await service.list_tenants(limit=limit, offset=offset)
    return TenantListResponse(
        items=[TenantResponse.model_validate(t, from_attributes=True) for t in items],
        total=total,
    )


@admin_router.post("/tenants", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
async def create_tenant(
    body: TenantCreate,
    owner_id: UUID,
    service: TenantService = Depends(),
) -> TenantResponse:
    """Manually create a tenant and assign it to a user (by owner_id query param)."""
    tenant = await service.create_tenant(name=body.name, owner_id=owner_id)
    return TenantResponse.model_validate(tenant, from_attributes=True)


@admin_router.get("/tenants/{tenant_id}", response_model=TenantResponse, status_code=status.HTTP_200_OK)
async def get_tenant(
    tenant_id: UUID,
    service: TenantService = Depends(),
) -> TenantResponse:
    """Get tenant details."""
    tenant = await service.get_tenant(tenant_id)
    return TenantResponse.model_validate(tenant, from_attributes=True)


@admin_router.patch("/tenants/{tenant_id}", response_model=TenantResponse, status_code=status.HTTP_200_OK)
async def update_tenant(
    tenant_id: UUID,
    is_active: Optional[bool] = None,
    name: Optional[str] = None,
    service: TenantService = Depends(),
) -> TenantResponse:
    """Activate or deactivate a tenant, or rename it."""
    updates = {k: v for k, v in {"is_active": is_active, "name": name}.items() if v is not None}
    if not updates:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update")
    tenant = await service.update_tenant(tenant_id, **updates)
    return TenantResponse.model_validate(tenant, from_attributes=True)


@admin_router.delete("/tenants/{tenant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_tenant(
    tenant_id: UUID,
    service: TenantService = Depends(),
) -> None:
    """Deactivate a tenant (soft delete)."""
    await service.deactivate_tenant(tenant_id)


# ─── Quota management ─────────────────────────────────────────────────────────

@admin_router.get(
    "/tenants/{tenant_id}/quota",
    response_model=dict,
    status_code=status.HTTP_200_OK,
)
async def get_tenant_quota(
    tenant_id: UUID,
    quota_service: QuotaService = Depends(),
) -> dict:
    """Get quota limits and current usage for a tenant."""
    summary = await quota_service.get_usage_summary(tenant_id)
    return summary


@admin_router.patch(
    "/tenants/{tenant_id}/quota",
    response_model=QuotaResponse,
    status_code=status.HTTP_200_OK,
)
async def update_tenant_quota(
    tenant_id: UUID,
    body: QuotaUpdate,
    quota_service: QuotaService = Depends(),
) -> QuotaResponse:
    """Update quota limits for a tenant."""
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update")
    from src.infrastructure.schemas.users import UserRequest, Roles
    # Admin check already done via router dependency; build a dummy admin UserRequest
    admin_user = UserRequest(
        id=UUID("00000000-0000-0000-0000-000000000000"),
        email="admin@system",
        role=Roles.ADMIN,
        username="system",
        is_active=True,
    )
    quota = await quota_service.update_quota(tenant_id, admin_user, **updates)
    return QuotaResponse.model_validate(quota, from_attributes=True)


# ─── Global statistics ────────────────────────────────────────────────────────

@admin_router.get("/stats", status_code=status.HTTP_200_OK)
async def get_stats(
    tenant_repo: TenantRepository = Depends(),
    vm_repo: VMRepository = Depends(),
) -> dict:
    """Global platform statistics."""
    total_tenants = await tenant_repo.count()
    active_tenants = await tenant_repo.count(Tenant.is_active == True)  # noqa: E712

    # VM counts
    all_vms = await vm_repo.get_all_across_tenants(limit=100_000, offset=0)
    total_vms = len(all_vms)
    running_vms = sum(1 for v in all_vms if v.status == VMStatus.RUNNING)
    total_vcpu = sum(v.vcpu for v in all_vms if v.status == VMStatus.RUNNING)
    total_ram = sum(v.ram_mb for v in all_vms if v.status == VMStatus.RUNNING)
    total_disk = sum(v.disk_gb for v in all_vms)

    # Top 5 tenants by VM count
    from collections import Counter
    tenant_vm_counts = Counter(str(v.tenant_id) for v in all_vms)
    top_tenant_ids = [tid for tid, _ in tenant_vm_counts.most_common(5)]
    top_tenants = []
    for tid in top_tenant_ids:
        tenant = await tenant_repo.get(Tenant.id == UUID(tid))
        if tenant:
            top_tenants.append({"tenant_name": tenant.name, "vm_count": tenant_vm_counts[tid]})

    return {
        "total_tenants": total_tenants,
        "active_tenants": active_tenants,
        "total_vms": total_vms,
        "running_vms": running_vms,
        "total_vcpu_allocated": total_vcpu,
        "total_ram_mb_allocated": total_ram,
        "total_disk_gb_allocated": total_disk,
        "top_tenants_by_vms": top_tenants,
    }


# ─── All VMs across tenants ───────────────────────────────────────────────────

@admin_router.get("/vms", status_code=status.HTTP_200_OK)
async def list_all_vms(
    limit: int = 20,
    offset: int = 0,
    vm_repo: VMRepository = Depends(),
    tenant_repo: TenantRepository = Depends(),
) -> dict:
    """List ALL VMs across all tenants with tenant_name (admin monitoring)."""
    vms = await vm_repo.get_all_across_tenants(limit=limit, offset=offset)
    result = []
    for vm in vms:
        tenant = await tenant_repo.get(Tenant.id == vm.tenant_id)
        row = VMResponse.model_validate(vm, from_attributes=True).model_dump()
        row["tenant_name"] = tenant.name if tenant else None
        result.append(row)
    return {"items": result, "total": len(result)}
