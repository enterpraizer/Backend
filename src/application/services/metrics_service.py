import math
import random
from datetime import datetime, timezone
from fastapi import Depends
from src.infrastructure.models.virtual_machine import VirtualMachine, VMStatus
from src.infrastructure.models.vm_metrics import VmMetrics
from src.infrastructure.repositories.vm_metrics import VmMetricsRepository


class MetricsService:
    def __init__(self, metrics_repo: VmMetricsRepository = Depends()) -> None:
        self._repo = metrics_repo

    async def collect_for_vm(self, vm: VirtualMachine) -> VmMetrics:
        if vm.status != VMStatus.RUNNING:
            return await self._repo.create(
                vm_id=vm.id, cpu_pct=0.0, ram_pct=0.0, disk_pct=0.0
            )

        age_hours = (datetime.now(timezone.utc) - vm.created_at).total_seconds() / 3600

        base_cpu = random.uniform(5, 80)
        daily_cycle = 10 * math.sin(2 * math.pi * age_hours / 24)
        cpu_pct = max(1.0, min(99.0, base_cpu + daily_cycle + random.uniform(-5, 5)))

        ram_pct = min(99.0, random.uniform(20, 85) + random.uniform(-5, 5))
        disk_pct = min(99.0, 30 + (age_hours * 0.1) + random.uniform(-2, 2))

        return await self._repo.create(
            vm_id=vm.id,
            cpu_pct=round(cpu_pct, 1),
            ram_pct=round(ram_pct, 1),
            disk_pct=round(disk_pct, 1),
        )

    async def get_recent(self, vm_id, hours: int = 168) -> list[VmMetrics]:
        return await self._repo.get_recent(vm_id=vm_id, hours=hours)
