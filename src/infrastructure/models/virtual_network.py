import enum
import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, String, Table, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import ENUM as PgEnum
from sqlalchemy.dialects.postgresql import UUID as Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .tenant import Tenant
from .virtual_machine import VirtualMachine

vm_network_association = Table(
    "vm_network_association",
    Base.metadata,
    Column("vm_id",
           Uuid(as_uuid=True),
           ForeignKey("virtual_machines.id", ondelete="CASCADE"), primary_key=True),
    Column("network_id",
           Uuid(as_uuid=True),
           ForeignKey("virtual_networks.id", ondelete="CASCADE"), primary_key=True),
)


class NetworkStatus(enum.StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class VirtualNetwork(Base):
    __tablename__ = "virtual_networks"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_network_tenant_name"),
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
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    cidr: Mapped[str] = mapped_column(String(18), nullable=False)
    status: Mapped[NetworkStatus] = mapped_column(
        PgEnum(NetworkStatus, name="networkstatus", create_type=True),
        default=NetworkStatus.ACTIVE,
        nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="networks")
    vms: Mapped[list["VirtualMachine"]] = relationship(
        "VirtualMachine",
        secondary="vm_network_association",
        back_populates="networks"
    )
