from enum import StrEnum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr


class Roles(StrEnum):
    USER = "user"
    ADMIN = "admin"


class UserBase(BaseModel):
    email: EmailStr
    username: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    avatar_url: Optional[str] = None


class CreateUser(UserBase):
    password: str


class UserUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    avatar_url: Optional[str] = None


class UserResponse(UserBase):
    id: UUID
    is_active: Optional[bool] = True
    is_verified: Optional[bool] = False
    hashed_password: Optional[str] = None
    role: Roles = Roles.USER


class UserRequest(BaseModel):
    id: UUID
    email: EmailStr
    role: Roles = Roles.USER
    username: str
    is_active: bool
    tenant_id: Optional[UUID] = None


class UserDeleteRequest(BaseModel):
    user_id: UUID
