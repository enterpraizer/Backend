# 🤖 AI VM Recommendations — Implementation Plan

## Overview

When creating a VM, users can describe their workload in plain text and receive an LLM-powered configuration recommendation (CPU/RAM/Disk) before submitting. After a VM has been running, the system periodically analyzes usage patterns and proactively suggests optimizations. This turns CloudIaaS into an intelligent platform that reduces over-provisioning and under-provisioning.

## Architecture

```
User types description
        │
        ▼
Frontend (VMCreatePage)
  POST /vms/suggest {description}
        │
        ▼
FastAPI (LLMService)
  ├── Few-shot examples from synthetic dataset
  └── Anthropic Claude API (claude-3-haiku)
        │
        ▼
  Returns {vcpu, ram_mb, disk_gb, reasoning}
        │
        ▼
Frontend shows AISuggestionCard
  User: Accept / Customize / Ignore
        │
        ▼
  POST /vms (with chosen config)
  vm_description_log saved to DB

─────────────────────────────────────

Background (Celery Beat, every 5min)
  collect_vm_metrics task
        │
        ▼
  MetricsService.simulate_vm_metrics(vm_id)
  → stores in vm_metrics table
        │
  (every 1h) analyze_and_suggest task
        │
        ▼
  SuggestionService.analyze_and_suggest(vm_id)
  → LLM analyzes 7-day metrics
  → stores in vm_suggestions if confidence > 0.7
        │
        ▼
Frontend (VMDetailPage / Dashboard)
  GET /vms/{id}/suggestions
  Shows dismissible notification cards
```

## New Files & DB Changes

| File Path | Purpose | Depends On |
|---|---|---|
| `src/infrastructure/models/vm_metrics.py` | ORM model for collected metrics | `virtual_machine.py` |
| `src/infrastructure/models/vm_suggestion.py` | ORM model for LLM suggestions | `virtual_machine.py` |
| `src/infrastructure/models/vm_description_log.py` | Logs description + chosen config | `virtual_machine.py` |
| `src/infrastructure/repositories/vm_metrics.py` | CRUD for metrics | `vm_metrics.py` model |
| `src/infrastructure/repositories/vm_suggestion.py` | CRUD for suggestions | `vm_suggestion.py` model |
| `src/application/services/llm_service.py` | Anthropic API integration | `settings` |
| `src/application/services/metrics_service.py` | Simulated metrics collection | `vm_metrics` repo |
| `src/application/services/suggestion_service.py` | LLM-based optimization analysis | `llm_service`, `vm_metrics` repo |
| `src/infrastructure/scripts/generate_synthetic_data.py` | 50+ description→config pairs | — |
| `src/settings/llm.py` | `ANTHROPIC_API_KEY`, `LLM_MODEL` settings | `pydantic-settings` |

## New DB Tables

```sql
CREATE TABLE vm_metrics (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vm_id       UUID NOT NULL REFERENCES virtual_machines(id) ON DELETE CASCADE,
    cpu_pct     FLOAT NOT NULL,   -- 0.0–100.0
    ram_pct     FLOAT NOT NULL,
    disk_pct    FLOAT NOT NULL,
    recorded_at TIMESTAMP NOT NULL DEFAULT now()
);
CREATE INDEX ix_vm_metrics_vm_id ON vm_metrics(vm_id);
CREATE INDEX ix_vm_metrics_recorded_at ON vm_metrics(recorded_at);

CREATE TYPE suggestion_status AS ENUM ('pending', 'accepted', 'dismissed');

CREATE TABLE vm_suggestions (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vm_id            UUID NOT NULL REFERENCES virtual_machines(id) ON DELETE CASCADE,
    tenant_id        UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    suggestion_text  TEXT NOT NULL,
    suggested_config JSONB,         -- {vcpu, ram_mb, disk_gb}
    confidence       FLOAT NOT NULL,
    status           suggestion_status NOT NULL DEFAULT 'pending',
    created_at       TIMESTAMP NOT NULL DEFAULT now()
);
CREATE INDEX ix_vm_suggestions_vm_id ON vm_suggestions(vm_id);
CREATE INDEX ix_vm_suggestions_tenant_id ON vm_suggestions(tenant_id);

CREATE TABLE vm_description_log (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vm_id          UUID REFERENCES virtual_machines(id) ON DELETE SET NULL,
    tenant_id      UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    description    TEXT NOT NULL,
    suggested_config JSONB,
    chosen_config  JSONB NOT NULL,
    created_at     TIMESTAMP NOT NULL DEFAULT now()
);
```

