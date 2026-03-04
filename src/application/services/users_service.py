from typing import List
from uuid import UUID

from asyncpg import UniqueViolationError
from fastapi import Depends
from passlib.context import CryptContext

from src.application.services import exceptions
from src.infrastructure.models.users import User
from src.infrastructure.repositories.users import UserRepository
from src.infrastructure.schemas.users import CreateUser, UserResponse, UserUpdate, UserRequest

bcrypt_context = CryptContext(schemes=['bcrypt'], deprecated='auto')


class UserService:
    def __init__(self, repository: UserRepository = Depends()):
        self._repository = repository

    async def get(self, *args, request_user=None) -> UserResponse:
        user = await self._repository.get(*args)
        if user is None:
            raise exceptions.UserNotFound(
                'Данный пользователь не существует',
            )
        if request_user:
            if not request_user.is_active:
                raise exceptions.UserPermissionDenied(
                    'Пользователь не имеет прав на это действие'
                )
        return UserResponse.model_validate(user, from_attributes=True)

    async def get_all(self, limit: int, offset: int,
                      request_user: UserRequest,
                      ordering: str | None = None,
                      role: str | None = None) -> List[UserResponse]:
        request_user = await self.get(User.email == request_user.email)
        if not request_user.is_active:
            raise exceptions.UserPermissionDenied(
                'Пользователь не имеет прав на это действие'
            )
        users_data = await self._repository.get_all(limit, offset, ordering, role)
        users_response = [UserResponse.model_validate(user, from_attributes=True) for user in users_data]
        return users_response

    async def delete(self, user_id: UUID, request_user: UserRequest) -> None:
        user = await self.get(User.id == user_id)
        request_user = await self.get(User.email == request_user.email)
        if (request_user == user and request_user.is_active) or request_user.role == 'admin':
            await self._repository.delete(User.id == user_id)
            return
        raise exceptions.UserPermissionDenied(
            'Пользователь не имеет прав на это действие'
        )

    async def update(self, user_id: UUID, request_user: UserRequest, user_to_update: UserUpdate) -> None:
        user = await self.get(User.id == user_id)
        request_user = await self.get(User.email == request_user.email)
        has_permission = (request_user.id == user.id and request_user.is_active) or request_user.role == 'admin'
        if not has_permission:
            raise exceptions.UserPermissionDenied('Пользователь не имеет прав на это действие')
        update_data = user_to_update.model_dump(exclude_unset=True)
        await self._repository.update(
            User.id == user_id,
            **update_data
        )

    async def create(self, user_data: CreateUser) -> UserResponse:
        user_data = user_data.model_dump()
        user_data['hashed_password'] = bcrypt_context.hash(user_data.pop('password'))
        try:
            user = await self._repository.create(
                **user_data,
            )
        except UniqueViolationError:
            raise exceptions.UserAlreadyExistsError(
                'Пользователь с такими данными уже существует'
            )
        return UserResponse.model_validate(user, from_attributes=True)

    @property
    def repository(self):
        return self._repository
