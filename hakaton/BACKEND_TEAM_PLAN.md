# 🖥️ BACKEND — Разделение задач на 3 разработчика

> Стек: Python FastAPI + SQLAlchemy 2.0 async + PostgreSQL + Alembic + Docker SDK  
> Каждый пункт = готовый промт для GitHub Copilot Chat  
> Каждый разработчик работает в своей ветке и делает PR в `develop`

---

## 🌿 Git-стратегия

```
main
└── develop
    ├── feature/be1-foundation        ← Dev 1
    ├── feature/be2-vm-hypervisor     ← Dev 2
    └── feature/be3-admin-audit       ← Dev 3
```

**Порядок мержей:**
1. Dev 1 мержит первым (foundation) — остальные делают `git rebase develop` после этого
2. Dev 2 и Dev 3 могут работать параллельно с Dev 1 на заглушках, мержат после Dev 1
3. Итоговый мерж `develop → main` делает тимлид после прохождения всех тестов

---

## ⚡ ОБЩИЙ СТАРТ (выполняет Dev 1 — один раз, остальные клонируют)

```bash
# Dev 1 инициализирует репо и структуру
git init cloudiaas && cd cloudiaas
git checkout -b develop
mkdir -p backend/app/{models,schemas,routers,services,middleware,hypervisor,utils}
mkdir -p backend/{migrations,tests}
touch backend/app/__init__.py
# ... создаёт структуру, делает первый коммит
git push origin develop
# Dev 2, Dev 3 делают:
git clone <repo> && cd cloudiaas && git checkout develop
```

---

---

# 👤 DEV 1 — Foundation: Scaffold + DB + Auth + Config

> **Ветка:** `feature/be1-foundation`  
> **Зона ответственности:** всё, от чего зависят Dev 2 и Dev 3  
> **Приоритет:** сделать первым и смержить как можно раньше

---

### ✅ День 1 — Утро

#### 1.1 Инициализация проекта и requirements.txt
```
Create backend/requirements.txt with all dependencies for the CloudIaaS FastAPI project:
fastapi==0.111.0, uvicorn[standard]==0.29.0, sqlalchemy[asyncio]==2.0.30,
asyncpg==0.29.0, alembic==1.13.1, pydantic-settings==2.2.1,
passlib[bcrypt]==1.7.4, python-jose[cryptography]==3.3.0,
docker==7.0.0, httpx==0.27.0, pytest-asyncio==0.23.6, pytest==8.2.0.
Then create backend/.gitignore ignoring: __pycache__, .env, *.pyc, .pytest_cache
```

#### 1.2 Config (pydantic-settings)
```
Create backend/app/config.py using pydantic-settings BaseSettings.
Fields: DATABASE_URL (str), SECRET_KEY (str), ACCESS_TOKEN_EXPIRE_MINUTES (int=15),
REFRESH_TOKEN_EXPIRE_DAYS (int=7), DOCKER_HOST (str="unix:///var/run/docker.sock"),
FIRST_ADMIN_EMAIL (str), FIRST_ADMIN_PASSWORD (str), ALLOWED_ORIGINS (list[str]=["*"]).
Load from .env file. Export singleton: settings = Settings()
File: backend/app/config.py
```

#### 1.3 Database (async SQLAlchemy)
```
Create backend/app/database.py with:
- async engine: create_async_engine(settings.DATABASE_URL, echo=True)
- AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)
- Base = DeclarativeBase()
- async def get_db() -> AsyncGenerator[AsyncSession, None]: yield session
File: backend/app/database.py
```

