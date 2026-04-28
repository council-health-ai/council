"""Convener agent — facilitates The Council's deliberation.

Architecture: the `convene_council` tool returns within seconds with a public
live-deliberation URL. The actual multi-agent deliberation (Round 1 fan-out
to 8 specialty agents + concordance brief synthesis) runs in a background
asyncio task that streams audit events + the final ConcordantPlan to Supabase.
The convene-ui static page subscribes to Supabase Realtime and renders the
deliberation as it happens.

This split is essential because Prompt Opinion's General Chat surface has a
~60s LLM-orchestration ceiling. A full Council deliberation across 8 specialty
LLMs + the brief takes ~50s of wallclock — close enough to the ceiling that
PO sometimes gives up before the function call returns. By returning fast
with a live link, the chat surface stays snappy and the rich rendering
happens at convene-ui in real time.

The Convener uses Gemini for chat framing only — the deliberation itself is
deterministic peer A2A (NOT orchestrator-with-Gemini-routing). That structural
choice is the differentiator: peer A2A is what the A2A spec was designed for,
HAO-style group chat is closer to a chatroom-with-LLM-router.
"""

from __future__ import annotations

import asyncio
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


# ── Background deliberation task ────────────────────────────────────────


async def _run_deliberation(
    *,
    convening_id: str,
    fhir_url: str,
    fhir_token: str,
    patient_id: str,
    a2a_context_id: str,
    fhir_metadata: dict[str, Any],
    focus_problem: str | None,
) -> None:
    """Run the full Council deliberation. Persists everything to Supabase.

    Designed to be spawned via asyncio.create_task() from the convene_council
    tool — never raises out to the caller. Errors are logged + recorded as
    a session_ended audit event so the UI shows the failure mode.
    """
    overall_started = time.monotonic()
    try:
        round1_prompt = ROUND_1_PROMPT_TEMPLATE.format(
            patient_id=patient_id, convening_id=convening_id
        )
        if focus_problem:
            round1_prompt += f"\n\nFocus problem: {focus_problem}\n"

        calls = [
            PeerCall(specialty=spec, url=url, prompt=round1_prompt)
            for spec, url in all_specialty_urls()
        ]
        logger.info("round 1 fanout", n_peers=len(calls), convening_id=convening_id)

        # Multi-region Vertex eliminates the 429-retry cliff. 60s wallclock
        # cap is generous now that we no longer need to fit inside PO's
        # General Chat ceiling — slow specialties (cold-start, region quota
        # contention) can still finish.
        results_r1 = await fan_out(
            calls=calls,
            context_id=a2a_context_id,
            fhir_metadata=fhir_metadata,
            timeout_seconds=60.0,
            wallclock_cap_seconds=60.0,
            max_concurrency=8,
        )

        views: list[dict[str, Any]] = []
        for r in results_r1:
            if r.success and r.structured_view:
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
                payload={
                    "error": msg,
                    "round1_results": [
                        r.specialty + ":" + ("ok" if r.success else "fail")
                        for r in results_r1
                    ],
                },
            )
            await close_session(convening_id=convening_id)
            return

        # ── Concordance brief synthesis ───────────────────────────────────
        cb_started = time.monotonic()
        try:
            plan = await call_mcp_tool(
                tool_name="get_concordance_brief",
                arguments={
                    "views": views,
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
            logger.warning("brief synthesis failed; persisting Round-1 only", err=str(brief_err))
            await record_audit_event(
                convening_id=convening_id,
                actor="agent/convener",
                action="session_ended",
                payload={"error": f"brief_failed: {str(brief_err)[:300]}", "n_views": len(views)},
            )
            await close_session(convening_id=convening_id)
            return

        await record_tool_call(
            convening_id=convening_id,
            tool_name="get_concordance_brief",
            params={"n_views": len(views), "n_conflicts": 0},
            result={"n_actions": len(plan.get("action_items", []))},
            status="success",
            latency_ms=int((time.monotonic() - cb_started) * 1000),
        )
        await record_audit_event(
            convening_id=convening_id,
            actor="agent/convener",
            action="plan_synthesized",
            payload={
                "specialties": plan.get("specialties_consulted", []),
                "n_actions": len(plan.get("action_items", [])),
            },
        )
        await record_audit_event(
            convening_id=convening_id,
            actor="agent/convener",
            action="session_ended",
            payload={"total_latency_ms": int((time.monotonic() - overall_started) * 1000)},
        )
        await close_session(convening_id=convening_id, plan_artifact=plan)
        logger.info(
            "deliberation complete",
            convening_id=convening_id,
            n_views=len(views),
            n_actions=len(plan.get("action_items", [])),
            latency_s=round(time.monotonic() - overall_started, 1),
        )

    except Exception as crash:
        logger.exception("deliberation crashed", convening_id=convening_id, err=str(crash))
        try:
            await record_audit_event(
                convening_id=convening_id,
                actor="agent/convener",
                action="session_ended",
                payload={"error": f"crashed: {str(crash)[:300]}"},
            )
            await close_session(convening_id=convening_id)
        except Exception:
            pass


# ── Tool exposed to the agent ───────────────────────────────────────────


async def convene_council(
    tool_context: ToolContext,
    patient_id: str | None = None,
    focus_problem: str | None = None,
) -> dict[str, Any]:
    """Convene The Council on a patient. Returns IMMEDIATELY with a live link.

    The deliberation (Round 1 fan-out + brief synthesis) runs in a background
    asyncio task that streams audit events + the final ConcordantPlan to
    Supabase. The chat surface gets a snappy response with a clickable URL;
    the full plan renders on convene-ui in real time as the deliberation
    plays out.

    The patient_id is OPTIONAL — when called from the Prompt Opinion platform,
    the FHIR context already includes the active patient's ID. Call this tool
    immediately on receiving any 'consult with the Convener' request rather
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

    if not patient_id:
        patient_id = state.get("patient_id", "")
    if not patient_id:
        return {
            "error": "No patient_id provided and none in FHIR context. The Council requires an active patient context."
        }
    if not fhir_url:
        return {"error": "FHIR URL not present in tool_context.state"}

    convening_id = state.get("convening_id") or await open_session(
        a2a_context_id=a2a_context_id,
        workspace_id=workspace_id,
        patient_id=patient_id,
    )
    if not convening_id:
        convening_id = uuid.uuid4().hex
        logger.warning(
            "supabase open_session unavailable; running with synthetic convening_id",
            convening_id=convening_id,
        )
    state["convening_id"] = convening_id

    fhir_metadata = {
        settings.fhir_extension_uri: {
            "fhirUrl": fhir_url,
            "fhirToken": fhir_token,
            "patientId": patient_id,
            "conveningId": convening_id,
            "roundId": 1,
        }
    }

    # Record the kick-off synchronously so the UI shows the session immediately.
    await record_audit_event(
        convening_id=convening_id,
        actor="agent/convener",
        action="session_started",
        payload={"patient_id": patient_id, "focus_problem": focus_problem},
    )

    # Spawn the deliberation in the background. asyncio.create_task() returns
    # immediately; the task continues running on the same event loop while
    # this tool returns to the caller. We hold a reference to prevent the
    # task from being garbage-collected mid-run.
    task = asyncio.create_task(
        _run_deliberation(
            convening_id=convening_id,
            fhir_url=fhir_url,
            fhir_token=fhir_token,
            patient_id=patient_id,
            a2a_context_id=a2a_context_id,
            fhir_metadata=fhir_metadata,
            focus_problem=focus_problem,
        )
    )
    _BACKGROUND_TASKS.add(task)
    task.add_done_callback(_BACKGROUND_TASKS.discard)

    live_url = f"{settings.convene_ui_url}/?id={convening_id}"
    logger.info(
        "convene_council kicked off; deliberation runs in background",
        convening_id=convening_id,
        live_url=live_url,
    )

    return {
        "status": "deliberating",
        "convening_id": convening_id,
        "patient_id": patient_id,
        "live_url": live_url,
        "message": (
            "The Council has begun deliberating on this patient. Eight specialty "
            "agents are reviewing the chart in parallel and will synthesize a "
            "ConcordantPlan in ~30-60 seconds. The deliberation streams live at "
            "the URL above — audit timeline, per-specialty consult notes, "
            "conflict resolution, and the final plan all render in real time."
        ),
    }


# Holding strong references to in-flight background tasks prevents them from
# being garbage-collected before they complete (asyncio.create_task only
# weak-refs by default).
_BACKGROUND_TASKS: set[asyncio.Task[Any]] = set()


SYSTEM_INSTRUCTION = """\
You are the Convener of The Council — an A2A peer-agent network that deliberates over a multi-morbid patient with up to 8 specialty agents.

You facilitate, you don't decide. The specialty agents own their domain expertise.

CRITICAL: When you receive ANY consultation request (e.g. "consult with the Convener", "convene the Council", "review this patient", "please consult on this patient"), IMMEDIATELY call the convene_council tool. Do NOT ask the user for a patient ID — the FHIR context that the platform attaches to your invocation already includes the active patient. The convene_council tool reads it from your state automatically.

The convene_council tool returns within ~5 seconds with a live deliberation URL. The deliberation itself (Round 1 fan-out to 8 specialty agents + concordance brief synthesis) runs in the background and streams to the URL in real time.

Once the tool returns, format a SHORT chat response (under 120 words) with this exact structure:

**🏛️ The Council has convened.**
One sentence: which patient and what's being deliberated (e.g. "Eight specialty agents are now reviewing Mrs. Chen's case in parallel — perioperative anticoagulation, T2DM intensification, CKD-aware dosing, and post-lumpectomy adjuvant therapy.")

**📺 Watch the deliberation live:** [link](<live_url>)

The full ConcordantPlan — continue/start/stop/monitor lists, action items with priority, conflict resolutions, preserved dissents, every specialty's consult note, and the audit trail — renders at the link above as the agents complete their analyses (~30-60 seconds).

Rules:
- Take `live_url` directly from the convene_council tool result.
- Do NOT wait for or attempt to display the plan inline — it does not exist yet at this point. The live link is the deliverable.
- Do NOT add boilerplate like "let me know if you'd like more detail." Skip it.
- Speak in clinician-facing language. The patient is referenced by their de-identified summary, not by name in chat.
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
