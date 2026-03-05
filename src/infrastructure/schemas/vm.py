from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class VMCreate(BaseModel):
    name: str = Field(..., min_length=3, max_length=100)
    vcpu: int = Field(..., ge=1, le=32)
    ram_mb: int = Field(..., ge=512, le=65536)
    disk_gb: int = Field(..., ge=10, le=500)


class VMUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=3, max_length=100)
    status: Optional[Literal["running", "stopped"]] = None


class VMResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    status: str
    vcpu: int
    ram_mb: int
    disk_gb: int
    ip_address: Optional[str]
    container_id: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class VMListResponse(BaseModel):
    items: list[VMResponse]
    total: int


class VMSuggestRequest(BaseModel):
    description: str = Field(..., min_length=10, max_length=1000)


class VMSuggestResponse(BaseModel):
    vcpu: int
    ram_mb: int
    disk_gb: int
    reasoning: str
    confidence: float


class SuggestionResponse(BaseModel):
    id: UUID
    vm_id: UUID
    tenant_id: UUID
    suggestion_text: str
    suggested_config: Optional[dict]
    confidence: float
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class TriggerAnalyzeResponse(BaseModel):
    suggestion: Optional[SuggestionResponse]
    cooldown_remaining_sec: int  # 0 means not on cooldown
    next_available_at: Optional[str]  # ISO timestamp or None
    message: str