#### 1.4 Все ORM модели
```
Create the following SQLAlchemy 2.0 ORM model files using mapped_column syntax.
All primary keys are UUID with server_default=text("gen_random_uuid()").
All models import Base from app.database.

File backend/app/models/tenant.py:
class Tenant: id, name (str unique), slug (str unique), 
status (str default="active"), created_at, max_vms (int=10), max_networks (int=5)

File backend/app/models/user.py:
class User: id, tenant_id (ForeignKey Tenant nullable), email (str unique),
hashed_password (str), role (str: admin/tenant_owner/tenant_user),
is_active (bool=True), created_at

File backend/app/models/virtual_machine.py:
class VirtualMachine: id, tenant_id (FK Tenant NOT NULL), name (str),
status (str default="creating"), cpu_cores (int), ram_mb (int), disk_gb (int),
docker_container_id (str nullable), ip_address (str nullable),
created_at, updated_at (onupdate=datetime.utcnow)

File backend/app/models/network.py:
class Network: id, tenant_id (FK Tenant NOT NULL), name (str), cidr (str),
is_active (bool=True), created_at

File backend/app/models/resource_quota.py:
class ResourceQuota: id, tenant_id (FK Tenant UNIQUE NOT NULL),
max_cpu_cores (int=8), max_ram_mb (int=8192), max_disk_gb (int=100),
max_vms (int=5), max_networks (int=5),
used_cpu_cores (int=0), used_ram_mb (int=0), used_disk_gb (int=0), used_vms (int=0)

File backend/app/models/audit_log.py:
class AuditLog: id, tenant_id (FK nullable), user_id (FK nullable),
action (str), resource_type (str), resource_id (str nullable),
detail (JSON nullable), created_at

File backend/app/models/__init__.py:
Export all models: from .tenant import Tenant, from .user import User, etc.
```

#### 1.5 Alembic + первая миграция
```
Initialize Alembic: alembic init backend/migrations
Configure backend/migrations/env.py:
- Import settings from app.config
- Set config.set_main_option("sqlalchemy.url", settings.DATABASE_URL.replace("+asyncpg", ""))
- Import Base from app.database and all models from app.models
- Use run_migrations_online() with async engine pattern

Generate migration: alembic revision --autogenerate -m "initial_schema"
Verify it creates all 6 tables: tenants, users, virtual_machines, networks, resource_quotas, audit_logs
File: backend/alembic.ini, backend/migrations/env.py
```

---

### ✅ День 1 — Вторая половина

#### 1.6 JWT утилиты
```
Create backend/app/utils/jwt.py with functions:
- create_access_token(data: dict) → str
  Use python-jose jwt.encode, algorithm HS256, exp = now + ACCESS_TOKEN_EXPIRE_MINUTES
- create_refresh_token(data: dict) → str  
  exp = now + REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 minutes
- decode_token(token: str) → dict
  Use jwt.decode, raise HTTPException(401) on JWTError or ExpiredSignatureError
JWT payload must include: sub (user_id str), tenant_id (str|None), role (str), exp
File: backend/app/utils/jwt.py
```

#### 1.7 Pydantic Schemas — Auth + User + Tenant
```
Create Pydantic v2 schemas with model_config = ConfigDict(from_attributes=True):

File backend/app/schemas/auth.py:
- RegisterRequest: name(str), email(EmailStr), password(str min=8), company_name(str)
- LoginRequest: email(EmailStr), password(str)
- TokenResponse: access_token(str), refresh_token(str), token_type(str="bearer")
- RefreshRequest: refresh_token(str)

File backend/app/schemas/tenant.py:
- TenantResponse: id(UUID), name, slug, status, created_at, max_vms, max_networks
- TenantCreate: name(str), email(EmailStr), password(str), max_vms(int=5)

File backend/app/schemas/user.py:
- UserResponse: id(UUID), email, role, tenant_id(UUID|None), is_active, created_at
```

#### 1.8 Auth Middleware Dependencies
```
Create backend/app/middleware/auth.py with FastAPI dependency functions:

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
    payload = decode_token(token)
    user = await db.get(User, UUID(payload["sub"]))
    if not user or not user.is_active: raise HTTPException(401)
    return user

async def get_tenant_context(current_user: User = Depends(get_current_user)) -> UUID:
    if not current_user.tenant_id: raise HTTPException(403, "No tenant")
    return current_user.tenant_id

async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin": raise HTTPException(403, "Admin only")
    return current_user

File: backend/app/middleware/auth.py
```

#### 1.9 Auth Router
```
Create backend/app/routers/auth.py with APIRouter(prefix="/auth", tags=["auth"]):

POST /register:
- Validate RegisterRequest
- Check email not already taken (raise 409 if exists)
- Create Tenant(name=company_name, slug=slugify(company_name))
- Create User(email, hashed_password=bcrypt(password), role="tenant_owner", tenant_id=tenant.id)
- Create ResourceQuota(tenant_id=tenant.id) with defaults
- Commit, return TokenResponse with create_access_token + create_refresh_token

POST /login:
- Find User by email, verify bcrypt password (raise 401 if wrong)
- Check user.is_active (raise 403 if suspended)
- Return TokenResponse

POST /refresh:
- Decode refresh token, get user, return new access_token

POST /logout:
- Return {"message": "logged out"} (stateless)

File: backend/app/routers/auth.py
```

