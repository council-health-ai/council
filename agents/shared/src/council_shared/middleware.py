"""Starlette middleware for the Council's A2A agents.

Handles four PO-platform compatibility concerns the canonical a2a-sdk doesn't:

1. **API key auth.** X-API-Key validation; 401/403 on miss/mismatch. Public paths
   (Agent Card, healthz) are exempt.
2. **JSON-RPC method aliasing.** PO sends proto-style PascalCase names
   (`SendMessage`, `SendStreamingMessage`, `GetTask`, `CancelTask`,
   `TaskResubscribe`); a2a-sdk only registers the spec names
   (`message/send`, `message/stream`, `tasks/get`, `tasks/cancel`,
   `tasks/resubscribe`). We rewrite on the way in. Streaming is downgraded to
   non-streaming because PO's client can't parse SSE.
3. **Role aliasing.** PO sends `ROLE_USER` / `ROLE_AGENT`; the SDK expects
   lowercase `user` / `agent`.
4. **FHIR metadata bridging.** PO places FHIR context at
   `params.message.metadata`; the ADK before_model_callback looks at
   `params.metadata`. We copy it up if absent.
5. **Response reshaping.** PO's parser expects the v1-flavored envelope:
   `{"jsonrpc":..., "id":..., "result": {"task": {id, contextId, status:
   {state: TASK_STATE_*}, artifacts: [...]}}}`. The SDK returns the spec form
   `{"result": {kind:"task", id:..., status:{state:"completed"}, artifacts:[
   {parts:[{kind:"text", text:"..."}]}]}}`. We translate on the way out.
"""

from __future__ import annotations

import json
from typing import Any

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from .config import settings

logger = structlog.get_logger("council.middleware")

# Public — no API key check on these paths
PUBLIC_PATHS = {
    "/.well-known/agent-card.json",
    "/.well-known/agent.json",
    "/healthz",
    "/",
}

# JSON-RPC method aliases — PO sends the left-hand side, a2a-sdk wants the right.
_METHOD_ALIASES: dict[str, str] = {
    "SendMessage": "message/send",
    "SendStreamingMessage": "message/send",  # downgrade — PO can't parse SSE responses
    "GetTask": "tasks/get",
    "CancelTask": "tasks/cancel",
    "TaskResubscribe": "tasks/resubscribe",
}

_ROLE_ALIASES: dict[str, str] = {
    "ROLE_USER": "user",
    "ROLE_AGENT": "agent",
}

# State → proto enum mapping for response reshape
_STATE_MAP: dict[str, str] = {
    "completed": "TASK_STATE_COMPLETED",
    "working": "TASK_STATE_WORKING",
    "submitted": "TASK_STATE_SUBMITTED",
    "input-required": "TASK_STATE_INPUT_REQUIRED",
    "failed": "TASK_STATE_FAILED",
    "canceled": "TASK_STATE_CANCELED",
}

_FHIR_CONTEXT_KEY_HINT = "fhir-context"


def _walk_fix_roles(node: Any) -> bool:
    """Mutate role values in-place. Returns True if anything changed."""
    changed = False
    if isinstance(node, dict):
        if "role" in node and node["role"] in _ROLE_ALIASES:
            node["role"] = _ROLE_ALIASES[node["role"]]
            changed = True
        for v in node.values():
            if _walk_fix_roles(v):
                changed = True
    elif isinstance(node, list):
        for item in node:
            if _walk_fix_roles(item):
                changed = True
    return changed


def _find_fhir_metadata(payload: dict) -> tuple[str | None, dict | None]:
    """Look for FHIR context under params.metadata or params.message.metadata."""
    params = payload.get("params") if isinstance(payload, dict) else None
    if not isinstance(params, dict):
        return None, None
    for metadata in (params.get("metadata"), (params.get("message") or {}).get("metadata")):
        if isinstance(metadata, dict):
            for key, value in metadata.items():
                if isinstance(key, str) and _FHIR_CONTEXT_KEY_HINT in key.lower() and isinstance(value, dict):
                    return key, value
    return None, None


def _reshape_to_po_envelope(parsed: dict) -> bool:
    """Mutate parsed JSON-RPC response into PO's expected shape. Returns True if changed."""
    if not isinstance(parsed, dict):
        return False
    result = parsed.get("result")
    if not isinstance(result, dict) or result.get("kind") != "task":
        return False

    task = {
        "id": result.get("id"),
        "contextId": result.get("contextId") or result.get("context_id"),
    }

    status = result.get("status") or {}
    raw_state = status.get("state", "")
    task["status"] = {"state": _STATE_MAP.get(raw_state, raw_state.upper() if raw_state else "")}

    clean_artifacts = []
    for artifact in result.get("artifacts", []) or []:
        clean_parts = []
        for part in artifact.get("parts", []) or []:
            clean_parts.append({k: v for k, v in part.items() if k != "kind"})
        clean_artifact = {k: v for k, v in artifact.items() if k != "parts"}
        clean_artifact["parts"] = clean_parts
        clean_artifacts.append(clean_artifact)
    task["artifacts"] = clean_artifacts

    parsed["result"] = {"task": task}
    return True


