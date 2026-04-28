"""Deterministic peer A2A fan-out for the Convener.

Uses a2a-sdk's A2ACardResolver + ClientFactory.create(card).send_message() — the canonical
peer-to-peer A2A pattern. NOT RemoteA2aAgent (which delegates routing to Gemini and is
non-deterministic). Council needs deterministic fan-out so we can collect SpecialtyViews
in parallel and synthesize a clean ConcordantPlan.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass
from typing import Any

import httpx
import structlog
from a2a.client import A2ACardResolver, ClientConfig, ClientFactory
from a2a.types import (
    Message,
    Part,
    Role,
    TextPart,
    TransportProtocol,
)
from council_shared import settings

logger = structlog.get_logger("convener.fanout")


@dataclass
class PeerCall:
    specialty: str
    url: str
    prompt: str


@dataclass
class PeerResult:
    specialty: str
    url: str
    success: bool
    response_text: str | None = None
    structured_view: dict[str, Any] | None = None
    error: str | None = None
    latency_ms: int = 0


def _peer_url(specialty: str) -> str:
    """Map a specialty name to its agent's public URL."""
    mapping = {
        "cardiology": settings.cardiology_url,
        "oncology": settings.oncology_url,
        "nephrology": settings.nephrology_url,
        "endocrinology": settings.endocrinology_url,
        "obstetrics": settings.obstetrics_url,
        "developmental_pediatrics": settings.pediatrics_url,
        "psychiatry": settings.psychiatry_url,
        "anesthesia": settings.anesthesia_url,
    }
    url = mapping.get(specialty)
    if not url:
        raise ValueError(f"Unknown specialty: {specialty}")
    return url


def all_specialty_urls() -> list[tuple[str, str]]:
    """Return [(specialty, url)] for all 8 specialties — used for default fan-out in Round 1."""
    return [
        ("cardiology", settings.cardiology_url),
        ("oncology", settings.oncology_url),
        ("nephrology", settings.nephrology_url),
        ("endocrinology", settings.endocrinology_url),
        ("obstetrics", settings.obstetrics_url),
        ("developmental_pediatrics", settings.pediatrics_url),
        ("psychiatry", settings.psychiatry_url),
        ("anesthesia", settings.anesthesia_url),
    ]


async def _call_one_peer(
    *,
    httpx_client: httpx.AsyncClient,
    factory: ClientFactory,
    specialty: str,
    url: str,
    prompt: str,
    context_id: str,
    fhir_metadata: dict[str, Any] | None,
    api_key: str,
) -> PeerResult:
    import time

    started = time.monotonic()
    try:
        resolver = A2ACardResolver(httpx_client, base_url=url)
        card = await resolver.get_agent_card()

        client = factory.create(card)

        msg = Message(
            role=Role.user,
            parts=[Part(root=TextPart(text=prompt))],
            message_id=uuid.uuid4().hex,
            context_id=context_id,
            metadata=(fhir_metadata or None),
        )
        responses: list[Any] = []
        async for chunk in client.send_message(msg):
            responses.append(chunk)
        latency_ms = int((time.monotonic() - started) * 1000)

        text, structured = _extract_view(responses)
        return PeerResult(
            specialty=specialty,
            url=url,
            success=True,
            response_text=text,
            structured_view=structured,
            latency_ms=latency_ms,
        )
    except Exception as err:
        latency_ms = int((time.monotonic() - started) * 1000)
        logger.warning("peer call failed", specialty=specialty, url=url, err=str(err))
        return PeerResult(
            specialty=specialty,
            url=url,
            success=False,
            error=str(err),
            latency_ms=latency_ms,
        )


def _extract_view(responses: list[Any]) -> tuple[str | None, dict[str, Any] | None]:
    """From a stream of A2A responses, find the agent's final text + try to parse as SpecialtyView JSON."""
    final_text: str | None = None
    for r in responses:
        # The streamed responses are typed objects; we duck-type robustly.
        # Try task artifact, message parts, raw text.
        text = _scan_for_text(r)
        if text:
            final_text = text

    if not final_text:
        return None, None

    # Try plain JSON parse first
    try:
        parsed = json.loads(final_text)
        if isinstance(parsed, dict) and "specialty" in parsed:
            return final_text, parsed
    except json.JSONDecodeError:
        pass

    # Tolerate ```json ... ``` markdown fences (LLMs love wrapping JSON in code blocks)
    fence_match = None
    for marker in ("```json", "```JSON", "```"):
        if marker in final_text:
            after = final_text.split(marker, 1)[1]
            end_idx = after.find("```")
            if end_idx > 0:
                fence_match = after[:end_idx].strip()
                break
    if fence_match:
        try:
            parsed = json.loads(fence_match)
            if isinstance(parsed, dict) and "specialty" in parsed:
                return final_text, parsed
        except json.JSONDecodeError:
            pass

    # Tolerate JSON embedded in surrounding prose: find first {...} balanced block
    first_brace = final_text.find("{")
    last_brace = final_text.rfind("}")
    if first_brace >= 0 and last_brace > first_brace:
        candidate = final_text[first_brace : last_brace + 1]
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict) and "specialty" in parsed:
                return final_text, parsed
        except json.JSONDecodeError:
            pass

    return final_text, None


def _scan_for_text(obj: Any) -> str | None:
    if isinstance(obj, str):
        return obj
    if isinstance(obj, dict):
        # Common shapes: {"text": "..."} or {"parts": [{"text": "..."}, ...]}
        if isinstance(obj.get("text"), str):
            return obj["text"]
        for v in obj.values():
            inner = _scan_for_text(v)
            if inner:
                return inner
    elif isinstance(obj, list):
        for item in obj:
            inner = _scan_for_text(item)
            if inner:
                return inner
    else:
        # Pydantic or dataclass-ish — try attribute scan
        for attr in ("text", "parts", "result", "artifact", "content"):
            value = getattr(obj, attr, None)
            if value is not None:
                inner = _scan_for_text(value)
                if inner:
                    return inner
    return None


async def fan_out(
    *,
    calls: list[PeerCall],
    context_id: str,
    fhir_metadata: dict[str, Any] | None,
    api_key: str | None = None,
    timeout_seconds: float = 90.0,
) -> list[PeerResult]:
    """Send the same/different prompt to multiple peers in parallel. Each peer's url is hit
    via its A2A AgentCard. Returns one PeerResult per call (success or error)."""
    api_key = api_key or settings.peer_api_key
    headers = {"X-API-Key": api_key} if api_key else {}

    timeout = httpx.Timeout(timeout_seconds, connect=15.0)
    async with httpx.AsyncClient(timeout=timeout, headers=headers) as httpx_client:
        config = ClientConfig(
            httpx_client=httpx_client,
            supported_transports=[TransportProtocol.jsonrpc],
        )
        factory = ClientFactory(config)

        async def run_one(call: PeerCall) -> PeerResult:
            return await _call_one_peer(
                httpx_client=httpx_client,
                factory=factory,
                specialty=call.specialty,
                url=call.url,
                prompt=call.prompt,
                context_id=context_id,
                fhir_metadata=fhir_metadata,
                api_key=api_key or "",
            )

        results = await asyncio.gather(*(run_one(c) for c in calls), return_exceptions=False)
    return list(results)