#### 1.10 Seed script
```
Create backend/app/seed.py as async main() function:
1. Check if User with FIRST_ADMIN_EMAIL exists → skip if yes (idempotent)
2. Create User: email=settings.FIRST_ADMIN_EMAIL, role="admin", tenant_id=None,
   hashed_password=bcrypt(settings.FIRST_ADMIN_PASSWORD), is_active=True
3. Create Tenant: name="Demo Corp", slug="demo", status="active"
4. Create User: email="demo@cloud.local", password="demo1234", role="tenant_owner"
5. Create ResourceQuota for demo tenant: max_vms=5, max_cpu_cores=8, max_ram_mb=8192
6. Print "Seed completed" or "Seed skipped (already exists)"

File: backend/app/seed.py
Run with: python -m app.seed
```

#### 1.11 Main app factory
```
Create backend/app/main.py:
- app = FastAPI(title="CloudIaaS API", version="1.0.0", docs_url="/api/docs")
- Add CORSMiddleware with allow_origins=settings.ALLOWED_ORIGINS, allow_methods=["*"], allow_headers=["*"]
- Include routers (add stubs for missing ones using APIRouter with placeholder 501 responses):
  app.include_router(auth_router, prefix="/api/v1/auth")
  app.include_router(vms_router, prefix="/api/v1/vms")      # stub OK
  app.include_router(networks_router, prefix="/api/v1/networks")  # stub OK
  app.include_router(quotas_router, prefix="/api/v1/quotas")      # stub OK
  app.include_router(admin_router, prefix="/api/v1/admin")        # stub OK
- @app.on_event("startup"): run alembic upgrade head, then await seed()
- @app.get("/health"): return {"status": "ok"}
File: backend/app/main.py
```

#### 1.12 Auth тесты
```
Create backend/tests/conftest.py with pytest-asyncio fixtures:
- event_loop fixture
- async_client fixture using httpx.AsyncClient with app

Create backend/tests/test_auth.py:
- test_register_success(): POST /api/v1/auth/register → 201, check access_token in response
- test_register_duplicate_email(): register twice → 409
- test_login_success(): register then login → 200, tokens returned
- test_login_wrong_password(): → 401
- test_refresh_token(): login → use refresh_token → get new access_token → 200

File: backend/tests/test_auth.py, backend/tests/conftest.py
```

> **После:** `git add . && git commit -m "feat: foundation - db, models, auth" && git push`  
> **Затем:** создать PR `feature/be1-foundation → develop` и смержить  
> **Dev 2 и Dev 3:** `git rebase develop` на своих ветках

---

---

# 👤 DEV 2 — VM Service + Mock Hypervisor + Quota Logic

> **Ветка:** `feature/be2-vm-hypervisor`  
> **Зона ответственности:** жизненный цикл виртуальных машин, Docker-мок, квоты  
> **Зависимость:** нужны модели от Dev 1. Пока Dev 1 не смержил — работай на заглушках моделей

---

### ✅ День 1 — Параллельно с Dev 1 (заглушки)

#### 2.1 Stub-модели для локальной работы
```
Until Dev 1 merges, create temporary stub files so Dev 2 can work independently:
Create backend/app/models/_stubs.py with simple dataclass stubs:
@dataclass class VirtualMachine: id, tenant_id, name, status, cpu_cores, ram_mb, disk_gb, docker_container_id
@dataclass class ResourceQuota: max_vms, max_cpu_cores, max_ram_mb, used_vms, used_cpu_cores, used_ram_mb
These stubs will be replaced when Dev 1 merges real ORM models.
Note: delete this file after rebasing on develop with Dev 1's work.
File: backend/app/models/_stubs.py (temporary, add to .gitignore pattern or delete before PR)
```

