# 📋 BACKEND PLAN — CloudIaaS Platform (FastAPI)

## Project Vision
A multi-tenant IaaS cloud platform inspired by TimeWeb Cloud.
Tenants (clients) manage isolated VMs and virtual networks with enforced resource quotas.
Docker is used as a mock hypervisor to simulate real VM lifecycle management.

---

## Tech Stack
| Layer | Technology |
|---|---|
| Framework | FastAPI 0.121 + Uvicorn + uvloop |
| Language | Python 3.13 |
| ORM | SQLAlchemy 2.0 async + asyncpg |
| Database | PostgreSQL 17 |
| Migrations | Alembic 1.17 |
| Auth | JWT (python-jose) + passlib/bcrypt — **already implemented** |
| Cache | Redis 7 |
| Task Queue | Celery 5 (email + async hypervisor ops) |
| Hypervisor Mock | Docker SDK for Python (`docker` package) |
| Containerization | Docker + docker-compose |
| Testing | Pytest + pytest-asyncio + httpx |

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                      FastAPI Application                     │
│                                                             │
│  interfaces/api/                                            │
│  ├── middleware/tenant.py   ← Injects tenant_id from JWT   │
│  ├── middleware/ratelimit.py                                │
│  ├── dependencies/          ← get_db, get_current_tenant   │
│  └── routers/               ← vms, networks, quotas, admin │
│                                                             │
│  application/services/                                      │
│  ├── vm_service.py          ← quota check → hypervisor call│
│  ├── network_service.py     ← VPC/subnet management        │
│  ├── quota_service.py       ← enforce + track usage        │
│  ├── hypervisor_service.py  ← Docker SDK mock hypervisor   │
│  └── tenant_service.py      ← tenant CRUD (admin)         │
│                                                             │
│  infrastructure/                                            │
│  ├── models/     ← User, Tenant, VM, Network, Quota, Usage │
│  └── repositories/          ← tenant-scoped queries        │
└─────────────────────────────────────────────────────────────┘
         │                        │
    PostgreSQL 17             Redis + Celery
    (row-level isolation)     (async tasks)
         │
    Docker Engine API
    (hypervisor simulation)
