import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, func, text
from sqlalchemy.dialects.postgresql import UUID as Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from . import Tenant

from .base import Base


class ResourceUsage(Base):
    __tablename__ = "resource_usage"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        unique=True
    )
    used_vcpu: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    used_ram_mb: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    used_disk_gb: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    used_vms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="usage")
