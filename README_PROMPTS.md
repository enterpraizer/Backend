# 📋 PROMPTS — Нереализованные задачи

> Все промты взяты из `README_BACKEND.md`.
> В качестве примера стиля и структуры смотри уже готовые сервисы:
> - `src/application/services/users_service.py` — паттерн сервиса (Depends, репозиторий, исключения, валидация)
> - `src/application/services/auth_service.py` — паттерн JWT, Depends-цепочки, схемы запрос/ответ

---

## Что уже сделано (не трогать)

| Файл | Статус |
|------|--------|
| `src/infrastructure/models/` — все модели | ✅ |
| `src/infrastructure/repositories/` — все репозитории | ✅ |
| `src/interfaces/api/middleware/tenant.py` | ✅ |
| `src/interfaces/api/dependencies/tenant.py` | ✅ |
| `src/application/services/auth_service.py` | ✅ |
| `src/application/services/users_service.py` | ✅ |
| JWT содержит `tenant_id` | ✅ |

---

## ⚠️ ЧАСТИЧНО: 1.3 — tenant_service + POST /auth/tenant

```
Read src/application/services/auth_service.py fully.

4. Create src/application/services/tenant_service.py:
   class TenantService:
     __init__(self, repo: TenantRepository = Depends(), quota_repo: QuotaRepository = Depends(), usage_repo: UsageRepository = Depends())

     async create_tenant(name: str, owner_id: UUID, session: AsyncSession) -> Tenant:
       - slugify name → slug
       - INSERT into tenants
       - INSERT default ResourceQuota for this tenant (max_vcpu=8, max_ram_mb=16384, max_disk_gb=200, max_vms=5)
       - INSERT ResourceUsage zeroed out for this tenant
       - Return tenant

     async get_tenant(tenant_id: UUID) → Tenant
     async list_tenants(limit, offset) → List[Tenant]  ← admin only
     async update_tenant(tenant_id, **kwargs) → Tenant
     async deactivate_tenant(tenant_id) → None

5. Add POST /auth/tenant (protected, any authenticated user) that calls tenant_service.create_tenant
   using the current user as owner. Returns TenantResponse with id, name, slug.
   On success, issue a new JWT pair with the new tenant_id embedded.
```

---

## ❌ 1.5 — Hypervisor Service (Docker SDK Mock)

