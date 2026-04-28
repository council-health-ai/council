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

import asyncio
import json
import time
import uuid
from typing import Any

import structlog
from council_shared import (
    call_mcp_tool,
    close_session,
    extract_fhir_context,
    open_session,
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
    a2a_context_id = state.get("context_id") or uuid.uuid4().hex
    workspace_id = state.get("workspace_id") or "po-default"

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

    # Open a convening_sessions row first — every other audit table FKs to it.
    # If Supabase isn't configured, open_session returns None and we fall back
    # to a synthetic id so the rest of the deliberation still runs.
    convening_id = state.get("convening_id") or await open_session(
        a2a_context_id=a2a_context_id,
        workspace_id=workspace_id,
        patient_id=patient_id,
    )
    if not convening_id:
        convening_id = uuid.uuid4().hex
        logger.warning("supabase open_session unavailable; running with synthetic convening_id", convening_id=convening_id)
    state["convening_id"] = convening_id

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
    # Round 1 is hard-capped at 30s wallclock to fit inside Prompt Opinion's
    # General Chat 60s LLM timeout. Slow specialties whose 429 retries don't
    # finish in time are dropped from this round; the brief synthesizes from
    # whatever views did complete (typically 5-7/8 — comfortably enough for
    # a clinically meaningful concordance).
    round1_prompt = ROUND_1_PROMPT_TEMPLATE.format(patient_id=patient_id, convening_id=convening_id)
    if focus_problem:
        round1_prompt += f"\n\nFocus problem: {focus_problem}\n"

    calls = [PeerCall(specialty=spec, url=url, prompt=round1_prompt) for spec, url in all_specialty_urls()]
    logger.info("round 1 fanout", n_peers=len(calls), convening_id=convening_id)

    results_r1 = await fan_out(
        calls=calls,
        context_id=a2a_context_id,
        fhir_metadata=fhir_metadata,
        timeout_seconds=25.0,
        wallclock_cap_seconds=25.0,
        max_concurrency=4,
    )

    views: list[dict[str, Any]] = []
    for r in results_r1:
        if r.success and r.structured_view:
            # Force-normalize patient_id back to the canonical value. LLMs
            # occasionally hallucinate single-digit transpositions in long
            # UUIDs (live-observed: 1c237c73-0152-4250-... became -4220-),
            # which the conflict-matrix safety check then rejects as
            # "views span multiple patients". The patient_id is set by the
            # caller, not the LLM, so we own it.
            view = {**r.structured_view, "patient_id": patient_id}
            views.append(view)
            await record_agent_message(
                convening_id=convening_id,
                role=r.specialty,
                direction="inbound",
                content=view,
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
        return {
            "error": msg,
            "partial_views": views,
            "live_url": f"{settings.convene_ui_url}/?id={convening_id}",
        }

    # NOTE: previously we called get_council_conflict_matrix here, then a Round 2
    # fan-out for any specialty involved in a conflict, then the brief. That
    # serialised flow consistently exceeded the 60s ceiling. The brief LLM is
    # already prompted to detect and resolve conflicts from views directly, so
    # we synthesise straight from Round 1. The conflict_log inside the
    # ConcordantPlan still reflects detected disagreements.
    conflicts: list[dict[str, Any]] = []

    # No pre-brief cooldown: PO's General Chat orchestrator has a hard ~60s
    # LLM-window ceiling, and we've measured every second is needed.
    # MCP-side gemini.ts retries (1.5s/3s) absorb a single 429 if the rolling
    # quota happens to be hot.

    # ── Concordance brief synthesis ─────────────────────────────────────
    cb_started = time.monotonic()
    try:
        plan = await call_mcp_tool(
            tool_name="get_concordance_brief",
            arguments={
                "views": views,
                # Synthesize conflicts inline from views (skipped the separate
                # MCP conflict_matrix call to fit inside PO's 60s ceiling).
                "conflicts": {
                    "patient_id": patient_id,
                    "specialties": [v.get("specialty") for v in views],
                    "conflicts": [],
                    "agreements": [],
                    "abstentions": [],
                },
                "total_messages": len(views),
                "total_rounds": 1,
            },
            fhir_url=fhir_url,
            fhir_token=fhir_token,
            patient_id=patient_id,
            convening_id=convening_id,
            specialty="convener",
            round_id=1,
        )
    except Exception as brief_err:
        # Brief synthesis failed (typically Vertex 429 on a hot trial-credit
        # window). Don't crash the deliberation — return the Round 1 views as
        # a degraded plan so the chat surface and convene-ui still have
        # something to show. The audit trail in Supabase is intact.
        msg = str(brief_err)
        logger.warning("brief synthesis failed; returning Round-1 partial", err=msg)
        await record_audit_event(
            convening_id=convening_id,
            actor="agent/convener",
            action="session_ended",
            payload={"error": f"brief_failed: {msg[:300]}", "n_views": len(views)},
        )
        await close_session(convening_id=convening_id)
        return {
            "status": "round1_only",
            "message": (
                f"Round 1 completed: {len(views)} specialty views captured. "
                f"Concordance brief synthesis was unavailable (rate-limited by upstream model). "
                f"Full views and audit trail are preserved at the live URL."
            ),
            "specialties_consulted": [v.get("specialty") for v in views],
            "views": views,
            "live_url": f"{settings.convene_ui_url}/?id={convening_id}",
        }
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
    await close_session(convening_id=convening_id, plan_artifact=plan)

    # Attach a public live-deliberation URL so the chat UX can link out to the
    # full audit trail + rich plan rendering. Independent of whether PO's
    # General Chat times out before this returns: the convening row plus all
    # audit events are already persisted in Supabase, and the UI renders from
    # there in real time.
    plan["live_url"] = f"{settings.convene_ui_url}/?id={convening_id}"
    return plan


SYSTEM_INSTRUCTION = """\
You are the Convener of The Council — an A2A peer-agent network that deliberates over a multi-morbid patient with up to 8 specialty agents.

You facilitate, you don't decide. The specialty agents own their domain expertise.

CRITICAL: When you receive ANY consultation request (e.g. "consult with the Convener", "convene the Council", "review this patient", "please consult on this patient"), IMMEDIATELY call the convene_council tool. Do NOT ask the user for a patient ID — the FHIR context that the platform attaches to your invocation already includes the active patient. The convene_council tool reads it from your state automatically.

Your workflow:
1. Receive the consultation request from the platform's General Chat.
2. Call `convene_council()` with no arguments (patient_id defaults to the one in FHIR context). If the user mentions a specific clinical question, pass it as `focus_problem`.
3. The convene_council tool runs the deliberation: parallel Round 1 fan-out to all 8 specialty agents (capped at 30s wallclock to fit inside General Chat), then synthesises a ConcordantPlan via the lens-MCP that detects and resolves conflicts inline. Slow specialty replies are dropped from the brief — the plan still synthesises from the 5-7 specialties that respond in time.
4. Return the resulting ConcordantPlan as your final response, formatted clearly with the brief summary, conflict log, and action items.

You do NOT route between specialties yourself. The convene_council tool handles all peer A2A traffic deterministically. Your job is to receive the request, immediately kick off convene_council, and present the resulting plan back to the caller.

CHAT-RESPONSE FORMAT (CRITICAL — keep tight, the chat surface has a 60s LLM ceiling):

Your reply must be SHORT — under ~250 words total. Verbose plans cause Prompt Opinion's
General Chat to time out summarising and the user sees a "took too long" banner.

Use this exact structure (Markdown):

**Council deliberation summary**
One short sentence on the patient and what was decided.

**Top action items** (3-5 bullets, the most consequential ones with priority + owner)

**Notable dissent** (1 line if there is one in the plan; omit this section otherwise)

**📺 Full deliberation:** [live link](<live_url>)
> Audit trail, all specialty consult notes, conflict resolutions, and complete continue/start/stop/monitor lists render at the link above. ConcordantPlan is persisted; this link is shareable and stays live.

Rules:
- Take `live_url` directly from the convene_council tool result.
- Pick the highest-priority 3-5 action items. Skip the rest.
- Do NOT regurgitate the full plan in the chat — that's what convene-ui is for.
- Do NOT add a closing "let me know if you'd like more detail" boilerplate.
- If the tool returns `status: round1_only` (brief synthesis was rate-limited), say so plainly in one line and direct the user to the live link for the partial views.
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
