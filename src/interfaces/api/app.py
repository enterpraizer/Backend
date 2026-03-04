import logging
import traceback

from fastapi import FastAPI, Depends, status, HTTPException, Request
from fastapi.exceptions import RequestValidationError
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

# Suppress noisy full tracebacks from Starlette for expected HTTP errors (4xx).
# The error is still returned correctly to the client; we just don't need a wall
# of stack frames in logs for things like expired tokens.
class _SuppressHTTPExceptions(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return "HTTPException" not in record.getMessage()

logging.getLogger("uvicorn.error").addFilter(_SuppressHTTPExceptions())

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(TenantMiddleware)
app.add_middleware(RedisRateLimitMiddleware)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(SecurityHeadersMiddleware)



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


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    if isinstance(exc, HTTPException):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    logger.error("Unhandled exception: %s\n%s", exc, traceback.format_exc())
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )



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