## New API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/vms/suggest` | LLM config recommendation from free-text description |
| `GET` | `/vms/{id}/suggestions` | Get optimization suggestions for a VM |
| `POST` | `/vms/{id}/suggestions/{sid}/accept` | Apply suggestion (triggers resize) |
| `POST` | `/vms/{id}/suggestions/{sid}/dismiss` | Dismiss suggestion |

---

## Implementation Plan (GitHub Copilot Prompts)

---

### DAY 1

---

#### Task 1.1 [BE] — New DB models

```
Read src/infrastructure/models/virtual_machine.py and src/infrastructure/models/audit_log.py
for style reference (UUID PK, timestamps, FK pattern).

Create three new ORM models:

1. src/infrastructure/models/vm_metrics.py
   class VmMetrics(Base):
     __tablename__ = "vm_metrics"
     id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
     vm_id: Mapped[UUID] = mapped_column(ForeignKey("virtual_machines.id", ondelete="CASCADE"), index=True)
     cpu_pct: Mapped[float]
     ram_pct: Mapped[float]
     disk_pct: Mapped[float]
     recorded_at: Mapped[datetime] = mapped_column(server_default=func.now(), index=True)
     vm: Mapped["VirtualMachine"] = relationship(back_populates="metrics")

2. src/infrastructure/models/vm_suggestion.py
   class SuggestionStatus(str, Enum): pending / accepted / dismissed
   class VmSuggestion(Base):
     __tablename__ = "vm_suggestions"
     id, vm_id (FK→virtual_machines), tenant_id (FK→tenants),
     suggestion_text: Mapped[str]
     suggested_config: Mapped[dict] = mapped_column(JSON, nullable=True)
     confidence: Mapped[float]
     status: Mapped[SuggestionStatus] = mapped_column(default=SuggestionStatus.PENDING)
     created_at: Mapped[datetime] = mapped_column(server_default=func.now())

3. src/infrastructure/models/vm_description_log.py
   class VmDescriptionLog(Base):
     __tablename__ = "vm_description_log"
     id, vm_id (nullable FK), tenant_id (FK),
     description: Mapped[str]
     suggested_config: Mapped[dict] = mapped_column(JSON, nullable=True)
     chosen_config: Mapped[dict] = mapped_column(JSON)
     created_at: Mapped[datetime] = mapped_column(server_default=func.now())

Also add back_populates="metrics" and back_populates="suggestions" to VirtualMachine model.
```

---

#### Task 1.2 [BE] — Alembic migration

```
Read alembic/env.py. It currently imports 6 models.

Add imports for the 3 new models:
  from src.infrastructure.models.vm_metrics import VmMetrics
  from src.infrastructure.models.vm_suggestion import VmSuggestion
  from src.infrastructure.models.vm_description_log import VmDescriptionLog

Then run inside the backend container:
  alembic revision --autogenerate -m "add_ai_vm_features"

Review the generated migration and verify:
  - suggestion_status ENUM created before vm_suggestions table
  - All 3 tables created with correct FK constraints
  - Indexes on vm_id and recorded_at for vm_metrics
  - JSON columns use correct type for PostgreSQL
```

---

#### Task 1.3 [BE] — Synthetic data generator

