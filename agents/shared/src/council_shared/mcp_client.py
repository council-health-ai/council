"""Minimal MCP client for calling the specialty-lens-mcp server with SHARP context forwarding.

Uses the official `mcp` Python SDK over Streamable HTTP. Each call opens a fresh session
(stateless, matches the server's pattern). Headers are constructed per-call to forward
the SHARP context that lives in the agent's tool_context.state.
"""

from __future__ import annotations

import json
from typing import Any

import structlog
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from .config import settings

logger = structlog.get_logger("council.mcp_client")

MCP_BASE_URL = settings.mcp_url


async def call_mcp_tool(
    tool_name: str,
    arguments: dict[str, Any],
    *,
    fhir_url: str,
    fhir_token: str,
    patient_id: str | None = None,
    convening_id: str | None = None,
    specialty: str | None = None,
    round_id: int | None = None,
    mcp_url: str | None = None,
) -> dict[str, Any]:
    """Call a specialty-lens-mcp tool. Returns the parsed structured content as a dict.

    Raises if the call fails or returns non-JSON content.
    """
    url = mcp_url or settings.mcp_url
    headers: dict[str, str] = {
        "X-FHIR-Server-URL": fhir_url,
        "X-FHIR-Access-Token": fhir_token,
    }
    if patient_id:
        headers["X-Patient-ID"] = patient_id
    if convening_id:
        headers["X-Council-Convening-Id"] = convening_id
    if specialty:
        headers["X-Council-Specialty"] = specialty
    if round_id is not None:
        headers["X-Council-Round-Id"] = str(round_id)

    logger.info("mcp call", tool=tool_name, patient_id=patient_id, convening_id=convening_id)

    async with (
        streamablehttp_client(url, headers=headers) as (read_stream, write_stream, _),
        ClientSession(read_stream, write_stream) as session,
    ):
        await session.initialize()
        result = await session.call_tool(tool_name, arguments=arguments)

    if result.isError:
        msg = _extract_text(result.content) or "MCP tool returned error with empty body"
        raise RuntimeError(f"MCP tool {tool_name} failed: {msg}")

    structured = getattr(result, "structuredContent", None) or getattr(result, "structured_content", None)
    if structured:
        return dict(structured)

    text = _extract_text(result.content)
    if not text:
        raise RuntimeError(f"MCP tool {tool_name} returned no text content")
    try:
        return json.loads(text)
    except json.JSONDecodeError as err:
        raise RuntimeError(f"MCP tool {tool_name} returned non-JSON text: {err}") from err


def _extract_text(content: list[Any]) -> str | None:
    for part in content or []:
        text = getattr(part, "text", None)
        if isinstance(text, str):
            return text
    return None