#### 2.2 VM Pydantic Schemas
```
Create backend/app/schemas/vm.py with Pydantic v2 schemas:
- VMCreate: name(str min=1 max=64), cpu_cores(int ge=1 le=16), 
  ram_mb(int ge=512 le=32768), disk_gb(int ge=10 le=1000)
- VMResponse: id(UUID), tenant_id(UUID), name, status, cpu_cores, ram_mb, disk_gb,
  docker_container_id(str|None), ip_address(str|None), created_at, updated_at
  model_config = ConfigDict(from_attributes=True)
- VMListResponse: items(list[VMResponse]), total(int)
File: backend/app/schemas/vm.py
```

#### 2.3 Mock Hypervisor Client
```
Create backend/app/hypervisor/docker_client.py with class MockHypervisor.
Use Docker SDK: import docker. Wrap all blocking calls with asyncio.get_event_loop().run_in_executor(None, ...).

Implement:
async def create_vm(self, vm_id: str, cpu_cores: int, ram_mb: int) -> str:
  container = client.containers.run(
    "alpine:latest", command="sleep infinity", detach=True,
    name=f"cloudiaas-vm-{vm_id}",
    cpu_period=100000, cpu_quota=cpu_cores * 100000,
    mem_limit=f"{ram_mb}m", labels={"cloudiaas": "true", "vm_id": vm_id}
  )
  return container.id

async def start_vm(self, container_id: str) -> None:
  client.containers.get(container_id).start()

async def stop_vm(self, container_id: str) -> None:
  client.containers.get(container_id).stop()

async def delete_vm(self, container_id: str) -> None:
  container = client.containers.get(container_id)
  container.stop(timeout=2); container.remove()

async def get_status(self, container_id: str) -> str:
  status_map = {"running": "running", "exited": "stopped", "created": "creating"}
  try:
    status = client.containers.get(container_id).status
    return status_map.get(status, "error")
  except docker.errors.NotFound:
    return "deleted"

Instantiate singleton: hypervisor = MockHypervisor()
File: backend/app/hypervisor/docker_client.py
```

---

### ✅ День 1 — После мержа Dev 1

#### 2.4 Quota Service
```
Create backend/app/services/quota_service.py with class QuotaService:

async def get_quota(db: AsyncSession, tenant_id: UUID) -> ResourceQuota:
  result = await db.execute(select(ResourceQuota).where(ResourceQuota.tenant_id == tenant_id))
  quota = result.scalar_one_or_none()
  if not quota: raise HTTPException(404, "Quota not found")
  return quota

async def check_vm_quota(db: AsyncSession, tenant_id: UUID, vm: VMCreate) -> None:
  quota = await get_quota(db, tenant_id)
  if quota.used_vms >= quota.max_vms: raise HTTPException(422, "VM quota exceeded")
  if quota.used_cpu_cores + vm.cpu_cores > quota.max_cpu_cores: raise HTTPException(422, "CPU quota exceeded")
  if quota.used_ram_mb + vm.ram_mb > quota.max_ram_mb: raise HTTPException(422, "RAM quota exceeded")

async def consume_vm_quota(db: AsyncSession, tenant_id: UUID, vm: VirtualMachine) -> None:
  quota = await get_quota(db, tenant_id)
  quota.used_vms += 1; quota.used_cpu_cores += vm.cpu_cores; quota.used_ram_mb += vm.ram_mb
  await db.commit()

async def release_vm_quota(db: AsyncSession, tenant_id: UUID, vm: VirtualMachine) -> None:
  quota = await get_quota(db, tenant_id)
  quota.used_vms = max(0, quota.used_vms - 1)
  quota.used_cpu_cores = max(0, quota.used_cpu_cores - vm.cpu_cores)
  quota.used_ram_mb = max(0, quota.used_ram_mb - vm.ram_mb)
  await db.commit()

File: backend/app/services/quota_service.py
```

