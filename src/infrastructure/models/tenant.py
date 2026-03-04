import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, String, func, text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.infrastructure.models.virtual_network import VirtualNetwork
from src.infrastructure.models.audit_log import AuditLog
from src.infrastructure.models.base import Base
from src.infrastructure.models.resource_quota import ResourceQuota
from src.infrastructure.models.resource_usage import ResourceUsage
from src.infrastructure.models.users import User
from src.infrastructure.models.virtual_machine import VirtualMachine


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        unique=True,
        index=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    owner: Mapped["User"] = relationship("User", back_populates="owned_tenants")
    quota: Mapped[Optional["ResourceQuota"]] = relationship(
        "ResourceQuota", back_populates="tenant", uselist=False
    )
    usage: Mapped[Optional["ResourceUsage"]] = relationship(
        "ResourceUsage", back_populates="tenant", uselist=False
    )
    vms: Mapped[list["VirtualMachine"]] = relationship("VirtualMachine", back_populates="tenant")
    networks: Mapped[list["VirtualNetwork"]] = relationship("VirtualNetwork", back_populates="tenant")
    audit_logs: Mapped[list["AuditLog"]] = relationship("AuditLog", back_populates="tenant")