```
Install docker Python SDK: add "docker>=7.0.0" to pyproject.toml dependencies.
Read src/infrastructure/models/virtual_machine.py (VirtualMachine model with VMStatus enum).

Create src/application/services/hypervisor_service.py:

import docker
from docker.errors import NotFound, APIError, DockerException
from src.infrastructure.models.virtual_machine import VMStatus

HYPERVISOR_IMAGE = "alpine:latest"  ← lightweight mock OS image

class HypervisorService:
    def __init__(self):
        try:
            self._client = docker.from_env()
        except DockerException:
            self._client = None  ← graceful degradation if Docker not available

    def _container_name(self, vm_id: UUID, tenant_id: UUID) -> str:
        return f"vm-{tenant_id!s:.8}-{vm_id!s:.8}"

    async def provision_vm(self, vm_id: UUID, tenant_id: UUID, name: str,
                           vcpu: int, ram_mb: int, disk_gb: int) -> dict:
        """
        Spawn a Docker container simulating a VM.
        Maps:
          vcpu     → nano_cpus = vcpu * 1_000_000_000
          ram_mb   → mem_limit = f"{ram_mb}m"
          disk_gb  → binds a named Docker volume: vm-{vm_id}-disk
        Returns: {"container_id": str, "container_name": str, "ip_address": str}
        """
        if not self._client:
            return {"container_id": "mock-" + str(vm_id)[:8],
                    "container_name": self._container_name(vm_id, tenant_id),
                    "ip_address": "10.0.0.1"}
        volume_name = f"vm-{vm_id}-disk"
        container = self._client.containers.run(
            image=HYPERVISOR_IMAGE,
            name=self._container_name(vm_id, tenant_id),
            command="sleep infinity",
            nano_cpus=vcpu * 1_000_000_000,
            mem_limit=f"{ram_mb}m",
            volumes={volume_name: {"bind": "/data", "mode": "rw"}},
            detach=True,
            labels={"tenant_id": str(tenant_id), "vm_id": str(vm_id), "managed_by": "cloudiaas"},
        )
        networks = container.attrs.get("NetworkSettings", {}).get("Networks", {})
        ip = next(iter(networks.values()), {}).get("IPAddress", "")
        return {"container_id": container.id, "container_name": container.name, "ip_address": ip}

    async def start_vm(self, container_id: str) -> VMStatus:
        if not self._client or container_id.startswith("mock-"):
            return VMStatus.RUNNING
        container = self._client.containers.get(container_id)
        container.start()
        return VMStatus.RUNNING

    async def stop_vm(self, container_id: str) -> VMStatus:
        if not self._client or container_id.startswith("mock-"):
            return VMStatus.STOPPED
        container = self._client.containers.get(container_id)
        container.stop(timeout=10)
        return VMStatus.STOPPED

    async def terminate_vm(self, container_id: str, vm_id: UUID) -> None:
        """Stop + remove container + remove disk volume."""
        if not self._client or container_id.startswith("mock-"):
            return
        try:
            container = self._client.containers.get(container_id)
            container.stop(timeout=5)
            container.remove(force=True)
        except NotFound:
            pass
        try:
            volume = self._client.volumes.get(f"vm-{vm_id}-disk")
            volume.remove()
        except NotFound:
            pass

    async def get_vm_status(self, container_id: str) -> VMStatus:
        if not self._client or container_id.startswith("mock-"):
            return VMStatus.RUNNING
        try:
            container = self._client.containers.get(container_id)
            state = container.status  ← "running" | "exited" | "created" | "paused"
            mapping = {"running": VMStatus.RUNNING, "exited": VMStatus.STOPPED,
                       "created": VMStatus.PENDING, "paused": VMStatus.STOPPED}
            return mapping.get(state, VMStatus.STOPPED)
        except NotFound:
            return VMStatus.TERMINATED

    async def list_tenant_containers(self, tenant_id: UUID) -> list[dict]:
        """List all containers belonging to this tenant via label filter."""
        if not self._client:
            return []
        containers = self._client.containers.list(
            all=True, filters={"label": f"tenant_id={tenant_id}"}
        )
        return [{"id": c.id, "name": c.name, "status": c.status} for c in containers]
```

---

## ⚠️ ЧАСТИЧНО: 1.6 — docker-compose + .env.example + Makefile

```
Read the current docker-compose.yaml, .env.example, pyproject.toml.

Update docker-compose.yaml:
  - Mount Docker socket into backend service:
      volumes:
        - .:/app
        - /var/run/docker.sock:/var/run/docker.sock
    so the FastAPI app can control Docker containers (hypervisor simulation).
  - Add `celery-beat` service:
      command: celery -A src.application.services.celery_config.celery_app beat --loglevel=info
      (for periodic VM status sync tasks)
  - Fix: backend healthcheck URL should use /health

Overwrite .env.example with ALL required variables:
  # PostgreSQL
  POSTGRES_HOST=db
  POSTGRES_PORT=5432
  POSTGRES_DB=cloudiaas
  POSTGRES_USER=postgres
  POSTGRES_PASSWORD=secret

  # Redis
  REDIS_HOST=redis
  REDIS_PORT=6379
  REDIS_DB=0

  # Email
  EMAIL_HOST=smtp.gmail.com
  EMAIL_PORT=587
  EMAIL_USERNAME=your@email.com
  EMAIL_PASSWORD=yourpassword

  # JWT & App
  SECRET_KEY=changeme
  FRONTEND_URL=http://localhost:3000
  APP_SECRET_KEY=changeme-access
  APP_REFRESH_SECRET_KEY=changeme-refresh
  APP_ALGORITHM=HS256
  APP_ACCESS_TOKEN_EXPIRE_MINUTES=30
  APP_REFRESH_TOKEN_EXPIRE_DAYS=7
  DEBUG=true

Generate Makefile:
  dev:        docker compose up --build
  down:       docker compose down -v
  migrate:    docker compose exec backend alembic upgrade head
  mm:         docker compose exec backend alembic revision --autogenerate -m "$(msg)"
  test:       docker compose exec backend pytest tests/ -v --asyncio-mode=auto
  logs:       docker compose logs -f backend
  shell:      docker compose exec backend python
  pull-image: docker pull alpine:latest  ← pre-pull hypervisor base image
```