#### 2.5 VM Service
```
Create backend/app/services/vm_service.py with class VMService.
All methods take (db: AsyncSession, tenant_id: UUID).
Always filter queries by tenant_id — never trust VM lookup without this check.

async def list_vms(db, tenant_id) -> list[VirtualMachine]:
  result = await db.execute(select(VirtualMachine).where(VirtualMachine.tenant_id == tenant_id))
  return result.scalars().all()

async def get_vm(db, tenant_id, vm_id: UUID) -> VirtualMachine:
  vm = await db.get(VirtualMachine, vm_id)
  if not vm or vm.tenant_id != tenant_id: raise HTTPException(404, "VM not found")
  return vm

async def create_vm(db, tenant_id, data: VMCreate, user_id: UUID) -> VirtualMachine:
  await QuotaService.check_vm_quota(db, tenant_id, data)
  vm = VirtualMachine(**data.model_dump(), tenant_id=tenant_id, status="creating")
  db.add(vm); await db.flush()
  container_id = await hypervisor.create_vm(str(vm.id), vm.cpu_cores, vm.ram_mb)
  vm.docker_container_id = container_id; vm.status = "running"
  db.add(AuditLog(tenant_id=tenant_id, user_id=user_id, action="vm.create",
    resource_type="vm", resource_id=str(vm.id), detail={"name": vm.name}))
  await db.commit(); await db.refresh(vm)
  await QuotaService.consume_vm_quota(db, tenant_id, vm)
  return vm

async def start_vm(db, tenant_id, vm_id, user_id) -> VirtualMachine:
  vm = await get_vm(db, tenant_id, vm_id)
  if vm.status == "running": raise HTTPException(400, "Already running")
  await hypervisor.start_vm(vm.docker_container_id)
  vm.status = "running"; await db.commit(); await db.refresh(vm)
  return vm

async def stop_vm(db, tenant_id, vm_id, user_id) -> VirtualMachine:
  vm = await get_vm(db, tenant_id, vm_id)
  await hypervisor.stop_vm(vm.docker_container_id)
  vm.status = "stopped"; await db.commit(); await db.refresh(vm)
  return vm

async def delete_vm(db, tenant_id, vm_id, user_id) -> None:
  vm = await get_vm(db, tenant_id, vm_id)
  if vm.docker_container_id:
    await hypervisor.delete_vm(vm.docker_container_id)
  await QuotaService.release_vm_quota(db, tenant_id, vm)
  await db.delete(vm); await db.commit()

File: backend/app/services/vm_service.py
```

#### 2.6 VM Router
```
Create backend/app/routers/vms.py with APIRouter(prefix="", tags=["vms"]):
All routes use: current_user=Depends(get_current_user), db=Depends(get_db)
Extract tenant_id = current_user.tenant_id (raise 403 if None)

GET /           → list_vms(db, tenant_id) → VMListResponse
POST /          → create_vm(db, tenant_id, body, user_id) → VMResponse, status_code=201
GET /{vm_id}    → get_vm(db, tenant_id, vm_id) → VMResponse
POST /{vm_id}/start  → start_vm → VMResponse
POST /{vm_id}/stop   → stop_vm → VMResponse
DELETE /{vm_id}      → delete_vm → Response(status_code=204)

File: backend/app/routers/vms.py
```

#### 2.7 Quota Router
```
Create backend/app/routers/quotas.py with APIRouter(prefix="", tags=["quotas"]):

GET /me:
  quota = await QuotaService.get_quota(db, current_user.tenant_id)
  Return QuotaResponse including calculated usage percentages:
  vm_percent = round(quota.used_vms / quota.max_vms * 100, 1)
  cpu_percent, ram_percent similarly

Schema: QuotaResponse in backend/app/schemas/quota.py with all fields + percentages
File: backend/app/routers/quotas.py, backend/app/schemas/quota.py
```

#### 2.8 VM тесты
```
Create backend/tests/test_vms.py using pytest-asyncio + httpx AsyncClient:

test_create_vm_success(): register → login → POST /api/v1/vms → 201, status="running"
test_create_vm_updates_quota(): create VM → GET /api/v1/quotas/me → used_vms == 1
test_get_vm_not_found(): GET /api/v1/vms/<random_uuid> → 404
test_cannot_access_other_tenant_vm():
  register tenant A, create VM, get vm_id
  register tenant B, try GET /api/v1/vms/{vm_id} → 404 (isolation check)
test_vm_quota_exceeded():
  Create ResourceQuota with max_vms=1, create 1 VM, try create 2nd → 422
test_stop_running_vm(): create → stop → status=="stopped"
test_delete_vm_removes_from_list(): create → delete → GET / → empty list

Use unittest.mock to patch hypervisor.create_vm, start_vm, stop_vm, delete_vm
(so tests don't require real Docker)
File: backend/tests/test_vms.py
```

