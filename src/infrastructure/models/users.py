import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, String, Text, func, text
from sqlalchemy.dialects.postgresql import ENUM as Enum
from sqlalchemy.dialects.postgresql import UUID as Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.models.base import Base
from src.infrastructure.models.tenant import Tenant
from src.infrastructure.models.virtual_machine import VirtualMachine
from src.infrastructure.models.audit_log import AuditLog


class Roles(enum.StrEnum):
    USER = "user"
    ADMIN = "admin"


class User(Base):
    __tablename__ = "users"

    id: Mapped[Uuid] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        unique=True,
        index=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()")
    )
    email: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    username: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(Text, nullable=False)
    first_name: Mapped[Optional[str]] = mapped_column(String(25))
    last_name: Mapped[Optional[str]] = mapped_column(String(25))
    is_active: Mapped[Optional[bool]] = mapped_column(Boolean, default=False)
    is_verified: Mapped[Optional[bool]] = mapped_column(Boolean, default=False)
    role: Mapped[Optional[Roles]] = mapped_column(
        Enum(Roles,
             name="roles",
             create_type=True
             ),
        nullable=False,
        default=Roles.USER
    )
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now())
    owned_tenants: Mapped[list["Tenant"]] = relationship(
        "Tenant", back_populates="owner"
    )
    vms: Mapped[list["VirtualMachine"]] = relationship(
        "VirtualMachine", back_populates="owner"
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship(
        "AuditLog", back_populates="user"
    )

