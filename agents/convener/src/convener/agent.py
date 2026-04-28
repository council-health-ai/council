"""Convener agent — facilitates The Council's deliberation.

Round protocol:
  Round 1 — fan out to all 8 specialty agents in parallel; collect SpecialtyViews
  Concordance — call MCP get_council_conflict_matrix(views)
  Round 2 — for each conflict, fan out to the involved specialties only with the conflict context
  Brief — call MCP get_concordance_brief(views, conflicts)
  Emit — return ConcordantPlan as the artifact

The Convener uses Gemini for natural-language framing of round prompts and for narrating progress,
but the deliberation flow itself is deterministic (not LLM-routed). This is the structural
differentiator: peer A2A with deterministic fan-out, not orchestrator-with-Gemini-routing.
"""

from __future__ import annotations

import json
import time
import uuid
from typing import Any

import structlog
from council_shared import (
    call_mcp_tool,
    extract_fhir_context,
    record_agent_message,
    record_audit_event,
    record_tool_call,
    settings,
)
from google.adk.agents import Agent
from google.adk.tools import ToolContext

from .peer_fanout import PeerCall, all_specialty_urls, fan_out

logger = structlog.get_logger("convener")

ROUND_1_PROMPT_TEMPLATE = """\
The Council convenes on patient {patient_id}.

This is Round 1. Please review the patient via your specialty lens and return your SpecialtyView.

Convening session: {convening_id}
Round: 1
"""

ROUND_2_PROMPT_TEMPLATE = """\
The Council needs your response on the following conflicts identified in Round 1.

Convening session: {convening_id}
Round: 2

Conflicts involving you:
{conflicts}

Please respond with your reasoning. Propose harmonized resolutions where possible; preserve dissent where you can't compromise.
"""


