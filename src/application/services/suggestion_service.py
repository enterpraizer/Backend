from uuid import UUID

from fastapi import Depends
from uuid import UUID

from src.application.services.llm_service import LLMService
from src.application.services.quota_service import QuotaService
from src.infrastructure.models.virtual_machine import VirtualMachine
from src.infrastructure.models.vm_suggestion import SuggestionStatus, VmSuggestion
from src.infrastructure.repositories.virtual_machine import VMRepository
from src.infrastructure.repositories.vm_metrics import VmMetricsRepository
from src.infrastructure.repositories.vm_suggestion import VmSuggestionRepository


class SuggestionService:
    def __init__(
        self,
        suggestion_repo: VmSuggestionRepository = Depends(),
        metrics_repo: VmMetricsRepository = Depends(),
        llm: LLMService = Depends(),
        quota_svc: QuotaService = Depends(),
        vm_repo: VMRepository = Depends(),
    ) -> None:
        self._suggestions = suggestion_repo
        self._metrics = metrics_repo
        self._llm = llm
        self._quota_svc = quota_svc
        self._vm_repo = vm_repo

    async def analyze_and_suggest(self, vm: VirtualMachine) -> VmSuggestion | None:
        """
        Fetch last 7 days of metrics, ask LLM for an optimization suggestion.
        Skips if fewer than 5 data points or confidence < 0.7.
        Constraints: LLM may not recommend beyond remaining quota + what the VM already uses.
        """
        metrics = await self._metrics.get_recent(vm.id, hours=168)
        if len(metrics) < 1:
            return None

        avg_cpu = sum(m.cpu_pct for m in metrics) / len(metrics)
        avg_ram = sum(m.ram_pct for m in metrics) / len(metrics)
        max_disk = max(m.disk_pct for m in metrics)

        # Compute constraints: the VM can use up to (remaining free quota + what it already consumes)
        constraints = None
        try:
            usage_summary = await self._quota_svc.get_usage_summary(vm.tenant_id)
            avail_vcpu = (usage_summary["vcpu"]["max"] - usage_summary["vcpu"]["used"]) + vm.vcpu
            avail_ram_mb = (usage_summary["ram_mb"]["max"] - usage_summary["ram_mb"]["used"]) + vm.ram_mb
            avail_disk_gb = (usage_summary["disk_gb"]["max"] - usage_summary["disk_gb"]["used"]) + vm.disk_gb
            constraints = {
                "avail_vcpu": avail_vcpu,
                "avail_ram_mb": avail_ram_mb,
                "avail_disk_gb": avail_disk_gb,
                "max_vcpu": usage_summary["vcpu"]["max"],
                "max_ram_mb": usage_summary["ram_mb"]["max"],
                "max_disk_gb": usage_summary["disk_gb"]["max"],
            }
        except Exception:
            pass

        prompt = (
            f"VM: {vm.vcpu} vCPU / {vm.ram_mb} MB RAM / {vm.disk_gb} GB disk\n"
            f"7-day averages: CPU={avg_cpu:.1f}% RAM={avg_ram:.1f}% Disk max={max_disk:.1f}%\n"
            "Suggest an optimization if there is a clear opportunity."
        )

        result = await self._llm.suggest_optimization(prompt, constraints)
        if result.get("confidence", 0) < 0.7:
            return None

        return await self._suggestions.create(
            vm_id=vm.id,
            tenant_id=vm.tenant_id,
            suggestion_text=result["text"],
            suggested_config=result.get("config"),
            confidence=result["confidence"],
        )

    async def get_pending(self, vm_id) -> list[VmSuggestion]:
        return await self._suggestions.get_pending(vm_id=vm_id)

    async def accept(self, suggestion_id: UUID, vm_id: UUID, tenant_id: UUID) -> VmSuggestion | None:
        suggestion = await self._suggestions.get_by_id(suggestion_id, vm_id)
        if not suggestion or suggestion.tenant_id != tenant_id:
            return None
        return await self._suggestions.set_status(suggestion_id, SuggestionStatus.ACCEPTED)

    async def dismiss(self, suggestion_id: UUID, vm_id: UUID, tenant_id: UUID) -> VmSuggestion | None:
        suggestion = await self._suggestions.get_by_id(suggestion_id, vm_id)
        if not suggestion or suggestion.tenant_id != tenant_id:
            return None
        return await self._suggestions.set_status(suggestion_id, SuggestionStatus.DISMISSED)

    async def analyze_by_id(self, vm_id: UUID, tenant_id: UUID) -> VmSuggestion | None:
        """Fetch VM ORM object by id+tenant and run analyze_and_suggest."""
        import sqlalchemy as sa
        vm = (await self._vm_repo._session.execute(
            sa.select(VirtualMachine).where(
                VirtualMachine.id == vm_id,
                VirtualMachine.tenant_id == tenant_id,
            )
        )).scalar_one_or_none()
        if vm is None:
            return None
        return await self.analyze_and_suggest(vm=vm)