---

## ❌ 2.1 — Quota Service

```
Read src/infrastructure/repositories/quota_repository.py and usage_repository.py.

Create src/application/services/quota_service.py:

class QuotaExceededError(Exception):
    def __init__(self, resource: str, requested: int, available: int):
        self.resource = resource
        self.requested = requested
        self.available = available
        super().__init__(f"Quota exceeded for {resource}: requested {requested}, available {available}")

class QuotaService:
    def __init__(self,
                 quota_repo: QuotaRepository = Depends(),
                 usage_repo: UsageRepository = Depends()):
        self._quota = quota_repo
        self._usage = usage_repo

    async def check_and_reserve(self, tenant_id: UUID, vcpu: int, ram_mb: int, disk_gb: int) -> None:
        """
        Atomically validate that current_usage + requested <= quota.
        Raises QuotaExceededError with details if any resource is exceeded.
        Steps:
          1. quota = await self._quota.get_by_tenant(tenant_id)
          2. usage = await self._usage.get_by_tenant(tenant_id)
          3. Check each dimension:
             if usage.used_vcpu + vcpu > quota.max_vcpu → raise QuotaExceededError("vCPU", ...)
             if usage.used_ram_mb + ram_mb > quota.max_ram_mb → raise QuotaExceededError("RAM", ...)
             if usage.used_disk_gb + disk_gb > quota.max_disk_gb → raise QuotaExceededError("Disk", ...)
             if usage.used_vms + 1 > quota.max_vms → raise QuotaExceededError("VM count", ...)
          4. On success: await self._usage.increment(tenant_id, vcpu, ram_mb, disk_gb)
        """

    async def release(self, tenant_id: UUID, vcpu: int, ram_mb: int, disk_gb: int) -> None:
        """Called on VM stop or terminate. Decrements usage."""
        await self._usage.decrement(tenant_id, vcpu, ram_mb, disk_gb)

    async def get_usage_summary(self, tenant_id: UUID) -> dict:
        quota = await self._quota.get_by_tenant(tenant_id)
        usage = await self._usage.get_by_tenant(tenant_id)
        return {
            "vcpu":    {"used": usage.used_vcpu,    "max": quota.max_vcpu,    "pct": round(usage.used_vcpu / quota.max_vcpu * 100, 1)},
            "ram_mb":  {"used": usage.used_ram_mb,  "max": quota.max_ram_mb,  "pct": round(usage.used_ram_mb / quota.max_ram_mb * 100, 1)},
            "disk_gb": {"used": usage.used_disk_gb, "max": quota.max_disk_gb, "pct": round(usage.used_disk_gb / quota.max_disk_gb * 100, 1)},
            "vms":     {"used": usage.used_vms,     "max": quota.max_vms,     "pct": round(usage.used_vms / quota.max_vms * 100, 1)},
        }

    async def update_quota(self, tenant_id: UUID, admin_user: UserRequest, **quota_fields) -> ResourceQuota:
        """Admin-only: update quota limits."""
        if admin_user.role != "admin":
            raise PermissionError("Only admins can update quotas")
        return await self._quota.update(ResourceQuota.tenant_id == tenant_id, **quota_fields)
```

