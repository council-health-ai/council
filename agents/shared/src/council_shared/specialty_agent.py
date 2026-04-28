"""Factory for specialty agents — every specialty has the same structural shape (call its lens MCP tool,
return the SpecialtyView), so we generate them from a single function.
"""

from __future__ import annotations

import time
from typing import Any

import structlog
from google.adk.agents import Agent
from google.adk.tools import ToolContext

from .audit import record_audit_event, record_tool_call
from .config import settings
from .fhir_hook import extract_fhir_context
from .mcp_client import call_mcp_tool
from .models import Specialty

SYSTEM_INSTRUCTION_TEMPLATE = """\
You are the {human_name} specialty agent in The Council — an A2A peer-agent network where independent specialty agents convene on a multi-morbid patient and negotiate a concordant care plan.

Your job:
1. When asked to opine on a patient (Round 1), call `{tool_name}` with the patient_id you were given. The tool returns a structured SpecialtyView dict.
2. When asked to respond to specific conflicts identified by the Convener (Round 2), reason about the conflicts in light of {focus_blurb}. Propose harmonized resolutions or accept reasoned alternatives — don't stonewall.
3. Stay in your specialty — defer to other specialties when an issue is outside {human_name}.
4. Never invent FHIR data. If the lens result lacks information needed to answer, say so explicitly.

OUTPUT RULE — CRITICAL:
Your final response MUST be exactly the JSON object returned by `{tool_name}` (Round 1) or by you (Round 2). No prose. No preamble. No "Here is the SpecialtyView:". No markdown code fences. No trailing commentary.

The Convener parses your response with `json.loads()` and discards anything that doesn't deserialize into a SpecialtyView dict (with `specialty`, `primary_concerns`, and `proposed_plan` fields). If you wrap the JSON in any natural language, your contribution is silently dropped from the deliberation and the patient loses your specialty's voice.

Round 1: emit the dict from `{tool_name}` verbatim.
Round 2: emit a JSON dict with keys `specialty`, `conflict_responses` (list of {{conflict_id, position, reasoning}}), and `revised_plan` (same shape as SpecialtyView.proposed_plan).

Preserve `reasoning_trace` and `fhir_refs` — they feed the audit log.
"""


def _humanize(specialty: Specialty) -> str:
    if specialty == "developmental_pediatrics":
        return "Developmental Pediatrics"
    return specialty.replace("_", " ").title()


def build_specialty_agent(specialty: Specialty, focus_blurb: str) -> Agent:
    """Build a specialty agent that wraps the corresponding `get_<specialty>_perspective` MCP tool."""
    tool_name = f"get_{specialty}_perspective"
    actor = f"agent/{specialty}"
    human_name = _humanize(specialty)
    logger = structlog.get_logger(f"council.{specialty}")

    async def lens_tool(
        patient_id: str,
        tool_context: ToolContext,
        focus_problem: str | None = None,
    ) -> dict[str, Any]:
        """Get this specialty's perspective on the patient via the MCP server's lens tool."""
        state = tool_context.state
        fhir_url = state.get("fhir_url", "")
        fhir_token = state.get("fhir_token", "")
        convening_id = state.get("convening_id")
        round_id = state.get("round_id")

        # Only fhir_url is mandatory. fhir_token may be empty (PO empty-token regression);
        # downstream FHIR call surfaces the host-level error if the endpoint requires auth.
        if not fhir_url:
            return {"error": f"FHIR URL not present in tool_context.state for {specialty}"}

        started = time.monotonic()
        await record_audit_event(
            convening_id=convening_id,
            actor=actor,
            action="tool_called",
            payload={"tool": tool_name, "patient_id": patient_id},
            round_id=round_id,
        )

        try:
            view = await call_mcp_tool(
                tool_name=tool_name,
                arguments={"patient_id": patient_id, "focus_problem": focus_problem},
                fhir_url=fhir_url,
                fhir_token=fhir_token,
                patient_id=state.get("patient_id") or patient_id,
                convening_id=convening_id,
                specialty=specialty,
                round_id=round_id,
            )
            latency_ms = int((time.monotonic() - started) * 1000)
            await record_tool_call(
                convening_id=convening_id,
                tool_name=tool_name,
                params={"patient_id": patient_id, "focus_problem": focus_problem},
                result={"specialty": specialty, "n_concerns": len(view.get("primary_concerns", []))},
                status="success",
                latency_ms=latency_ms,
            )
            await record_audit_event(
                convening_id=convening_id,
                actor=actor,
                action="tool_returned",
                payload={
                    "primary_concerns": view.get("primary_concerns", []),
                    "red_flags": view.get("red_flags", []),
                },
                fhir_refs=view.get("fhir_refs"),
                round_id=round_id,
            )
            return view
        except Exception as err:
            latency_ms = int((time.monotonic() - started) * 1000)
            msg = str(err)
            logger.error("specialty lens call failed", err=msg)
            await record_tool_call(
                convening_id=convening_id,
                tool_name=tool_name,
                params={"patient_id": patient_id, "focus_problem": focus_problem},
                result=None,
                status="error",
                error_message=msg,
                latency_ms=latency_ms,
            )
            return {"error": msg}

    # ADK uses __name__ as the function tool's identifier.
    lens_tool.__name__ = tool_name
    lens_tool.__doc__ = (
        f"Get the {human_name} specialty perspective for a patient. "
        f"Returns a structured SpecialtyView with concerns, red flags, and a proposed plan."
    )

    instruction = SYSTEM_INSTRUCTION_TEMPLATE.format(
        human_name=human_name,
        tool_name=tool_name,
        focus_blurb=focus_blurb,
    )

    return Agent(
        name=specialty,
        model=settings.gemini_model,
        instruction=instruction,
        tools=[lens_tool],
        before_model_callback=extract_fhir_context,
    )
