import logging
import traceback

from fastapi import FastAPI, Depends, status, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from src.interfaces.api.dependencies.session import get_db
from src.interfaces.api.middleware.tenant import TenantMiddleware
from src.interfaces.api.middleware.rate_limit import RedisRateLimitMiddleware
from src.interfaces.api.middleware.logging_middleware import RequestLoggingMiddleware
from src.interfaces.api.middleware.security_headers import SecurityHeadersMiddleware
from src.interfaces.api.routers import users, auth
from src.interfaces.api.routers.vms import vms_router
from src.interfaces.api.routers.networks import networks_router
from src.interfaces.api.routers.admin import admin_router
from src.interfaces.api.routers.dashboard import dashboard_router
from src.application.services.exceptions import (
    UserAlreadyExistsError,
    UserNotFound,
    UserPermissionDenied,
)
from src.application.services.quota_service import QuotaExceededError
from src.settings import settings

logger = logging.getLogger(__name__)

app = FastAPI()

# Middleware order (added last = runs first):
# 1. CORSMiddleware  (outermost)
# 2. TenantMiddleware
# 3. RedisRateLimitMiddleware
# 4. RequestLoggingMiddleware
# 5. SecurityHeadersMiddleware (innermost, adds headers to every response)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(TenantMiddleware)
app.add_middleware(RedisRateLimitMiddleware)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(SecurityHeadersMiddleware)


# ---------------------------------------------------------------------------
# Global exception handlers
# ---------------------------------------------------------------------------

@app.exception_handler(QuotaExceededError)
async def quota_exceeded_handler(request: Request, exc: QuotaExceededError):
    return JSONResponse(
        status_code=429,
        content={
            "detail": str(exc),
            "resource": exc.resource,
            "requested": exc.requested,
            "available": exc.available,
        },
    )


@app.exception_handler(UserNotFound)
async def user_not_found_handler(request: Request, exc: UserNotFound):
    return JSONResponse(status_code=404, content={"detail": "User not found"})


@app.exception_handler(UserPermissionDenied)
async def user_permission_denied_handler(request: Request, exc: UserPermissionDenied):
    return JSONResponse(status_code=403, content={"detail": "Permission denied"})


@app.exception_handler(UserAlreadyExistsError)
async def user_already_exists_handler(request: Request, exc: UserAlreadyExistsError):
    return JSONResponse(status_code=409, content={"detail": "User already exists"})


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception: %s\n%s", exc, traceback.format_exc())
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health", status_code=status.HTTP_200_OK)
async def health_check(db: AsyncSession = Depends(get_db)):
    try:
        await db.execute(text("SELECT 1"))
        return {"status": "healthy", "database": "connected"}
    except Exception:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE)


app.include_router(users.users_router)
app.include_router(auth.auth_router)
app.include_router(vms_router)
app.include_router(networks_router)
app.include_router(admin_router)
app.include_router(dashboard_router)
