from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class QuotaUpdate(BaseModel):
    max_vcpu: Optional[int] = None
    max_ram_mb: Optional[int] = None
    max_disk_gb: Optional[int] = None
    max_vms: Optional[int] = None


class QuotaResponse(BaseModel):
    tenant_id: UUID
    max_vcpu: int
    max_ram_mb: int
    max_disk_gb: int
    max_vms: int

    model_config = {"from_attributes": True}


class ResourceMetric(BaseModel):
    used: int
    max: int
    pct: float


class UsageSummaryResponse(BaseModel):
    vcpu: ResourceMetric
    ram_mb: ResourceMetric
    disk_gb: ResourceMetric
    vms: ResourceMetric
