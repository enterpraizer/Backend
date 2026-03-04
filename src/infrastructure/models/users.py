import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, String, Text, func, text
from sqlalchemy.dialects.postgresql import ENUM as Enum
from sqlalchemy.dialects.postgresql import UUID as Uuid
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


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
    avatar_url: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now())