async def convene_council(
    tool_context: ToolContext,
    patient_id: str | None = None,
    focus_problem: str | None = None,
) -> dict[str, Any]:
    """Convene The Council on a patient. Returns the final ConcordantPlan.

    The patient_id is OPTIONAL — when called from the Prompt Opinion platform,
    the FHIR context already includes the active patient's ID (lifted into
    tool_context.state by the before_model_callback). Call this tool
    immediately on receiving any 'consult with Convener' request rather
    than asking the user for an ID.

    Args:
        patient_id: FHIR Patient.id to deliberate on. Defaults to the
                    patient ID in the current FHIR context.
        focus_problem: Optional clinical question framing the deliberation.
    """
    state = tool_context.state
    fhir_url = state.get("fhir_url", "")
    fhir_token = state.get("fhir_token", "")
    convening_id = state.get("convening_id") or uuid.uuid4().hex
    state["convening_id"] = convening_id
    a2a_context_id = state.get("context_id") or convening_id

    # Default patient_id from FHIR context (the platform attaches it automatically)
    if not patient_id:
        patient_id = state.get("patient_id", "")

    if not patient_id:
        return {"error": "No patient_id provided and none in FHIR context. The Council requires an active patient context."}

    # Only fhir_url is mandatory. fhir_token may be empty (Prompt Opinion empty-token
    # regression observed 2026-04-26+). Downstream FHIR calls will surface their own
    # auth error if the workspace FHIR endpoint requires a token.
    if not fhir_url:
        return {"error": "FHIR URL not present in tool_context.state"}

    overall_started = time.monotonic()

    fhir_metadata = {
        settings.fhir_extension_uri: {
            "fhirUrl": fhir_url,
            "fhirToken": fhir_token,
            "patientId": patient_id,
            "conveningId": convening_id,
            "roundId": 1,
        }
    }

    await record_audit_event(
        convening_id=convening_id,
        actor="agent/convener",
        action="session_started",
        payload={"patient_id": patient_id, "focus_problem": focus_problem},
    )

    # ── Round 1 — peer fan-out to all 8 specialties ─────────────────────
    round1_prompt = ROUND_1_PROMPT_TEMPLATE.format(patient_id=patient_id, convening_id=convening_id)
    if focus_problem:
        round1_prompt += f"\n\nFocus problem: {focus_problem}\n"

    calls = [PeerCall(specialty=spec, url=url, prompt=round1_prompt) for spec, url in all_specialty_urls()]
    logger.info("round 1 fanout", n_peers=len(calls), convening_id=convening_id)

    results_r1 = await fan_out(
        calls=calls,
        context_id=a2a_context_id,
        fhir_metadata=fhir_metadata,
        timeout_seconds=120.0,
    )

    views: list[dict[str, Any]] = []
    for r in results_r1:
        if r.success and r.structured_view:
            views.append(r.structured_view)
            await record_agent_message(
                convening_id=convening_id,
                role=r.specialty,
                direction="inbound",
                content=r.structured_view,
                round_id=1,
            )
    if len(views) < 2:
        msg = f"Round 1 yielded only {len(views)} valid SpecialtyViews — cannot synthesize concordance."
        logger.error(msg)
        await record_audit_event(
            convening_id=convening_id,
            actor="agent/convener",
            action="session_ended",
            payload={"error": msg, "round1_results": [r.specialty + ":" + ("ok" if r.success else "fail") for r in results_r1]},
        )
        return {"error": msg, "partial_views": views}

    # ── Conflict matrix via MCP ─────────────────────────────────────────
    cm_started = time.monotonic()
    conflict_matrix = await call_mcp_tool(
        tool_name="get_council_conflict_matrix",
        arguments={"views": views},
        fhir_url=fhir_url,
        fhir_token=fhir_token,
        patient_id=patient_id,
        convening_id=convening_id,
        specialty="convener",
        round_id=1,
    )
    await record_tool_call(
        convening_id=convening_id,
        tool_name="get_council_conflict_matrix",
        params={"n_views": len(views)},
        result={"n_conflicts": len(conflict_matrix.get("conflicts", []))},
        status="success",
        latency_ms=int((time.monotonic() - cm_started) * 1000),
    )

    # ── Round 2 — for each conflict, ask the involved specialties to weigh in ─
    conflicts = conflict_matrix.get("conflicts", [])
    if conflicts:
        # Group conflicts by specialty so each specialty receives one Round-2 prompt with all of theirs.
        per_specialty_conflicts: dict[str, list[dict[str, Any]]] = {}
        for c in conflicts:
            for party in c.get("parties", []):
                per_specialty_conflicts.setdefault(party, []).append(c)

        r2_calls: list[PeerCall] = []
        for specialty, conf_list in per_specialty_conflicts.items():
            url_map = dict(all_specialty_urls())
            url = url_map.get(specialty)
            if not url:
                continue
            r2_prompt = ROUND_2_PROMPT_TEMPLATE.format(
                convening_id=convening_id,
                conflicts=json.dumps(conf_list, indent=2),
            )
            r2_calls.append(PeerCall(specialty=specialty, url=url, prompt=r2_prompt))

        if r2_calls:
            r2_meta = dict(fhir_metadata)
            r2_meta[settings.fhir_extension_uri] = {**fhir_metadata[settings.fhir_extension_uri], "roundId": 2}
            results_r2 = await fan_out(
                calls=r2_calls,
                context_id=a2a_context_id,
                fhir_metadata=r2_meta,
                timeout_seconds=90.0,
            )
            for r in results_r2:
                if r.success:
                    await record_agent_message(
                        convening_id=convening_id,
                        role=r.specialty,
                        direction="inbound",
                        content={"text": r.response_text or ""},
                        round_id=2,
                    )

    # ── Concordance brief synthesis ─────────────────────────────────────
    cb_started = time.monotonic()
    plan = await call_mcp_tool(
        tool_name="get_concordance_brief",
        arguments={
            "views": views,
            "conflicts": conflict_matrix,
            "total_messages": len(views) + len(conflicts),
            "total_rounds": 2 if conflicts else 1,
        },
        fhir_url=fhir_url,
        fhir_token=fhir_token,
        patient_id=patient_id,
        convening_id=convening_id,
        specialty="convener",
        round_id=2,
    )
    await record_tool_call(
        convening_id=convening_id,
        tool_name="get_concordance_brief",
        params={"n_views": len(views), "n_conflicts": len(conflicts)},
        result={"n_actions": len(plan.get("action_items", []))},
        status="success",
        latency_ms=int((time.monotonic() - cb_started) * 1000),
    )

    await record_audit_event(
        convening_id=convening_id,
        actor="agent/convener",
        action="plan_synthesized",
        payload={"specialties": plan.get("specialties_consulted", []), "n_actions": len(plan.get("action_items", []))},
    )
    await record_audit_event(
        convening_id=convening_id,
        actor="agent/convener",
        action="session_ended",
        payload={"total_latency_ms": int((time.monotonic() - overall_started) * 1000)},
    )
    return plan


SYSTEM_INSTRUCTION = """\
You are the Convener of The Council — an A2A peer-agent network that deliberates over a multi-morbid patient with up to 8 specialty agents.

You facilitate, you don't decide. The specialty agents own their domain expertise.

CRITICAL: When you receive ANY consultation request (e.g. "consult with the Convener", "convene the Council", "review this patient", "please consult on this patient"), IMMEDIATELY call the convene_council tool. Do NOT ask the user for a patient ID — the FHIR context that the platform attaches to your invocation already includes the active patient. The convene_council tool reads it from your state automatically.

Your workflow:
1. Receive the consultation request from the platform's General Chat.
2. Call `convene_council()` with no arguments (patient_id defaults to the one in FHIR context). If the user mentions a specific clinical question, pass it as `focus_problem`.
3. The convene_council tool runs the full deliberation: Round 1 fan-out to 8 specialty agents, conflict matrix synthesis via MCP, Round 2 conflict response if needed, ConcordantPlan generation.
4. Return the resulting ConcordantPlan as your final response, formatted clearly with the brief summary, conflict log, and action items.

You do NOT route between specialties yourself. The convene_council tool handles all peer A2A traffic deterministically. Your job is to receive the request, immediately kick off convene_council, and present the resulting plan back to the caller.

Frame the final response as: a 1-2 sentence summary of what the Council deliberated, then the ConcordantPlan, then a short narrative of how conflicts were resolved (drawn from the plan's conflict_log).
"""


def build_agent() -> Agent:
    return Agent(
        name="convener",
        model=settings.convener_model,
        instruction=SYSTEM_INSTRUCTION,
        tools=[convene_council],
        before_model_callback=extract_fhir_context,
    )


root_agent = build_agent()