---

## ❌ 2.2 — VM Service + Full Lifecycle

```
Read src/application/services/quota_service.py, src/application/services/hypervisor_service.py,
src/infrastructure/repositories/vm_repository.py, src/infrastructure/schemas/vm.py.

Replace the stub in src/application/services/vm_service.py with:

class VMService:
    def __init__(self,
                 vm_repo: VMRepository = Depends(),
                 quota_service: QuotaService = Depends(),
                 hypervisor: HypervisorService = Depends()):
        self._vm_repo = vm_repo
        self._quota = quota_service
        self._hypervisor = hypervisor

    async def create(self, tenant_id: UUID, owner_id: UUID, data: VMCreate) -> VMResponse:
        """
        1. await self._quota.check_and_reserve(tenant_id, data.vcpu, data.ram_mb, data.disk_gb)
           ← raises QuotaExceededError if limits exceeded
        2. vm = await self._vm_repo.create(tenant_id=tenant_id, owner_id=owner_id,
                                           name=data.name, vcpu=data.vcpu,
                                           ram_mb=data.ram_mb, disk_gb=data.disk_gb,
                                           status=VMStatus.PENDING)
        3. result = await self._hypervisor.provision_vm(vm.id, tenant_id, data.name,
                                                        data.vcpu, data.ram_mb, data.disk_gb)
        4. vm = await self._vm_repo.update_status(vm.id, tenant_id, VMStatus.RUNNING,
                                                   container_id=result["container_id"],
                                                   ip_address=result["ip_address"],
                                                   container_name=result["container_name"])
        5. return VMResponse.model_validate(vm, from_attributes=True)
        """

    async def start(self, vm_id: UUID, tenant_id: UUID) -> VMResponse:
        """
        1. vm = get VM (with tenant_id check for isolation)
        2. If vm.status != STOPPED → raise HTTPException 409 "VM is not stopped"
        3. await self._hypervisor.start_vm(vm.container_id)
        4. await self._vm_repo.update_status(vm_id, tenant_id, VMStatus.RUNNING)
        5. await self._quota.reserve_running(tenant_id, vm.vcpu, vm.ram_mb)  ← increment on start
        """

    async def stop(self, vm_id: UUID, tenant_id: UUID) -> VMResponse:
        """
        1. vm = get VM (tenant_id check)
        2. If vm.status != RUNNING → raise 409
        3. await self._hypervisor.stop_vm(vm.container_id)
        4. await self._vm_repo.update_status(vm_id, tenant_id, VMStatus.STOPPED)
        5. await self._quota.release(tenant_id, vm.vcpu, vm.ram_mb, 0)  ← release CPU/RAM only (disk stays)
        """

    async def terminate(self, vm_id: UUID, tenant_id: UUID) -> None:
        """
        1. vm = get VM (tenant_id check)
        2. await self._hypervisor.terminate_vm(vm.container_id, vm_id)
        3. await self._vm_repo.update_status(vm_id, tenant_id, VMStatus.TERMINATED)
        4. await self._quota.release(tenant_id, vm.vcpu, vm.ram_mb, vm.disk_gb)  ← full release
        5. Optional hard delete after 24h via Celery task
        """

    async def get(self, vm_id: UUID, tenant_id: UUID) -> VMResponse:
        vm = await self._vm_repo.get(VirtualMachine.id == vm_id, tenant_id=tenant_id)
        if not vm: raise HTTPException(404)
        return VMResponse.model_validate(vm, from_attributes=True)

    async def list(self, tenant_id: UUID, limit: int, offset: int,
                   status_filter: VMStatus | None = None) -> tuple[list[VMResponse], int]:
        items = await self._vm_repo.get_all(tenant_id=tenant_id, limit=limit, offset=offset)
        total = await self._vm_repo.count(tenant_id=tenant_id)
        return [VMResponse.model_validate(v, from_attributes=True) for v in items], total

Also create src/infrastructure/schemas/vm.py with Pydantic v2:
  VMCreate: name str(3-100), vcpu int(1-32), ram_mb int(512-65536), disk_gb int(10-500)
  VMUpdate: name optional, status: Optional[Literal['running','stopped']]
  VMResponse: id, tenant_id, name, status, vcpu, ram_mb, disk_gb, ip_address, container_id, created_at
  VMListResponse: items: List[VMResponse], total: int
```