```
Create src/infrastructure/scripts/generate_synthetic_data.py

Generate a Python list of 60 dicts with this structure:
  {"description": str, "vcpu": int, "ram_mb": int, "disk_gb": int}

Cover these workload categories (10 examples each):
  1. Web apps (Django/FastAPI/Rails, various scales)
  2. Databases (PostgreSQL, MySQL, MongoDB, Redis)
  3. ML/AI workloads (PyTorch, training, inference)
  4. CI/CD runners (GitHub Actions, Jenkins)
  5. Game servers (Minecraft, CS:GO-style)
  6. Microservices (small API, message broker)

Examples:
  {"description": "Small WordPress blog, <50 visitors/day", "vcpu": 1, "ram_mb": 512, "disk_gb": 10}
  {"description": "ML training pipeline with PyTorch, ImageNet dataset", "vcpu": 8, "ram_mb": 16384, "disk_gb": 200}
  {"description": "Redis cache cluster for high-traffic e-commerce", "vcpu": 2, "ram_mb": 4096, "disk_gb": 20}

Save the list to SYNTHETIC_DATASET variable.
Add a main() that prints the dataset as JSON.
This data will be used as few-shot examples in LLM prompts.
```

---

#### Task 1.4 [BE] — LLM service

```
Read src/settings/__init__.py and src/application/services/audit_service.py for patterns.

Create src/settings/llm.py:
  class LLMConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LLM_", env_file=".env", extra="ignore")
    anthropic_api_key: str = ""
    model: str = "claude-3-haiku-20240307"
    enabled: bool = True

Add to src/settings/__init__.py:
  from src.settings.llm import LLMConfig
  llm: LLMConfig = LLMConfig()

Create src/application/services/llm_service.py:

  Pick 5 diverse examples from SYNTHETIC_DATASET as few-shot examples.

  class LLMService:
    async def suggest_vm_config(self, description: str) -> dict:
      """
      Calls Anthropic Claude with few-shot examples.
      Returns: {vcpu: int, ram_mb: int, disk_gb: int, reasoning: str, confidence: float}
      Falls back to default config if API unavailable or key not set.
      """
      if not settings.llm.enabled or not settings.llm.anthropic_api_key:
          return self._default_config(description)

      client = anthropic.AsyncAnthropic(api_key=settings.llm.anthropic_api_key)
      system_prompt = build_system_prompt(FEW_SHOT_EXAMPLES)

      response = await client.messages.create(
          model=settings.llm.model,
          max_tokens=300,
          tools=[VM_CONFIG_TOOL],   # tool_use for structured JSON output
          system=system_prompt,
          messages=[{"role": "user", "content": description}]
      )
      return parse_tool_response(response)

  VM_CONFIG_TOOL = {
    "name": "suggest_vm_config",
    "description": "Suggest optimal VM configuration for the described workload",
    "input_schema": {
      "type": "object",
      "properties": {
        "vcpu": {"type": "integer", "minimum": 1, "maximum": 32},
        "ram_mb": {"type": "integer", "minimum": 512, "maximum": 65536},
        "disk_gb": {"type": "integer", "minimum": 10, "maximum": 500},
        "reasoning": {"type": "string"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1}
      },
      "required": ["vcpu", "ram_mb", "disk_gb", "reasoning", "confidence"]
    }
  }

  def _default_config(description: str) -> dict:
    # Return sensible defaults when LLM unavailable
    return {"vcpu": 2, "ram_mb": 2048, "disk_gb": 40, "reasoning": "Default configuration", "confidence": 0.5}

Add anthropic>=0.25.0 to pyproject.toml dependencies.
```

---

#### Task 1.5 [BE] — Suggest endpoint

