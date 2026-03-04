import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Float, Index, func, text
from sqlalchemy.dialects.postgresql import UUID as Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.models.base import Base


class VmMetrics(Base):
    __tablename__ = "vm_metrics"
    __table_args__ = (
        Index("ix_vm_metrics_vm_recorded", "vm_id", "recorded_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()")
    )
    vm_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("virtual_machines.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    cpu_pct: Mapped[float] = mapped_column(Float, nullable=False)
    ram_pct: Mapped[float] = mapped_column(Float, nullable=False)
    disk_pct: Mapped[float] = mapped_column(Float, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), index=True
    )

    vm: Mapped["VirtualMachine"] = relationship("VirtualMachine", back_populates="metrics")