> **После:** `git add . && git commit -m "feat: vm service, hypervisor mock, quota logic" && git push`

---

---

# 👤 DEV 3 — Networks + Admin Panel + AuditLog + DevOps

> **Ветка:** `feature/be3-admin-audit`  
> **Зона ответственности:** сетевой слой, весь admin API, audit log, Docker Compose  
> **Зависимость:** нужны модели от Dev 1. Аналогично — работай на заглушках до мержа

---

### ✅ День 1 — Параллельно с Dev 1

#### 3.1 Network + Admin Pydantic Schemas
```
Create backend/app/schemas/network.py:
- NetworkCreate: name(str), cidr(str — validate as CIDR with regex r'^\d+\.\d+\.\d+\.\d+/\d+$')
- NetworkResponse: id(UUID), tenant_id(UUID), name, cidr, is_active, created_at
  ConfigDict(from_attributes=True)

Create backend/app/schemas/admin.py:
- TenantAdminResponse: id, name, slug, status, created_at, vm_count(int), quota(QuotaResponse|None)
- QuotaUpdateRequest: max_vms(int|None), max_cpu_cores(int|None), max_ram_mb(int|None), max_disk_gb(int|None)
- TenantStatusUpdate: status(Literal["active","suspended"])
- PlatformStats: total_tenants(int), total_vms(int), running_vms(int), suspended_tenants(int)
- AuditLogResponse: id, tenant_id, user_id, action, resource_type, resource_id, detail, created_at
- PaginatedAuditLog: items(list[AuditLogResponse]), total(int), page(int), size(int)

File: backend/app/schemas/network.py, backend/app/schemas/admin.py
```

#### 3.2 Dockerfile и docker-compose
```
Create backend/Dockerfile:
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

Create infra/docker-compose.yml with services:
  postgres:
    image: postgres:15-alpine
    environment: POSTGRES_DB=cloudiaas, POSTGRES_USER=cloudiaas, POSTGRES_PASSWORD=cloudiaas
    volumes: postgres_data:/var/lib/postgresql/data
    healthcheck: test: ["CMD", "pg_isready", "-U", "cloudiaas"], interval: 5s, retries: 5
    ports: "5432:5432"

  backend:
    build: ../backend
    ports: "8000:8000"
    depends_on: {postgres: {condition: service_healthy}}
    volumes: /var/run/docker.sock:/var/run/docker.sock
    env_file: ../.env

volumes:
  postgres_data:

File: backend/Dockerfile, infra/docker-compose.yml
```

---

### ✅ День 1 — После мержа Dev 1

#### 3.3 Network Service
```
Create backend/app/services/network_service.py:

async def list_networks(db, tenant_id) -> list[Network]:
  result = await db.execute(select(Network).where(Network.tenant_id == tenant_id))
  return result.scalars().all()

async def create_network(db, tenant_id, data: NetworkCreate, user_id: UUID) -> Network:
  # Check quota: count existing networks
  count = await db.scalar(select(func.count()).where(Network.tenant_id == tenant_id))
  quota = await db.scalar(select(ResourceQuota.max_networks).where(ResourceQuota.tenant_id == tenant_id))
  if count >= (quota or 5): raise HTTPException(422, "Network quota exceeded")
  # Check CIDR uniqueness within tenant
  existing = await db.scalar(select(Network).where(Network.tenant_id == tenant_id, Network.cidr == data.cidr))
  if existing: raise HTTPException(409, "CIDR already in use")
  network = Network(**data.model_dump(), tenant_id=tenant_id)
  db.add(network)
  db.add(AuditLog(tenant_id=tenant_id, user_id=user_id, action="network.create",
    resource_type="network", detail={"cidr": data.cidr}))
  await db.commit(); await db.refresh(network)
  return network

async def delete_network(db, tenant_id, network_id: UUID, user_id: UUID) -> None:
  network = await db.get(Network, network_id)
  if not network or network.tenant_id != tenant_id: raise HTTPException(404)
  db.add(AuditLog(tenant_id=tenant_id, user_id=user_id, action="network.delete",
    resource_type="network", resource_id=str(network_id)))
  await db.delete(network); await db.commit()

File: backend/app/services/network_service.py
```

