"""Supabase audit log writes — non-blocking, graceful degradation if creds missing."""

from __future__ import annotations

from typing import Any, Literal

import structlog

from supabase import Client, create_client

from .config import settings

logger = structlog.get_logger("council.audit")

_client: Client | None = None


def _get_client() -> Client | None:
    global _client
    if _client is not None:
        return _client
    if not settings.supabase_url or not settings.supabase_service_role_key:
        return None
    _client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    return _client


AuditAction = Literal[
    "session_started",
    "session_ended",
    "message_received",
    "message_emitted",
    "reasoning_started",
    "reasoning_completed",
    "tool_called",
    "tool_returned",
    "fhir_query",
    "fhir_returned",
    "conflict_flagged",
    "conflict_resolved",
    "plan_synthesized",
    "guideline_referenced",
]


async def record_audit_event(
    *,
    convening_id: str | None,
    actor: str,
    action: AuditAction,
    payload: dict[str, Any] | None = None,
    fhir_refs: list[str] | None = None,
    round_id: int | None = None,
) -> None:
    client = _get_client()
    if client is None:
        return
    row = {
        "convening_id": convening_id,
        "actor": actor,
        "action": action,
        "payload": payload or {},
        "fhir_refs": fhir_refs,
        "round_id": round_id,
    }
    try:
        client.table("audit_events").insert(row).execute()
    except Exception as err:
        logger.warning("audit event insert failed", err=str(err))


async def record_agent_message(
    *,
    convening_id: str,
    role: str,
    direction: Literal["inbound", "outbound"],
    content: dict[str, Any],
    round_id: int | None = None,
    a2a_task_id: str | None = None,
    a2a_message_id: str | None = None,
) -> None:
    client = _get_client()
    if client is None:
        return
    row = {
        "convening_id": convening_id,
        "role": role,
        "direction": direction,
        "round_id": round_id,
        "a2a_task_id": a2a_task_id,
        "a2a_message_id": a2a_message_id,
        "content": content,
    }
    try:
        client.table("agent_messages").insert(row).execute()
    except Exception as err:
        logger.warning("agent message insert failed", err=str(err))


async def record_tool_call(
    *,
    convening_id: str | None,
    tool_name: str,
    params: dict[str, Any],
    result: dict[str, Any] | None,
    status: Literal["success", "error"],
    error_message: str | None = None,
    latency_ms: int = 0,
) -> None:
    client = _get_client()
    if client is None:
        return
    row = {
        "convening_id": convening_id,
        "tool_name": tool_name,
        "params": params,
        "result": result,
        "status": status,
        "error_message": error_message,
        "latency_ms": latency_ms,
    }
    try:
        client.table("mcp_tool_calls").insert(row).execute()
    except Exception as err:
        logger.warning("tool call insert failed", err=str(err))


async def open_session(
    *,
    a2a_context_id: str,
    workspace_id: str,
    patient_id: str,
) -> str | None:
    """Create or upsert a convening_sessions row. Returns the convening_id (uuid) or None on degradation."""
    client = _get_client()
    if client is None:
        return None
    try:
        existing = (
            client.table("convening_sessions")
            .select("id")
            .eq("a2a_context_id", a2a_context_id)
            .limit(1)
            .execute()
        )
        if existing.data:
            return str(existing.data[0]["id"])

        inserted = (
            client.table("convening_sessions")
            .insert({
                "a2a_context_id": a2a_context_id,
                "workspace_id": workspace_id,
                "patient_id": patient_id,
                "status": "active",
            })
            .execute()
        )
        if inserted.data:
            return str(inserted.data[0]["id"])
    except Exception as err:
        logger.warning("open session failed", err=str(err))
    return None


async def close_session(*, convening_id: str, plan_artifact: dict[str, Any] | None = None) -> None:
    client = _get_client()
    if client is None:
        return
    try:
        client.table("convening_sessions").update({
            "status": "completed",
            "ended_at": "now()",
            "plan_artifact": plan_artifact,
        }).eq("id", convening_id).execute()
    except Exception as err:
        logger.warning("close session failed", err=str(err))
