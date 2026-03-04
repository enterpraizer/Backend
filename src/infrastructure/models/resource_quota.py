import uuid
from datetime import datetime
from typing import Optional

import sqlalchemy as sa
from sqlalchemy import DateTime, Integer, func, text
from sqlalchemy.dialects.postgresql import UUID as Uuid
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class ResourceQuota(Base):
    __tablename__ = "resource_quotas"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        sa.ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    max_vcpu: Mapped[int] = mapped_column(Integer, default=8, nullable=False)
    max_ram_mb: Mapped[int] = mapped_column(Integer, default=16384, nullable=False)
    max_disk_gb: Mapped[int] = mapped_column(Integer, default=200, nullable=False)
    max_vms: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