#### 3.4 Network Router
```
Create backend/app/routers/networks.py with APIRouter(prefix="", tags=["networks"]):

GET /    → list_networks → list[NetworkResponse]
POST /   → create_network → NetworkResponse, status_code=201
DELETE /{network_id} → delete_network → Response(status_code=204)

All routes: current_user=Depends(get_current_user), db=Depends(get_db)
File: backend/app/routers/networks.py
```

#### 3.5 Admin Service
```
Create backend/app/services/admin_service.py:

async def list_tenants(db, page: int = 1, size: int = 20) -> tuple[list, int]:
  offset = (page - 1) * size
  result = await db.execute(select(Tenant).offset(offset).limit(size))
  total = await db.scalar(select(func.count(Tenant.id)))
  tenants = result.scalars().all()
  return tenants, total

async def update_tenant_quota(db, tenant_id: UUID, data: QuotaUpdateRequest) -> ResourceQuota:
  quota = await db.scalar(select(ResourceQuota).where(ResourceQuota.tenant_id == tenant_id))
  if not quota: raise HTTPException(404)
  for field, value in data.model_dump(exclude_none=True).items():
    setattr(quota, field, value)
  await db.commit(); await db.refresh(quota)
  return quota

async def update_tenant_status(db, tenant_id: UUID, data: TenantStatusUpdate) -> Tenant:
  tenant = await db.get(Tenant, tenant_id)
  if not tenant: raise HTTPException(404)
  tenant.status = data.status
  if data.status == "suspended":
    await db.execute(update(User).where(User.tenant_id == tenant_id).values(is_active=False))
  else:
    await db.execute(update(User).where(User.tenant_id == tenant_id).values(is_active=True))
  await db.commit(); await db.refresh(tenant)
  return tenant

async def get_platform_stats(db) -> PlatformStats:
  total_tenants = await db.scalar(select(func.count(Tenant.id)))
  total_vms = await db.scalar(select(func.count(VirtualMachine.id)))
  running_vms = await db.scalar(select(func.count(VirtualMachine.id)).where(VirtualMachine.status == "running"))
  suspended_tenants = await db.scalar(select(func.count(Tenant.id)).where(Tenant.status == "suspended"))
  return PlatformStats(total_tenants=total_tenants, total_vms=total_vms,
    running_vms=running_vms, suspended_tenants=suspended_tenants)

async def list_audit_logs(db, tenant_id=None, action=None, page=1, size=20) -> tuple[list, int]:
  query = select(AuditLog).order_by(AuditLog.created_at.desc())
  if tenant_id: query = query.where(AuditLog.tenant_id == tenant_id)
  if action: query = query.where(AuditLog.action.ilike(f"%{action}%"))
  total = await db.scalar(select(func.count()).select_from(query.subquery()))
  result = await db.execute(query.offset((page-1)*size).limit(size))
  return result.scalars().all(), total

File: backend/app/services/admin_service.py
```

#### 3.6 Admin Router
```
Create backend/app/routers/admin.py with APIRouter(prefix="", tags=["admin"]):
All routes: admin=Depends(require_admin), db=Depends(get_db)

GET /tenants         → list_tenants(db, page, size) → paginated TenantAdminResponse
POST /tenants        → create tenant (call auth logic to register tenant + owner)
PUT /tenants/{id}/quota   → update_tenant_quota → QuotaResponse
PUT /tenants/{id}/status  → update_tenant_status → TenantResponse
GET /audit-logs      → list_audit_logs(db, tenant_id?, action?, page, size) → PaginatedAuditLog
GET /stats           → get_platform_stats → PlatformStats
GET /tenants/{id}    → get single tenant with quota and vm_count

File: backend/app/routers/admin.py
```