---

## ❌ 2.3 — VM Router

```
Read src/application/services/vm_service.py and src/interfaces/api/dependencies/tenant.py.

Replace stub in src/interfaces/api/routers/vms.py:
  vms_router = APIRouter(prefix="/vms", tags=["Virtual Machines"])

  All endpoints require:
    current_user: UserRequest = Depends(AuthService.get_current_user)
    tenant: Tenant = Depends(get_current_tenant)
  tenant.id is passed to every service call for isolation.

  GET    /vms                → list all tenant VMs (paginated: ?limit=20&offset=0&status=running)
  POST   /vms                → create VM (body: VMCreate)
                               catches QuotaExceededError → returns HTTP 429 with:
                               {"detail": "Quota exceeded", "resource": "...", "requested": N, "available": N}
  GET    /vms/{vm_id}        → get single VM (tenant-scoped)
  POST   /vms/{vm_id}/start  → start stopped VM
  POST   /vms/{vm_id}/stop   → stop running VM
  DELETE /vms/{vm_id}        → terminate VM (sets status=terminated, removes container)
  PATCH  /vms/{vm_id}        → update VM metadata (name only)

  Add response_model, status codes, and docstrings to every endpoint.
  Include vms_router in src/interfaces/api/app.py.
```

---

## ❌ 2.4 — Network Service + Router (VPC/Subnet)

```
Read src/infrastructure/repositories/network_repository.py and tenant dependency.

Create src/infrastructure/schemas/network.py:
  NetworkCreate: name str(3-100), cidr str (regex validated IPv4 CIDR), is_public bool=False
  NetworkResponse: id, tenant_id, name, cidr, status, is_public, created_at
  NetworkListResponse: items: List[NetworkResponse], total: int
  AttachVMRequest: vm_id: UUID

Replace stub in src/application/services/network_service.py:
  class NetworkService:
    All queries pass tenant_id for isolation.
    async create(tenant_id, data: NetworkCreate) → NetworkResponse
      ← validate CIDR not overlapping existing tenant networks (fetch all, check with ipaddress module)
    async get(network_id, tenant_id) → NetworkResponse
    async list(tenant_id, limit, offset) → NetworkListResponse
    async delete(network_id, tenant_id) → None
    async attach_vm(network_id: UUID, vm_id: UUID, tenant_id: UUID) → None
      ← validate both network and VM belong to same tenant_id before inserting association
    async detach_vm(network_id: UUID, vm_id: UUID, tenant_id: UUID) → None
    async get_network_vms(network_id: UUID, tenant_id: UUID) → List[VMResponse]

Replace stub in src/interfaces/api/routers/networks.py:
  networks_router = APIRouter(prefix="/networks", tags=["Virtual Networks"])
  GET    /networks                    → list tenant networks
  POST   /networks                    → create VPC
  GET    /networks/{id}               → network detail
  DELETE /networks/{id}               → delete network
  POST   /networks/{id}/attach-vm     → attach VM to network (validates same tenant)
  POST   /networks/{id}/detach-vm     → detach VM
  GET    /networks/{id}/vms           → list VMs in network
  Include networks_router in app.py.
```

---

## ❌ 2.5 — Admin Router (Tenant + Quota management)

