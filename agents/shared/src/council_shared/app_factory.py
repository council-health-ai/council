"""Starlette ASGI factory that wires an ADK agent to A2A with v0 + v1 path coverage.

Uses a2a-sdk 0.3.26's `A2AStarletteApplication` to handle JSON-RPC routing, and adds:
- /.well-known/agent.json — v0 backcompat path (the Prompt Opinion walkthrough uses this)
- /healthz — service health probe (HF Spaces healthcheck + GitHub Actions cron)
- API key middleware
- Sentry integration
"""

from __future__ import annotations

from typing import Any

import structlog
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentSkill
from starlette.requests import Request
from starlette.responses import JSONResponse

from .card_factory import make_agent_card
from .middleware import ApiKeyMiddleware, get_default_api_keys
from .sentry_init import init_sentry

logger = structlog.get_logger("council.app_factory")


def create_a2a_app(
    *,
    agent: Any,  # google.adk.agents.Agent — duck-typed
    name: str,
    description: str,
    url: str,
    role: str,
    skills: list[AgentSkill],
    require_api_key: bool = True,
    version: str = "0.1.0",
):
    """Build a Starlette ASGI app exposing an ADK agent over A2A (v0.3 native + v0 path backcompat)."""

    init_sentry(service_name=name)

    card = make_agent_card(
        name=name,
        description=description,
        url=url,
        role=role,
        skills=skills,
        require_api_key=require_api_key,
        version=version,
    )

    # Bridge ADK Agent -> A2A AgentExecutor
    from google.adk.a2a.executor.a2a_agent_executor import A2aAgentExecutor

    executor = A2aAgentExecutor(runner=_make_runner(agent))

    handler = DefaultRequestHandler(
        agent_executor=executor,
        task_store=InMemoryTaskStore(),
    )

    a2a_app = A2AStarletteApplication(agent_card=card, http_handler=handler)
    # build() at the v1 well-known path; we'll add v0 alias separately
    starlette_app = a2a_app.build(agent_card_url="/.well-known/agent-card.json", rpc_url="/")

    # ── extra routes ─────────────────────────────────────────────────
    async def healthz(_request: Request) -> JSONResponse:
        return JSONResponse({"ok": True, "service": name, "version": version})

    async def root(_request: Request) -> JSONResponse:
        return JSONResponse({
            "service": name,
            "description": description,
            "agent_card_v1": "/.well-known/agent-card.json",
            "agent_card_v0": "/.well-known/agent.json",
            "rpc": "POST /",
        })

    def card_dump() -> dict:
        return card.model_dump(mode="json", by_alias=True, exclude_none=True)

    async def agent_card_v0(_request: Request) -> JSONResponse:
        return JSONResponse(card_dump())

    starlette_app.add_route("/healthz", healthz, methods=["GET"])
    starlette_app.add_route("/", root, methods=["GET"])
    starlette_app.add_route("/.well-known/agent.json", agent_card_v0, methods=["GET"])

    # ── middleware ───────────────────────────────────────────────────
    if require_api_key:
        keys = get_default_api_keys()
        if keys:
            starlette_app.add_middleware(ApiKeyMiddleware, valid_keys=keys)
        else:
            logger.warning(
                "require_api_key=True but no API_KEYS in env — auth disabled. Set API_KEY_PRIMARY.",
                service=name,
            )

    logger.info("a2a app ready", name=name, url=url, role=role, n_skills=len(skills))
    return starlette_app


def _make_runner(agent: Any):
    """Build a google-adk Runner around the agent. The A2aAgentExecutor delegates to it."""
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService

    return Runner(
        app_name=getattr(agent, "name", "council-agent"),
        agent=agent,
        session_service=InMemorySessionService(),
    )
