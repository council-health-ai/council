"""ADK before_model_callback that extracts SHARP/FHIR context from A2A metadata into tool_context.state.

The Prompt Opinion platform sends FHIR context as a metadata key whose URI ends in 'fhir-context'.
The agent shouldn't pass these credentials into the LLM prompt — they live in tool_context.state and
are read by tool functions when they call the MCP server.
"""

from __future__ import annotations

from typing import Any

import structlog

logger = structlog.get_logger("council.fhir_hook")


def _is_fhir_context_key(key: str) -> bool:
    """Match any URI containing 'fhir-context' — accommodates both
    https://app.promptopinion.ai/schemas/a2a/v1/fhir-context (production)
    and per-workspace variants like https://app.../workspaces/<id>/schemas/a2a/v1/fhir-context.
    """
    return "fhir-context" in key.lower()


def _walk_for_fhir(obj: Any) -> dict | None:
    """Recursively look for a dict whose key contains 'fhir-context' and value has fhirUrl/fhirToken."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if (
                isinstance(k, str)
                and _is_fhir_context_key(k)
                and isinstance(v, dict)
                and ("fhirUrl" in v or "fhir_url" in v)
            ):
                return v
            inner = _walk_for_fhir(v)
            if inner is not None:
                return inner
    elif isinstance(obj, list):
        for item in obj:
            inner = _walk_for_fhir(item)
            if inner is not None:
                return inner
    return None


def extract_fhir_context(callback_context, llm_request):
    """ADK before_model_callback. Lifts FHIR context from A2A message metadata into state.

    Searches in priority order:
      1. callback_context.state if FHIR context already there (idempotent)
      2. callback_context.metadata
      3. The most recent message in llm_request.contents
      4. Anywhere in callback_context.run_config / a2a_metadata

    State keys set:
      fhir_url, fhir_token, patient_id
    Optional Council headers (if present):
      convening_id, council_specialty, round_id
    """
    # Idempotent — if already populated, skip
    if callback_context.state.get("fhir_url") and callback_context.state.get("fhir_token"):
        return None

    candidates: list[Any] = []

    # 1. callback_context.metadata
    meta = getattr(callback_context, "metadata", None)
    if meta:
        candidates.append(meta)

    # 2. run_config / a2a_metadata
    run_config = getattr(callback_context, "run_config", None)
    if run_config is not None:
        cm = getattr(run_config, "custom_metadata", None)
        if cm:
            candidates.append(cm)

    # 3. Most-recent llm_request message metadata (varies by ADK version)
    contents = getattr(llm_request, "contents", None)
    if contents:
        try:
            last = contents[-1]
            last_meta = getattr(last, "metadata", None)
            if last_meta:
                candidates.append(last_meta)
        except (IndexError, AttributeError):
            pass

    fhir_data: dict | None = None
    for c in candidates:
        fhir_data = _walk_for_fhir(c)
        if fhir_data:
            break

    if not fhir_data:
        logger.debug("no FHIR context found in callback metadata")
        return None

    fhir_url = fhir_data.get("fhirUrl") or fhir_data.get("fhir_url") or ""
    fhir_token = fhir_data.get("fhirToken") or fhir_data.get("fhir_token") or ""
    patient_id = fhir_data.get("patientId") or fhir_data.get("patient_id") or ""

    callback_context.state["fhir_url"] = fhir_url
    callback_context.state["fhir_token"] = fhir_token
    callback_context.state["patient_id"] = patient_id

    # Optional Council headers — same metadata blob can carry them
    for k_in, k_out in [
        ("conveningId", "convening_id"),
        ("councilSpecialty", "council_specialty"),
        ("roundId", "round_id"),
    ]:
        v = fhir_data.get(k_in)
        if v is not None:
            callback_context.state[k_out] = v

    logger.info(
        "fhir context extracted into state",
        patient_id=patient_id,
        fhir_url_set=bool(fhir_url),
        fhir_token_set=bool(fhir_token),
    )
    return None
