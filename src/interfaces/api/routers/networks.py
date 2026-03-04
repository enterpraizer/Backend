from uuid import UUID

from fastapi import APIRouter, Depends, status

from src.application.services.auth_service import AuthService
from src.application.services.network_service import NetworkService
from src.infrastructure.models.tenant import Tenant
from src.infrastructure.schemas.network import (
    AttachVMRequest,
    NetworkCreate,
    NetworkListResponse,
    NetworkResponse,
)
from src.infrastructure.schemas.users import UserRequest
from src.infrastructure.schemas.vm import VMResponse
from src.interfaces.api.dependencies.tenant import get_current_tenant

networks_router = APIRouter(prefix="/networks", tags=["Virtual Networks"])


@networks_router.get("", response_model=NetworkListResponse, status_code=status.HTTP_200_OK)
async def list_networks(
    limit: int = 20,
    offset: int = 0,
    current_user: UserRequest = Depends(AuthService.get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
    service: NetworkService = Depends(),
) -> NetworkListResponse:
    """List all VPCs/networks for the current tenant."""
    return await service.list(tenant_id=tenant.id, limit=limit, offset=offset)


@networks_router.post("", response_model=NetworkResponse, status_code=status.HTTP_201_CREATED)
async def create_network(
    body: NetworkCreate,
    current_user: UserRequest = Depends(AuthService.get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
    service: NetworkService = Depends(),
) -> NetworkResponse:
    """Create a new VPC. Returns 409 if CIDR overlaps with an existing network."""
    return await service.create(tenant_id=tenant.id, data=body, user_id=current_user.id)


@networks_router.get("/{network_id}", response_model=NetworkResponse, status_code=status.HTTP_200_OK)
async def get_network(
    network_id: UUID,
    current_user: UserRequest = Depends(AuthService.get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
    service: NetworkService = Depends(),
) -> NetworkResponse:
    """Get network details (tenant-scoped)."""
    return await service.get(network_id=network_id, tenant_id=tenant.id)


@networks_router.delete("/{network_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_network(
    network_id: UUID,
    current_user: UserRequest = Depends(AuthService.get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
    service: NetworkService = Depends(),
) -> None:
    """Delete a network."""
    await service.delete(network_id=network_id, tenant_id=tenant.id, user_id=current_user.id)


@networks_router.post("/{network_id}/attach-vm", status_code=status.HTTP_204_NO_CONTENT)
async def attach_vm(
    network_id: UUID,
    body: AttachVMRequest,
    current_user: UserRequest = Depends(AuthService.get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
    service: NetworkService = Depends(),
) -> None:
    """Attach a VM to this network. Both must belong to the same tenant."""
    await service.attach_vm(network_id=network_id, vm_id=body.vm_id, tenant_id=tenant.id)


@networks_router.post("/{network_id}/detach-vm", status_code=status.HTTP_204_NO_CONTENT)
async def detach_vm(
    network_id: UUID,
    body: AttachVMRequest,
    current_user: UserRequest = Depends(AuthService.get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
    service: NetworkService = Depends(),
) -> None:
    """Detach a VM from this network."""
    await service.detach_vm(network_id=network_id, vm_id=body.vm_id, tenant_id=tenant.id)


@networks_router.get("/{network_id}/vms", response_model=list[VMResponse], status_code=status.HTTP_200_OK)
async def list_network_vms(
    network_id: UUID,
    current_user: UserRequest = Depends(AuthService.get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
    service: NetworkService = Depends(),
) -> list[VMResponse]:
    """List all VMs attached to this network."""
    return await service.get_network_vms(network_id=network_id, tenant_id=tenant.id)
