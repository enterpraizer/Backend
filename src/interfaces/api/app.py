from fastapi import FastAPI, Depends, status, HTTPException
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from src.settings import settings
from src.interfaces.api.dependencies.session import get_db

app = FastAPI()

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,
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
