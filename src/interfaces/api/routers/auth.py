from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from jose import JWTError

from src.application.services import exceptions
from src.application.services.auth_service import AuthService, get_auth_service
from src.infrastructure.models.users import User
from src.infrastructure.schemas.auth import RefreshToken, Tokens, ChangePassword
from src.infrastructure.schemas.users import CreateUser, UserResponse, UserRequest

auth_router = APIRouter(prefix='/auth', tags=['auth'])


@auth_router.post('/register', status_code=status.HTTP_201_CREATED)
async def create_user(user: CreateUser, service: AuthService = Depends(get_auth_service)) -> UserResponse:
    return await service.register_user(user)


@auth_router.get('/register_confirm', status_code=status.HTTP_200_OK)
async def confirm_registration(token: str, service: AuthService = Depends(get_auth_service)) -> dict[str, str]:
    await service.confirm_user(token=token)
    return {"message": "Электронная почта подтверждена"}


@auth_router.patch('/change_password')
async def change_password(request_user: Annotated[UserRequest, Depends(AuthService.get_current_user)],
                          passwords: ChangePassword,
                          service: AuthService = Depends(get_auth_service)
                          ) -> dict[str, Any]:
    try:
        await service.change_password(passwords.old_password, passwords.new_password, request_user)
        return {"status_code": status.HTTP_200_OK}
    except exceptions.UserPermissionDenied as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        ) from None


@auth_router.post('/token')
async def login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
                service: AuthService = Depends(get_auth_service)) -> Tokens:
    try:
        return await service.login(form_data.username, form_data.password)
    except exceptions.UserPermissionDenied as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        ) from None


@auth_router.post('/refresh')
async def refresh_token(token: RefreshToken, service: AuthService = Depends(get_auth_service)) -> Tokens:
    try:
        return await service.refresh(token)
    except exceptions.UserPermissionDenied as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        ) from None
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Невалидный refresh токен")


@auth_router.get('/me')
async def read_current_user(
        request_user: Annotated[UserRequest, Depends(AuthService.get_current_user)],
        service: AuthService = Depends(get_auth_service)
        ) -> UserResponse:
    try:
        request_user = await service.user_service.get(User.email == request_user.email)
        return request_user
    except exceptions.UserValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from None
