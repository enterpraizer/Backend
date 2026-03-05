import time
import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = logging.getLogger(__name__)

SKIP_PATHS = {"/health"}


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path in SKIP_PATHS:
            return await call_next(request)

        start = time.monotonic()

        # Tenant id is injected by TenantMiddleware into request.state
        tenant_id = getattr(request.state, "tenant_id", "-")

        response = await call_next(request)

        duration_ms = round((time.monotonic() - start) * 1000, 1)
        logger.info(
            "%s %s [%s] → %s in %sms",
            request.method,
            request.url.path,
            tenant_id,
            response.status_code,
            duration_ms,
        )
        return response
