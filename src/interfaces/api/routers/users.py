from typing import Annotated, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from src.application.services import exceptions
from src.application.services.auth_service import AuthService
from src.application.services.users_service import UserService
from src.infrastructure.models.users import User
from src.infrastructure.schemas.users import UserResponse, UserUpdate, UserRequest, UserDeleteRequest

users_router = APIRouter(prefix="/users", tags=["users"])


@users_router.get("", status_code=status.HTTP_200_OK)
async def get_all_users(limit: int, offset: int,
                        request_user: Annotated[UserRequest, Depends(AuthService.get_current_user)],
                        ordering: str | None = None,
                        role: str | None = None,
                        service: UserService = Depends()) -> List[UserResponse]:
    try:
        user_data = await service.get_all(limit, offset, request_user, ordering, role)
        return user_data
    except exceptions.UserPermissionDenied as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        ) from None


@users_router.delete("/delete", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(request_user: Annotated[UserRequest, Depends(AuthService.get_current_user)],
                      delete_data: UserDeleteRequest,
                      service: UserService = Depends()) -> None:
    try:
        await service.delete(delete_data.user_id, request_user)
    except exceptions.UserPermissionDenied as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        ) from None
    except exceptions.UserNotFound as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from None


@users_router.get("/{user_id}", status_code=status.HTTP_200_OK)
async def user_detail(user_id: UUID, request_user: Annotated[UserRequest, Depends(AuthService.get_current_user)],
                      service: UserService = Depends()) -> UserResponse:
    try:
        user = await service.get(User.id == user_id, request_user=request_user)
        return user
    except exceptions.UserPermissionDenied as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        ) from None
    except exceptions.UserNotFound as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from None


@users_router.patch("/{user_id}", status_code=status.HTTP_200_OK)
async def update_user(user_id: UUID, request_user: Annotated[UserRequest, Depends(AuthService.get_current_user)],
                      user_update: UserUpdate, service: UserService = Depends()) -> None:
    try:
        await service.update(user_id, request_user, user_update)
    except exceptions.UserPermissionDenied as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        ) from None
    except exceptions.UserNotFound as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from None