class A2APlatformBridgeMiddleware(BaseHTTPMiddleware):
    """One middleware: auth + method aliasing + FHIR bridging + (optional) PO reshape.

    `reshape_response`: True only on agents PO calls directly (the Convener).
    Specialty agents called peer-to-peer by the Convener via a2a-sdk MUST NOT
    reshape — the SDK expects the canonical spec shape and rejects PO's shape
    with 7 pydantic validation errors.
    """

    def __init__(self, app, valid_keys: tuple[str, ...] = (), reshape_response: bool = True):
        super().__init__(app)
        self.valid_keys = set(valid_keys)
        self.reshape_response = reshape_response

    async def dispatch(self, request: Request, call_next) -> Response:
        # ── 1. Read body once (we may rewrite) ───────────────────────────
        body_bytes = await request.body()
        parsed: dict | None = None
        if body_bytes:
            try:
                parsed = json.loads(body_bytes.decode("utf-8", errors="replace"))
            except json.JSONDecodeError:
                parsed = None

        body_dirty = False

        # ── 2. Method aliasing ──────────────────────────────────────────
        if isinstance(parsed, dict):
            method = parsed.get("method")
            if method in _METHOD_ALIASES:
                parsed["method"] = _METHOD_ALIASES[method]
                body_dirty = True
                logger.info("method rewritten", original=method, rewritten=parsed["method"])

        # ── 3. Role aliasing ────────────────────────────────────────────
        if isinstance(parsed, dict) and _walk_fix_roles(parsed):
            body_dirty = True

        # ── 4. FHIR metadata bridging ───────────────────────────────────
        if isinstance(parsed, dict):
            fhir_key, fhir_data = _find_fhir_metadata(parsed)
            params = parsed.get("params")
            if (
                fhir_key
                and fhir_data
                and isinstance(params, dict)
                and not params.get("metadata")
            ):
                params["metadata"] = {fhir_key: fhir_data}
                body_dirty = True
                logger.info("fhir metadata bridged", key=fhir_key, fhir_url_set=bool(fhir_data.get("fhirUrl")))

        # If we mutated, write the new body back so call_next sees it
        if body_dirty and parsed is not None:
            new_body = json.dumps(parsed, ensure_ascii=False).encode("utf-8")
            request._body = new_body  # type: ignore[attr-defined]

        # ── 5. API key check ────────────────────────────────────────────
        if self.valid_keys and request.url.path not in PUBLIC_PATHS:
            api_key = request.headers.get("X-API-Key")
            if not api_key:
                return JSONResponse(
                    {"error": "unauthorized", "message": "X-API-Key header required"},
                    status_code=401,
                )
            if api_key not in self.valid_keys:
                return JSONResponse(
                    {"error": "forbidden", "message": "invalid X-API-Key"},
                    status_code=403,
                )

        # ── 6. Dispatch and capture response ────────────────────────────
        response = await call_next(request)

        content_type = response.headers.get("content-type", "")
        if "application/json" not in content_type:
            return response

        resp_body = b""
        async for chunk in response.body_iterator:
            resp_body += chunk if isinstance(chunk, bytes) else chunk.encode()

        try:
            resp_parsed = json.loads(resp_body)
        except json.JSONDecodeError:
            # Pass through unchanged — non-JSON or malformed
            return Response(
                content=resp_body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type,
            )

        # ── 7. Reshape response to PO's envelope (only on agents PO calls) ─
        if self.reshape_response and _reshape_to_po_envelope(resp_parsed):
            logger.info("response reshaped to po envelope", task_id=resp_parsed.get("result", {}).get("task", {}).get("id"))

        new_resp_body = json.dumps(resp_parsed, ensure_ascii=False).encode("utf-8")
        new_headers = dict(response.headers)
        new_headers.pop("content-length", None)
        new_headers["content-length"] = str(len(new_resp_body))

        return Response(
            content=new_resp_body,
            status_code=response.status_code,
            headers=new_headers,
            media_type=response.media_type,
        )


# Backward-compatible alias for existing callers
ApiKeyMiddleware = A2APlatformBridgeMiddleware


def get_default_api_keys() -> tuple[str, ...]:
    return settings.api_keys
