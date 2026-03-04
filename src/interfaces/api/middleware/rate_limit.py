import time
import logging

import redis.asyncio as aioredis
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from src.settings import settings

logger = logging.getLogger(__name__)

# Limits
GENERAL_LIMIT = 100   # req/min
AUTH_LIMIT = 10       # req/min for /auth/* (brute-force protection)
WINDOW_SECONDS = 60


class RedisRateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self._redis: aioredis.Redis | None = None

    def _get_redis(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = aioredis.from_url(settings.redis.url, decode_responses=True)
        return self._redis

    async def dispatch(self, request: Request, call_next):
        ip = request.client.host if request.client else "unknown"
        is_auth = request.url.path.startswith("/auth/")

        key = f"rate:auth:{ip}" if is_auth else f"rate:{ip}"
        limit = AUTH_LIMIT if is_auth else GENERAL_LIMIT

        try:
            redis = self._get_redis()
            now = int(time.time())
            window_start = now - WINDOW_SECONDS

            pipe = redis.pipeline()
            # Sliding window: store each request timestamp as score
            pipe.zremrangebyscore(key, 0, window_start)
            pipe.zadd(key, {str(now) + f"-{id(request)}": now})
            pipe.zcard(key)
            pipe.expire(key, WINDOW_SECONDS)
            results = await pipe.execute()

            count = results[2]
        except Exception:
            # Redis unavailable — fail open (let the request through)
            logger.warning("Rate limiter Redis unavailable, skipping check")
            return await call_next(request)

        if count > limit:
            retry_after = WINDOW_SECONDS
            return JSONResponse(
                {"detail": "Too many requests"},
                status_code=429,
                headers={"Retry-After": str(retry_after)},
            )

        return await call_next(request)