```
Read src/interfaces/api/routers/vms.py and src/infrastructure/schemas/vm.py.

Add to src/infrastructure/schemas/vm.py:
  class VMSuggestRequest(BaseModel):
    description: str = Field(..., min_length=10, max_length=1000)

  class VMSuggestResponse(BaseModel):
    vcpu: int
    ram_mb: int
    disk_gb: int
    reasoning: str
    confidence: float

Add to src/interfaces/api/routers/vms.py (BEFORE the POST /vms endpoint):

  @vms_router.post(
      "/suggest",
      response_model=VMSuggestResponse,
      summary="Get AI-powered VM configuration recommendation",
  )
  async def suggest_vm_config(
      body: VMSuggestRequest,
      current_user: UserRequest = Depends(AuthService.get_current_user),
      llm: LLMService = Depends(),
  ) -> VMSuggestResponse:
      result = await llm.suggest_vm_config(body.description)
      return VMSuggestResponse(**result)

Important: place this route BEFORE any /{vm_id} routes to avoid path conflicts.
```

---

#### Task 1.6 [BE] — Metrics simulator

```
Read src/application/services/hypervisor_service.py and
src/application/services/tasks.py.

Create src/application/services/metrics_service.py:

  class MetricsService:
    def __init__(self, metrics_repo: VmMetricsRepository = Depends()):
      self._repo = metrics_repo

    async def collect_for_vm(self, vm: VirtualMachine) -> VmMetrics:
      """
      Simulate realistic metrics based on VM status and age.
      Uses random + time-based patterns to mimic real workloads.
      """
      import random, math
      from datetime import timezone

      age_hours = (datetime.now(timezone.utc) - vm.created_at).total_seconds() / 3600

      # Simulate gradual load increase + daily cycle
      base_cpu = random.uniform(5, 80)
      daily_cycle = 10 * math.sin(2 * math.pi * age_hours / 24)
      cpu_pct = max(1.0, min(99.0, base_cpu + daily_cycle + random.uniform(-5, 5)))

      ram_pct = random.uniform(20, 85) + random.uniform(-5, 5)
      disk_pct = min(99.0, 30 + (age_hours * 0.1) + random.uniform(-2, 2))

      return await self._repo.create(
          vm_id=vm.id,
          cpu_pct=round(cpu_pct, 1),
          ram_pct=round(ram_pct, 1),
          disk_pct=round(disk_pct, 1),
      )

Add Celery task to src/application/services/tasks.py:
  @celery_app.task(name="collect_vm_metrics")
  def collect_vm_metrics():
    # Query all RUNNING VMs, call metrics_service.collect_for_vm() for each

Add to celery_config.py beat_schedule:
  "collect-vm-metrics": {"task": "collect_vm_metrics", "schedule": 300.0}  # every 5min
```

---

#### Task 1.7 [BE] — Optimization suggestion engine

```
Read src/application/services/llm_service.py (created in Task 1.4).

Create src/application/services/suggestion_service.py:

  OPTIMIZATION_SYSTEM_PROMPT = """
  You are a cloud infrastructure optimizer. Analyze the VM metrics for the last 7 days
  and suggest ONE optimization if needed. Be specific and actionable.
  Only suggest if confidence > 0.7.
  """

  class SuggestionService:
    def __init__(self,
                 suggestion_repo: VmSuggestionRepository = Depends(),
                 metrics_repo: VmMetricsRepository = Depends(),
                 llm: LLMService = Depends()):
      ...

    async def analyze_and_suggest(self, vm: VirtualMachine) -> VmSuggestion | None:
      metrics = await self._metrics_repo.get_last_7_days(vm.id)
      if len(metrics) < 5:  # not enough data
          return None

      avg_cpu = sum(m.cpu_pct for m in metrics) / len(metrics)
      avg_ram = sum(m.ram_pct for m in metrics) / len(metrics)
      max_disk = max(m.disk_pct for m in metrics)

      prompt = f"""VM: {vm.vcpu} vCPU / {vm.ram_mb}MB RAM / {vm.disk_gb}GB disk
      7-day averages: CPU={avg_cpu:.1f}% RAM={avg_ram:.1f}% Disk max={max_disk:.1f}%
      Suggest an optimization if there is a clear opportunity."""

      result = await self._llm.suggest_optimization(prompt)
      if result["confidence"] < 0.7:
          return None

      return await self._suggestion_repo.create(
          vm_id=vm.id,
          tenant_id=vm.tenant_id,
          suggestion_text=result["text"],
          suggested_config=result.get("config"),
          confidence=result["confidence"],
      )

Add Celery task:
  @celery_app.task(name="analyze_vm_optimizations")
  def analyze_vm_optimizations():
    # Run for all RUNNING VMs, skip if suggestion created in last 24h

Add to beat_schedule: schedule=3600.0 (hourly)

Also add to src/interfaces/api/routers/vms.py:
  GET  /vms/{vm_id}/suggestions   → list pending suggestions for VM
  POST /vms/{vm_id}/suggestions/{sid}/accept   → status=accepted, log to AuditLog
  POST /vms/{vm_id}/suggestions/{sid}/dismiss  → status=dismissed
```