#### 3.7 .env.example и полный docker-compose
```
Create .env.example in project root with all required variables:
DATABASE_URL=postgresql+asyncpg://cloudiaas:cloudiaas@postgres:5432/cloudiaas
SECRET_KEY=change_me_use_openssl_rand_hex_32
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7
DOCKER_HOST=unix:///var/run/docker.sock
FIRST_ADMIN_EMAIL=admin@cloud.local
FIRST_ADMIN_PASSWORD=Admin1234!
ALLOWED_ORIGINS=["http://localhost","http://localhost:3000","http://localhost:3001"]

Create .gitignore in project root:
.env, __pycache__, *.pyc, .pytest_cache, node_modules, dist, .DS_Store

Update infra/docker-compose.yml to add nginx service:
  nginx:
    image: nginx:alpine
    ports: ["80:80"]
    volumes: [./nginx/nginx.conf:/etc/nginx/nginx.conf:ro]
    depends_on: [backend]

Create infra/nginx/nginx.conf proxying:
  location /api/ → proxy_pass http://backend:8000/
  location /admin/ → proxy_pass http://frontend-admin:80/ (placeholder)
  location / → proxy_pass http://frontend-customer:80/ (placeholder)

File: .env.example, .gitignore, infra/nginx/nginx.conf
```

#### 3.8 Network + Admin тесты
```
Create backend/tests/test_networks.py:
- test_create_network_success(): register → POST /api/v1/networks → 201
- test_create_duplicate_cidr(): create twice with same CIDR → 409
- test_delete_network(): create → delete → GET / returns empty list
- test_network_quota_exceeded(): set max_networks=1, create 2nd → 422

Create backend/tests/test_admin.py:
- test_list_tenants_requires_admin(): call with tenant token → 403
- test_list_tenants_as_admin(): seed admin → login → GET /api/v1/admin/tenants → 200
- test_update_quota(): update max_vms=20 → verify in response
- test_suspend_tenant(): status="suspended" → tenant user login returns 403
- test_get_stats(): → PlatformStats with correct counts

File: backend/tests/test_networks.py, backend/tests/test_admin.py
```

#### 3.9 E2E Smoke Test
```
Create backend/tests/e2e_smoke.py as standalone script using httpx (sync):
BASE = "http://localhost:8000"

Steps (print PASS/FAIL per step):
1. POST /api/v1/auth/register → expect 201, save token
2. POST /api/v1/networks → create "net-1" 192.168.1.0/24 → expect 201
3. POST /api/v1/vms → create "web-01" 2cpu/1024mb/20gb → expect 201, save vm_id
4. Poll GET /api/v1/vms/{vm_id} every 2s max 30s until status=="running"
5. POST /api/v1/vms/{vm_id}/stop → expect 200, status=="stopped"
6. DELETE /api/v1/vms/{vm_id} → expect 204
7. GET /api/v1/vms/{vm_id} → expect 404
8. Admin login → GET /api/v1/admin/tenants → verify registered tenant in list
9. GET /api/v1/admin/stats → total_vms >= 0

Run: python backend/tests/e2e_smoke.py
File: backend/tests/e2e_smoke.py
```

> **После:** `git add . && git commit -m "feat: networks, admin api, audit, devops" && git push`

---

---

## 🔀 ПОРЯДОК МЕРЖЕЙ В GIT

```
День 1, вечер:
  Dev 1: PR feature/be1-foundation → develop  (ревью от Dev 2 или 3, мерж)
  
  Dev 2: git fetch origin && git rebase origin/develop
         PR feature/be2-vm-hypervisor → develop
  
  Dev 3: git fetch origin && git rebase origin/develop  
         PR feature/be3-admin-audit → develop

День 2, утро:
  develop → main  (финальный мерж тимлидом после smoke test)
```

---

## 📋 ИТОГОВЫЙ ЧЕКЛИСТ БЭКЕНДА

```
Dev 1:
□ alembic upgrade head проходит без ошибок
□ POST /api/v1/auth/register → 201 + токены
□ POST /api/v1/auth/login → 200 + токены
□ GET /health → {"status": "ok"}
□ test_auth.py — все тесты зелёные

Dev 2:
□ POST /api/v1/vms → создаёт Docker контейнер
□ GET /api/v1/vms/{id} → возвращает статус
□ Квота уменьшается после создания VM
□ Изоляция: чужой тенант не видит VM
□ test_vms.py — все тесты зелёные

Dev 3:
□ POST /api/v1/networks → 201
□ GET /api/v1/admin/tenants → требует роль admin
□ GET /api/v1/admin/stats → корректные цифры
□ docker compose up --build → все сервисы healthy
□ test_networks.py + test_admin.py — зелёные
□ e2e_smoke.py — все шаги PASS
```
