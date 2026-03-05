from fastapi import Depends, HTTPException, status

from src.application.services.auth_service import AuthService
from src.infrastructure.schemas.users import UserRequest


async def require_admin(
    user: UserRequest = Depends(AuthService.get_current_user),
) -> UserRequest:
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user