---

### DAY 2

---

#### Task 2.1 [FE] — Description field in VM Create form

```
In the VM creation form/page, add an optional textarea field:
  Label: "Опишите ваш проект (необязательно)"
  Placeholder: "Например: Django веб-приложение с PostgreSQL, ~100 пользователей в день"
  Max length: 1000 characters

Add a button "✨ Получить рекомендацию ИИ" that:
  1. Calls POST /vms/suggest with {description}
  2. Shows a loading spinner during the request
  3. On success: renders <AISuggestionCard /> with the response
  4. On error: shows a small toast "Сервис рекомендаций недоступен"

The textarea and button should be visually separated from the main form fields
(e.g. inside a dashed-border card with a ✨ icon and "AI-powered" badge).
```

---

#### Task 2.2 [FE] — AISuggestionCard component

```
Create a component AISuggestionCard that receives:
  Props: { vcpu, ram_mb, disk_gb, reasoning, confidence, onAccept, onDismiss }

Visual design:
  - Purple/indigo gradient background (e.g. bg-gradient-to-r from-violet-500 to-indigo-600)
  - ✨ sparkle icon + "AI Recommendation" heading
  - Three metric badges: "2 vCPU" | "2048 MB RAM" | "40 GB Disk"
  - Confidence bar: "Уверенность: 87%" with progress bar
  - Reasoning text in italic, smaller font
  - Two buttons: "Принять" (primary, fills form fields) and "Игнорировать" (ghost)
  - Smooth fade-in animation on appearance

onAccept callback should update the parent form's vcpu/ram_mb/disk_gb fields.
onDismiss hides the card.
```

---

#### Task 2.3 [FE] — Optimization notification banners

```
On the VM Detail page and on the Dashboard, fetch GET /vms/{id}/suggestions
(only status=pending suggestions).

For each suggestion, render a dismissible notification card:
  - Yellow/amber color scheme (warning style)
  - 🤖 robot icon
  - Suggestion text (e.g. "Ваша VM использует <10% CPU 7 дней → рекомендуем снизить до 1 vCPU")
  - Confidence badge: "Уверенность: 82%"
  - Two buttons: "Применить" (calls POST .../accept) and "Отклонить" (calls POST .../dismiss)
  - After accept/dismiss: optimistically remove the card from UI

On Dashboard: show count badge "2 рекомендации ИИ" on the VM summary card,
clicking it navigates to the VM detail page.
```

---

#### Task 2.4 [FE] — API hooks for AI features

