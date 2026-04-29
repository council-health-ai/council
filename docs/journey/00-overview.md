# 00 · Overview

## What we built

**The Council** — a peer-to-peer A2A network where eight specialty
healthcare agents (Cardiology, Oncology, Nephrology, Endocrinology,
Obstetrics & MFM, Developmental Pediatrics, Psychiatry, Anesthesia &
Perioperative) convene on a multi-morbid patient, exchange peer A2A
messages, surface conflicts, and synthesize a single ConcordantPlan.
A lightweight Convener facilitates the rounds; it does not decide.

Two tracks shipped:
- **Specialty-Lens MCP** (TypeScript, SHARP-on-MCP) — eight `get_<specialty>_perspective` tools + concordance synthesis (`get_council_conflict_matrix`, `get_concordance_brief`)
- **Council A2A network** (Python ADK) — Convener + 8 specialty agents

Plus:
- A live deliberation viewer at `convene-ui.static.hf.space` that subscribes to Supabase Realtime and renders the multi-agent deliberation as it happens
- A SHARP convening-session extension RFC contributed upstream as a real PR to `prompt-opinion/po-community-mcp`
- An audit log + `mcp_tool_calls` table on Supabase for clinical observability (the Mandel/MedLog hook)

## Why it matters

- **Multi-morbidity is the dominant cost driver** in U.S. healthcare. 60% of Medicare patients have ≥2 chronic conditions; multi-morbidity drives ~$1.5T/year in care.
- **Reasoning across conflicting specialty guidelines** is canonical agent-not-rule-based work. A patient on apixaban for AFib who needs lumpectomy for ER+ breast cancer with eGFR 38 and HbA1c 9.2% has FOUR specialty guidelines pulling in different directions. Single-LLM RAG over a guideline corpus cannot resolve those tensions; eight specialty agents reasoning over the same chart through their own lenses can.
- **Microsoft Healthcare Agent Orchestrator (HAO)** popularized multi-agent for cancer tumor boards. The Council generalizes the architecture and inverts the topology: peer A2A (the protocol's intended pattern) instead of orchestrator-with-Gemini-routing (what HAO actually does, despite the framing).

## What was hard

In rough chronological order, the major battles:

1. **GCP / Vertex setup hell** — eight different API keys exhausted before discovering only the service-account JSON path consumes the $300 trial credit.
2. **PO platform shape mismatches with the a2a-sdk** — 6+ distinct shape bugs (method aliasing, role aliasing, securitySchemes shape, AgentCard v1 fields, streaming=False requirement, response envelope reshaping).
3. **A2A SDK Pydantic discriminated unions** — the response walker missed `.root`, every peer returned `text_len=0` for hours.
4. **Vertex 429 quota across regions** — trial-credit per-region RPM is tight; specialty fan-out hammers a single region; multi-region distribution + per-specialty MCP routing was the eventual fix.
5. **PO General Chat 60s LLM ceiling** — every speed optimization helped marginally; the real fix was architectural (fire-and-forget — Convener returns in <5s with a live URL, deliberation runs in background, convene-ui renders in real time).
6. **PO empty-bearer-token regression on FHIR proxy** — service-to-service calls returned 403; built a FHIR fixture fallback that ships hand-crafted bundles with the MCP.
7. **HF Spaces concurrent-services quota** — 10 services deployed but free tier capped at ~6 running, triggered the Cloud Run migration.
8. **Audit log silent FK failures** — Convener never opened the parent `convening_sessions` row, so all child inserts were silently rejected and no one knew why for several hours.

Every battle is documented in detail in the chronological files.

## What it taught us

- **Production multi-agent on platform constraints** is mostly an *integration*
  problem, not a *modeling* problem. The LLM is the easy part. Wiring eight
  specialty agents into a platform that has its own LLM-orchestration timeout,
  its own auth shape, its own envelope format, and its own bearer-token
  regression is where 80% of the engineering goes.
- **Free-tier multi-region** is a real architectural pattern, not a hack.
  Spreading 10 services across 10 GCP regions on the same project gives you ~10× the
  burst quota for nothing — same trial credit pool, no new accounts, no new cards.
- **Fire-and-forget + Realtime audit streaming** is a stronger demo than waiting
  for a wall of text in chat. Once we accepted PO's 60s ceiling as a platform
  constraint and stopped fighting it, the whole story got better — the live
  deliberation playback IS the architectural differentiator.
- **The audit log is the architectural differentiator** for healthcare. It's
  not a side effect of the system; it's the artifact a clinician trusts and a
  compliance officer demands. SHARP-on-MCP + Supabase Realtime + per-specialty
  consult cards gives us a live MedLog-style trail that no orchestrator-and-router
  pattern can produce.
