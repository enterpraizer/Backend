import enum
import uuid
from datetime import datetime
from typing import Optional

import sqlalchemy as sa
from sqlalchemy import Boolean, DateTime, String, Table, Column, func, text
from sqlalchemy.dialects.postgresql import ENUM as PgEnum
from sqlalchemy.dialects.postgresql import UUID as Uuid
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class NetworkStatus(enum.StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"


vm_network_association = Table(
    "vm_network_association",
    Base.metadata,
    Column("vm_id", Uuid(as_uuid=True), sa.ForeignKey("virtual_machines.id", ondelete="CASCADE"), primary_key=True),
    Column("network_id", Uuid(as_uuid=True), sa.ForeignKey("virtual_networks.id", ondelete="CASCADE"), primary_key=True),
)


class VirtualNetwork(Base):
    __tablename__ = "virtual_networks"

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
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    cidr: Mapped[str] = mapped_column(String(18), nullable=False)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[NetworkStatus] = mapped_column(
        PgEnum(NetworkStatus, name="network_status", create_type=True),
        nullable=False,
        default=NetworkStatus.ACTIVE,
    )
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, server_default=func.now()
    )

    __table_args__ = (
        sa.UniqueConstraint("tenant_id", "name", name="uq_network_tenant_name"),
    )
