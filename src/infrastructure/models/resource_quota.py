import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, func, text
from sqlalchemy.dialects.postgresql import UUID as Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.models.base import Base
from src.infrastructure.models.tenant import Tenant


class ResourceQuota(Base):
    __tablename__ = "resource_quotas"

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
        unique=True   # один квота-объект на тенанта
    )
    max_vcpu: Mapped[int] = mapped_column(Integer, default=8, nullable=False)
    max_ram_mb: Mapped[int] = mapped_column(Integer, default=16384, nullable=False)
    max_disk_gb: Mapped[int] = mapped_column(Integer, default=200, nullable=False)
    max_vms: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="quota")
