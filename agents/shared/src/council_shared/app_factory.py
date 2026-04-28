"""Starlette ASGI factory matching po-adk-python's working pattern exactly.

Uses google-adk's `to_a2a` helper instead of manually wiring A2aAgentExecutor
+ DefaultRequestHandler + A2AStarletteApplication.build(). The manual path
emits Message events for short responses; PO's parser only treats Task events
as valid responses, hence "external agent did not respond with a task."
The `to_a2a` helper emits Tasks consistently when streaming=False (per
po-adk-python — confirmed working in production).

Adds on top:
- /healthz route
- /.well-known/agent.json (v0 backcompat — walkthrough video uses this path)
- A2APlatformBridgeMiddleware (method aliasing, role aliasing, FHIR metadata
  bridging, response reshape into PO's task envelope)
- Sentry init
"""

from __future__ import annotations

from typing import Any

import structlog
from a2a.types import AgentSkill
from google.adk.a2a.utils.agent_to_a2a import to_a2a
from starlette.requests import Request
from starlette.responses import JSONResponse

from .card_factory import AgentCardV1, make_agent_card
from .middleware import A2APlatformBridgeMiddleware, get_default_api_keys
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
    reshape_response_for_po: bool = True,
    version: str = "0.1.0",
):
    """Build a Starlette ASGI app exposing an ADK agent over A2A using ADK's to_a2a helper."""

    init_sentry(service_name=name)

    card: AgentCardV1 = make_agent_card(
        name=name,
        description=description,
        url=url,
        role=role,
        skills=skills,
        require_api_key=require_api_key,
        version=version,
    )

    # ── ADK's to_a2a does the right thing: builds a Starlette app with proper
    #    Task-emitting executor, mounts the agent card at /.well-known/agent-card.json,
    #    and the JSON-RPC endpoint at /. Returns a Starlette instance.
    app = to_a2a(agent, port=7860, agent_card=card)

    # ── Add v0 backcompat agent-card route (the walkthrough video uses this path).
    async def agent_card_v0(_request: Request) -> JSONResponse:
        return JSONResponse(card.model_dump(mode="json", by_alias=True, exclude_none=True))

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

    app.add_route("/.well-known/agent.json", agent_card_v0, methods=["GET"])
    app.add_route("/healthz", healthz, methods=["GET"])
    # NOTE: root path "/" is owned by the JSON-RPC handler (POST). GET / will 405.

    # ── Bridge middleware (auth + method aliasing + FHIR bridging + reshape) ─
    keys = get_default_api_keys() if require_api_key else ()
    if require_api_key and not keys:
        logger.warning("require_api_key=True but no API_KEYS in env — auth disabled", service=name)
    app.add_middleware(
        A2APlatformBridgeMiddleware,
        valid_keys=keys,
        reshape_response=reshape_response_for_po,
    )

    logger.info("a2a app ready", name=name, url=url, role=role, n_skills=len(skills))
    return app
