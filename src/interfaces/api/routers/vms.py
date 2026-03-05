from fastapi import APIRouter
from typing import Optional
from uuid import UUID
from datetime import datetime, timezone, timedelta

import redis.asyncio as aioredis
from fastapi import Depends, HTTPException, status

from src.application.services.auth_service import AuthService
from src.application.services.llm_service import LLMService
from src.application.services.quota_service import QuotaExceededError, QuotaService
from src.application.services.suggestion_service import SuggestionService
from src.application.services.vm_service import VMService
from src.infrastructure.models.tenant import Tenant
from src.infrastructure.models.virtual_machine import VMStatus
from src.infrastructure.schemas.users import UserRequest
from src.infrastructure.schemas.vm import (
    SuggestionResponse,
    TriggerAnalyzeResponse,
    VMCreate,
    VMListResponse,
    VMResponse,
    VMSuggestRequest,
    VMSuggestResponse,
    VMUpdate,
)
from src.interfaces.api.dependencies.tenant import get_current_tenant
from src.settings import settings

vms_router = APIRouter(prefix="/vms", tags=["Virtual Machines"])

_redis_vms: Optional[aioredis.Redis] = None

def _get_redis_vms() -> aioredis.Redis:
    global _redis_vms
    if _redis_vms is None:
        _redis_vms = aioredis.from_url(settings.redis.url, decode_responses=True)
    return _redis_vms

_ANALYZE_COOLDOWN_SEC = 86_400  # 24 hours


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


