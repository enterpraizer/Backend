from fastapi import APIRouter
from typing import Optional
from uuid import UUID

from fastapi import Depends, HTTPException, status

from src.application.services.auth_service import AuthService
from src.application.services.quota_service import QuotaExceededError
from src.application.services.vm_service import VMService
from src.infrastructure.models.tenant import Tenant
from src.infrastructure.models.virtual_machine import VMStatus
from src.infrastructure.schemas.users import UserRequest
from src.infrastructure.schemas.vm import VMCreate, VMListResponse, VMResponse, VMUpdate
from src.interfaces.api.dependencies.tenant import get_current_tenant

vms_router = APIRouter(prefix="/vms", tags=["Virtual Machines"])


@vms_router.get("", response_model=VMListResponse, status_code=status.HTTP_200_OK)
async def list_vms(
    limit: int = 20,
    offset: int = 0,
    status_filter: Optional[VMStatus] = None,
    current_user: UserRequest = Depends(AuthService.get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
    service: VMService = Depends(),
) -> VMListResponse:
    """List all VMs for the current tenant (paginated, optional status filter)."""
    items, total = await service.list(
        tenant_id=tenant.id, limit=limit, offset=offset, status_filter=status_filter
    )
    return VMListResponse(items=items, total=total)


@vms_router.post("", response_model=VMResponse, status_code=status.HTTP_201_CREATED)
async def create_vm(
    body: VMCreate,
    current_user: UserRequest = Depends(AuthService.get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
    service: VMService = Depends(),
) -> VMResponse:
    """Create and provision a new VM. Returns 429 if tenant quota is exceeded."""
    try:
        return await service.create(
            tenant_id=tenant.id, owner_id=current_user.id, data=body
        )
    except QuotaExceededError as e:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "detail": "Quota exceeded",
                "resource": e.resource,
                "requested": e.requested,
                "available": e.available,
            },
        )


@vms_router.get("/{vm_id}", response_model=VMResponse, status_code=status.HTTP_200_OK)
async def get_vm(
    vm_id: UUID,
    current_user: UserRequest = Depends(AuthService.get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
    service: VMService = Depends(),
) -> VMResponse:
    """Get a single VM by ID (tenant-scoped — returns 404 if VM belongs to another tenant)."""
    return await service.get(vm_id=vm_id, tenant_id=tenant.id)


@vms_router.post("/{vm_id}/start", response_model=VMResponse, status_code=status.HTTP_200_OK)
async def start_vm(
    vm_id: UUID,
    current_user: UserRequest = Depends(AuthService.get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
    service: VMService = Depends(),
) -> VMResponse:
    """Start a stopped VM. Returns 409 if VM is not in STOPPED state."""
    return await service.start(vm_id=vm_id, tenant_id=tenant.id, user_id=current_user.id)


@vms_router.post("/{vm_id}/stop", response_model=VMResponse, status_code=status.HTTP_200_OK)
async def stop_vm(
    vm_id: UUID,
    current_user: UserRequest = Depends(AuthService.get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
    service: VMService = Depends(),
) -> VMResponse:
    """Stop a running VM. Returns 409 if VM is not in RUNNING state."""
    return await service.stop(vm_id=vm_id, tenant_id=tenant.id, user_id=current_user.id)


@vms_router.delete("/{vm_id}", status_code=status.HTTP_204_NO_CONTENT)
async def terminate_vm(
    vm_id: UUID,
    current_user: UserRequest = Depends(AuthService.get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
    service: VMService = Depends(),
) -> None:
    """Terminate a VM: stops and removes the Docker container, releases all quota."""
    await service.terminate(vm_id=vm_id, tenant_id=tenant.id, user_id=current_user.id)


@vms_router.patch("/{vm_id}", response_model=VMResponse, status_code=status.HTTP_200_OK)
async def update_vm(
    vm_id: UUID,
    body: VMUpdate,
    current_user: UserRequest = Depends(AuthService.get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
    service: VMService = Depends(),
) -> VMResponse:
    """Update VM metadata (name only)."""
    updates = body.model_dump(exclude_none=True, exclude={"status"})
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="No updatable fields provided"
        )
    return await service.update(vm_id=vm_id, tenant_id=tenant.id, **updates)