```

### Key Architectural Concepts

**Tenant Middleware** — Every authenticated request extracts `tenant_id` from JWT payload and attaches it to `request.state.tenant_id`. All repository queries are filtered by this `tenant_id` automatically.

**Hypervisor Service** — `HypervisorService` wraps Docker SDK. Creating a VM spawns a real Docker container with `nano_cpus`, `mem_limit`, and a bind volume. VM state maps to container state.

**Quota Service** — Before any VM creation, `QuotaService.check_and_reserve()` validates that tenant's current usage + requested resources ≤ quota limits. On VM delete/stop, usage is decremented.

**Resource Usage Tracking** — `ResourceUsage` model stores live counters per tenant (used_vcpu, used_ram_mb, used_disk_gb, used_vms). Updated atomically on every VM lifecycle event.

---

## Team
| Role | Responsibility |
|---|---|
| **Dev-1** | Architecture, Tenant Middleware, API wiring |
| **Dev-2** | DB Models, Migrations, Row-Level Isolation |
| **Dev-3** | Auth hardening, Tenant context in JWT, Security |
| **Dev-4** | Hypervisor Service, VM Lifecycle, Quota Engine |
| **Dev-5** | Testing, DevOps, Monitoring endpoints |

---

## ✅ Already Implemented
- `User` model + `UserRepository` + `BaseRepository`
- `AuthService` (register, login, refresh, email confirmation via Celery)
- `UserService` (CRUD with permission checks)
- Routers: `/auth/*`, `/users/*`
- Docker Compose: PostgreSQL + Redis + backend + Celery worker
- Alembic init migration (users table)

---

## DAY 1 — Core Architecture & Multi-Tenant Isolation

### 1.1 [Dev-2] Tenant, VM, Network, Quota, ResourceUsage Models
- [x] ✅ **СДЕЛАНО** | **Demonstrates: Multi-tenancy, Resource Control** | ⏱ 3h

<details>
<summary>📎 Copilot Prompt</summary>

```
Read src/infrastructure/models/base.py and src/infrastructure/models/users.py.
Using SQLAlchemy 2.0 async ORM, create the following models in separate files under src/infrastructure/models/:

FILE: src/infrastructure/models/tenant.py
class Tenant(Base):
  __tablename__ = "tenants"
  id: UUID PK, server_default gen_random_uuid()
  name: String(100), unique=True, nullable=False
  slug: String(100), unique=True, nullable=False  ← URL-safe identifier
  owner_id: UUID FK → users.id, nullable=False
  is_active: Boolean, default=True
  created_at: DateTime, server_default=func.now()

FILE: src/infrastructure/models/resource_quota.py
class ResourceQuota(Base):
  __tablename__ = "resource_quotas"
  id: UUID PK
  tenant_id: UUID FK → tenants.id, nullable=False, unique=True
  max_vcpu: Integer, default=8
  max_ram_mb: Integer, default=16384
  max_disk_gb: Integer, default=200
  max_vms: Integer, default=5
  created_at: DateTime, server_default=func.now()
  updated_at: DateTime, server_default=func.now(), onupdate=func.now()

FILE: src/infrastructure/models/resource_usage.py
class ResourceUsage(Base):
  __tablename__ = "resource_usage"
  id: UUID PK
  tenant_id: UUID FK → tenants.id, nullable=False, unique=True
  used_vcpu: Integer, default=0, nullable=False
  used_ram_mb: Integer, default=0, nullable=False
  used_disk_gb: Integer, default=0, nullable=False
  used_vms: Integer, default=0, nullable=False
  updated_at: DateTime, server_default=func.now(), onupdate=func.now()

FILE: src/infrastructure/models/virtual_machine.py
class VMStatus(StrEnum): PENDING="pending" RUNNING="running" STOPPED="stopped" TERMINATED="terminated"
class VirtualMachine(Base):
  __tablename__ = "virtual_machines"
  id: UUID PK, server_default gen_random_uuid()
  tenant_id: UUID FK → tenants.id, nullable=False, index=True  ← TENANT ISOLATION KEY
  owner_id: UUID FK → users.id, nullable=False
  name: String(100), nullable=False
  status: ENUM(VMStatus), default=VMStatus.PENDING, nullable=False
  vcpu: Integer, nullable=False
  ram_mb: Integer, nullable=False
  disk_gb: Integer, nullable=False
  ip_address: String(45), nullable=True
  container_id: String(64), nullable=True  ← Docker container ID
  container_name: String(128), nullable=True
  created_at: DateTime, server_default=func.now()
  updated_at: DateTime, server_default=func.now(), onupdate=func.now()
  Add __table_args__ = (Index('ix_vm_tenant_status', 'tenant_id', 'status'),)

FILE: src/infrastructure/models/virtual_network.py
class NetworkStatus(StrEnum): ACTIVE="active" INACTIVE="inactive"
class VirtualNetwork(Base):
  __tablename__ = "virtual_networks"
  id: UUID PK
  tenant_id: UUID FK → tenants.id, nullable=False, index=True  ← TENANT ISOLATION KEY
  name: String(100), nullable=False
  cidr: String(18), nullable=False  ← e.g. "10.0.0.0/24"
  status: ENUM(NetworkStatus), default=NetworkStatus.ACTIVE
  created_at: DateTime, server_default=func.now()
  Add UniqueConstraint('tenant_id', 'name') so names are unique per tenant only

Add association table vm_network_association (vm_id UUID FK, network_id UUID FK).
Export all models in src/infrastructure/models/__init__.py.
Register all models in alembic/env.py target_metadata.
Run: alembic revision --autogenerate -m "add_tenant_vm_network_quota_usage_tables"
```
</details>

---

### 1.2 [Dev-1] Tenant Middleware + Tenant Context Dependency
- [x] ✅ **СДЕЛАНО** — `middleware/tenant.py` (TenantMiddleware) ✅, `dependencies/tenant.py` (get_tenant_id, get_current_tenant) ✅, подключено в `app.py` + CORSMiddleware ✅ | **Demonstrates: Multi-tenancy, Row-Level Isolation** | ⏱ 2h

<details>
<summary>📎 Copilot Prompt</summary>

```
Read src/application/services/auth_service.py (AuthService.get_current_user returns UserRequest with role, id, email).
Read src/interfaces/api/dependencies/session.py.

Create src/interfaces/api/middleware/tenant.py:
  Starlette BaseHTTPMiddleware subclass TenantMiddleware.
  For every request:
    1. If path starts with /auth/ or /health → skip
    2. Extract Bearer token from Authorization header
    3. Decode JWT (use AuthService.decode_access_token) to get payload
    4. Extract tenant_id from payload field "tenant_id" (add this field to JWT in step 1.3)
    5. Set request.state.tenant_id = UUID(tenant_id) or None
    6. On JWTError: set request.state.tenant_id = None

Create src/interfaces/api/dependencies/tenant.py:
  async def get_tenant_id(request: Request) -> UUID:
      tenant_id = request.state.tenant_id
      if tenant_id is None:
          raise HTTPException(status_code=403, detail="Tenant context missing")
      return tenant_id

  async def get_current_tenant(
      tenant_id: UUID = Depends(get_tenant_id),
      session: AsyncSession = Depends(get_db)
  ) -> Tenant:
      tenant = await session.get(Tenant, tenant_id)
      if not tenant or not tenant.is_active:
          raise HTTPException(status_code=403, detail="Tenant not found or inactive")
      return tenant

Add TenantMiddleware to src/interfaces/api/app.py BEFORE routers.
Add CORSMiddleware with origins from settings.

IMPORTANT: Every protected router endpoint should accept:
  tenant: Tenant = Depends(get_current_tenant)
and pass tenant.id to all service/repository calls for isolation.
```
</details>

---

### 1.3 [Dev-3] Auth: Embed tenant_id in JWT + Tenant Assignment
- [ ] ⚠️ **ЧАСТИЧНО** — JWT содержит `tenant_id` ✅, `refresh()` переносит его ✅, поле `tenant_id` в `UserRequest` ✅ | но `tenant_service.py` ❌, эндпоинт `POST /auth/tenant` ❌, импорт из `schemas.tenant` не дописан ❌ | **Demonstrates: Multi-tenancy, Security** | ⏱ 2h

<details>
<summary>📎 Copilot Prompt</summary>

```
Read src/application/services/auth_service.py fully.

1. In AuthService.login() → after authenticating user, look up the user's tenant:
   query: SELECT * FROM tenants WHERE owner_id = user.id LIMIT 1
   If tenant exists, add "tenant_id": str(tenant.id) to the JWT payload dict.
   If no tenant yet (new user has no tenant), set "tenant_id": None.

2. In AuthService.get_current_user() → extract tenant_id from payload and include it
   in the returned UserRequest schema. Add Optional[UUID] tenant_id field to UserRequest
   in src/infrastructure/schemas/users.py.

3. In AuthService.refresh() → carry tenant_id forward into the new access token payload.

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
</details>

---

### 1.4 [Dev-2] Tenant-Scoped BaseRepository
- [x] ✅ **СДЕЛАНО** — `TenantScopedRepository` ✅, `VMRepository` ✅, `NetworkRepository` ✅, `QuotaRepository` ✅, `TenantRepository` ✅, `AuditLogRepository` ✅ | **Demonstrates: Row-Level Isolation** | ⏱ 2h

<details>
<summary>📎 Copilot Prompt</summary>

```
Read src/infrastructure/repositories/base.py fully.

Create src/infrastructure/repositories/tenant_scoped.py:
  class TenantScopedRepository(BaseRepository):
    """
    All queries automatically filter by tenant_id.
    Subclasses must set: table (SQLAlchemy model with tenant_id column).
    """
    async def get(self, *args, tenant_id: UUID) -> Any | None:
        query = sa.select(self.table).where(self.table.tenant_id == tenant_id, *args)
        result = await self._session.execute(query)
        return result.scalar_one_or_none()

    async def get_all(self, tenant_id: UUID, limit: int, offset: int,
                      ordering=None, *args) -> Sequence[Any]:
        query = (sa.select(self.table)
                   .where(self.table.tenant_id == tenant_id, *args)
                   .offset(offset).limit(limit).order_by(ordering))
        result = await self._session.execute(query)
        return result.scalars().all()

    async def count(self, tenant_id: UUID, *args) -> int:
        query = sa.select(sa.func.count()).select_from(self.table).where(
            self.table.tenant_id == tenant_id, *args)
        result = await self._session.execute(query)
        return result.scalar_one()

    async def create(self, tenant_id: UUID, **kwargs) -> Any:
        query = sa.insert(self.table).values(tenant_id=tenant_id, **kwargs).returning(self.table)
        result = await self._session.execute(query)
        await self._session.flush()
        return result.scalar_one()

    async def update(self, *args, tenant_id: UUID, **kwargs) -> Any | None:
        query = (sa.update(self.table)
                   .where(self.table.tenant_id == tenant_id, *args)
                   .values(**kwargs).returning(self.table))
        result = await self._session.execute(query)
        await self._session.flush()
        return result.scalar_one_or_none()

    async def delete(self, *args, tenant_id: UUID) -> Any | None:
        query = (sa.delete(self.table)
                   .where(self.table.tenant_id == tenant_id, *args)
                   .returning(self.table))
        result = await self._session.execute(query)
        await self._session.flush()
        return result.scalar_one_or_none()

Create src/infrastructure/repositories/vm_repository.py:
  class VMRepository(TenantScopedRepository):
    table = VirtualMachine
    async def get_by_status(self, tenant_id: UUID, status: VMStatus) → List[VirtualMachine]
    async def update_status(self, vm_id: UUID, tenant_id: UUID, status: VMStatus, container_id: str = None) → VirtualMachine
    async def count_active(self, tenant_id: UUID) → int  ← counts RUNNING + PENDING

Create src/infrastructure/repositories/network_repository.py:
  class NetworkRepository(TenantScopedRepository):
    table = VirtualNetwork

Create src/infrastructure/repositories/quota_repository.py:
  class QuotaRepository(BaseRepository):
    table = ResourceQuota
    async def get_by_tenant(self, tenant_id: UUID) → ResourceQuota

Create src/infrastructure/repositories/usage_repository.py:
  class UsageRepository(BaseRepository):
    table = ResourceUsage
    async def get_by_tenant(self, tenant_id: UUID) → ResourceUsage
    async def increment(self, tenant_id: UUID, vcpu: int, ram_mb: int, disk_gb: int) → None:
        (atomic UPDATE: used_vcpu += vcpu, used_ram_mb += ram_mb, used_disk_gb += disk_gb, used_vms += 1)
    async def decrement(self, tenant_id: UUID, vcpu: int, ram_mb: int, disk_gb: int) → None:
        (atomic UPDATE with max(0, used_x - x) to prevent negative values)
```
</details>

---

### 1.5 [Dev-4] Hypervisor Service (Docker SDK Mock)
- [ ] ❌ **НЕ СДЕЛАНО** — `hypervisor_service.py` не существует | **Demonstrates: Hypervisor Simulation** | ⏱ 3h

<details>
<summary>📎 Copilot Prompt</summary>

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
</details>

---

### 1.6 [Dev-5] docker-compose + .env.example + Makefile
- [ ] ⚠️ **ЧАСТИЧНО** — `docker-compose.yaml` есть ✅, `.env.example` есть но значения пустые ⚠️ | Docker socket не смонтирован ❌, `celery-beat` сервис отсутствует ❌, `Makefile` не создан ❌ | **Demonstrates: DevOps** | ⏱ 1h

<details>
<summary>📎 Copilot Prompt</summary>

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
</details>

---

## DAY 2 — VM Lifecycle, Quota Engine & Networking

### 2.1 [Dev-4] Quota Service (enforce + track)
- [ ] ❌ **НЕ СДЕЛАНО** — `quota_service.py` не существует | **Demonstrates: Resource Distribution Control** | ⏱ 2h

<details>
<summary>📎 Copilot Prompt</summary>

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
</details>

---

### 2.2 [Dev-4] VM Service + Full Lifecycle
- [ ] ❌ **НЕ СДЕЛАНО** — `vm_service.py` стаб ❌, `schemas/vm.py` стаб ❌ | **Demonstrates: Hypervisor, Multi-tenancy, Resource Control** | ⏱ 3h

<details>
<summary>📎 Copilot Prompt</summary>

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
</details>

---

### 2.3 [Dev-1] VM Router (full REST + lifecycle actions)
- [ ] ❌ **НЕ СДЕЛАНО** — `routers/vms.py` стаб | **Demonstrates: Multi-tenancy, Hypervisor** | ⏱ 2h

<details>
<summary>📎 Copilot Prompt</summary>

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
</details>

---

### 2.4 [Dev-2] Network Service + Router (VPC/Subnet)
- [ ] ❌ **НЕ СДЕЛАНО** — `network_service.py` стаб ❌, `schemas/network.py` стаб ❌, `routers/networks.py` стаб ❌ | `NetworkRepository` ✅ (единственное что готово) | **Demonstrates: Multi-tenancy, Networking** | ⏱ 2h

<details>
<summary>📎 Copilot Prompt</summary>

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
</details>

---

### 2.5 [Dev-3] Admin Router (Tenant + Quota management)
- [ ] ❌ **НЕ СДЕЛАНО** — `routers/admin.py` стаб ❌, `dependencies/permissions.py` ❌, `schemas/tenant.py` стаб ❌, `schemas/quota.py` стаб ❌ | **Demonstrates: Resource Distribution Control, Multi-tenancy** | ⏱ 2h

<details>
<summary>📎 Copilot Prompt</summary>

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
</details>

---

### 2.6 [Dev-5] Celery Tasks: VM Status Sync
- [ ] ❌ **НЕ СДЕЛАНО** — в `tasks.py` только `send_confirmation_email` ❌, `beat_schedule` в `celery_config.py` отсутствует ❌ | **Demonstrates: Hypervisor, Background Tasks** | ⏱ 1h

<details>
<summary>📎 Copilot Prompt</summary>

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
</details>

---

## DAY 3 — Monitoring, Security & Production

### 3.1 [Dev-1] Resource Usage Dashboard Endpoints
- [ ] ❌ **НЕ СДЕЛАНО** — `routers/dashboard.py` ❌, `audit_service.py` ❌ | `AuditLog` модель ✅ + `AuditLogRepository` ✅ (единственное что готово) | **Demonstrates: Resource Control, Monitoring** | ⏱ 2h

<details>
<summary>📎 Copilot Prompt</summary>

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

Add a minimal AuditLog model and repository:
  FILE: src/infrastructure/models/audit_log.py
  class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: UUID PK
    tenant_id: UUID FK → tenants.id, index=True
    user_id: UUID FK → users.id
    action: String(100)  ← e.g. "vm.create", "vm.stop", "network.create"
    resource_type: String(50)  ← "vm" | "network" | "quota"
    resource_id: UUID, nullable=True
    details: JSON, nullable=True
    created_at: DateTime, server_default=func.now()

Create src/application/services/audit_service.py:
  class AuditService:
    async def log(self, tenant_id, user_id, action, resource_type, resource_id=None, details=None)

Call audit_service.log() in vm_service.create(), start(), stop(), terminate() and network_service.create(), delete().
Include dashboard_router in app.py.
```
</details>

---

### 3.2 [Dev-3] Security: Rate Limiting + Security Headers
- [ ] ❌ **НЕ СДЕЛАНО** — папка `middleware/` не создана, ни один middleware не реализован | **Demonstrates: Security** | ⏱ 2h

<details>
<summary>📎 Copilot Prompt</summary>

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
  4. TenantMiddleware (already added Day 1)
  5. CORSMiddleware

Add global exception handlers for:
  QuotaExceededError → 429 {"detail": "...", "resource": "...", "available": N}
  UserNotFound → 404
  UserPermissionDenied → 403
  UserAlreadyExistsError → 409
  HTTPException → passthrough
  Exception → 500 (log traceback, return generic message)
```
</details>

---

### 3.3 [Dev-2] Alembic Migrations for all new models
- [ ] ❌ **НЕ СДЕЛАНО** — существует только init-миграция (`users` таблица), миграция для Tenant/VM/Network/Quota/Usage/AuditLog не создана | **Demonstrates: DevOps** | ⏱ 1h

<details>
<summary>📎 Copilot Prompt</summary>

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
</details>

---

### 3.4 [Dev-4] Integration Tests: Full Tenant Isolation Scenario
- [ ] ❌ **НЕ СДЕЛАНО** — папка `tests/` не создана | **Demonstrates: Multi-tenancy, Security** | ⏱ 3h

<details>
<summary>📎 Copilot Prompt</summary>

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
</details>

---

### 3.5 [Dev-5] GitHub Actions CI + Final OpenAPI Docs
- [ ] ❌ **НЕ СДЕЛАНО** — `.github/workflows/ci.yml` не создан, OpenAPI не настроен | **Demonstrates: DevOps** | ⏱ 2h

<details>
<summary>📎 Copilot Prompt</summary>

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
</details>

---

## API Endpoints Reference

| Method | Path | Auth | Tenant Scoped | Description |
|--------|------|------|--------------|-------------|
| POST | `/auth/register` | ❌ | ❌ | Register user |
| POST | `/auth/token` | ❌ | ❌ | Login → JWT |
| POST | `/auth/refresh` | ❌ | ❌ | Refresh tokens |
| GET | `/auth/me` | ✅ | ❌ | Current user |
| POST | `/auth/tenant` | ✅ | ❌ | Create tenant for user |
| GET | `/vms` | ✅ | ✅ | List tenant VMs |
| POST | `/vms` | ✅ | ✅ | Create VM (quota check) |
| GET | `/vms/{id}` | ✅ | ✅ | VM detail |
| POST | `/vms/{id}/start` | ✅ | ✅ | Start VM |
| POST | `/vms/{id}/stop` | ✅ | ✅ | Stop VM |
| DELETE | `/vms/{id}` | ✅ | ✅ | Terminate VM |
| GET | `/networks` | ✅ | ✅ | List tenant networks |
| POST | `/networks` | ✅ | ✅ | Create VPC |
| POST | `/networks/{id}/attach-vm` | ✅ | ✅ | Attach VM to network |
| GET | `/dashboard/usage` | ✅ | ✅ | Resource usage % |
| GET | `/dashboard/vms/summary` | ✅ | ✅ | VM status counts |
| GET | `/dashboard/activity` | ✅ | ✅ | Audit log |
| GET | `/admin/tenants` | 🔒 Admin | ❌ | All tenants |
| PATCH | `/admin/tenants/{id}/quota` | 🔒 Admin | ❌ | Set quotas |
| GET | `/admin/stats` | 🔒 Admin | ❌ | Global stats |
| GET | `/admin/vms` | 🔒 Admin | ❌ | All VMs all tenants |
| GET | `/health` | ❌ | ❌ | Health check |