```
Read src/application/services/tenant_service.py, quota_service.py, src/infrastructure/schemas/tenant.py.

Create src/infrastructure/schemas/tenant.py:
  TenantCreate: name str(3-100)
  TenantResponse: id, name, slug, owner_id, is_active, created_at
  TenantListResponse: items: List[TenantResponse], total: int

Create src/infrastructure/schemas/quota.py:
  QuotaUpdate: max_vcpu: Optional[int], max_ram_mb: Optional[int], max_disk_gb: Optional[int], max_vms: Optional[int]
  QuotaResponse: tenant_id, max_vcpu, max_ram_mb, max_disk_gb, max_vms
  UsageSummaryResponse: (nested dict per resource: used, max, pct)

Create src/interfaces/api/dependencies/permissions.py:
  async def require_admin(user: UserRequest = Depends(get_current_user)):
      if user.role != "admin": raise HTTPException(403, "Admin access required")
      return user

Replace stub in src/interfaces/api/routers/admin.py:
  admin_router = APIRouter(prefix="/admin", tags=["Admin"], dependencies=[Depends(require_admin)])

  # Tenant management
  GET    /admin/tenants                    → list all tenants (paginated)
  POST   /admin/tenants                    → create tenant manually (assigns to user)
  GET    /admin/tenants/{tenant_id}        → tenant detail
  PATCH  /admin/tenants/{tenant_id}        → update tenant (activate/deactivate)
  DELETE /admin/tenants/{tenant_id}        → deactivate tenant

  # Quota management
  GET    /admin/tenants/{tenant_id}/quota  → get quota + current usage
  PATCH  /admin/tenants/{tenant_id}/quota  → update quota limits (body: QuotaUpdate)

  # Global statistics
  GET    /admin/stats → return:
    {
      "total_tenants": int,
      "active_tenants": int,
      "total_vms": int,
      "running_vms": int,
      "total_vcpu_allocated": int,
      "total_ram_mb_allocated": int,
      "total_disk_gb_allocated": int,
      "top_tenants_by_vms": List[{tenant_name, vm_count}]  ← top 5
    }

  # All VMs across tenants (admin monitoring)
  GET    /admin/vms   → list ALL VMs across ALL tenants (with tenant_name, paginated)
  Include admin_router in app.py.
```

---

## ❌ 2.6 — Celery Tasks: VM Status Sync

```
Read src/application/services/hypervisor_service.py, src/application/services/celery_config.py.
Read src/application/services/tasks.py (existing send_confirmation_email task).

Add to src/application/services/tasks.py:

@celery_app.task(name="sync_vm_statuses")
def sync_vm_statuses():
    """
    Periodic task: runs every 60 seconds via Celery Beat.
    1. Query all VMs with status IN (RUNNING, PENDING) from DB (use synchronous SQLAlchemy for Celery)
    2. For each VM: hypervisor.get_vm_status(vm.container_id)
    3. If actual status differs from DB status → update DB
    4. Log discrepancies
    """

@celery_app.task(name="cleanup_terminated_vms")
def cleanup_terminated_vms():
    """
    Periodic task: runs every hour.
    Delete VMs with status=TERMINATED and updated_at older than 24 hours from DB.
    """

@celery_app.task(name="provision_vm_async")
def provision_vm_async(vm_id: str, tenant_id: str, name: str, vcpu: int, ram_mb: int, disk_gb: int):
    """
    Alternative: async VM provisioning via Celery for non-blocking API response.
    Called by vm_service.create() for large VMs.
    Updates VM status from PENDING → RUNNING after Docker container starts.
    """

Add Celery Beat schedule in src/application/services/celery_config.py:
  celery_app.conf.beat_schedule = {
      "sync-vm-statuses": {"task": "sync_vm_statuses", "schedule": 60.0},
      "cleanup-terminated": {"task": "cleanup_terminated_vms", "schedule": 3600.0},
  }
```

---

## ❌ 3.1 — Resource Usage Dashboard + AuditService

