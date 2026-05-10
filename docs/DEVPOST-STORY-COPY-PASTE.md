<!--
  DEVPOST SUBMISSION — copy-paste-ready
  ─────────────────────────────────────
  Two sections below:
    1. PROJECT STORY  → paste into Devpost "About the project" field
    2. BUILT WITH     → paste into Devpost "Built with" tags
  Images live in docs/devpost-images/ in this repo and are embedded via
  raw.githubusercontent.com URLs so Devpost renders them inline.
-->


<!-- ============================================================ -->
<!-- 1. PROJECT STORY  —  paste everything below into "About the project" -->
<!-- ============================================================ -->

> **Eight specialists. One multi-morbid patient. A peer-to-peer A2A network that surfaces every conflict, preserves dissent, and synthesises a single concordant care plan.**
>
> *Built on Prompt Opinion's MCP + A2A + SHARP + FHIR stack.*

![Architecture — peer A2A · SHARP-on-MCP · live FHIR · queryable audit](https://raw.githubusercontent.com/council-health-ai/council/main/docs/devpost-images/architecture.svg)

## 🩺 Inspiration

**60% of Medicare patients live with two or more chronic conditions.** Multi-morbidity drives ~$1.5 trillion of U.S. healthcare spend annually. And yet most clinical AI tooling still assumes you're optimising one disease at a time — single-LLM RAG over a guideline corpus, or single-condition decision support.

The hard problem isn't *retrieving* cardiology guidance, oncology guidance, or nephrology guidance. It's *reasoning across them when they pull in different directions*.

A 67-year-old woman with **new ER+ breast cancer**, **paroxysmal AF on apixaban**, **T2DM with HbA1c 9.2%**, and **CKD stage 3a** is guided in four different directions simultaneously by four different specialty literatures. Every recommendation a single specialty would make is reasonable in isolation. **The interaction is where harm happens.**

Microsoft's Healthcare Agent Orchestrator (HAO) showed multi-agent collaboration worked for cancer tumour boards. **The Council generalises the architecture to multi-morbidity and inverts the topology**: peer-to-peer A2A, not orchestrator-with-router. Eight specialty agents reason in parallel through their own clinical lens, exchange A2A messages, surface their conflicts explicitly, and synthesise one concordant plan with preserved dissent.

## ⚡ What it does

A primary-care clinician opens **General Chat in Prompt Opinion** with a patient selected and types one sentence:

> *"Convene the Council on this patient."*

What happens next:

1. The **Convener** agent (a real A2A peer) opens a convening session in Supabase, then fans out a Round-1 prompt over A2A to **eight specialty agents in parallel** — Cardiology, Oncology, Nephrology, Endocrinology, Obstetrics & MFM, Developmental Pediatrics, Psychiatry, Anesthesia & Perioperative.
2. Each specialty agent calls its **SHARP-on-MCP lens tool** (`get_<specialty>_perspective`). The MCP server fetches the live FHIR R4 chart through the SHARP-bound token, summarises it through that specialty's clinical lens, and returns a **structured `SpecialtyView`**: primary concerns, red flags, applicable guidelines, proposed plan (continue / start / stop / monitor), and full reasoning trace.
3. The Convener calls `get_council_conflict_matrix` then `get_concordance_brief` — two MCP tools that **detect conflicts inline** and synthesise a **`ConcordantPlan`** in Prompt Opinion's 5T framework: a plain-English brief, a continue/start/stop/monitor plan, an action-item table for the primary clinician, a conflict log with explicit resolution methods (`harmonized` / `deferred-to-specialty` / `guideline-aligned` / `patient-preference` / `unresolved`), and **preserved dissents** where the Council didn't fully converge.
4. Every reasoning step writes to a Supabase audit table with **Realtime publication enabled**. A **live deliberation viewer** subscribes via Realtime and renders the multi-agent deliberation as it happens — agents activating, audit events streaming, the ConcordantPlan landing as a fully formatted clinical document.

The Convener's response in PO chat is intentionally short — a single paragraph plus a live link. **The rich rendering happens on the convene-ui**, where it has its own time budget.

> The Council doesn't decide. The clinician does. **The Council surfaces the trade-offs that single-LLM systems hide.**

## 🖥 The convene-ui — what a clinician actually sees

### Concordant Plan (the deliverable)

![Concordant Plan tab — brief, 5T plan, action items, conflict log](https://raw.githubusercontent.com/council-health-ai/council/main/docs/devpost-images/01-plan.png)

A clinical document, not a chat log. Doc-meta header: 5 specialties consulted · 16 action items · 4 conflicts · preserved dissents. Then: brief, 5T plan (Continue · Start · Stop · Monitor), per-task ownership & timing, and explicit conflict resolutions ("harmonized via temporal sequencing", "deferred to Endocrinology", etc.).

### Live Deliberation (the work, in flight)

![Live Deliberation tab — specialist roster + audit timeline streaming](https://raw.githubusercontent.com/council-health-ai/council/main/docs/devpost-images/02-deliberation.png)

The eight-specialty roster on the left, audit timeline on the right. Every event ticks in via Supabase Realtime: tool calls, lens returns (with concern/red-flag counts), peer A2A messages, the final "Concordant plan synthesised" event.

### Specialty Consults (drill-down)

![Specialty Consults tab — per-specialty SpecialtyView cards with concerns, flags, guidelines](https://raw.githubusercontent.com/council-health-ai/council/main/docs/devpost-images/03-consults.png)

Each specialty's full `SpecialtyView` — primary concerns, red flags, applicable guidelines, reasoning trace. The clinician can verify any claim by reading the lens that produced it.

### Audit Log (the safety substrate)

![Audit Log tab — every state transition, MCP call, A2A message logged](https://raw.githubusercontent.com/council-health-ai/council/main/docs/devpost-images/04-audit.png)

Every state transition, every MCP tool invocation, every A2A peer message. The Mandel/MedLog vision — every reasoning step queryable — realised as a first-class architectural feature, not an afterthought.

## 🔑 How we built it — the four standards

Every one of Prompt Opinion's four core standards is **load-bearing** here, not decorative:

### MCP
`specialty-lens-mcp` — TypeScript Express 5 + `@modelcontextprotocol/sdk`. Exposes **8 `get_<specialty>_perspective` tools** + **2 concordance tools** (`get_council_conflict_matrix`, `get_concordance_brief`). Each tool returns structured output (validated `SpecialtyView` / `ConflictMatrix` / `ConcordantPlan` schemas) — no free-text JSON parsing.

### A2A
**Real peer A2A.** Each agent has its own `AgentCard` served at both `/.well-known/agent-card.json` (v1) **and** `/.well-known/agent.json` (v0 backcompat). The Convener fan-out is deterministic peer dispatch, *not* `gemini.decideWhichExpertToConsultNext()`. Specialty agents that don't apply to a patient (Developmental Pediatrics on a 67-year-old) explicitly **abstain** — and the abstention is preserved in the audit log as clinical signal.

### SHARP
Full **SHARP context propagation** across the entire 8-agent A2A call chain: `patient_id`, FHIR token, audience binding, every hop. **First SHARP-on-MCP impl with real HTTP 403 enforcement at the request edge** — none of the three reference implementations in `prompt-opinion/po-community-mcp` (TypeScript / Python / .NET) do this. We also shipped an **upstream RFC PR** to `po-community-mcp` proposing three new SHARP headers (`X-Council-Convening-Id`, `X-Council-Specialty`, `X-Council-Round-Id`) for grouping MCP calls into a multi-agent deliberation session — and we use the extension in production right now.

### FHIR
**Live FHIR R4 — no mocks, no fixtures.** Every specialty lens fetches the real chart through the SHARP-bound token: Patient, Condition, MedicationStatement / MedicationRequest, Observation, AllergyIntolerance, Procedure. The lens then summarises through its specialty filter — anti-coag for Cardiology, glycaemic targets for Endocrinology, renal-cleared dosing for Nephrology, perioperative risk for Anaesthesia, etc.

## 🛡️ The audit trail

Healthcare clinical decision support without a queryable reasoning trail is **unshippable**. The Council writes four parallel ledgers to Supabase:

| Table | What's logged |
|---|---|
| `audit_events`         | Every state transition, one row per event |
| `agent_messages`       | Every A2A message between Convener ↔ specialty peers |
| `mcp_tool_calls`       | Every MCP tool invocation, with SHARP context + latency + result hash |
| `convening_sessions`   | One row per session, `plan_artifact` JSONB column holds the final ConcordantPlan |

Supabase **Realtime publication** is enabled on all four. The convene-ui subscribes and renders the deliberation as it streams. **Every reasoning step is queryable** — by clinician, by oversight, by future audit.

## 🔒 Privacy & feasibility

Multi-specialty AI on real patient data demands real privacy guarantees. We deliberately built three layers:

1. **SHARP enforcement at the edge.** The MCP server emits real HTTP 403 on any request missing or carrying invalid SHARP context — no opaque fallback, no silent "best effort". The reference impls in `po-community-mcp` describe this enforcement; we are the first to actually emit it.
2. **Per-session isolation in the convene-ui.** The viewer requires an explicit `?id=<convening-uuid>` URL — no auto-loading of "the latest session", no public browsing of sessions. (Per-session RLS is the next layer, planned post-hackathon for clinical pilots.)
3. **Synthetic data for the demo.** All FHIR data in the public deliberation viewer is synthesised via Synthea — no real PHI is stored or rendered in this hackathon submission.

## 🧠 What we learned

- **Peer A2A > orchestrator-with-router for multi-specialty reasoning.** When eight peers each have their own AgentCard, their own SHARP context, their own model choice, their own audit identity, you get cleaner abstention semantics, cleaner per-specialty observability, and a substrate where adding a 9th specialty is one Cloud Run service, not an orchestrator config rewrite.
- **Standards-native is the unlock.** MCP, A2A, SHARP, FHIR all compose. We didn't write any custom protocol glue — every cross-boundary call goes through one of the four standards. The platform handled the rest.
- **An empty state is a feature.** When a clinician opens the link, the Plan tab shows *"Plan will appear once the Council finishes synthesising"* with a live deliberation tab they can switch to. That intermediate state IS the product — it's the difference between "this is a real live system" and "this is a static mockup."
- **Conflict resolution is multi-modal.** Not every conflict is `harmonized` ("both safety boundaries can be honoured by sequencing"). Some are `deferred-to-specialty` ("Endocrinology owns the glucose intensification call"). Some are `guideline-aligned` ("KDIGO 2024 trumps individual specialty preference"). Some are `unresolved` and must be **preserved as dissent** for the clinician.

## 🪨 Challenges we ran into

- **A2A v0 ↔ v1 AgentCard discovery**: real production A2A peers expect both `/.well-known/agent-card.json` (v1) and `/.well-known/agent.json` (v0). We serve both.
- **SHARP context propagation through Google ADK's `to_a2a()` adapter** required per-tool middleware, not just per-server middleware — every MCP tool invocation re-binds the SHARP context from the request.
- **Supabase CHECK constraint** initially rejected our `endocrinology` and `developmental_pediatrics` specialty names; we updated the migration and re-deployed live without losing audit history.
- **Realtime publication latency** on Hugging Face Spaces for the static convene-ui — solved by subscribing on session-id rather than table-wide.
- **A Cloud Run quirk** where `GET /healthz` (no trailing slash) is intercepted by Google's frontend before reaching the container; surfaced via `/healthz/` (with slash). The MCP `/mcp` endpoint is unaffected.

## 🏆 Accomplishments we're proud of

- **All 10 marketplace listings live on Prompt Opinion**: Convener + 8 specialty agents + the SHARP-on-MCP server. Discoverable and invokable by any PO user from day one.
- **First SHARP impl with real HTTP 403 enforcement** at the request edge.
- **Upstream RFC PR** to `po-community-mcp` (convening-session SHARP extension) — used in production by The Council right now.
- **Zero mocks**: every specialty view comes from a real FHIR fetch, every audit row is real, every plan artifact is generated by a real model on real data.
- **A submission video that shows the actual hosted app**, not a mockup — including the empty/loading state, the live deliberation timeline, and the final ConcordantPlan render.

## 🔭 What's next for The Council

- **Per-session RLS** in Supabase so the anon-key client can only read sessions it's been granted access to via a sharing token. (Today: explicit URL = effective access; next: cryptographic session sharing.)
- **Round-2 deliberation**: when conflicts can't be resolved in Round-1, the Convener re-fans out a targeted question to the specific peers in disagreement. Architecture supports it; workflow is the next ship.
- **Patient-preference axis**: a 9th "lens" representing the patient's own values / preferences / contraindications, sourced from a structured intake.
- **Tumour-board mode**: same architecture, different specialty roster (path / rad onc / surgical onc / med onc / palliative). Already trivially achievable by changing the peer-list config.
- **EHR write-back**: today the ConcordantPlan is rendered for a clinician to read; the next step is FHIR `CarePlan` resource write-back through SHARP scopes.

---

**🔗 Live now**
- Live deliberation viewer (demo session): <https://council-health-ai-convene-ui.static.hf.space/?id=bd662973-8b75-4350-bdca-fe39a51603fa>
- Marketplace publisher: **The Council** (10 listings on Prompt Opinion)
- Source: <https://github.com/council-health-ai/council>


<!-- ============================================================ -->
<!-- 2. BUILT WITH  —  paste these tags into the "Built with" field -->
<!-- ============================================================ -->

typescript
python
react
remotion
google-adk
google-cloud-run
vertex-ai
gemini-2.5-flash
supabase
postgres
supabase-realtime
huggingface-spaces
mcp
a2a
sharp
fhir
fhir-r4
smart-on-fhir
model-context-protocol
agent-to-agent
prompt-opinion
expressjs
nodejs
zod
pino
sentry
pgvector
puppeteer