```
Create API hooks/functions for AI feature endpoints:

1. useSuggestVM (mutation):
   - Calls POST /vms/suggest
   - Input: { description: string }
   - Returns: VMSuggestResponse | null
   - Loading/error state management

2. useVMSuggestions (query):
   - Calls GET /vms/{vmId}/suggestions
   - Auto-refetches every 5 minutes
   - Returns: VmSuggestion[]

3. useAcceptSuggestion (mutation):
   - Calls POST /vms/{vmId}/suggestions/{suggestionId}/accept
   - On success: invalidates useVMSuggestions cache

4. useDismissSuggestion (mutation):
   - Calls POST /vms/{vmId}/suggestions/{suggestionId}/dismiss
   - On success: invalidates useVMSuggestions cache

Add TypeScript types:
  VMSuggestResponse: { vcpu, ram_mb, disk_gb, reasoning, confidence }
  VmSuggestion: { id, suggestion_text, suggested_config, confidence, status, created_at }
```

---

#### Task 2.5 [BE] — Accept suggestion endpoint + resize VM

```
Read src/application/services/vm_service.py and
src/application/services/audit_service.py.

Add resize() method to VMService:
  async def resize(self, vm_id: UUID, tenant_id: UUID, vcpu: int, ram_mb: int, disk_gb: int, user_id: UUID) -> VMResponse:
    vm = await self._vm_repo.get(VirtualMachine.id == vm_id, tenant_id=tenant_id)
    if not vm:
        raise HTTPException(404)
    if vm.status == VMStatus.RUNNING:
        raise HTTPException(409, "Stop VM before resizing")
    vm = await self._vm_repo.update(vm_id, tenant_id, vcpu=vcpu, ram_mb=ram_mb, disk_gb=disk_gb)
    await self._audit.log(tenant_id, user_id, "vm.resize", "vm", vm_id,
                          {"vcpu": vcpu, "ram_mb": ram_mb, "disk_gb": disk_gb})
    return VMResponse.model_validate(vm, from_attributes=True)

The accept suggestion endpoint in vms.py should:
  1. Get the suggestion by id (verify tenant ownership)
  2. If suggestion has suggested_config: call vm_service.resize()
  3. Update suggestion status to "accepted"
  4. Return updated VMResponse
```

---

## Environment Variables to Add

```env
# LLM / AI
LLM_ANTHROPIC_API_KEY=sk-ant-...
LLM_MODEL=claude-3-haiku-20240307
LLM_ENABLED=true
```

Add to `.env.example`.

---

## Testing Checklist

```
□ POST /vms/suggest returns valid vcpu/ram_mb/disk_gb for a description
□ POST /vms/suggest returns fallback config when LLM_ENABLED=false
□ POST /vms/suggest returns 422 if description < 10 chars
□ Celery task collect_vm_metrics inserts rows into vm_metrics
□ Celery task analyze_vm_optimizations creates suggestion if enough metrics exist
□ GET /vms/{id}/suggestions returns only pending suggestions for correct tenant
□ POST .../accept updates suggestion status and calls vm resize
□ POST .../dismiss updates suggestion status, VM unchanged
□ AISuggestionCard renders and onAccept fills form fields correctly
□ Dashboard shows suggestion count badge
□ Suggestion cards dismiss optimistically in UI
```

---

## MVP Cutdown (if short on time)

**Must have (2-3h):**
- `LLMService.suggest_vm_config()` with Anthropic API + fallback
- `POST /vms/suggest` endpoint
- Frontend textarea + "Get AI recommendation" button + AISuggestionCard

**Skip for MVP:**
- ~~vm_metrics table~~ → mock with random values inline
- ~~Celery metrics collection~~ → skip entirely
- ~~SuggestionService + optimization analysis~~ → skip entirely
- ~~Accept/resize endpoint~~ → Accept just fills the form, no DB resize

**Minimum demo script:**
1. User opens "Create VM"
2. Types "Django app with Redis, ~500 requests/sec"
3. Clicks "✨ Get AI Recommendation"
4. Sees: "Recommended: 4 vCPU / 4096 MB RAM / 60 GB Disk — because high-traffic Django needs..."
5. Clicks Accept → form auto-filled → submits VM