```
Read src/application/services/quota_service.py get_usage_summary() and all routers.

Create src/interfaces/api/routers/dashboard.py:
  dashboard_router = APIRouter(prefix="/dashboard", tags=["Dashboard"])
  All endpoints: Depends(get_current_tenant)

  GET /dashboard/usage
    Returns QuotaService.get_usage_summary(tenant_id) — per-resource dict with used/max/pct.
    Cache result in Redis with key "usage:{tenant_id}" TTL=30s using redis.asyncio.

  GET /dashboard/vms/summary
    Returns: { total: int, running: int, stopped: int, pending: int, terminated: int }
    Counts from vm_repo grouped by status for the tenant.

  GET /dashboard/networks/summary
    Returns: { total: int, active: int }

  GET /dashboard/activity
    Returns last 20 activity log entries for this tenant (see AuditLog model below).

Create src/application/services/audit_service.py:
  class AuditService:
    async def log(self, tenant_id, user_id, action, resource_type, resource_id=None, details=None)

Call audit_service.log() in vm_service.create(), start(), stop(), terminate() and network_service.create(), delete().
Include dashboard_router in app.py.
```

---

## ❌ 3.2 — Rate Limiting + Security Headers

```
Read src/interfaces/api/app.py and src/settings/redis.py.

Create src/interfaces/api/middleware/rate_limit.py:
  RedisRateLimitMiddleware(BaseHTTPMiddleware):
    Uses redis.asyncio client. Sliding window algorithm.
    Key = "rate:{ip_address}"
    Default: 100 req/min for general endpoints.
    Key = "rate:auth:{ip_address}" for /auth/* endpoints.
    Auth limit: 10 req/min (brute force protection).
    On exceeded: return JSONResponse({"detail": "Too many requests"}, status_code=429)
    Add Retry-After header.

Create src/interfaces/api/middleware/logging_middleware.py:
  RequestLoggingMiddleware(BaseHTTPMiddleware):
    Log every request: "{method} {path} [{tenant_id}] → {status} in {duration}ms"
    Use Python structlog or standard logging.
    Skip /health endpoint.

Create src/interfaces/api/middleware/security_headers.py:
  SecurityHeadersMiddleware(BaseHTTPMiddleware):
    Add response headers:
      X-Content-Type-Options: nosniff
      X-Frame-Options: DENY
      X-XSS-Protection: 1; mode=block
      Strict-Transport-Security: max-age=31536000

Update src/interfaces/api/app.py to add all three middlewares in order:
  1. SecurityHeadersMiddleware
  2. RequestLoggingMiddleware
  3. RedisRateLimitMiddleware
  4. TenantMiddleware (already added)
  5. CORSMiddleware

Add global exception handlers for:
  QuotaExceededError → 429 {"detail": "...", "resource": "...", "available": N}
  UserNotFound → 404
  UserPermissionDenied → 403
  UserAlreadyExistsError → 409
  HTTPException → passthrough
  Exception → 500 (log traceback, return generic message)
```

---

## ❌ 3.3 — Alembic Migrations

```
Read alembic/env.py and all files in src/infrastructure/models/.
Ensure all new models are imported in alembic/env.py:
  from src.infrastructure.models.tenant import Tenant
  from src.infrastructure.models.resource_quota import ResourceQuota
  from src.infrastructure.models.resource_usage import ResourceUsage
  from src.infrastructure.models.virtual_machine import VirtualMachine
  from src.infrastructure.models.virtual_network import VirtualNetwork
  from src.infrastructure.models.audit_log import AuditLog

Run: alembic revision --autogenerate -m "add_full_iaas_schema"

Review the generated migration and verify:
  - ENUM types created before tables that use them
  - All FK constraints correct
  - All indexes present
  - vm_network_association table created
  - UniqueConstraint on (tenant_id, name) for virtual_networks

Generate a seed data script at src/infrastructure/seed.py:
  Creates: 1 admin user, 1 demo tenant, assigns quota, creates 2 demo VMs in STOPPED state.
  Run via: python -m src.infrastructure.seed
```

