"""Sentry initialization for A2A agents."""

from __future__ import annotations

import structlog

logger = structlog.get_logger("council.sentry")


def init_sentry(service_name: str) -> None:
    """Initialize Sentry if SENTRY_DSN is set. Safe to call multiple times — sentry guards itself."""
    from .config import settings

    if not settings.sentry_dsn:
        logger.info("sentry not configured", service=service_name)
        return

    import sentry_sdk
    from sentry_sdk.integrations.starlette import StarletteIntegration

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.sentry_environment,
        traces_sample_rate=0.1 if settings.sentry_environment == "production" else 1.0,
        send_default_pii=False,
        integrations=[StarletteIntegration()],
        before_send=_strip_secrets,
    )
    logger.info("sentry initialized", service=service_name, env=settings.sentry_environment)


def _strip_secrets(event, hint):
    headers = (event.get("request") or {}).get("headers") or {}
    for sensitive in ("authorization", "x-fhir-access-token", "x-api-key"):
        for key in list(headers.keys()):
            if key.lower() == sensitive:
                headers[key] = "[redacted]"
    return event
