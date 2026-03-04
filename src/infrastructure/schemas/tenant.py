from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class TenantCreate(BaseModel):
    name: str = Field(..., min_length=3, max_length=100)


class TenantResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    owner_id: UUID
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class TenantListResponse(BaseModel):
    items: list[TenantResponse]
    total: int