@vms_router.post(
    "/suggest",
    response_model=VMSuggestResponse,
    summary="Get AI-powered VM configuration recommendation",
)
async def suggest_vm_config(
    body: VMSuggestRequest,
    current_user: UserRequest = Depends(AuthService.get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
    llm: LLMService = Depends(),
    quota_svc: QuotaService = Depends(),
) -> VMSuggestResponse:
    """Returns LLM-suggested VM config based on a free-text workload description, capped by tenant quota."""
    # Compute available resources so LLM never recommends beyond what the tenant has left
    try:
        usage_summary = await quota_svc.get_usage_summary(tenant.id)
        constraints = {
            "avail_vcpu": usage_summary["vcpu"]["max"] - usage_summary["vcpu"]["used"],
            "avail_ram_mb": usage_summary["ram_mb"]["max"] - usage_summary["ram_mb"]["used"],
            "avail_disk_gb": usage_summary["disk_gb"]["max"] - usage_summary["disk_gb"]["used"],
            "max_vcpu": usage_summary["vcpu"]["max"],
            "max_ram_mb": usage_summary["ram_mb"]["max"],
            "max_disk_gb": usage_summary["disk_gb"]["max"],
        }
    except Exception:
        constraints = None
    result = await llm.suggest_vm_config(body.description, constraints)
    return VMSuggestResponse(**result)


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


@vms_router.get(
    "/{vm_id}/suggestions",
    response_model=list[SuggestionResponse],
    status_code=status.HTTP_200_OK,
)
async def list_suggestions(
    vm_id: UUID,
    current_user: UserRequest = Depends(AuthService.get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
    svc: SuggestionService = Depends(),
) -> list[SuggestionResponse]:
    """List pending AI optimization suggestions for a VM."""
    return await svc.get_pending(vm_id=vm_id)


@vms_router.post(
    "/{vm_id}/suggestions/{suggestion_id}/accept",
    response_model=VMResponse,
    status_code=status.HTTP_200_OK,
)
async def accept_suggestion(
    vm_id: UUID,
    suggestion_id: UUID,
    current_user: UserRequest = Depends(AuthService.get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
    svc: SuggestionService = Depends(),
    vm_service: VMService = Depends(),
) -> VMResponse:
    """Accept an AI suggestion; if it carries a suggested_config, stop→resize→start the VM."""
    suggestion = await svc.accept(
        suggestion_id=suggestion_id, vm_id=vm_id, tenant_id=tenant.id
    )
    if not suggestion:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Suggestion not found")

    if suggestion.suggested_config:
        config = suggestion.suggested_config
        current_vm = await vm_service.get(vm_id=vm_id, tenant_id=tenant.id)

        was_running = current_vm.status == VMStatus.RUNNING
        if was_running:
            await vm_service.stop(vm_id=vm_id, tenant_id=tenant.id, user_id=current_user.id)

        updated_vm = await vm_service.resize(
            vm_id=vm_id,
            tenant_id=tenant.id,
            vcpu=config.get("vcpu", current_vm.vcpu),
            ram_mb=config.get("ram_mb", current_vm.ram_mb),
            disk_gb=config.get("disk_gb", current_vm.disk_gb),
            user_id=current_user.id,
        )

        if was_running:
            updated_vm = await vm_service.start(vm_id=vm_id, tenant_id=tenant.id, user_id=current_user.id)

        return updated_vm

    return await vm_service.get(vm_id=vm_id, tenant_id=tenant.id)


@vms_router.post(
    "/{vm_id}/suggestions/{suggestion_id}/dismiss",
    response_model=SuggestionResponse,
    status_code=status.HTTP_200_OK,
)
async def dismiss_suggestion(
    vm_id: UUID,
    suggestion_id: UUID,
    current_user: UserRequest = Depends(AuthService.get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
    svc: SuggestionService = Depends(),
) -> SuggestionResponse:
    """Dismiss an AI suggestion."""
    result = await svc.dismiss(suggestion_id=suggestion_id, vm_id=vm_id, tenant_id=tenant.id)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Suggestion not found")
    return result


@vms_router.post(
    "/{vm_id}/trigger-analyze",
    response_model=TriggerAnalyzeResponse,
    status_code=status.HTTP_200_OK,
    summary="Manually trigger AI optimization analysis for a VM (once per 24h)",
)
async def trigger_analyze(
    vm_id: UUID,
    current_user: UserRequest = Depends(AuthService.get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
    svc: SuggestionService = Depends(),
) -> TriggerAnalyzeResponse:
    """
    Immediately run LLM optimization analysis for the given VM.
    Rate-limited to once per 24 hours per tenant+VM via Redis.
    """
    redis_key = f"analyze:cooldown:{tenant.id}:{vm_id}"

    # Check cooldown
    try:
        redis = _get_redis_vms()
        ttl = await redis.ttl(redis_key)
        if ttl > 0:
            next_at = (datetime.now(timezone.utc) + timedelta(seconds=ttl)).isoformat()
            h, m = ttl // 3600, (ttl % 3600) // 60
            return TriggerAnalyzeResponse(
                suggestion=None,
                cooldown_remaining_sec=ttl,
                next_available_at=next_at,
                message=f"Анализ уже выполнялся сегодня. Следующий будет доступен через {h}ч {m}мин.",
            )
    except Exception:
        pass  # Redis unavailable — skip rate-limit check

    # Run analysis (fetches VM ORM object internally)
    suggestion = await svc.analyze_by_id(vm_id=vm_id, tenant_id=tenant.id)

    # Set cooldown in Redis
    try:
        redis = _get_redis_vms()
        await redis.setex(redis_key, _ANALYZE_COOLDOWN_SEC, "1")
    except Exception:
        pass

    if suggestion:
        return TriggerAnalyzeResponse(
            suggestion=SuggestionResponse.model_validate(suggestion, from_attributes=True),
            cooldown_remaining_sec=0,
            next_available_at=None,
            message="✅ Анализ выполнен — новая рекомендация добавлена.",
        )

    return TriggerAnalyzeResponse(
        suggestion=None,
        cooldown_remaining_sec=0,
        next_available_at=None,
        message="ИИ проанализировал VM — оптимизация не требуется или уверенность недостаточна.",
    )
