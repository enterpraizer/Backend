import re
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

_CIDR_RE = re.compile(
    r"^(\d{1,3}\.){3}\d{1,3}/([0-9]|[1-2]\d|3[0-2])$"
)


class NetworkCreate(BaseModel):
    name: str = Field(..., min_length=3, max_length=100)
    cidr: str
    is_public: bool = False

    @field_validator("cidr")
    @classmethod
    def validate_cidr(cls, v: str) -> str:
        if not _CIDR_RE.match(v):
            raise ValueError("Invalid IPv4 CIDR notation (e.g. 10.0.0.0/24)")
        # validate each octet is 0-255
        ip_part = v.split("/")[0]
        if any(int(o) > 255 for o in ip_part.split(".")):
            raise ValueError("IP address octet out of range (0-255)")
        return v


class AttachVMRequest(BaseModel):
    vm_id: UUID


class NetworkResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    cidr: str
    status: str
    is_public: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class NetworkListResponse(BaseModel):
    items: list[NetworkResponse]
    total: int
