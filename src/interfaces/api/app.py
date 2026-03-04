from fastapi import FastAPI, Depends, status, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from src.interfaces.api.dependencies.session import get_db
from src.interfaces.api.middleware.tenant import TenantMiddleware
from src.interfaces.api.routers import users, auth
from src.interfaces.api.routers.vms import vms_router
from src.interfaces.api.routers.networks import networks_router
from src.interfaces.api.routers.admin import admin_router
from src.settings import settings

app = FastAPI()

app.add_middleware(TenantMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", status_code=status.HTTP_200_OK)
async def health_check(db: AsyncSession = Depends(get_db)):
    try:
        await db.execute(text("SELECT 1"))
        return {
            "status": "healthy",
            "database": "connected"
        }
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE
        )

app.include_router(users.users_router)
app.include_router(auth.auth_router)
app.include_router(vms_router)
app.include_router(networks_router)
app.include_router(admin_router)
