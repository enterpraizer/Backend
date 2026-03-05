import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, JSON, String, func, text
from sqlalchemy.dialects.postgresql import UUID as Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.models.base import Base


class VmDescriptionLog(Base):
    __tablename__ = "vm_description_log"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()")
    )
    vm_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("virtual_machines.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    description: Mapped[str] = mapped_column(String, nullable=False)
    suggested_config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    chosen_config: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    vm: Mapped[Optional["VirtualMachine"]] = relationship("VirtualMachine")
    tenant: Mapped["Tenant"] = relationship("Tenant")
