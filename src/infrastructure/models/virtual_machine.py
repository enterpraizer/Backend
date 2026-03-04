import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String, func, text
from sqlalchemy.dialects.postgresql import ENUM as PgEnum
from sqlalchemy.dialects.postgresql import UUID as Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from . import Tenant, User, VirtualNetwork

from .base import Base


class VMStatus(enum.StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    STOPPED = "stopped"
    TERMINATED = "terminated"


class VirtualMachine(Base):
    __tablename__ = "virtual_machines"
    __table_args__ = (
        Index("ix_vm_tenant_status", "tenant_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[VMStatus] = mapped_column(
        PgEnum(VMStatus, name="vmstatus", create_type=True),
        default=VMStatus.PENDING,
        nullable=False
    )
    vcpu: Mapped[int] = mapped_column(Integer, nullable=False)
    ram_mb: Mapped[int] = mapped_column(Integer, nullable=False)
    disk_gb: Mapped[int] = mapped_column(Integer, nullable=False)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    container_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    container_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="vms")
    owner: Mapped["User"] = relationship("User", back_populates="vms")
    networks: Mapped[list["VirtualNetwork"]] = relationship(
        "VirtualNetwork",
        secondary="vm_network_association",
        back_populates="vms"
    )