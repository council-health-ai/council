"""API key + audit middleware for A2A agents."""

from __future__ import annotations

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from .config import settings

logger = structlog.get_logger("council.middleware")

# Paths that are exempt from API key (Agent Card discovery, health check)
PUBLIC_PATHS = {
    "/.well-known/agent-card.json",
    "/.well-known/agent.json",
    "/healthz",
    "/",
}


class ApiKeyMiddleware(BaseHTTPMiddleware):
    """Reject requests missing or with an unrecognized X-API-Key header.

    Empty `valid_keys` (no keys configured in env) disables auth — useful for the
    public Convener and for local dev. Specialty agents should always have keys set.
    """

    def __init__(self, app, valid_keys: tuple[str, ...] = ()):
        super().__init__(app)
        self.valid_keys = set(valid_keys)

    async def dispatch(self, request: Request, call_next) -> Response:
        if not self.valid_keys:
            return await call_next(request)
        if request.url.path in PUBLIC_PATHS:
            return await call_next(request)

        provided = request.headers.get("X-API-Key", "")
        if not provided:
            return JSONResponse(
                {"error": "unauthorized", "message": "X-API-Key header required"},
                status_code=401,
            )
        if provided not in self.valid_keys:
            return JSONResponse(
                {"error": "forbidden", "message": "invalid X-API-Key"},
                status_code=403,
            )
        return await call_next(request)


def get_default_api_keys() -> tuple[str, ...]:
    return settings.api_keys