---

## ❌ 3.4 — Integration Tests

```
Read src/interfaces/api/app.py, all routers, src/application/services/.
Read existing tests structure.

Create tests/conftest.py:
  - async fixture client: httpx.AsyncClient with ASGITransport
  - async fixture db: SQLite in-memory, create_all, override get_db
  - async fixture tenant_a_client: registers user A, creates tenant A, returns authenticated client
  - async fixture tenant_b_client: registers user B, creates tenant B, returns authenticated client
  - async fixture admin_client: creates admin user (role=admin), authenticated client

Create tests/test_tenant_isolation.py — CRITICAL isolation tests:
  test_tenant_cannot_see_other_tenant_vms:
    1. tenant_a creates VM → gets vm_a_id
    2. tenant_b calls GET /vms/{vm_a_id} → must return 404 (not 403, to not leak existence)

  test_tenant_cannot_stop_other_tenant_vm:
    1. tenant_a creates and starts VM
    2. tenant_b calls POST /vms/{vm_a_id}/stop → must return 404

  test_tenant_network_isolation:
    1. tenant_a creates network "net-a"
    2. tenant_b calls GET /networks → must NOT see "net-a"

  test_quota_enforcement:
    1. Admin sets tenant quota: max_vms=2
    2. tenant_a creates VM1 → 201
    3. tenant_a creates VM2 → 201
    4. tenant_a creates VM3 → 429 QuotaExceeded

  test_quota_releases_on_terminate:
    1. Create VM → quota used_vms=1
    2. DELETE /vms/{id} → terminate
    3. GET /dashboard/usage → used_vms=0

  test_admin_can_see_all_tenants:
    1. tenant_a and tenant_b each create VMs
    2. admin GET /admin/vms → sees VMs from both tenants

Create tests/test_vm_lifecycle.py:
  test_vm_full_lifecycle: create → PENDING → RUNNING → stop → STOPPED → start → RUNNING → terminate → TERMINATED
  test_create_vm_quota_exceeded_returns_429_with_details
  test_vm_response_contains_ip_address_after_provision

Run: pytest tests/ -v --asyncio-mode=auto -x
```

---

## ❌ 3.5 — GitHub Actions CI + OpenAPI Docs

```
Read all routes and models in the project.

1. Enhance every FastAPI endpoint with:
   - summary, description, response_model, responses dict (200/201/400/401/403/404/409/429/503)
   - tags already set per router
   - Add request/response examples to all Pydantic schemas using model_config examples

2. Customize FastAPI app in app.py:
   app = FastAPI(
     title="CloudIaaS API",
     version="2.0.0",
     description="Multi-tenant IaaS Cloud Platform with Docker Hypervisor simulation",
     contact={"name": "CloudIaaS Team", "email": "api@cloudiaas.dev"},
     docs_url="/docs",
     redoc_url="/redoc",
   )

3. Generate .github/workflows/ci.yml:
   name: CI
   on: push/PR to main and dev
   jobs:
     test:
       runs-on: ubuntu-latest
       services:
         postgres:
           image: postgres:17
           env: POSTGRES_DB=test POSTGRES_USER=test POSTGRES_PASSWORD=test
           options: --health-cmd pg_isready
         redis:
           image: redis:latest
           options: --health-cmd "redis-cli ping"
       steps:
         - uses: actions/checkout@v4
         - uses: actions/setup-python@v5 (python 3.13)
         - run: pip install uv && uv pip install --system -e .
         - run: alembic upgrade head
         - run: pytest tests/ -v --asyncio-mode=auto --cov=src --cov-report=xml
         - uses: codecov/codecov-action@v4

4. Add GET /openapi-summary endpoint (admin only) listing all routes with method/path/summary.
```
