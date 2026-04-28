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

        # Diagnostic: surface raw response shape + parse outcome to HF logs.
        chunk_types = [type(r).__name__ for r in responses]
        # Dump the first chunk to JSON so we can see the actual a2a-sdk shape
        # — this is what tells us if our walker is finding the right keys.
        first_chunk_dump: str | None = None
        if responses:
            try:
                plain = _to_plain(responses[0])
                first_chunk_dump = json.dumps(plain, default=str)[:800]
            except Exception as dump_err:
                first_chunk_dump = f"<dump failed: {dump_err}>"
        logger.info(
            "peer response parsed",
            specialty=specialty,
            url=url,
            latency_ms=latency_ms,
            response_chunks=len(responses),
            chunk_types=chunk_types,
            first_chunk_dump=first_chunk_dump,
            text_len=(len(text) if text else 0),
            text_preview=(text[:400] if text else None),
            structured_view_specialty=(structured.get("specialty") if isinstance(structured, dict) else None),
            structured_view_keys=(sorted(structured.keys()) if isinstance(structured, dict) else None),
            view_extracted=structured is not None,
        )
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


# A SpecialtyView dict is identified by carrying any of these signature fields.
# We don't require all of them because Gemini sometimes drops a key when paraphrasing.
_SPECIALTY_VIEW_SIGNATURE_KEYS = frozenset(
    {
        "specialty",
        "primary_concerns",
        "red_flags",
        "proposed_plan",
        "applicable_guidelines",
        "reasoning_trace",
    }
)


def _looks_like_view(parsed: Any) -> bool:
    return (
        isinstance(parsed, dict)
        and len(_SPECIALTY_VIEW_SIGNATURE_KEYS & parsed.keys()) >= 2
    )


def _extract_view(responses: list[Any]) -> tuple[str | None, dict[str, Any] | None]:
    """From a stream of A2A responses, find a SpecialtyView dict.

    Strategy (most robust first):
      1. Walk the stream for function/tool-response artifacts — the raw MCP tool
         output lives there as a structured dict, *before* Gemini paraphrases it.
      2. Fall back to the agent's final text and try increasingly tolerant
         JSON parses: plain, markdown fence, prose-wrapped, partial.
    """
    # 1. Look for raw structured tool outputs first
    for r in responses:
        view = _scan_for_structured_view(r)
        if view is not None:
            try:
                return json.dumps(view), view
            except (TypeError, ValueError):
                pass

    # 2. Fall back to text extraction + JSON parse
    final_text: str | None = None
    for r in responses:
        text = _scan_for_text(r)
        if text:
            final_text = text

    if not final_text:
        return None, None

    # Plain JSON
    try:
        parsed = json.loads(final_text)
        if _looks_like_view(parsed):
            return final_text, parsed
    except json.JSONDecodeError:
        pass

    # Markdown fence
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
            if _looks_like_view(parsed):
                return final_text, parsed
        except json.JSONDecodeError:
            pass

    # Prose-wrapped: largest balanced {…} span
    first_brace = final_text.find("{")
    last_brace = final_text.rfind("}")
    if first_brace >= 0 and last_brace > first_brace:
        candidate = final_text[first_brace : last_brace + 1]
        try:
            parsed = json.loads(candidate)
            if _looks_like_view(parsed):
                return final_text, parsed
        except json.JSONDecodeError:
            pass

    return final_text, None


def _to_plain(obj: Any) -> Any:
    """Convert any A2A SDK / Pydantic / dataclass object to plain dict/list/scalar.

    a2a-sdk uses Pydantic models with discriminated unions (Part.root → TextPart),
    so attribute-walking misses field paths. model_dump() flattens everything.
    """
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, dict):
        return {k: _to_plain(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_plain(x) for x in obj]
    if hasattr(obj, "model_dump"):
        try:
            return obj.model_dump(mode="json", exclude_none=True)
        except Exception:
            pass
    if hasattr(obj, "__dict__"):
        return {k: _to_plain(v) for k, v in vars(obj).items() if not k.startswith("_")}
    return str(obj)


def _scan_for_structured_view(obj: Any) -> dict[str, Any] | None:
    """Walk a (now-plain) A2A response looking for a SpecialtyView-shaped dict."""
    plain = _to_plain(obj)
    return _walk_for_view(plain)


def _walk_for_view(node: Any) -> dict[str, Any] | None:
    if isinstance(node, dict):
        if _looks_like_view(node):
            return node  # type: ignore[return-value]
        for v in node.values():
            inner = _walk_for_view(v)
            if inner is not None:
                return inner
    elif isinstance(node, list):
        for item in node:
            inner = _walk_for_view(item)
            if inner is not None:
                return inner
    return None


def _scan_for_text(obj: Any) -> str | None:
    """Find the agent's text response anywhere in a (now-plain) A2A payload.

    Walks the dict tree looking for `{"text": "..."}` or `{"kind":"text","text":...}`.
    Picks the LAST text found so we get the agent's final response, not an early
    intermediate event.
    """
    plain = _to_plain(obj)
    found: list[str] = []
    _walk_for_text(plain, found)
    return found[-1] if found else None


def _walk_for_text(node: Any, found: list[str]) -> None:
    if isinstance(node, dict):
        text_val = node.get("text")
        if isinstance(text_val, str) and text_val.strip():
            found.append(text_val)
        for v in node.values():
            _walk_for_text(v, found)
    elif isinstance(node, list):
        for item in node:
            _walk_for_text(item, found)


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
