from datetime import datetime, timedelta
from typing import Annotated, Optional
from uuid import UUID

from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from itsdangerous import BadSignature, URLSafeTimedSerializer
from jose import jwt
from passlib.context import CryptContext
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.services import exceptions
from src.application.services.tasks import send_confirmation_email
from src.application.services.users_service import UserService
from src.infrastructure.models.users import User
from src.infrastructure.models.tenant import Tenant
from src.infrastructure.schemas.auth import RefreshToken, Tokens, TenantTokenResponse
from src.infrastructure.schemas.users import CreateUser, UserResponse, UserRequest
from src.settings import settings

bcrypt_context = CryptContext(schemes=['bcrypt'], deprecated='auto')
oauth2_scheme = OAuth2PasswordBearer(tokenUrl='auth/token')


class AuthService:
    def __init__(self, user_service: UserService) -> None:
        self._user_service = user_service
        self.serializer = URLSafeTimedSerializer(
            secret_key=settings.secret_key.get_secret_value(),
            salt="email-confirmation"
        )

    async def register_user(self, user: CreateUser) -> UserResponse:
        try:
            user_exist = await self._user_service.get(
                or_(User.username == user.username, User.email == user.email)
            )
            user_data = user_exist
        except exceptions.UserNotFound:
            user_data = await self._user_service.create(user)
        confirmation_token = self.serializer.dumps(user_data.email)
        send_confirmation_email.delay(to_email=user_data.email, token=confirmation_token)
        return user_data

    async def confirm_user(self, token: str) -> None:
        try:
            email = self.serializer.loads(token, max_age=3600)
        except BadSignature:
            raise HTTPException(status_code=400, detail="Неверный или просроченный токен")
        await self._user_service.repository.confirm_user(email=email)

    async def authenticate_user(self, username: str, password: str) -> UserResponse:
        user = await self._user_service.get(User.username == username)
        if not user or not bcrypt_context.verify(password, user.hashed_password) or not user.is_active:
            raise exceptions.UserPermissionDenied('Пользователь не имеет прав на это действие')
        return UserResponse.model_validate(user, from_attributes=True)

    async def _get_tenant_id_for_user(self, user_id: UUID) -> Optional[UUID]:
        tenant_id = await self._user_service.repository.get_tenant_id_for_user(user_id)
        return tenant_id

    async def login(self, username: str, password: str) -> Tokens:
        user = await self.authenticate_user(username, password)

        tenant_id = await self._get_tenant_id_for_user(user.id)

        data = self._build_token_data(user, tenant_id)

        access = await self.create_access_token(data)
        refresh = await self.create_refresh_token(data)

        return Tokens.model_validate(
            {'access_token': access, 'refresh_token': refresh, 'token_type': 'bearer'},
            from_attributes=True
        )

    async def refresh(self, token: RefreshToken) -> Tokens:
        payload = await self.decode_refresh_token(token.refresh_token)
        username = payload.get('sub')

        user = await self._user_service.get(User.username == username)
        user_response = UserResponse.model_validate(user, from_attributes=True)

        tenant_id = await self._get_tenant_id_for_user(user.id)

        data = self._build_token_data(user_response, tenant_id)
        new_access = await self.create_access_token(data)
        new_refresh = await self.create_refresh_token({"sub": username})

        return Tokens.model_validate(
            {'access_token': new_access, 'refresh_token': new_refresh, 'token_type': 'bearer'},
            from_attributes=True
        )

    async def issue_tokens_with_tenant(
        self,
        user: UserResponse,
        tenant: Tenant,
    ) -> TenantTokenResponse:
        data = self._build_token_data(user, tenant.id)
        access = await self.create_access_token(data)
        refresh = await self.create_refresh_token(data)

        return TenantTokenResponse(
            access_token=access,
            refresh_token=refresh,
            token_type='bearer',
            tenant_id=tenant.id,
            tenant_slug=tenant.slug,
        )

    async def change_password(self, old_password: str, new_password: str, request_user: UserRequest):
        request_user = await self._user_service.get(User.email == request_user.email)
        if not request_user or not bcrypt_context.verify(old_password, request_user.hashed_password):
            raise exceptions.UserPermissionDenied('Вы ввели неверный пароль')
        await self._user_service.repository.update(
            User.id == request_user.id,
            hashed_password=bcrypt_context.hash(new_password)
        )

    @staticmethod
    async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]) -> UserRequest:
        payload = await AuthService.decode_access_token(token)

        username: str = payload.get('sub')
        user_id: str = payload.get('id')
        role: str = payload.get('role')
        email: str = payload.get('email')
        is_active: bool = payload.get('is_active')
        tenant_id: Optional[str] = payload.get('tenant_id')

        if username is None or user_id is None:
            raise exceptions.UserValidationError('Валидация пользователя прошла неудачно')

        return UserRequest.model_validate(
            {
                'username': username,
                'id': user_id,
                'role': role,
                'email': email,
                'is_active': is_active,
                'tenant_id': tenant_id,
            },
            from_attributes=True
        )

    @staticmethod
    def _build_token_data(user: UserResponse, tenant_id: Optional[UUID] = None) -> dict:
        return {
            'sub': user.username,
            'id': str(user.id),
            'role': user.role,
            'email': user.email,
            'is_active': user.is_active,
            'tenant_id': str(tenant_id) if tenant_id else None,
        }

    @staticmethod
    async def create_jwt_token(data: dict, expires_delta: timedelta, secret_key: str):
        to_encode = data.copy()
        expires = datetime.now() + expires_delta
        to_encode.update({'exp': expires})
        return jwt.encode(to_encode, secret_key, algorithm=settings.app.algorithm)

    @staticmethod
    async def create_access_token(data: dict):
        return await AuthService.create_jwt_token(
            data,
            timedelta(minutes=settings.app.access_token_expire_minutes),
            settings.app.secret_key
        )

    @staticmethod
    async def create_refresh_token(data: dict):
        return await AuthService.create_jwt_token(
            data,
            timedelta(days=settings.app.refresh_token_expire_days),
            settings.app.refresh_secret_key
        )

    @staticmethod
    async def decode_access_token(token: str):
        return jwt.decode(token, settings.app.secret_key, algorithms=[settings.app.algorithm])

    @staticmethod
    async def decode_refresh_token(token: str):
        return jwt.decode(token, settings.app.refresh_secret_key, algorithms=[settings.app.algorithm])

    @property
    def user_service(self):
        return self._user_service


async def get_auth_service(user_service: UserService = Depends()) -> AuthService:
    return AuthService(user_service=user_service)